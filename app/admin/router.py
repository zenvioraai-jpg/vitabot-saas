import logging
import io
import os
from datetime import datetime
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openpyxl import Workbook
from app.config import settings
from app.db.database import get_db
from app.db import crud
from app.db.models import Customer, Conversation, Company
from app.whatsapp.client import WhatsAppCreds

_BOT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "bot_config.json")

router = APIRouter()
logger = logging.getLogger(__name__)


def _creds_for(company: Company) -> WhatsAppCreds:
    return WhatsAppCreds(phone_number_id=company.whatsapp_phone_number_id,
                         access_token=company.whatsapp_access_token)


def _require_company(db: Session, token: str) -> Company:
    """Resuelve la empresa dueña de este token de panel. 401 si no existe."""
    company = crud.get_company_by_admin_token(db, token)
    if not company:
        raise HTTPException(status_code=401, detail="Token inválido")
    return company


def _auth(token: str, authorization: str) -> str:
    return authorization.removeprefix("Bearer ").strip() or token


def verify_admin(token: str = Query(default=""), authorization: str = Header(default=""),
                 db: Session = Depends(get_db)) -> Company:
    return _require_company(db, _auth(token, authorization))


# ── JSON API (usada por el panel web via fetch) ────────────────────────────────

def _conv_to_dict(c, db) -> dict:
    last_msg = crud.get_last_message_time(db, c.id)
    msgs = crud.get_recent_messages(db, c.id, limit=6)
    real = [m for m in msgs if "FOTO_ENVIADA:" not in m.content]
    preview = (real[-1].content[:80] if real else "").replace("[NOTA INTERNA]", "🔒")
    customer = crud.get_or_create_customer(db, c.company_id, c.phone_number)
    return {
        "id": c.id,
        "phone_number": c.phone_number,
        "customer_name": customer.name,
        "mode": c.mode,
        "status": c.status,
        "assigned_to": c.assigned_to,
        "escalation_reason": c.escalation_reason,
        "escalated_at": c.escalated_at.isoformat() if c.escalated_at else None,
        "updated_at": c.updated_at.isoformat(),
        "last_message_at": last_msg.isoformat() if last_msg else None,
        "last_message_preview": preview,
    }


