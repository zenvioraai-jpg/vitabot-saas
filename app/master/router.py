"""Panel MAESTRO: el dueño del SaaS ve, crea y administra TODAS las empresas.
Protegido por MASTER_ADMIN_TOKEN (variable de plataforma, no confundir con el
admin_token de cada empresa, que solo abre SU propio panel)."""
import logging
import secrets
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.db.database import get_db
from app.db import crud
from app.db.models import Message, Conversation, Customer, Company
from app.onboarding_templates import BUSINESS_TYPES, get_extra_fields

router = APIRouter()
logger = logging.getLogger(__name__)


def _require_master(token: str) -> None:
    if not token or token != settings.master_admin_token:
        raise HTTPException(status_code=401, detail="Token maestro inválido")


def _auth(token: str, authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip() or token


def _slugify(name: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "empresa"


@router.get("/api/business-types")
def api_business_types(token: str = Query(default="")):
    _require_master(token)
    return [{"key": k, "label": v, "extra_fields": get_extra_fields(k)} for k, v in BUSINESS_TYPES.items()]


@router.get("/api/companies")
def api_list_companies(token: str = Query(default=""), db: Session = Depends(get_db)):
    _require_master(token)
    since_today = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    out = []
    for c in crud.list_companies(db):
        msgs_today = (
            db.query(Message)
            .filter(Message.company_id == c.id, Message.timestamp >= since_today)
            .count()
        )
        convs = db.query(Conversation).filter(Conversation.company_id == c.id).count()
        customers = db.query(Customer).filter(Customer.company_id == c.id).count()
        last_msg = (
            db.query(Message)
            .filter(Message.company_id == c.id)
            .order_by(Message.timestamp.desc())
            .first()
        )
        out.append({
            "id": c.id, "name": c.name, "slug": c.slug, "business_type": c.business_type,
            "status": c.status, "admin_token": c.admin_token,
            "whatsapp_phone_number_id": c.whatsapp_phone_number_id,
            "notification_email": c.notification_email or "",
            "messages_today": msgs_today, "conversations": convs, "customers": customers,
            "last_activity": last_msg.timestamp.isoformat() if last_msg else None,
            "created_at": c.created_at.isoformat(),
        })
    out.sort(key=lambda x: x["created_at"], reverse=True)
    return out


@router.post("/api/companies")
async def api_create_company(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    _require_master(_auth(token, authorization))
    name = (body.get("name") or "").strip()
    phone_number_id = (body.get("whatsapp_phone_number_id") or "").strip()
    access_token = (body.get("whatsapp_access_token") or "").strip()
    business_type = (body.get("business_type") or "otro").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Falta el nombre de la empresa")
    if business_type not in BUSINESS_TYPES:
        business_type = "otro"

    base_slug = _slugify(name)
    slug = base_slug
    i = 2
    while db.query(Company).filter(Company.slug == slug).first():
        slug = f"{base_slug}-{i}"
        i += 1

    company = crud.create_company(
        db,
        name=name, slug=slug, business_type=business_type,
        whatsapp_phone_number_id=phone_number_id or f"pendiente-{secrets.token_hex(6)}",
        whatsapp_access_token=access_token or "",
        webhook_verify_token=(body.get("webhook_verify_token") or "").strip(),
        admin_token=secrets.token_urlsafe(18),
        notification_email=(body.get("notification_email") or "").strip(),
        status="onboarding",
    )
    logger.info("Empresa creada: %s (id=%d, tipo=%s)", company.name, company.id, business_type)
    return {
        "id": company.id, "name": company.name, "slug": company.slug,
        "admin_token": company.admin_token, "status": company.status,
        "panel_url": f"/admin/panel?token={company.admin_token}",
    }


@router.post("/api/companies/{company_id}/status")
async def api_set_company_status(company_id: int, body: dict, token: str = Query(default=""),
                                 authorization: str = Header(default=""), db: Session = Depends(get_db)):
    _require_master(_auth(token, authorization))
    status = (body.get("status") or "").strip()
    if status not in ("onboarding", "active", "paused"):
        raise HTTPException(status_code=400, detail="Estado inválido")
    company = crud.set_company_status(db, company_id, status)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return {"status": "ok", "company_status": company.status}


@router.post("/api/companies/{company_id}")
async def api_update_company(company_id: int, body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Editar credenciales de WhatsApp / correo de una empresa ya creada."""
    _require_master(_auth(token, authorization))
    fields = {}
    for key in ("name", "whatsapp_phone_number_id", "whatsapp_access_token",
               "webhook_verify_token", "notification_email", "business_type"):
        if key in body and body[key] is not None:
            fields[key] = body[key].strip() if isinstance(body[key], str) else body[key]
    company = crud.update_company(db, company_id, **fields)
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return {"status": "ok"}


@router.get("/api/profile")
def api_get_profile(token: str = Query(default=""), db: Session = Depends(get_db)):
    _require_master(token)
    return crud.get_master_profile(db)


@router.post("/api/profile")
async def api_save_profile(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    _require_master(_auth(token, authorization))
    crud.save_master_profile(db, body.get("name", ""), body.get("photo_b64"))
    return {"status": "ok"}


@router.get("/api/dashboard")
def api_dashboard(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Resumen general para el Dashboard del panel maestro: metricas reales
    agregadas de TODAS las empresas (nada de datos de ejemplo)."""
    _require_master(token)
    from datetime import timedelta
    companies = crud.list_companies(db)
    today = datetime.utcnow().date()
    start_today = datetime.combine(today, datetime.min.time())

    companies_active = sum(1 for c in companies if c.status == "active")
    conversations_today = db.query(Conversation).filter(Conversation.created_at >= start_today).count()
    total_contacts = db.query(Customer).count()

    # Conversaciones por dia (ultimos 7 dias, todas las empresas)
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    chart = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = (
            db.query(Conversation)
            .filter(Conversation.created_at >= datetime.combine(day, datetime.min.time()),
                    Conversation.created_at < datetime.combine(next_day, datetime.min.time()))
            .count()
        )
        chart.append({"label": dias[day.weekday()], "count": count})

    # Rendimiento por empresa (top 6 por num. de conversaciones)
    performance = []
    for c in companies:
        total = db.query(Conversation).filter(Conversation.company_id == c.id).count()
        if total == 0:
            continue
        resolved = db.query(Conversation).filter(Conversation.company_id == c.id, Conversation.status == "resolved").count()
        performance.append({
            "name": c.name, "business_type": c.business_type,
            "conversations": total,
            "success_rate": round((resolved / total) * 100, 1) if total else 0.0,
        })
    performance.sort(key=lambda x: x["conversations"], reverse=True)
    performance = performance[:6]

    # Empresas recientes (para la tabla)
    recent_companies = []
    for c in sorted(companies, key=lambda x: x.created_at, reverse=True)[:5]:
        convs_today = db.query(Conversation).filter(Conversation.company_id == c.id,
                                                     Conversation.created_at >= start_today).count()
        recent_companies.append({
            "id": c.id, "name": c.name, "slug": c.slug, "status": c.status,
            "conversations_today": convs_today,
        })

    # Actividad reciente: ultimas conversaciones iniciadas + empresas creadas
    activity = []
    company_names = {c.id: c.name for c in companies}
    recent_convs = db.query(Conversation).order_by(Conversation.created_at.desc()).limit(6).all()
    for conv in recent_convs:
        activity.append({
            "text": f"Nueva conversación en {company_names.get(conv.company_id, 'una empresa')}",
            "detail": f"+{conv.phone_number}",
            "at": conv.created_at.isoformat(),
        })
    for c in sorted(companies, key=lambda x: x.created_at, reverse=True)[:3]:
        activity.append({
            "text": "Nueva empresa agregada", "detail": c.name, "at": c.created_at.isoformat(),
        })
    activity.sort(key=lambda x: x["at"], reverse=True)
    activity = activity[:8]

    return {
        "companies_active": companies_active,
        "companies_total": len(companies),
        "chatbots_active": companies_active,
        "conversations_today": conversations_today,
        "total_contacts": total_contacts,
        "chart": chart,
        "performance": performance,
        "recent_companies": recent_companies,
        "activity": activity,
    }


@router.get("/api/recent-conversations")
def api_recent_conversations(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Conversaciones mas recientes de TODAS las empresas, con link directo al panel
    de la empresa dueña para abrirla."""
    _require_master(token)
    companies = {c.id: c for c in crud.list_companies(db)}
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(30).all()
    out = []
    for conv in convs:
        company = companies.get(conv.company_id)
        if not company:
            continue
        last_msg = (
            db.query(Message)
            .filter(Message.conversation_id == conv.id)
            .order_by(Message.timestamp.desc())
            .first()
        )
        out.append({
            "id": conv.id, "company_name": company.name, "phone_number": conv.phone_number,
            "mode": conv.mode, "status": conv.status,
            "preview": (last_msg.content[:80] if last_msg else ""),
            "updated_at": conv.updated_at.isoformat(),
            "panel_url": f"/admin/panel?token={company.admin_token}#chat/{conv.id}",
        })
    return out


@router.get("/panel", response_class=HTMLResponse)
async def master_panel(token: str = Query(default="")):
    if not token or token != settings.master_admin_token:
        return HTMLResponse("<h2>🔒 Acceso denegado</h2>", status_code=401)
    from app.master.ui import render_master_panel
    return HTMLResponse(render_master_panel(token))