@router.get("/api/company-info")
def api_company_info(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Info básica de la empresa dueña de este token (para pintar el nombre en el panel)."""
    company = _require_company(db, token)
    return {"name": company.name, "business_type": company.business_type, "status": company.status}


@router.post("/api/seed-conversation")
async def api_seed_conversation(body: dict, token: str = Query(default=""),
                                authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Inserta una conversación DE DEMOSTRACIÓN directamente en la BD (cliente, mensajes,
    segmento y pedido si aplica), sin llamar a Claude ni enviar nada por WhatsApp."""
    company = _require_company(db, _auth(token, authorization))
    phone = (body.get("phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Falta el número de teléfono")
    turns = body.get("turns") or []

    customer = crud.get_or_create_customer(db, company.id, phone)
    fields = {k: body[k] for k in ("name", "city", "cedula", "email", "address") if body.get(k)}
    if fields:
        customer = crud.update_customer(db, company.id, phone, **fields)

    conversation = crud.create_new_conversation(db, company.id, phone, customer.id)

    for turn in turns:
        role = turn.get("role")
        text = turn.get("text") or ""
        if not text:
            continue
        crud.save_message(
            db, company_id=company.id, conversation_id=conversation.id,
            direction="inbound" if role == "customer" else "outbound",
            sender="customer" if role == "customer" else "ai",
            content=text,
        )

    segment = body.get("segment")
    if segment:
        crud.set_customer_segment(db, company.id, customer.id, segment)

    order = body.get("order")
    if order and order.get("items"):
        crud.create_order(
            db, company_id=company.id, customer_id=customer.id, conversation_id=conversation.id,
            items=order["items"], total=order.get("total"),
            payment_method=order.get("payment_method"),
            shipping_city=order.get("shipping_city") or customer.city,
            status=order.get("status", "pending"),
        )

    return {"status": "ok", "conversation_id": conversation.id, "customer_id": customer.id}


@router.get("/api/conversations")
def api_list_conversations(
    token: str = Query(default=""),
    filter: str = Query(default="open"),  # "open" | "all"
    db: Session = Depends(get_db),
):
    company = _require_company(db, token)
    convs = crud.list_all_conversations(db, company.id) if filter == "all" else crud.list_open_conversations(db, company.id)
    result = [_conv_to_dict(c, db) for c in convs]
    result.sort(key=lambda x: x["last_message_at"] or x["updated_at"], reverse=True)
    return result


class SendImageRequest(BaseModel):
    image_url: str
    caption: str = ""


@router.post("/conversations/{conversation_id}/send_image")
async def send_image_to_client(
    conversation_id: int,
    body: SendImageRequest,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404)
    if not body.image_url.startswith("http"):
        raise HTTPException(status_code=400, detail="La URL de la imagen debe ser pública (https://...)")
    from app.whatsapp.client import send_image_message
    success = await send_image_message(_creds_for(company), conv.phone_number, body.image_url, body.caption)
    if not success:
        raise HTTPException(status_code=502, detail="Error enviando la imagen por WhatsApp")
    content = f"[Imagen enviada por asesor: {body.image_url}]" + (f" — {body.caption}" if body.caption else "")
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=content)
    return {"status": "sent"}


@router.get("/api/conversations/{conversation_id}/messages")
def api_get_messages(
    conversation_id: int,
    token: str = Query(default=""),
    since: str = Query(default=""),
    db: Session = Depends(get_db),
):
    company = _require_company(db, token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404)
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            msgs = crud.get_messages_since(db, conversation_id, since_dt)
        except ValueError:
            msgs = crud.get_recent_messages(db, conversation_id, limit=100)
    else:
        msgs = crud.get_recent_messages(db, conversation_id, limit=100)
    return [
        {
            "id": m.id,
            "direction": m.direction,
            "sender": m.sender,
            "content": m.content,
            "timestamp": m.timestamp.isoformat(),
            "is_internal": "[NOTA INTERNA]" in m.content,
        }
        for m in msgs
        if "FOTO_ENVIADA:" not in m.content
    ]


# ── API: Estadísticas del Dashboard ───────────────────────────────────────────

@router.get("/api/stats")
def api_stats(token: str = Query(default=""), period: str = Query(default="all"),
              start: str = Query(default=""), end: str = Query(default=""),
              db: Session = Depends(get_db)):
    company = _require_company(db, token)
    from app.db.models import Order
    from datetime import timedelta

    now = datetime.utcnow()
    since = None
    until = None
    if start or end:
        try:
            if start:
                since = datetime.strptime(start, "%Y-%m-%d")
            if end:
                until = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido (usa AAAA-MM-DD)")
        period = "custom"
    elif period == "day":
        since = datetime.combine(now.date(), datetime.min.time())
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    elif period == "year":
        since = now - timedelta(days=365)
    else:
        since = None

    def _in_period(q):
        if since:
            q = q.filter(Conversation.created_at >= since)
        if until:
            q = q.filter(Conversation.created_at < until)
        return q

    base_conv_q = db.query(Conversation).filter(Conversation.company_id == company.id)
    total_convs = _in_period(base_conv_q).count()
    open_convs = base_conv_q.filter(Conversation.status == "open").count()
    ai_convs = base_conv_q.filter(Conversation.status == "open", Conversation.mode == "ai").count()
    human_convs = base_conv_q.filter(Conversation.status == "open", Conversation.mode == "human").count()
    resolved_convs = _in_period(base_conv_q.filter(Conversation.status == "resolved")).count()
    total_customers = db.query(Customer).filter(Customer.company_id == company.id).count()

    _orders_q = db.query(Order).filter(Order.company_id == company.id, Order.status == "paid")
    if since:
        _orders_q = _orders_q.filter(Order.created_at >= since)
    if until:
        _orders_q = _orders_q.filter(Order.created_at < until)
    paid_orders = _orders_q.all()
    convs_with_sale = len(set(o.conversation_id for o in paid_orders))
    ingresos = sum(o.total or 0 for o in paid_orders)
    conversion = round((convs_with_sale / total_convs * 100), 1) if total_convs else 0.0

    start_day = datetime.combine(now.date(), datetime.min.time())
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ventas_dia = sum(o.total or 0 for o in paid_orders if o.created_at and o.created_at >= start_day)
    ventas_mes = sum(o.total or 0 for o in paid_orders if o.created_at and o.created_at >= start_month)
    num_ventas = len(paid_orders)
    ticket_promedio = int(ingresos / num_ventas) if num_ventas else 0
    clientes_nuevos = db.query(Customer).filter(Customer.company_id == company.id,
                                                Customer.created_at >= (since or start_month)).count()
    compras_por_cliente: dict[int, int] = {}
    for o in paid_orders:
        compras_por_cliente[o.customer_id] = compras_por_cliente.get(o.customer_id, 0) + 1
    clientes_recurrentes = sum(1 for n in compras_por_cliente.values() if n >= 2)
    valor_prom_cliente = int(ingresos / len(compras_por_cliente)) if compras_por_cliente else 0
    ia_rate = round((resolved_convs / total_convs * 100), 1) if total_convs else 0.0

    today = datetime.utcnow().date()
    per_day = []
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = (
            db.query(Conversation)
            .filter(Conversation.company_id == company.id,
                    Conversation.created_at >= datetime.combine(day, datetime.min.time()),
                    Conversation.created_at < datetime.combine(next_day, datetime.min.time()))
            .count()
        )
        per_day.append({"label": dias[day.weekday()], "count": count})

    return {
        "total_conversations": total_convs,
        "open_conversations": open_convs,
        "ai_conversations": ai_convs,
        "human_conversations": human_convs,
        "resolved_conversations": resolved_convs,
        "total_customers": total_customers,
        "conversations_with_sale": convs_with_sale,
        "ingresos": int(ingresos),
        "conversion_rate": conversion,
        "ia_resolution_rate": ia_rate,
        "per_day": per_day,
        "ventas_completadas": resolved_convs,
        "ventas_en_proceso": human_convs,
        "ventas_pendientes": ai_convs,
        "num_ventas": num_ventas,
        "ventas_dia": int(ventas_dia),
        "ventas_mes": int(ventas_mes),
        "ticket_promedio": ticket_promedio,
        "clientes_nuevos": clientes_nuevos,
        "clientes_recurrentes": clientes_recurrentes,
        "valor_promedio_cliente": valor_prom_cliente,
        "comprobantes": crud.receipt_metrics(db, company.id),
        "period": period,
    }


@router.get("/api/top-products")
def api_top_products(token: str = Query(default=""), period: str = Query(default="all"),
                     start: str = Query(default=""), end: str = Query(default=""),
                     db: Session = Depends(get_db)):
    """Productos más vendidos en un período: unidades, ingresos estimados, top clientes."""
    company = _require_company(db, token)
    import json as _json
    from datetime import timedelta
    from app.db.models import Order

    now = datetime.utcnow()
    since = until = None
    if start or end:
        try:
            if start:
                since = datetime.strptime(start, "%Y-%m-%d")
            if end:
                until = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido (AAAA-MM-DD)")
        period = "custom"
    elif period == "day":
        since = datetime.combine(now.date(), datetime.min.time())
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    elif period == "year":
        since = now - timedelta(days=365)

    q = db.query(Order).filter(Order.company_id == company.id, Order.status == "paid")
    if since:
        q = q.filter(Order.created_at >= since)
    if until:
        q = q.filter(Order.created_at < until)
    orders = q.all()

    price_map = {p.name.lower(): (p.price or 0) for p in crud.list_products(db, company.id)}

    def _price(name):
        low = (name or "").lower()
        if low in price_map:
            return price_map[low]
        return next((v for k, v in price_map.items() if k in low or low in k), 0)

    stats = {p.name: {"name": p.name, "units": 0, "orders": 0, "revenue": 0, "customers": {}}
             for p in crud.list_products(db, company.id)}

    cust_ids = set()
    for o in orders:
        try:
            items = _json.loads(o.items_json) if o.items_json else []
        except Exception:
            items = []
        for it in items:
            name = it.get("name", "Producto")
            qty = int(it.get("quantity", 1) or 1)
            ps = stats.setdefault(name, {"name": name, "units": 0, "orders": 0, "revenue": 0, "customers": {}})
            ps["units"] += qty
            ps["orders"] += 1
            ps["revenue"] += _price(name) * qty
            ps["customers"][o.customer_id] = ps["customers"].get(o.customer_id, 0) + qty
            cust_ids.add(o.customer_id)

    names = {c.id: (c.name or f"+{c.phone_number}") for c in
             db.query(Customer).filter(Customer.id.in_(cust_ids)).all()} if cust_ids else {}

    products = []
    for ps in stats.values():
        top = sorted(ps["customers"].items(), key=lambda kv: kv[1], reverse=True)[:3]
        products.append({
            "name": ps["name"], "units": ps["units"], "orders": ps["orders"],
            "revenue": int(ps["revenue"]),
            "top_customers": [{"name": names.get(cid, "Cliente"), "units": u} for cid, u in top],
        })
    products.sort(key=lambda x: x["units"], reverse=True)

    return {
        "period": period,
        "total_units": sum(p["units"] for p in products),
        "total_revenue": int(sum(o.total or 0 for o in orders)),
        "total_orders": len(orders),
        "products": products,
    }


# ── API: Lista de Clientes ─────────────────────────────────────────────────────

@router.get("/api/customers")
def api_customers(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    import json
    from app.db.models import Order

    customers = db.query(Customer).filter(Customer.company_id == company.id).order_by(Customer.created_at.desc()).all()
    result = []
    for c in customers:
        orders = db.query(Order).filter(Order.customer_id == c.id, Order.status == "paid").all()
        purchase_count = len(orders)
        last_purchase = max([o.created_at for o in orders], default=None)
        total_amount = sum([o.total or 0 for o in orders]) if orders else 0
        product_count = 0
        prod_freq: dict[str, int] = {}
        for order in orders:
            try:
                items = json.loads(order.items_json) if order.items_json else []
                for item in items:
                    qty = item.get("quantity", 1)
                    product_count += qty
                    nm = item.get("name", "Producto")
                    prod_freq[nm] = prod_freq.get(nm, 0) + qty
            except Exception:
                pass
        top_product = max(prod_freq.items(), key=lambda x: x[1])[0] if prod_freq else "—"
        ticket_prom = int(total_amount / purchase_count) if purchase_count else 0
        estado = "Recurrente" if purchase_count >= 2 else ("Nuevo" if purchase_count == 1 else "Sin compra")
        result.append({
            "id": c.id,
            "name": c.name or "—",
            "phone_number": c.phone_number,
            "cedula": c.cedula or "—",
            "email": c.email or "—",
            "address": c.address or "—",
            "city": c.city or "",
            "registered": c.created_at.strftime("%d/%m/%Y") if c.created_at else "—",
            "last_purchase": last_purchase.strftime("%d/%m/%Y") if last_purchase else "—",
            "product_count": product_count,
            "purchase_count": purchase_count,
            "top_product": top_product,
            "ticket_promedio": ticket_prom,
            "estado": estado,
            "total": int(total_amount),
        })
    return result


# ── API: Comprobantes de Pago ──────────────────────────────────────────────────

@router.get("/api/receipts")
def api_receipts(phone: str = Query(default=""), token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    customer_id = None
    if phone:
        c = crud.get_or_create_customer(db, company.id, phone)
        customer_id = c.id
    receipts = crud.list_receipts(db, company.id, customer_id=customer_id)
    cust_ids = {r.customer_id for r in receipts}
    names = {c.id: (c.name or "") for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()} if cust_ids else {}
    phones = {c.id: c.phone_number for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()} if cust_ids else {}
    return [
        {
            "id": r.id,
            "customer_name": names.get(r.customer_id) or "Sin nombre",
            "customer_phone": phones.get(r.customer_id) or "",
            "bank": r.bank or "—",
            "amount": r.amount or 0,
            "reference": r.reference or "—",
            "receipt_date": r.receipt_date or "—",
            "is_valid": r.is_valid,
            "created_at": r.created_at.isoformat(),
            "image": f"data:{r.mime_type};base64,{r.image_b64}" if r.image_b64 else None,
        }
        for r in receipts
    ]


@router.get("/api/receipts/download")
def api_receipts_download(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Descarga un ZIP con TODOS los comprobantes, nombrados por fecha y cliente."""
    company = _require_company(db, token)
    import zipfile, base64 as _b64, re as _re
    receipts = crud.list_receipts(db, company.id, limit=100000)
    cust_ids = {r.customer_id for r in receipts}
    names = {c.id: (c.name or "") for c in db.query(Customer).filter(Customer.id.in_(cust_ids)).all()} if cust_ids else {}
    buf = io.BytesIO()
    used = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in receipts:
            if not r.image_b64:
                continue
            try:
                raw = _b64.b64decode(r.image_b64)
            except Exception:
                continue
            ext = "png" if "png" in (r.mime_type or "") else "jpg"
            fecha = r.created_at.strftime("%Y-%m-%d") if r.created_at else "sinfecha"
            nombre = names.get(r.customer_id) or "SinNombre"
            nombre = _re.sub(r"[^A-Za-z0-9áéíóúÁÉÍÓÚñÑ _-]", "", nombre).strip().replace(" ", "_") or "SinNombre"
            estado = "VALIDO" if r.is_valid else "revisar"
            base = f"{fecha}_{nombre}_{estado}"
            used[base] = used.get(base, 0) + 1
            suffix = "" if used[base] == 1 else f"_{used[base]}"
            zf.writestr(f"{fecha}/{base}{suffix}.{ext}", raw)
    buf.seek(0)
    fname = f"comprobantes_{company.slug}_{datetime.utcnow().strftime('%Y%m%d')}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── API: Catálogo (productos, guardado en la BD) ───────────────────────────────

@router.get("/api/catalog")
def api_get_catalog(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return [
        {"sku": p.sku, "name": p.name, "base_price": p.price, "price_cop": p.price,
         "description": p.description or "", "in_stock": p.in_stock}
        for p in crud.list_products(db, company.id)
    ]


@router.post("/api/catalog")
async def api_save_catalog(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """body = { sku: {price_cop, in_stock}, ... } — actualiza precio/stock de productos existentes."""
    company = _require_company(db, _auth(token, authorization))
    for sku, vals in body.items():
        p = crud.get_product(db, company.id, sku)
        if not p:
            continue
        fields = {}
        if "price_cop" in vals:
            fields["price"] = vals["price_cop"]
        if "in_stock" in vals:
            fields["in_stock"] = bool(vals["in_stock"])
        if fields:
            crud.upsert_product(db, company.id, sku, **fields)
    return {"status": "ok"}


@router.post("/api/products")
async def api_create_product(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Crear o editar por completo un producto (sku, name, price, description)."""
    company = _require_company(db, _auth(token, authorization))
    sku = (body.get("sku") or "").strip()
    name = (body.get("name") or "").strip()
    if not sku or not name:
        raise HTTPException(status_code=400, detail="Falta el SKU o el nombre del producto")
    crud.upsert_product(
        db, company.id, sku, name=name,
        price=body.get("price") or 0,
        description=(body.get("description") or "").strip(),
        in_stock=bool(body.get("in_stock", True)),
    )
    return {"status": "ok"}


@router.delete("/api/products/{sku}")
async def api_delete_product(sku: str, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.delete_product(db, company.id, sku)
    crud.delete_media_blob(db, company.id, sku, "image")
    crud.delete_media_blob(db, company.id, sku, "video")
    return {"status": "ok"}


# ── API: Catálogo multimedia ───────────────────────────────────────────────────

@router.get("/api/product-media")
def api_get_product_media(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    media = crud.get_product_media(db, company.id)
    blobs = crud.media_blob_skus(db, company.id)
    products = []
    for p in crud.list_products(db, company.id):
        m = media.get(p.sku, {})
        has_img = (p.sku, "image") in blobs or bool(m.get("image_media_id"))
        has_vid = (p.sku, "video") in blobs or bool(m.get("video_media_id"))
        products.append({
            "sku": p.sku, "name": p.name,
            "image_url": m.get("image_url", ""),
            "video_url": m.get("video_url", ""),
            "link": m.get("link", ""),
            "has_image_file": has_img,
            "has_video_file": has_vid,
            "image_preview": (f"/admin/api/product-media/file/{p.sku}/image?token={token}" if (p.sku, "image") in blobs else ""),
            "video_preview": (f"/admin/api/product-media/file/{p.sku}/video?token={token}" if (p.sku, "video") in blobs else ""),
        })
    return products


@router.get("/api/product-media/file/{sku}/{kind}")
def api_product_media_file(sku: str, kind: str, token: str = Query(default=""),
                           db: Session = Depends(get_db)):
    """Sirve el archivo guardado en la BD (para previsualizar foto/video en el panel)."""
    company = _require_company(db, token)
    data = crud.get_media_blob(db, company.id, sku, kind)
    if not data:
        raise HTTPException(status_code=404, detail="Sin archivo")
    content, mime = data
    return Response(content=content, media_type=mime, headers={"Cache-Control": "no-cache"})


@router.get("/media/{company_id}/{sku}/{kind}")
def public_product_media_file(company_id: int, sku: str, kind: str, db: Session = Depends(get_db)):
    """URL PÚBLICA (sin token) del archivo del producto. WhatsApp la descarga
    directamente para enviar la foto/video al cliente, sin depender de media_ids
    que caducan. Solo expone media de catálogo (no es información sensible)."""
    data = crud.get_media_blob(db, company_id, sku, kind)
    if not data:
        raise HTTPException(status_code=404, detail="Sin archivo")
    content, mime = data
    return Response(content=content, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


@router.post("/api/product-media")
async def api_save_product_media(body: dict, token: str = Query(default=""),
                                 authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    existing = crud.get_product_media(db, company.id)
    for sku, vals in body.items():
        cur = existing.get(sku, {})
        cur.update(vals)
        existing[sku] = cur
    crud.save_product_media(db, company.id, existing)
    return {"status": "ok"}


@router.post("/api/product-media/upload")
async def api_upload_product_media(
    sku: str = Query(...),
    kind: str = Query(...),   # 'image' | 'video'
    file: UploadFile = File(...),
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Subir imagen (jpg/png) o video (mp4) directamente y guardarlo como media de un producto."""
    company = _require_company(db, _auth(token, authorization))

    content = await file.read()
    ctype = file.content_type or ""
    if kind == "image":
        if not ctype.startswith("image/"):
            raise HTTPException(status_code=400, detail="El archivo debe ser una imagen (JPG/PNG)")
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")
    else:
        if not ctype.startswith("video/"):
            raise HTTPException(status_code=400, detail="El archivo debe ser un video (MP4)")
        if len(content) > 16 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="El video no puede superar 16MB")

    try:
        crud.save_media_blob(db, company.id, sku, kind, content, ctype)
    except Exception as exc:
        logger.error("No se pudo guardar el media en la BD: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo. Intenta de nuevo.")

    from app.whatsapp.client import upload_media_to_whatsapp
    media_id = await upload_media_to_whatsapp(_creds_for(company), content, ctype,
                                              file.filename or ("media." + ("mp4" if kind == "video" else "jpg")))

    media = crud.get_product_media(db, company.id)
    item = media.get(sku, {})
    if kind == "image":
        item["image_media_id"] = media_id or ""
        item["image_mime"] = ctype
    else:
        item["video_media_id"] = media_id or ""
        item["video_mime"] = ctype
    media[sku] = item
    crud.save_product_media(db, company.id, media)
    logger.info("Media subido sku=%s kind=%s (wa_id=%s)", sku, kind, bool(media_id))
    return {"status": "ok", "media_id": media_id, "preview": True}


@router.post("/api/product-media/test-send")
async def api_test_send_product_media(body: dict, token: str = Query(default=""),
                                      authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Envía una prueba REAL de la foto/video de un producto a un número de WhatsApp."""
    import re
    company = _require_company(db, _auth(token, authorization))
    sku = (body.get("sku") or "").strip()
    kind = (body.get("kind") or "image").strip()
    phone = re.sub(r"[^\d]", "", body.get("phone") or "")
    if not sku or not phone:
        return {"ok": False, "message": "Falta el producto o el número de WhatsApp."}
    from app.whatsapp.media_send import test_send_product_media
    ok, message = await test_send_product_media(db, company.id, _creds_for(company), phone, sku, kind)
    return {"ok": ok, "message": message}


@router.delete("/api/product-media/{sku}/{kind}")
async def api_delete_product_media(
    sku: str, kind: str,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Eliminar la imagen o el video de un producto (archivo en BD + media_id)."""
    company = _require_company(db, _auth(token, authorization))
    crud.delete_media_blob(db, company.id, sku, kind)
    media = crud.get_product_media(db, company.id)
    item = media.get(sku)
    if item:
        if kind == "image":
            item.pop("image_media_id", None)
            item.pop("image_url", None)
            item.pop("image_mime", None)
        else:
            item.pop("video_media_id", None)
            item.pop("video_url", None)
            item.pop("video_mime", None)
        media[sku] = item
        crud.save_product_media(db, company.id, media)
    return {"status": "ok"}


# ── API: Productos comprados por cliente ───────────────────────────────────────

@router.get("/api/customers/{phone}/orders")
def api_customer_orders(phone: str, token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    import json as _json
    from app.db.models import Order
    customer = crud.get_or_create_customer(db, company.id, phone)
    orders = db.query(Order).filter(Order.customer_id == customer.id).order_by(Order.created_at.desc()).all()
    out = []
    for o in orders:
        try:
            items = _json.loads(o.items_json) if o.items_json else []
        except Exception:
            items = []
        out.append({
            "id": o.id,
            "date": o.created_at.strftime("%d/%m/%Y") if o.created_at else "",
            "items": [{"name": it.get("name", "Producto"), "quantity": it.get("quantity", 1)} for it in items],
            "total": int(o.total or 0),
            "payment_method": o.payment_method or "",
            "status": o.status,
            "payment_received": crud.is_payment_received(db, o.id) or o.status == "paid",
        })
    return out


# ── Conversación: marcar pago recibido / enviar producto / enviar audio ─────────

@router.post("/conversations/{conversation_id}/mark-payment-received")
async def mark_payment_received_ep(conversation_id: int, token: str = Query(default=""),
                                   authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    order = crud.get_latest_order_for_conversation(db, conversation_id)
    if not order:
        raise HTTPException(status_code=404, detail="No hay pedido en esta conversación")
    crud.mark_payment_received(db, company.id, order.id)
    crud.mark_order_paid(db, conversation_id)
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/send_product")
async def send_product_ep(conversation_id: int, body: dict, token: str = Query(default=""),
                          authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Enviar al cliente (modo humano) la foto/video/link de un producto guardado en configuración."""
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404)
    sku = body.get("sku", "")
    what = body.get("what", "photo")  # photo | video | link
    media = crud.get_product_media(db, company.id).get(sku, {})
    from app.whatsapp.media_send import send_product_photo, send_product_video
    from app.catalog_util import media_marker
    from app.whatsapp.client import send_text_message
    creds = _creds_for(company)
    product = crud.get_product(db, company.id, sku)
    pname = product.name if product else sku
    sent = False
    record = ""
    if what == "photo":
        sent = await send_product_photo(db, company.id, creds, conv.phone_number, sku)
        record = media_marker("image", sku, pname)
    elif what == "video":
        sent = await send_product_video(db, company.id, creds, conv.phone_number, sku)
        record = media_marker("video", sku, pname)
    elif what == "link" and media.get("link"):
        sent = await send_text_message(creds, conv.phone_number, f"🔗 {pname}: {media['link']}")
        record = f"🔗 {pname}: {media['link']}"
    if not sent:
        raise HTTPException(status_code=400, detail="Ese producto no tiene ese contenido cargado en Multimedia")
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=record)
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/messages/{message_id}/delete")
def delete_message_ep(conversation_id: int, message_id: int, token: str = Query(default=""),
                      authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Eliminar un mensaje del historial del panel."""
    _require_company(db, _auth(token, authorization))
    ok = crud.delete_message(db, conversation_id, message_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/send_audio")
async def send_audio_ep(conversation_id: int, file: UploadFile = File(...), token: str = Query(default=""),
                        authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Subir y enviar una nota de voz/audio (modo humano)."""
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404)
    content = await file.read()
    if len(content) > 16 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El audio no puede superar 16MB")
    mime = file.content_type or "audio/ogg"
    from app.audio_service import convert_to_ogg_opus
    converted = convert_to_ogg_opus(content, mime)
    if not converted:
        logger.error("No se pudo preparar el audio (mime=%s). ¿ffmpeg instalado?", mime)
        raise HTTPException(status_code=502, detail="No se pudo preparar el audio para enviar. Intenta grabarlo de nuevo.")
    content, mime, fname = converted
    import uuid
    from app.runtime import public_base
    from app.whatsapp.client import upload_media_to_whatsapp, send_audio_by_id, send_audio_by_url
    creds = _creds_for(company)
    key = f"aud-{uuid.uuid4().hex[:12]}"
    try:
        crud.save_media_blob(db, company.id, key, "audio", content, "audio/ogg")
    except Exception as exc:
        logger.error("No se pudo guardar el audio: %s", exc)
    base = public_base()
    sent = False
    if base and crud.get_media_blob(db, company.id, key, "audio"):
        sent = await send_audio_by_url(creds, conv.phone_number, f"{base}/media/{company.id}/{key}/audio")
    if not sent:
        media_id = await upload_media_to_whatsapp(creds, content, mime, fname)
        if media_id:
            sent = await send_audio_by_id(creds, conv.phone_number, media_id)
    if not sent:
        raise HTTPException(status_code=502, detail="WhatsApp rechazó el audio. Intenta grabarlo de nuevo.")
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content="[Asesor envió una nota de voz]")
    return {"status": "ok"}


# ── API: Cuentas de pago / Bre-B ───────────────────────────────────────────────

@router.get("/api/payment-config")
def api_get_payment(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return crud.get_payment_config(db, company.id)


@router.post("/api/payment-config")
async def api_save_payment(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_payment_config(db, company.id, body)
    return {"status": "ok"}


# ── API: Cupones / Descuentos ──────────────────────────────────────────────────

@router.get("/api/coupons")
def api_list_coupons(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return [
        {"code": c.code, "kind": c.kind, "value": c.value, "active": c.active,
         "uses": c.uses, "max_uses": c.max_uses}
        for c in crud.list_coupons(db, company.id)
    ]


@router.post("/api/coupons")
async def api_create_coupon(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    code = (body.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="El código no puede estar vacío")
    crud.create_coupon(db, company.id, code=code, kind=body.get("kind", "percent"),
                       value=int(body.get("value", 0) or 0), max_uses=int(body.get("max_uses", 0) or 0))
    return {"status": "ok"}


@router.delete("/api/coupons/{code}")
async def api_delete_coupon(code: str, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.delete_coupon(db, company.id, code)
    return {"status": "ok"}


# ── API: Configuración de Voz (ElevenLabs) ─────────────────────────────────────

@router.get("/api/voice-config")
def api_get_voice(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    cfg = crud.get_voice_config(db, company.id)
    cfg["api_key_set"] = bool(settings.elevenlabs_api_key)
    return cfg


@router.post("/api/voice-config")
async def api_save_voice(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_voice_config(db, company.id, enabled=bool(body.get("enabled", False)), voice_id=body.get("voice_id", ""))
    return {"status": "ok"}


# ── API: Postventa / Reseñas ───────────────────────────────────────────────────

@router.get("/api/postventa-config")
def api_get_postventa(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return crud.get_postventa_config(db, company.id)


@router.post("/api/postventa-config")
async def api_save_postventa(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_postventa_config(db, company.id, **body)
    return {"status": "ok"}


# ── Reset / borrado de datos (protegido por clave fija) ────────────────────────
_RESET_PASSWORD = "Juanjo15+"


def _check_reset_password(body: dict) -> None:
    if (body or {}).get("password", "") != _RESET_PASSWORD:
        raise HTTPException(status_code=403, detail="Clave de seguridad incorrecta")


@router.post("/api/reset/all")
async def api_reset_all(body: dict, token: str = Query(default=""),
                        authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    _check_reset_password(body)
    counts = crud.reset_all_customer_data(db, company.id)
    logger.warning("RESET TOTAL de datos de clientes ejecutado (empresa %d): %s", company.id, counts)
    return {"status": "ok", "deleted": counts}


@router.post("/api/reset/customer")
async def api_reset_customer(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    _check_reset_password(body)
    cid = body.get("customer_id")
    phone = body.get("phone")
    if not cid and phone:
        c = db.query(Customer).filter(Customer.company_id == company.id, Customer.phone_number == phone).first()
        cid = c.id if c else None
    if not cid:
        raise HTTPException(status_code=400, detail="Falta customer_id o phone")
    ok = crud.reset_customer(db, company.id, int(cid))
    if not ok:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    logger.warning("Cliente %s borrado por reset (empresa %d)", cid, company.id)
    return {"status": "ok"}


@router.post("/api/reset/category")
async def api_reset_category(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    _check_reset_password(body)
    name = (body.get("category") or "").strip().lower()
    if name not in ("cupones",):
        raise HTTPException(status_code=400, detail="Categoría no válida")
    n = crud.clear_category(db, company.id, name)
    logger.warning("Categoría '%s' borrada (%d filas) por reset (empresa %d)", name, n, company.id)
    return {"status": "ok", "deleted": n}


@router.post("/api/help-chat")
async def api_help_chat(body: dict, token: str = Query(default=""),
                        authorization: str = Header(default="")):
    """Chatbot de AYUDA para el operador del panel. Totalmente independiente del bot
    de clientes: NO toca la base de datos ni envía WhatsApp. Solo responde dudas del panel."""
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        _require_company(db, _auth(token, authorization))
    finally:
        db.close()
    from app.agent.help_prompt import HELP_SYSTEM_PROMPT
    from app.agent.claude_client import get_ai_response

    raw_msgs = body.get("messages", [])
    messages = []
    for m in raw_msgs[-12:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:2000]})
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Falta el mensaje del usuario")
    try:
        reply = get_ai_response(HELP_SYSTEM_PROMPT, messages)
    except Exception as exc:
        logger.error("Error en help-chat: %s", exc)
        raise HTTPException(status_code=502, detail="No se pudo obtener respuesta del asistente")
    return {"reply": reply}


@router.post("/api/test-chat")
async def api_test_chat(body: dict, token: str = Query(default=""),
                        authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Chat de PRUEBA con el bot REAL de esta empresa (su catálogo/entrenamiento), sin
    tocar WhatsApp ni la base de datos de clientes reales. Para probar el bot antes de
    salir en vivo, durante el onboarding."""
    company = _require_company(db, _auth(token, authorization))
    from app.agent.system_prompt import build_system_prompt
    from app.agent.claude_client import get_ai_response

    raw_msgs = body.get("messages", [])
    messages = []
    for m in raw_msgs[-20:]:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content[:2000]})
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="Falta el mensaje del usuario")

    products = crud.list_products(db, company.id)
    system_prompt = build_system_prompt(
        company_name=company.name,
        products=[{"sku": p.sku, "name": p.name, "price": p.price, "description": p.description} for p in products],
        is_first_message=len(messages) <= 1,
        payment_config=crud.get_payment_config(db, company.id),
        coupons=[{"code": c.code, "kind": c.kind, "value": c.value} for c in crud.get_active_coupons(db, company.id)],
        training_notes=crud.get_training_notes(db, company.id),
        bot_name=crud.get_bot_name(db, company.id),
    )
    try:
        reply = get_ai_response(system_prompt, messages)
    except Exception as exc:
        logger.error("Error en test-chat: %s", exc)
        raise HTTPException(status_code=502, detail="No se pudo obtener respuesta del asistente")
    import re as _re
    reply = _re.sub(r'\[[A-Z_]+(?:: [^\]]+)?\]', '', reply).strip()
    return {"reply": reply}


@router.get("/api/bot-paused")
def api_get_bot_paused(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return {"paused": crud.get_bot_paused(db, company.id)}


@router.post("/api/bot-paused")
async def api_set_bot_paused(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.set_bot_paused(db, company.id, bool(body.get("paused")))
    return {"status": "ok", "paused": crud.get_bot_paused(db, company.id)}


@router.get("/api/notif-config")
def api_get_notif(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return crud.get_notif_config(db, company.id)


@router.post("/api/notif-config")
async def api_save_notif(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_notif_config(db, company.id, body)
    return {"status": "ok"}


@router.post("/api/notif-test")
async def api_notif_test(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Guarda la config actual y envía un correo de prueba, devolviendo el resultado real."""
    company = _require_company(db, _auth(token, authorization))
    if body:
        crud.save_notif_config(db, company.id, body)
    cfg = crud.get_notif_config(db, company.id)
    from app.email_service import send_test_email
    raw = (cfg.get("email") or "").strip() or company.notification_email or ""
    destinatarios = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
    if not destinatarios:
        return {"ok": False, "message": "No hay ningún correo configurado para recibir avisos."}
    ok, msg = False, ""
    for email in destinatarios:
        ok, msg = send_test_email(company.id, email)
        if not ok:
            return {"ok": False, "message": f"{email}: {msg}"}
    return {"ok": True, "message": f"Correo de prueba enviado a: {', '.join(destinatarios)}"}


@router.get("/api/quick-replies")
def api_get_quick_replies(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return crud.get_quick_replies(db, company.id)


@router.post("/api/quick-replies")
async def api_save_quick_replies(body: dict, token: str = Query(default=""),
                                 authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_quick_replies(db, company.id, body.get("items", []))
    return {"status": "ok"}


@router.get("/api/bot-name")
def api_get_bot_name(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return {"name": crud.get_bot_name(db, company.id)}


@router.post("/api/bot-name")
async def api_save_bot_name(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_bot_name(db, company.id, body.get("name", ""))
    return {"status": "ok", "name": crud.get_bot_name(db, company.id)}


@router.get("/api/training-config")
def api_get_training(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return {"notes": crud.get_training_notes(db, company.id)}


@router.post("/api/training-config")
async def api_save_training(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_training_notes(db, company.id, body.get("notes", ""))
    return {"status": "ok"}


@router.get("/api/promo-config")
def api_get_promo(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return crud.get_promo_config(db, company.id)


@router.post("/api/promo-config")
async def api_save_promo(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    crud.save_promo_config(db, company.id, **body)
    return {"status": "ok"}


@router.post("/tasks/run-followups")
async def run_followups(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Enviar seguimiento postventa a clientes con compra pagada hace N días, para
    TODAS las empresas. Pensado para llamarse desde un cron interno o externo."""
    if token != settings.master_admin_token:
        raise HTTPException(status_code=401, detail="Token inválido")
    from app.whatsapp.client import send_template_message, send_text_message
    total_sent, total_failed, last_error = 0, 0, ""
    for company in crud.list_companies(db):
        if company.status != "active":
            continue
        creds = _creds_for(company)
        cfg = crud.get_postventa_config(db, company.id)
        if not cfg.get("enabled"):
            continue
        pendientes = crud.orders_pending_followup(db, company.id, cfg.get("days_after", 3))
        template_name = (cfg.get("template_name") or "").strip()
        template_lang = (cfg.get("template_lang") or "es").strip()
        for order in pendientes:
            customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
            if not customer:
                continue
            nombre = (customer.name or "").split()[0] if customer.name else "🌿"
            msg = cfg["message"].replace("{nombre}", nombre)
            if template_name:
                ok, err = await send_template_message(creds, customer.phone_number, template_name,
                                                      body_params=[nombre], language=template_lang)
            else:
                ok = await send_text_message(creds, customer.phone_number, msg)
                err = "" if ok else "fuera de la ventana de 24h (configura una plantilla de Meta)"
            if ok:
                conv = crud.get_open_conversation(db, company.id, customer.phone_number)
                if conv:
                    crud.save_message(db, company_id=company.id, conversation_id=conv.id,
                                      direction="outbound", sender="ai", content=msg)
                crud.mark_followup(db, company.id, order.id, customer.id, kind="postventa")
                total_sent += 1
            else:
                total_failed += 1
                last_error = err or last_error
    logger.info("Postventa (todas las empresas): %d enviados, %d fallidos (%s)", total_sent, total_failed, last_error)
    return {"status": "ok", "sent": total_sent, "failed": total_failed, "error": last_error}


@router.post("/tasks/run-reminders")
async def run_reminders(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Enviar recordatorios a clientes que dijeron que volverían y no lo hicieron,
    para TODAS las empresas."""
    if token != settings.master_admin_token:
        raise HTTPException(status_code=401, detail="Token inválido")
    from app.whatsapp.client import send_template_message, send_text_message
    pendientes = crud.due_reminders(db)
    sent, failed, last_error = 0, 0, ""
    companies_cache: dict[int, Company] = {}
    for r in pendientes:
        customer = db.query(Customer).filter(Customer.id == r.customer_id).first()
        if not customer:
            crud.mark_reminder_sent(db, r.id)
            continue
        company = companies_cache.get(r.company_id) or crud.get_company(db, r.company_id)
        companies_cache[r.company_id] = company
        if not company or company.status != "active":
            crud.mark_reminder_sent(db, r.id)
            continue
        creds = _creds_for(company)
        cfg = crud.get_postventa_config(db, company.id)
        recon_template = (cfg.get("recontacto_template") or "").strip()
        nombre = (customer.name or "").split()[0] if customer.name else "🌿"
        motivo = (r.note or "").strip()
        msg = (f"Hola *{nombre}* 🌿 Te escribo para recordarte lo que tenías pendiente"
               + (f": {motivo}." if motivo else ".")
               + " ¿Te ayudo a continuar? 💚")
        if recon_template:
            ok, err = await send_template_message(creds, customer.phone_number, recon_template,
                                                  body_params=[nombre], language="es")
        else:
            ok = await send_text_message(creds, customer.phone_number, msg)
            err = "" if ok else "fuera de la ventana de 24h (configura una plantilla de recordatorio)"
        if ok:
            conv = crud.get_open_conversation(db, company.id, customer.phone_number)
            if conv:
                crud.save_message(db, company_id=company.id, conversation_id=conv.id,
                                  direction="outbound", sender="ai", content=msg)
            sent += 1
        else:
            failed += 1
            last_error = err or last_error
        crud.mark_reminder_sent(db, r.id)
    logger.info("Recordatorios (todas las empresas): %d enviados, %d fallidos (%s)", sent, failed, last_error)
    return {"status": "ok", "sent": sent, "failed": failed, "error": last_error}


# ── API: Campañas de Marketing ─────────────────────────────────────────────────

def _segment_customers(db: Session, company_id: int, segment: str) -> list:
    from app.db.models import Order
    customers = db.query(Customer).filter(Customer.company_id == company_id).all()
    paid_counts: dict[int, int] = {}
    for o in db.query(Order).filter(Order.company_id == company_id, Order.status == "paid").all():
        paid_counts[o.customer_id] = paid_counts.get(o.customer_id, 0) + 1
    if segment == "con_compra":
        return [c for c in customers if paid_counts.get(c.id, 0) >= 1]
    if segment == "sin_compra":
        return [c for c in customers if paid_counts.get(c.id, 0) == 0]
    if segment == "recurrentes":
        return [c for c in customers if paid_counts.get(c.id, 0) >= 2]
    return customers


@router.get("/api/campaign/audiences")
def api_campaign_audiences(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    segs = ["all", "con_compra", "sin_compra", "recurrentes"]
    result = {}
    for s in segs:
        cs = _segment_customers(db, company.id, s)
        result[s] = {"total": len(cs), "con_email": sum(1 for c in cs if c.email)}
    return result


@router.post("/api/campaign/send")
async def api_campaign_send(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    channel = body.get("channel", "email")
    segment = body.get("segment", "all")
    subject = (body.get("subject") or "").strip()
    message = (body.get("body") or "").strip()
    if not message and channel != "whatsapp_template":
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    customers = _segment_customers(db, company.id, segment)
    sent, failed = 0, 0
    last_error = ""
    creds = _creds_for(company)

    if channel == "email":
        from app.email_service import send_marketing_email
        for c in customers:
            if not c.email:
                continue
            ok = send_marketing_email(company.id, c.email, subject or company.name, message)
            if ok:
                sent += 1
            else:
                failed += 1
                last_error = "no se pudo enviar el email (revisa la API key de Resend)"
    elif channel == "whatsapp_template":
        from app.whatsapp.client import send_template_message
        template_name = (body.get("template_name") or "").strip()
        template_lang = (body.get("template_lang") or "es").strip()
        if not template_name:
            raise HTTPException(status_code=400, detail="Falta el nombre de la plantilla aprobada")
        for c in customers:
            nombre = (c.name or "").split()[0] if c.name else "🌿"
            ok, err = await send_template_message(creds, c.phone_number, template_name,
                                                  body_params=[nombre], language=template_lang)
            if ok:
                sent += 1
            else:
                failed += 1
                last_error = err or last_error
    else:  # whatsapp (texto libre, solo dentro de la ventana de 24h)
        from app.whatsapp.client import send_text_with_result
        for c in customers:
            nombre = (c.name or "").split()[0] if c.name else ""
            text = message.replace("{nombre}", nombre)
            ok, err = await send_text_with_result(creds, c.phone_number, text)
            if ok:
                sent += 1
            else:
                failed += 1
                last_error = err or last_error

    logger.info("Campaña %s/%s (empresa %d): %d enviados, %d fallidos (%s)",
                channel, segment, company.id, sent, failed, last_error)
    return {"status": "ok", "sent": sent, "failed": failed, "error": last_error}


# ── API: Etiquetas de Clientes ─────────────────────────────────────────────────

@router.get("/api/tags")
def api_list_tags(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return [t for t in crud.list_all_tags(db, company.id) if not t["tag"].startswith("seg:")]


@router.get("/api/customers/{phone}/tags")
def api_customer_tags(phone: str, token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    customer = crud.get_or_create_customer(db, company.id, phone)
    return [{"tag": t.tag, "color": t.color} for t in crud.get_customer_tags(db, customer.id)
            if not t.tag.startswith("seg:")]


@router.get("/api/segments")
def api_segments(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, token)
    return crud.list_segmented_customers(db, company.id)


class TagRequest(BaseModel):
    tag: str
    color: str = "p"


@router.post("/api/customers/{phone}/tags")
def api_add_tag(phone: str, body: TagRequest, token: str = Query(default=""),
                authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    customer = crud.get_or_create_customer(db, company.id, phone)
    crud.add_customer_tag(db, company.id, customer.id, body.tag, body.color)
    return {"status": "ok"}


@router.delete("/api/customers/{phone}/tags/{tag}")
def api_remove_tag(phone: str, tag: str, token: str = Query(default=""),
                   authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    customer = crud.get_or_create_customer(db, company.id, phone)
    crud.remove_customer_tag(db, customer.id, tag)
    return {"status": "ok"}


# ── API: Conversación — cerrar / archivar / borrar ─────────────────────────────

@router.post("/conversations/{conversation_id}/close")
async def close_conv(conversation_id: int, token: str = Query(default=""),
                     authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    crud.close_conversation(db, conversation_id)
    return {"status": "closed"}


@router.post("/conversations/{conversation_id}/archive")
async def archive_conv(conversation_id: int, body: dict | None = None,
                       token: str = Query(default=""), authorization: str = Header(default=""),
                       db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    archived = True if body is None else bool(body.get("archived", True))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    crud.archive_conversation(db, conversation_id, archived=archived)
    return {"status": "archived" if archived else "open"}


@router.post("/conversations/{conversation_id}/delete")
async def delete_conv(conversation_id: int, token: str = Query(default=""),
                      authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    ok = crud.delete_conversation(db, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"status": "deleted"}


@router.post("/conversations/{conversation_id}/set_mode")
async def set_conversation_mode(conversation_id: int, body: dict, token: str = Query(default=""),
                                authorization: str = Header(default=""), db: Session = Depends(get_db)):
    company = _require_company(db, _auth(token, authorization))
    mode = body.get("mode")
    if mode not in ("ai", "human"):
        raise HTTPException(status_code=400, detail="mode debe ser 'ai' o 'human'")
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    previous_mode = conv.mode
    crud.set_conversation_mode(db, conversation_id, mode, reason=body.get("reason"),
                               assigned_to=body.get("advisor_name"))
    if mode == "ai" and previous_mode == "human":
        crud.close_advisor_session(db, conversation_id, handback_reason=body.get("reason"))
        logger.info("Conversación %d devuelta a IA (silencioso).", conversation_id)
    if mode == "human" and previous_mode == "ai":
        crud.create_advisor_session(db, company.id, conversation_id, advisor_name=body.get("advisor_name"))
    return {"conversation_id": conversation_id, "mode": mode, "previous_mode": previous_mode}


@router.post("/conversations/{conversation_id}/send_message")
async def send_advisor_message(conversation_id: int, body: dict, token: str = Query(default=""),
                               authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Send a WhatsApp message as human advisor from the admin panel."""
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
    from app.whatsapp.client import send_text_message
    success = await send_text_message(_creds_for(company), conv.phone_number, text)
    if not success:
        raise HTTPException(status_code=502, detail="Error enviando mensaje por WhatsApp")
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=text)
    return {"status": "sent"}


@router.post("/conversations/{conversation_id}/send_email")
async def send_confirmation_email(conversation_id: int, body: dict, token: str = Query(default=""),
                                  authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Send order confirmation email to the customer."""
    company = _require_company(db, _auth(token, authorization))
    from app.email_service import send_order_confirmation
    to_email = (body.get("to_email") or "").strip()
    success = send_order_confirmation(company.id, to_email, body.get("customer_name", ""),
                                      body.get("order_summary", ""))
    if not success:
        raise HTTPException(status_code=502, detail="Error enviando el correo. Revisa la configuración de Resend.")
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=f"[NOTA INTERNA] Email de confirmación enviado a {to_email}")
    return {"status": "email_sent", "to": to_email}


@router.post("/conversations/{conversation_id}/send_qr")
async def send_qr_manually(conversation_id: int, token: str = Query(default=""),
                          authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Send the configured QR image to the client from the admin panel."""
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    qr = crud.get_qr_config(db, company.id)
    if not qr.get("enabled"):
        raise HTTPException(status_code=400, detail="El QR no está habilitado. Actívalo en ⚙️ Config.")
    media_id = qr.get("media_id", "")
    caption = qr.get("caption", "")
    if not media_id:
        raise HTTPException(status_code=400, detail="No hay imagen QR configurada. Súbela en ⚙️ Config.")
    from app.whatsapp.client import send_image_by_id
    success = await send_image_by_id(_creds_for(company), conv.phone_number, media_id, caption)
    if not success:
        raise HTTPException(status_code=502, detail="No se pudo enviar el QR por WhatsApp")
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content="[QR de pago enviado manualmente por asesor]")
    return {"status": "sent"}


@router.post("/config/qr/upload")
async def upload_qr_image(file: UploadFile = File(...), caption: str = "", enabled: str = "false",
                          token: str = Query(default=""), authorization: str = Header(default=""),
                          db: Session = Depends(get_db)):
    """Upload QR image to WhatsApp and save media_id to the database."""
    import base64
    company = _require_company(db, _auth(token, authorization))
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen (PNG, JPG)")
    image_bytes = await file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")
    from app.whatsapp.client import upload_image_to_whatsapp
    media_id = await upload_image_to_whatsapp(_creds_for(company), image_bytes, file.content_type,
                                              file.filename or "qr.jpg")
    if not media_id:
        raise HTTPException(status_code=502, detail="No se pudo subir la imagen a WhatsApp. Verifica el token de acceso.")
    preview_b64 = base64.b64encode(image_bytes).decode("utf-8")
    crud.save_qr_config(db, company.id, enabled=enabled.lower() in ("true", "1", "on"), media_id=media_id,
                        caption=caption, filename=file.filename or "qr.jpg", preview_b64=preview_b64)
    logger.info("QR imagen subida a WhatsApp y guardada en BD. Media ID: %s", media_id)
    return {"status": "ok", "media_id": media_id}


@router.post("/config/qr")
async def update_qr_config(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Update QR enabled/caption in the database without changing the image."""
    company = _require_company(db, _auth(token, authorization))
    crud.save_qr_config(db, company.id, enabled=bool(body.get("enabled", False)), caption=body.get("caption", ""))
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/upload_and_send")
async def upload_and_send_image(conversation_id: int, file: UploadFile = File(...), token: str = Query(default=""),
                                authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Adjuntar y enviar un archivo (foto, video o documento) al cliente."""
    import uuid
    company = _require_company(db, _auth(token, authorization))
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv or conv.company_id != company.id:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo no puede superar 30MB")
    ctype = (file.content_type or "").lower()
    fname = file.filename or "archivo"
    if ctype.startswith("image/"):
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB (límite de WhatsApp)")
        kind, wa = "image", "image"
    elif ctype.startswith("video/"):
        if len(data) > 16 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="El video no puede superar 16MB (límite de WhatsApp).")
        kind, wa = "video", "video"
    else:
        kind, wa = "document", "document"

    key = f"chat-{uuid.uuid4().hex[:12]}"
    try:
        crud.save_media_blob(db, company.id, key, kind, data, ctype or "application/octet-stream")
    except Exception as exc:
        logger.error("No se pudo guardar el adjunto: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo")

    from app.runtime import public_base
    from app.whatsapp.client import (send_image_by_url, send_image_by_id, send_video_by_url,
                                     send_video_by_id, send_document_by_url, upload_media_to_whatsapp)
    creds = _creds_for(company)
    base = public_base()
    url = f"{base}/media/{company.id}/{key}/{kind}" if base else ""
    sent = False
    if url:
        if wa == "image":
            sent = await send_image_by_url(creds, conv.phone_number, url)
        elif wa == "video":
            sent = await send_video_by_url(creds, conv.phone_number, url)
        else:
            sent = await send_document_by_url(creds, conv.phone_number, url, filename=fname)
    if not sent:
        media_id = await upload_media_to_whatsapp(creds, data, ctype or "application/octet-stream", fname)
        if media_id:
            if wa == "image":
                sent = await send_image_by_id(creds, conv.phone_number, media_id)
            elif wa == "video":
                sent = await send_video_by_id(creds, conv.phone_number, media_id)
    if not sent:
        raise HTTPException(status_code=502, detail="No se pudo enviar el archivo a WhatsApp. Intenta de nuevo.")

    if kind in ("image", "video"):
        record = f"[[MEDIA|{kind}|{key}|{'Imagen' if kind=='image' else 'Video'}]]"
    else:
        record = f"📎 Documento enviado: {fname}"
    crud.save_message(db, company_id=company.id, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=record)
    return {"status": "sent"}


# ── Panel Web Principal (SPA) ───────────────────────────────────────────────────

@router.get("/panel", response_class=HTMLResponse)
async def admin_panel(token: str = Query(default=""), db: Session = Depends(get_db)):
    company = crud.get_company_by_admin_token(db, token)
    if not company:
        return HTMLResponse("<h2>🔒 Acceso denegado</h2>", status_code=401)
    from app.admin.ui import render_panel
    return HTMLResponse(render_panel(token, company.name))


@router.get("/icon-512.png")
def admin_icon():
    path = os.path.join(os.path.dirname(__file__), "static", "icon-512.png")
    try:
        with open(path, "rb") as f:
            return Response(content=f.read(), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        raise HTTPException(status_code=404, detail="Sin ícono")


@router.get("/manifest.webmanifest")
def admin_manifest(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Manifiesto PWA para instalar el panel como app en el celular."""
    company = crud.get_company_by_admin_token(db, token)
    name = company.name if company else "VitaBot"
    icon = "/admin/icon-512.png"
    start = f"/admin/panel?token={token}" if token else "/admin/panel"
    return Response(content=__import__("json").dumps({
        "name": f"{name} — Panel",
        "short_name": name[:12],
        "description": f"Monitorea y atiende el WhatsApp de {name}",
        "start_url": start,
        "scope": "/admin/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0b1020",
        "theme_color": "#0b1020",
        "icons": [
            {"src": icon, "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
            {"src": icon, "sizes": "192x192", "type": "image/png", "purpose": "any"},
        ],
    }), media_type="application/manifest+json")


def _generate_customers_excel(db: Session, company_id: int) -> bytes:
    import json
    from app.db.models import Order

    customers = db.query(Customer).filter(Customer.company_id == company_id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    headers = ["Nombre", "Teléfono", "Cédula", "Email", "Dirección", "Fecha Registro",
              "Productos", "Compras", "Última Compra", "Monto Total"]
    ws.append(headers)

    for customer in customers:
        orders = db.query(Order).filter(Order.customer_id == customer.id, Order.status == "paid").all()
        purchase_count = len(orders)
        last_purchase = max([o.created_at for o in orders], default=None)
        total_amount = sum([o.total or 0 for o in orders]) if orders else 0
        all_products = []
        for order in orders:
            try:
                items = json.loads(order.items_json) if order.items_json else []
                for item in items:
                    all_products.append(f"{item.get('name', 'Producto')} x{item.get('quantity', 1)} und")
            except Exception:
                pass
        ws.append([
            customer.name or "", customer.phone_number or "", customer.cedula or "",
            customer.email or "", customer.address or "",
            customer.created_at.strftime('%d/%m/%Y') if customer.created_at else "",
            ", ".join(all_products), purchase_count,
            last_purchase.strftime('%d/%m/%Y') if last_purchase else "",
            int(total_amount) if total_amount else 0,
        ])

    widths = [20, 15, 15, 25, 30, 15, 40, 12, 15, 15]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(ord('A') + i)].width = w

    excel_bytes = io.BytesIO()
    wb.save(excel_bytes)
    excel_bytes.seek(0)
    return excel_bytes.getvalue()


@router.get("/api/customers/export")
def export_customers_to_excel(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Exportar clientes a Excel y enviarlo por correo (si hay Resend configurado)."""
    company = _require_company(db, token)
    excel_content = _generate_customers_excel(db, company.id)
    filename = f"clientes_{company.slug}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        from app.email_service import send_email_with_attachment
        if company.notification_email:
            send_email_with_attachment(
                company.id, company.notification_email,
                subject=f"📊 Reporte de Clientes - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                body="Adjunto se encuentra el reporte detallado de clientes y su historial de compras.",
                attachment_content=excel_content, attachment_filename=filename,
            )
    except Exception as e:
        logger.error("Error enviando Excel por email: %s", e)
    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )