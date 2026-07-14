import logging
import os
import io
from datetime import datetime
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openpyxl import Workbook
from app.config import settings
from app.db.database import get_db
from app.db import crud
from app.db.models import Customer, Conversation
from app.whatsapp.client import send_text_message, send_image_message, upload_image_to_whatsapp
from app.email_service import send_order_confirmation

_BOT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "bot_config.json")

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_token(token: str):
    if token != settings.admin_token:
        raise HTTPException(status_code=401, detail="Token inválido")


def verify_admin(authorization: str = Header(default="")):
    _check_token(authorization.removeprefix("Bearer ").strip())


# ── JSON API (usada por el panel web via fetch) ────────────────────────────────

def _conv_to_dict(c, db) -> dict:
    last_msg = crud.get_last_message_time(db, c.id)
    msgs = crud.get_recent_messages(db, c.id, limit=6)
    # Ignorar marcadores internos de control para la vista previa
    real = [m for m in msgs if "FOTO_ENVIADA:" not in m.content]
    preview = (real[-1].content[:80] if real else "").replace("[NOTA INTERNA]", "🔒")
    customer = crud.get_or_create_customer(db, c.phone_number)
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


@router.post("/api/seed-conversation")
async def api_seed_conversation(body: dict, token: str = Query(default=""),
                                authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Inserta una conversación DE DEMOSTRACIÓN directamente en la BD (cliente, mensajes,
    segmento y pedido si aplica), sin llamar a Claude ni enviar nada por WhatsApp. Sirve
    para mostrar en el panel ejemplos realistas del comportamiento del bot sin gastar
    tokens ni intentar envíos reales a números que no existen."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    phone = (body.get("phone") or "").strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Falta el número de teléfono")
    turns = body.get("turns") or []

    customer = crud.get_or_create_customer(db, phone)
    fields = {k: body[k] for k in ("name", "city", "cedula", "email", "address") if body.get(k)}
    if fields:
        customer = crud.update_customer(db, phone, **fields)

    conversation = crud.create_new_conversation(db, phone, customer.id)

    for turn in turns:
        role = turn.get("role")
        text = turn.get("text") or ""
        if not text:
            continue
        crud.save_message(
            db, conversation_id=conversation.id,
            direction="inbound" if role == "customer" else "outbound",
            sender="customer" if role == "customer" else "ai",
            content=text,
        )

    segment = body.get("segment")
    if segment:
        crud.set_customer_segment(db, customer.id, segment)

    order = body.get("order")
    if order and order.get("items"):
        crud.create_order(
            db, customer_id=customer.id, conversation_id=conversation.id,
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
    _check_token(token)
    convs = crud.list_all_conversations(db) if filter == "all" else crud.list_open_conversations(db)
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
    """Send an image (by public URL) to the client from the admin panel."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404)
    if not body.image_url.startswith("http"):
        raise HTTPException(status_code=400, detail="La URL de la imagen debe ser pública (https://...)")
    success = await send_image_message(conv.phone_number, body.image_url, body.caption)
    if not success:
        raise HTTPException(status_code=502, detail="Error enviando la imagen por WhatsApp")
    content = f"[Imagen enviada por asesor: {body.image_url}]" + (f" — {body.caption}" if body.caption else "")
    crud.save_message(db, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=content)
    return {"status": "sent"}


@router.get("/api/conversations/{conversation_id}/messages")
def api_get_messages(
    conversation_id: int,
    token: str = Query(default=""),
    since: str = Query(default=""),
    db: Session = Depends(get_db),
):
    _check_token(token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
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
        # Ocultar marcadores internos de control (no son mensajes reales)
        if "FOTO_ENVIADA:" not in m.content
    ]


# ── API: Estadísticas del Dashboard ───────────────────────────────────────────

@router.get("/api/stats")
def api_stats(token: str = Query(default=""), period: str = Query(default="all"),
              start: str = Query(default=""), end: str = Query(default=""),
              db: Session = Depends(get_db)):
    _check_token(token)
    from app.db.models import Order
    from datetime import timedelta

    # Ventana de tiempo seleccionada (día/semana/mes/año/todo) o rango libre (start/end)
    now = datetime.utcnow()
    since = None
    until = None  # cota superior (exclusiva), solo para rango libre
    if start or end:
        # Rango de fechas exactas elegido por el usuario (YYYY-MM-DD)
        try:
            if start:
                since = datetime.strptime(start, "%Y-%m-%d")
            if end:
                until = datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)  # incluye el día final
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
        since = None  # todo

    def _in_period(q):
        if since:
            q = q.filter(Conversation.created_at >= since)
        if until:
            q = q.filter(Conversation.created_at < until)
        return q

    total_convs = _in_period(db.query(Conversation)).count()
    open_convs = db.query(Conversation).filter(Conversation.status == "open").count()
    ai_convs = db.query(Conversation).filter(Conversation.status == "open", Conversation.mode == "ai").count()
    human_convs = db.query(Conversation).filter(Conversation.status == "open", Conversation.mode == "human").count()
    resolved_convs = _in_period(db.query(Conversation).filter(Conversation.status == "resolved")).count()
    total_customers = db.query(Customer).count()

    # Venta cerrada = pedido "paid"; se filtra por la ventana seleccionada
    _orders_q = db.query(Order).filter(Order.status == "paid")
    if since:
        _orders_q = _orders_q.filter(Order.created_at >= since)
    if until:
        _orders_q = _orders_q.filter(Order.created_at < until)
    paid_orders = _orders_q.all()
    convs_with_sale = len(set(o.conversation_id for o in paid_orders))
    ingresos = sum(o.total or 0 for o in paid_orders)
    conversion = round((convs_with_sale / total_convs * 100), 1) if total_convs else 0.0

    # Métricas ejecutivas
    start_day = datetime.combine(now.date(), datetime.min.time())
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ventas_dia = sum(o.total or 0 for o in paid_orders if o.created_at and o.created_at >= start_day)
    ventas_mes = sum(o.total or 0 for o in paid_orders if o.created_at and o.created_at >= start_month)
    num_ventas = len(paid_orders)
    ticket_promedio = int(ingresos / num_ventas) if num_ventas else 0
    # Clientes nuevos en la ventana seleccionada (o este mes si es "todo")
    clientes_nuevos = db.query(Customer).filter(Customer.created_at >= (since or start_month)).count()
    compras_por_cliente: dict[int, int] = {}
    for o in paid_orders:
        compras_por_cliente[o.customer_id] = compras_por_cliente.get(o.customer_id, 0) + 1
    clientes_recurrentes = sum(1 for n in compras_por_cliente.values() if n >= 2)
    valor_prom_cliente = int(ingresos / len(compras_por_cliente)) if compras_por_cliente else 0
    ia_rate = round((resolved_convs / total_convs * 100), 1) if total_convs else 0.0

    # Conversaciones por día (últimos 7 días)
    today = datetime.utcnow().date()
    per_day = []
    dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = (
            db.query(Conversation)
            .filter(Conversation.created_at >= datetime.combine(day, datetime.min.time()),
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
        # Métricas ejecutivas
        "num_ventas": num_ventas,
        "ventas_dia": int(ventas_dia),
        "ventas_mes": int(ventas_mes),
        "ticket_promedio": ticket_promedio,
        "clientes_nuevos": clientes_nuevos,
        "clientes_recurrentes": clientes_recurrentes,
        "valor_promedio_cliente": valor_prom_cliente,
        "comprobantes": crud.receipt_metrics(db),
        "period": period,
    }


@router.get("/api/top-products")
def api_top_products(token: str = Query(default=""), period: str = Query(default="all"),
                     start: str = Query(default=""), end: str = Query(default=""),
                     db: Session = Depends(get_db)):
    """Productos más vendidos en un período: unidades, ingresos estimados, top clientes."""
    _check_token(token)
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

    q = db.query(Order).filter(Order.status == "paid")
    if since:
        q = q.filter(Order.created_at >= since)
    if until:
        q = q.filter(Order.created_at < until)
    orders = q.all()

    # Mapa de precios del catálogo (con overrides del panel) para estimar ingresos
    price_map = {}
    try:
        overrides = crud.get_catalog_overrides(db)
        catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "products.json")
        with open(os.path.abspath(catalog_path), encoding="utf-8") as f:
            for p in _json.load(f).get("products", []):
                ov = overrides.get(p["sku"], {})
                price_map[p["name"].lower()] = ov.get("price_cop") or p.get("price_cop", 0)
    except Exception:
        pass

    def _price(name):
        low = (name or "").lower()
        if low in price_map:
            base = price_map[low]
        else:
            base = next((v for k, v in price_map.items() if k in low or low in k), 0)
        return base

    # Sembrar TODOS los productos del catálogo en 0 para llevar control desde el inicio;
    # a medida que se vendan, van subiendo.
    stats = {}
    try:
        catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "products.json")
        with open(os.path.abspath(catalog_path), encoding="utf-8") as f:
            for p in _json.load(f).get("products", []):
                nm = p["name"]
                stats[nm] = {"name": nm, "units": 0, "orders": 0, "revenue": 0, "customers": {}}
    except Exception:
        pass

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
    _check_token(token)
    import json
    from app.db.models import Order

    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    result = []
    for c in customers:
        # Solo pedidos pagados cuentan como compra / total gastado
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
        # Estado: Recurrente (2+), Nuevo (1), Sin compra (0)
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
    _check_token(token)
    customer_id = None
    if phone:
        c = crud.get_or_create_customer(db, phone)
        customer_id = c.id
    receipts = crud.list_receipts(db, customer_id=customer_id)
    # Mapa de nombres de cliente para mostrar en la categoría de comprobantes
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
    _check_token(token)
    import io, zipfile, base64 as _b64, re as _re
    receipts = crud.list_receipts(db, limit=100000)
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
    from datetime import datetime as _dt
    fname = f"comprobantes_vita_qualitat_{_dt.utcnow().strftime('%Y%m%d')}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ── API: Catálogo multimedia ───────────────────────────────────────────────────

@router.get("/api/product-media")
def api_get_product_media(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    import json as _json
    media = crud.get_product_media(db)
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "products.json")
    products = []
    try:
        with open(os.path.abspath(catalog_path), encoding="utf-8") as f:
            cat = _json.load(f)
        blobs = crud.media_blob_skus(db)  # {(sku, kind)} con archivo en la BD
        for p in cat.get("products", []):
            m = media.get(p["sku"], {})
            has_img = (p["sku"], "image") in blobs or bool(m.get("image_media_id"))
            has_vid = (p["sku"], "video") in blobs or bool(m.get("video_media_id"))
            products.append({
                "sku": p["sku"], "name": p["name"],
                "image_url": m.get("image_url", ""),
                "video_url": m.get("video_url", ""),
                "link": m.get("link", ""),
                "has_image_file": has_img,
                "has_video_file": has_vid,
                # URLs internas para previsualizar el archivo (servido desde la BD)
                "image_preview": (f"/admin/api/product-media/file/{p['sku']}/image?token={token}" if (p["sku"], "image") in blobs else ""),
                "video_preview": (f"/admin/api/product-media/file/{p['sku']}/video?token={token}" if (p["sku"], "video") in blobs else ""),
            })
    except Exception as e:
        logger.error("No se pudo cargar catálogo: %s", e)
    return products


@router.get("/api/product-media/file/{sku}/{kind}")
def api_product_media_file(sku: str, kind: str, token: str = Query(default=""),
                           db: Session = Depends(get_db)):
    """Sirve el archivo guardado en la BD (para previsualizar foto/video en el panel)."""
    _check_token(token)
    data = crud.get_media_blob(db, sku, kind)
    if not data:
        raise HTTPException(status_code=404, detail="Sin archivo")
    content, mime = data
    return Response(content=content, media_type=mime,
                    headers={"Cache-Control": "no-cache"})


@router.get("/media/{sku}/{kind}")
def public_product_media_file(sku: str, kind: str, db: Session = Depends(get_db)):
    """URL PÚBLICA (sin token) del archivo del producto. WhatsApp la descarga
    directamente para enviar la foto/video al cliente, sin depender de media_ids
    que caducan. Solo expone media de catálogo (no es información sensible)."""
    data = crud.get_media_blob(db, sku, kind)
    if not data:
        raise HTTPException(status_code=404, detail="Sin archivo")
    content, mime = data
    return Response(content=content, media_type=mime,
                    headers={"Cache-Control": "public, max-age=86400"})


@router.post("/api/product-media")
async def api_save_product_media(body: dict, token: str = Query(default=""),
                                 authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    # body = { sku: {image_url, video_url, link}, ... } — preserva los media_id ya guardados
    existing = crud.get_product_media(db)
    for sku, vals in body.items():
        cur = existing.get(sku, {})
        cur.update(vals)
        existing[sku] = cur
    crud.save_product_media(db, existing)
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
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

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

    # 1) Guardar el archivo DENTRO de la BD (persiste en el volumen, permite previsualizar
    #    y re-subir a WhatsApp con un media_id fresco cada vez que se envía). Es la clave
    #    para que el envío al cliente NUNCA falle por un media_id caducado.
    try:
        crud.save_media_blob(db, sku, kind, content, ctype)
    except Exception as exc:
        logger.error("No se pudo guardar el media en la BD: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo. Intenta de nuevo.")

    # 2) Subir a WhatsApp para obtener un media_id inicial (envío rápido la primera vez)
    from app.whatsapp.client import upload_media_to_whatsapp
    media_id = await upload_media_to_whatsapp(content, ctype, file.filename or ("media." + ("mp4" if kind == "video" else "jpg")))
    saved = True

    media = crud.get_product_media(db)
    item = media.get(sku, {})
    if kind == "image":
        item["image_media_id"] = media_id or ""
        item["image_mime"] = ctype
    else:
        item["video_media_id"] = media_id or ""
        item["video_mime"] = ctype
    media[sku] = item
    crud.save_product_media(db, media)
    logger.info("Media subido sku=%s kind=%s (BD=%s, wa_id=%s)", sku, kind, saved, bool(media_id))
    return {"status": "ok", "media_id": media_id, "preview": saved}


@router.post("/api/product-media/test-send")
async def api_test_send_product_media(body: dict, token: str = Query(default=""),
                                      authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Envía una prueba REAL de la foto/video de un producto a un número de WhatsApp, para
    diagnosticar desde el panel por qué la Multimedia no le llega a un cliente (en vez de
    fallar en silencio dentro de una conversación real)."""
    import re
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    sku = (body.get("sku") or "").strip()
    kind = (body.get("kind") or "image").strip()
    phone = re.sub(r"[^\d]", "", body.get("phone") or "")
    if not sku or not phone:
        return {"ok": False, "message": "Falta el producto o el número de WhatsApp."}
    from app.whatsapp.media_send import test_send_product_media
    ok, message = await test_send_product_media(db, phone, sku, kind)
    return {"ok": ok, "message": message}


@router.delete("/api/product-media/{sku}/{kind}")
async def api_delete_product_media(
    sku: str, kind: str,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Eliminar la imagen o el video de un producto (archivo en BD + media_id)."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.delete_media_blob(db, sku, kind)
    media = crud.get_product_media(db)
    item = media.get(sku)
    if item:
        if kind == "image":
            item.pop("image_media_id", None)
            item.pop("image_url", None)
            item.pop("image_file", None)
            item.pop("image_mime", None)
        else:
            item.pop("video_media_id", None)
            item.pop("video_url", None)
            item.pop("video_file", None)
            item.pop("video_mime", None)
        media[sku] = item
        crud.save_product_media(db, media)
    return {"status": "ok"}


# ── API: Productos comprados por cliente ───────────────────────────────────────

@router.get("/api/customers/{phone}/orders")
def api_customer_orders(phone: str, token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    import json as _json
    from app.db.models import Order
    customer = crud.get_or_create_customer(db, phone)
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


# ── API: Guías de transportadoras ──────────────────────────────────────────────

def _split_label(notes: str) -> tuple[str, str]:
    """Separa el texto visible de la URL del PDF (guardada como ' ::LABEL::<url>')."""
    notes = notes or ""
    if "::LABEL::" in notes:
        disp, _, lbl = notes.partition("::LABEL::")
        return disp.strip(" ·"), lbl.strip()
    return notes, ""


@router.get("/api/guides")
def api_list_guides(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    out = []
    for g in crud.list_shipping_guides(db):
        disp, label = _split_label(g.notes)
        out.append({
            "id": g.id, "customer_name": g.customer_name or "", "customer_phone": g.customer_phone or "",
            "carrier": g.carrier, "guide_number": g.guide_number, "tracking_link": g.tracking_link or "",
            "label_url": label, "notes": disp,
            "date": g.created_at.strftime("%d/%m/%Y") if g.created_at else "",
        })
    return out


@router.post("/api/guides")
async def api_create_guide(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.create_shipping_guide(
        db,
        customer_name=body.get("customer_name", ""), customer_phone=body.get("customer_phone", ""),
        carrier=body.get("carrier", ""), guide_number=body.get("guide_number", ""),
        tracking_link=body.get("tracking_link", ""), notes=body.get("notes", ""),
    )
    return {"status": "ok"}


@router.delete("/api/guides/{guide_id}")
async def api_delete_guide(guide_id: int, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.delete_shipping_guide(db, guide_id)
    return {"status": "ok"}


@router.get("/api/guides-config")
def api_guides_config(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return {"webhook_secret": crud.get_skydropx_secret(db), "autosend": crud.get_guides_autosend(db)}


@router.post("/api/guides-config")
async def api_save_guides_config(body: dict, token: str = Query(default=""),
                                 authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.set_guides_autosend(db, bool(body.get("autosend")))
    return {"status": "ok"}


@router.post("/api/guides/{guide_id}/send")
async def api_send_guide(guide_id: int, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Enviar la guía al cliente por WhatsApp (envío manual desde el panel)."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    g = crud.get_shipping_guide(db, guide_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guía no encontrada")
    if not g.customer_phone:
        raise HTTPException(status_code=400, detail="Esta guía no tiene teléfono del cliente")
    nombre = (g.customer_name or "").split()[0] if g.customer_name else "🌿"
    tracking = g.tracking_link or f"https://t.17track.net/es#nums={g.guide_number}"
    _, label = _split_label(g.notes)
    msg = (f"¡Hola {nombre}! 🚚 Tu pedido ya está en camino con {g.carrier}.\n"
           f"Número de guía: *{g.guide_number}*\nPuedes rastrearlo aquí: {tracking}")
    ok = await send_text_message(g.customer_phone, msg)
    if not ok:
        raise HTTPException(status_code=502, detail="No se pudo enviar (¿fuera de la ventana de 24h?)")
    if label:
        from app.whatsapp.client import send_document_by_url
        await send_document_by_url(g.customer_phone, label, filename=f"guia_{g.guide_number}.pdf",
                                   caption="Aquí está tu guía de envío 🌿")
    conv = crud.get_open_conversation(db, g.customer_phone)
    if conv:
        crud.save_message(db, conversation_id=conv.id, direction="outbound", sender="ai", content=msg)
    return {"status": "ok"}


# ── API: Contactos (proveedores / distribuidores) ──────────────────────────────

@router.get("/api/contacts")
def api_list_contacts(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return [
        {"id": c.id, "name": c.name, "kind": c.kind, "company": c.company or "",
         "phone": c.phone or "", "email": c.email or "", "city": c.city or "", "notes": c.notes or ""}
        for c in crud.list_contacts(db)
    ]


@router.post("/api/contacts")
async def api_create_contact(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.create_contact(
        db, name=body.get("name", ""), kind=body.get("kind", "proveedor"),
        company=body.get("company", ""), phone=body.get("phone", ""),
        email=body.get("email", ""), city=body.get("city", ""), notes=body.get("notes", ""),
    )
    return {"status": "ok"}


@router.delete("/api/contacts/{contact_id}")
async def api_delete_contact(contact_id: int, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.delete_contact(db, contact_id)
    return {"status": "ok"}


def _normalize_co_phone(phone: str) -> str:
    """Normaliza a formato WhatsApp Colombia (57XXXXXXXXXX)."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if len(digits) == 10 and digits.startswith("3"):
        digits = "57" + digits
    return digits


@router.post("/api/contacts/{contact_id}/chat")
async def api_contact_chat(contact_id: int, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Abre (o crea) una conversación en el panel para chatear con el proveedor/distribuidor
    por WhatsApp a través del número del bot, igual que con un cliente. Queda en modo humano."""
    from app.db.models import Contact
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact or not contact.phone:
        raise HTTPException(status_code=400, detail="Este contacto no tiene teléfono")
    phone = _normalize_co_phone(contact.phone)
    if len(phone) < 10:
        raise HTTPException(status_code=400, detail="Teléfono inválido")
    customer = crud.get_or_create_customer(db, phone)
    if not customer.name:
        crud.update_customer(db, phone, name=contact.name or contact.company or "Contacto")
    conv = crud.get_open_conversation(db, phone) or crud.create_new_conversation(db, phone, customer.id)
    crud.set_conversation_mode(db, conv.id, "human")  # el bot NO responde a proveedores
    return {"conversation_id": conv.id}


# ── Demo / simulación (para ver el bot trabajando en el panel) ─────────────────

@router.post("/api/demo/oncologico")
def api_demo_oncologico(token: str = Query(default=""), authorization: str = Header(default=""),
                        db: Session = Depends(get_db)):
    """Planta en el panel una conversación COMPLETA (generada por el bot real) de un
    cliente oncológico que hace y cierra su compra. Sirve para ver cómo trabaja el bot:
    segmentación, datos del cliente, pedido itemizado y venta cerrada. Es idempotente."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    import json as _json
    path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "demo_oncologico.json")
    with open(os.path.abspath(path), encoding="utf-8") as f:
        demo = _json.load(f)

    phone = demo["customer"]["phone_number"]
    # Idempotente: borra cualquier demo previa de este número y la vuelve a crear limpia
    existing = crud.get_or_create_customer(db, phone)
    crud.reset_customer(db, existing.id)

    cust = crud.get_or_create_customer(db, phone)
    crud.update_customer(db, phone, **{k: v for k, v in demo["customer"].items() if k != "phone_number"})
    conv = crud.get_or_reopen_conversation(db, phone, cust.id)
    for m in demo["messages"]:
        crud.save_message(
            db, conversation_id=conv.id,
            direction="inbound" if m["dir"] == "in" else "outbound",
            sender="customer" if m["dir"] == "in" else "ai", content=m["text"],
        )
    crud.set_customer_segment(db, cust.id, demo["segment"])
    o = demo["order"]
    crud.create_order(db, customer_id=cust.id, conversation_id=conv.id, items=o["items"],
                      total=o["total"], payment_method=o["payment_method"],
                      shipping_city=o.get("shipping_city"), status=o["status"])
    return {"status": "ok", "conversation_id": conv.id, "customer": cust.name,
            "segment": demo["segment"], "order_total": o["total"], "items": len(o["items"])}


# ── Conversación: marcar pago recibido / enviar producto / enviar audio ─────────

@router.post("/conversations/{conversation_id}/mark-payment-received")
async def mark_payment_received_ep(conversation_id: int, token: str = Query(default=""),
                                   authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    order = crud.get_latest_order_for_conversation(db, conversation_id)
    if not order:
        raise HTTPException(status_code=404, detail="No hay pedido en esta conversación")
    crud.mark_payment_received(db, order.id)
    crud.mark_order_paid(db, conversation_id)  # asegura que cuente como venta cobrada
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/send_product")
async def send_product_ep(conversation_id: int, body: dict, token: str = Query(default=""),
                          authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Enviar al cliente (modo humano) la foto/video/link de un producto guardado en configuración."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404)
    sku = body.get("sku", "")
    what = body.get("what", "photo")  # photo | video | link
    media = crud.get_product_media(db).get(sku, {})
    from app.whatsapp.media_send import send_product_photo, send_product_video
    from app.catalog_util import media_marker, product_name
    sent = False
    record = ""
    if what == "photo":
        sent = await send_product_photo(db, conv.phone_number, sku)
        record = media_marker("image", sku)
    elif what == "video":
        sent = await send_product_video(db, conv.phone_number, sku)
        record = media_marker("video", sku)
    elif what == "link" and media.get("link"):
        sent = await send_text_message(conv.phone_number, f"🔗 {product_name(sku)}: {media['link']}")
        record = f"🔗 {product_name(sku)}: {media['link']}"
    if not sent:
        raise HTTPException(status_code=400, detail="Ese producto no tiene ese contenido cargado en Multimedia")
    crud.save_message(db, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=record)
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/messages/{message_id}/delete")
def delete_message_ep(conversation_id: int, message_id: int, token: str = Query(default=""),
                      authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Eliminar un mensaje del historial del panel."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    ok = crud.delete_message(db, conversation_id, message_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return {"status": "ok"}


@router.post("/conversations/{conversation_id}/send_audio")
async def send_audio_ep(conversation_id: int, file: UploadFile = File(...), token: str = Query(default=""),
                        authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Subir y enviar una nota de voz/audio (modo humano)."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404)
    content = await file.read()
    if len(content) > 16 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El audio no puede superar 16MB")
    mime = file.content_type or "audio/ogg"
    # Preparar SIEMPRE como OGG/Opus (lo más fiable como nota de voz de WhatsApp).
    # Si el navegador grabó webm/mp4/etc, se transcodifica con ffmpeg.
    from app.audio_service import convert_to_ogg_opus
    converted = convert_to_ogg_opus(content, mime)
    if not converted:
        logger.error("No se pudo preparar el audio (mime=%s). ¿ffmpeg instalado?", mime)
        raise HTTPException(status_code=502,
                            detail="No se pudo preparar el audio para enviar. Intenta grabarlo de nuevo.")
    content, mime, fname = converted
    import uuid
    from app.runtime import public_base
    from app.whatsapp.client import upload_media_to_whatsapp, send_audio_by_id, send_audio_by_url
    # Preferir URL pública (WhatsApp descarga el OGG): se reproduce bien también en el
    # celular y Business, no solo en WhatsApp Web. Respaldo: media_id.
    key = f"aud-{uuid.uuid4().hex[:12]}"
    try:
        crud.save_media_blob(db, key, "audio", content, "audio/ogg")
    except Exception as exc:
        logger.error("No se pudo guardar el audio: %s", exc)
    base = public_base()
    sent = False
    if base and crud.get_media_blob(db, key, "audio"):
        sent = await send_audio_by_url(conv.phone_number, f"{base}/admin/media/{key}/audio")
    if not sent:
        media_id = await upload_media_to_whatsapp(content, mime, fname)
        if media_id:
            sent = await send_audio_by_id(conv.phone_number, media_id)
    if not sent:
        raise HTTPException(status_code=502, detail="WhatsApp rechazó el audio. Intenta grabarlo de nuevo.")
    crud.save_message(db, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content="[Asesor envió una nota de voz]")
    return {"status": "ok"}


# ── API: Cuentas de pago / Bre-B ───────────────────────────────────────────────

@router.get("/api/payment-config")
def api_get_payment(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return crud.get_payment_config(db)


@router.post("/api/payment-config")
async def api_save_payment(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_payment_config(db, body)
    return {"status": "ok"}


# ── API: Cupones / Descuentos ──────────────────────────────────────────────────

@router.get("/api/coupons")
def api_list_coupons(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return [
        {"code": c.code, "kind": c.kind, "value": c.value, "active": c.active,
         "uses": c.uses, "max_uses": c.max_uses}
        for c in crud.list_coupons(db)
    ]


@router.post("/api/coupons")
async def api_create_coupon(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    code = (body.get("code") or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="El código no puede estar vacío")
    crud.create_coupon(db, code=code, kind=body.get("kind", "percent"),
                       value=int(body.get("value", 0) or 0), max_uses=int(body.get("max_uses", 0) or 0))
    return {"status": "ok"}


@router.delete("/api/coupons/{code}")
async def api_delete_coupon(code: str, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.delete_coupon(db, code)
    return {"status": "ok"}


# ── API: Configuración de Voz (ElevenLabs) ─────────────────────────────────────

@router.get("/api/voice-config")
def api_get_voice(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    cfg = crud.get_voice_config(db)
    cfg["api_key_set"] = bool(settings.elevenlabs_api_key)
    return cfg


@router.post("/api/voice-config")
async def api_save_voice(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_voice_config(db, enabled=bool(body.get("enabled", False)), voice_id=body.get("voice_id", ""))
    return {"status": "ok"}


# ── API: Catálogo (precios / stock editables) ──────────────────────────────────

@router.get("/api/catalog")
def api_get_catalog(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    import json as _json
    overrides = crud.get_catalog_overrides(db)
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "products.json")
    out = []
    try:
        with open(os.path.abspath(catalog_path), encoding="utf-8") as f:
            cat = _json.load(f)
        for p in cat.get("products", []):
            ov = overrides.get(p["sku"], {})
            out.append({
                "sku": p["sku"], "name": p["name"],
                "base_price": p["price_cop"],
                "price_cop": ov.get("price_cop", p["price_cop"]),
                "in_stock": ov.get("in_stock", p["in_stock"]),
            })
    except Exception as e:
        logger.error("No se pudo cargar catálogo: %s", e)
    return out


@router.post("/api/catalog")
async def api_save_catalog(body: dict, token: str = Query(default=""),
                           authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    # body = { sku: {price_cop, in_stock}, ... }
    crud.save_catalog_overrides(db, body)
    return {"status": "ok"}


# ── API: Postventa / Reseñas ───────────────────────────────────────────────────

@router.get("/api/postventa-config")
def api_get_postventa(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return crud.get_postventa_config(db)


@router.post("/api/postventa-config")
async def api_save_postventa(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_postventa_config(db, **body)
    return {"status": "ok"}


# ── Reset / borrado de datos (protegido por clave fija) ────────────────────────
_RESET_PASSWORD = "Juanjo15+"


def _check_reset_password(body: dict) -> None:
    if (body or {}).get("password", "") != _RESET_PASSWORD:
        raise HTTPException(status_code=403, detail="Clave de seguridad incorrecta")


@router.post("/api/reset/all")
async def api_reset_all(body: dict, token: str = Query(default=""),
                        authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    _check_reset_password(body)
    counts = crud.reset_all_customer_data(db)
    logger.warning("RESET TOTAL de datos de clientes ejecutado: %s", counts)
    return {"status": "ok", "deleted": counts}


@router.post("/api/reset/customer")
async def api_reset_customer(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    _check_reset_password(body)
    cid = body.get("customer_id")
    phone = body.get("phone")
    if not cid and phone:
        c = db.query(Customer).filter(Customer.phone_number == phone).first()
        cid = c.id if c else None
    if not cid:
        raise HTTPException(status_code=400, detail="Falta customer_id o phone")
    ok = crud.reset_customer(db, int(cid))
    if not ok:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    logger.warning("Cliente %s borrado por reset", cid)
    return {"status": "ok"}


@router.post("/api/reset/category")
async def api_reset_category(body: dict, token: str = Query(default=""),
                             authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    _check_reset_password(body)
    name = (body.get("category") or "").strip().lower()
    if name not in ("guias", "contactos", "cupones"):
        raise HTTPException(status_code=400, detail="Categoría no válida")
    n = crud.clear_category(db, name)
    logger.warning("Categoría '%s' borrada (%d filas) por reset", name, n)
    return {"status": "ok", "deleted": n}


@router.post("/api/help-chat")
async def api_help_chat(body: dict, token: str = Query(default=""),
                        authorization: str = Header(default="")):
    """Chatbot de AYUDA para el operador del panel. Totalmente independiente del bot
    de clientes: NO toca la base de datos ni envía WhatsApp. Solo responde dudas del panel."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    from app.agent.help_prompt import HELP_SYSTEM_PROMPT
    from app.agent.claude_client import get_ai_response

    raw_msgs = body.get("messages", [])
    # Sanitizar: solo roles válidos y texto, máximo las últimas 12 intervenciones
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


@router.get("/api/bot-paused")
def api_get_bot_paused(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return {"paused": crud.get_bot_paused(db)}


@router.post("/api/bot-paused")
async def api_set_bot_paused(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.set_bot_paused(db, bool(body.get("paused")))
    return {"status": "ok", "paused": crud.get_bot_paused(db)}


@router.get("/api/notif-config")
def api_get_notif(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return crud.get_notif_config(db)


@router.post("/api/notif-config")
async def api_save_notif(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_notif_config(db, body)
    return {"status": "ok"}


@router.post("/api/notif-test")
async def api_notif_test(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    """Guarda la config actual y envía un correo de prueba a los destinatarios configurados,
    devolviendo el resultado real (para diagnosticar por qué no llegan)."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    if body:
        crud.save_notif_config(db, body)
    cfg = crud.get_notif_config(db)
    from app.email_service import send_test_email
    raw = (cfg.get("email") or "").strip() or settings.notification_email or ""
    destinatarios = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
    if not destinatarios:
        return {"ok": False, "message": "No hay ningún correo configurado para recibir avisos."}
    ok, msg = False, ""
    for email in destinatarios:
        ok, msg = send_test_email(email)
        if not ok:
            return {"ok": False, "message": f"{email}: {msg}"}
    return {"ok": True, "message": f"Correo de prueba enviado a: {', '.join(destinatarios)}"}


@router.get("/api/smtp-netcheck")
def api_smtp_netcheck(token: str = Query(default="")):
    """Prueba conectividad TCP cruda (sin SMTP) a distintos puertos de salida, para
    saber si el servidor bloquea puertos de correo salientes (muy común en PaaS)."""
    import socket
    _check_token(token)
    targets = [("smtp.gmail.com", 587), ("smtp.gmail.com", 465), ("smtp.gmail.com", 25),
               ("8.8.8.8", 443)]
    results = {}
    for host, port in targets:
        try:
            with socket.create_connection((host, port), timeout=5):
                results[f"{host}:{port}"] = "ok"
        except Exception as exc:
            results[f"{host}:{port}"] = f"error: {exc}"
    return results


@router.get("/api/smtp-debug")
def api_smtp_debug(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Diagnóstico SIN exponer secretos: qué host/puerto se usaría y de dónde saldrían
    las credenciales (variables de entorno vs. panel), para entender errores de envío."""
    _check_token(token)
    from app.email_service import _effective_smtp
    user, pw, host, port = _effective_smtp()
    cfg = crud.get_notif_config(db)
    return {
        "host": host,
        "port": port,
        "env_user_set": bool((settings.email_user or "").strip()),
        "env_password_set": bool((settings.email_password or "").strip()),
        "panel_smtp_user_set": bool((cfg.get("smtp_user") or "").strip()),
        "panel_smtp_pass_set": bool((cfg.get("smtp_pass") or "").strip()),
        "effective_user_set": bool(user),
        "effective_password_set": bool(pw),
    }


@router.get("/api/quick-replies")
def api_get_quick_replies(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return crud.get_quick_replies(db)


@router.post("/api/quick-replies")
async def api_save_quick_replies(body: dict, token: str = Query(default=""),
                                 authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_quick_replies(db, body.get("items", []))
    return {"status": "ok"}


@router.get("/api/bot-name")
def api_get_bot_name(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return {"name": crud.get_bot_name(db)}


@router.post("/api/bot-name")
async def api_save_bot_name(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_bot_name(db, body.get("name", ""))
    return {"status": "ok", "name": crud.get_bot_name(db)}


@router.get("/api/training-config")
def api_get_training(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return {"notes": crud.get_training_notes(db)}


@router.post("/api/training-config")
async def api_save_training(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_training_notes(db, body.get("notes", ""))
    return {"status": "ok"}


@router.get("/api/promo-config")
def api_get_promo(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return crud.get_promo_config(db)


@router.post("/api/promo-config")
async def api_save_promo(body: dict, token: str = Query(default=""),
                         authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_promo_config(db, **body)
    return {"status": "ok"}


@router.post("/tasks/run-followups")
async def run_followups(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Enviar seguimiento postventa a clientes con compra pagada hace N días.
    Pensado para llamarse desde un cron (Railway) o manualmente."""
    _check_token(token)
    cfg = crud.get_postventa_config(db)
    if not cfg.get("enabled"):
        return {"status": "disabled", "sent": 0}
    pendientes = crud.orders_pending_followup(db, cfg.get("days_after", 3))
    template_name = (cfg.get("template_name") or "").strip()
    template_lang = (cfg.get("template_lang") or "es").strip()
    sent, failed, last_error = 0, 0, ""
    for order in pendientes:
        customer = db.query(Customer).filter(Customer.id == order.customer_id).first()
        if not customer:
            continue
        nombre = (customer.name or "").split()[0] if customer.name else "🌿"
        msg = cfg["message"].replace("{nombre}", nombre)
        if template_name:
            # Plantilla aprobada por Meta: llega aunque hayan pasado las 24h.
            from app.whatsapp.client import send_template_message
            ok, err = await send_template_message(
                customer.phone_number, template_name, body_params=[nombre],
                language=template_lang,
            )
        else:
            # Texto libre: solo llega si el cliente escribió en las últimas 24h.
            ok = await send_text_message(customer.phone_number, msg)
            err = "" if ok else "fuera de la ventana de 24h (configura una plantilla de Meta)"
        if ok:
            conv = crud.get_open_conversation(db, customer.phone_number)
            if conv:
                crud.save_message(db, conversation_id=conv.id, direction="outbound",
                                  sender="ai", content=msg)
            crud.mark_followup(db, order.id, customer.id, kind="postventa")
            sent += 1
        else:
            failed += 1
            last_error = err or last_error
    logger.info("Postventa: %d enviados, %d fallidos (%s)", sent, failed, last_error)
    return {"status": "ok", "sent": sent, "failed": failed, "error": last_error}


@router.post("/tasks/run-reminders")
async def run_reminders(token: str = Query(default=""), db: Session = Depends(get_db)):
    """Enviar recordatorios a clientes que dijeron que volverían y no lo hicieron.
    Pensado para un cron (cada hora/día) en Railway."""
    _check_token(token)
    from app.whatsapp.client import send_template_message
    cfg = crud.get_postventa_config(db)
    recon_template = (cfg.get("recontacto_template") or "").strip()
    pendientes = crud.due_reminders(db)
    sent, failed, last_error = 0, 0, ""
    for r in pendientes:
        customer = db.query(Customer).filter(Customer.id == r.customer_id).first()
        if not customer:
            crud.mark_reminder_sent(db, r.id)
            continue
        nombre = (customer.name or "").split()[0] if customer.name else "🌿"
        motivo = (r.note or "").strip()
        msg = (f"Hola *{nombre}* 🌿 Te escribo para recordarte lo que tenías pendiente"
               + (f": {motivo}." if motivo else ".")
               + " ¿Te ayudo a continuar? 💚")
        if recon_template:
            ok, err = await send_template_message(customer.phone_number, recon_template,
                                                  body_params=[nombre], language="es")
        else:
            ok = await send_text_message(customer.phone_number, msg)
            err = "" if ok else "fuera de la ventana de 24h (configura una plantilla de recordatorio)"
        if ok:
            conv = crud.get_open_conversation(db, customer.phone_number)
            if conv:
                crud.save_message(db, conversation_id=conv.id, direction="outbound",
                                  sender="ai", content=msg)
            sent += 1
        else:
            failed += 1
            last_error = err or last_error
        crud.mark_reminder_sent(db, r.id)  # marcar siempre para no reintentar en bucle
    logger.info("Recordatorios: %d enviados, %d fallidos (%s)", sent, failed, last_error)
    return {"status": "ok", "sent": sent, "failed": failed, "error": last_error}


# ── API: Campañas de Marketing ─────────────────────────────────────────────────

def _segment_customers(db: Session, segment: str) -> list:
    """Devuelve clientes según el segmento."""
    from app.db.models import Order
    customers = db.query(Customer).all()
    paid_counts: dict[int, int] = {}
    for o in db.query(Order).filter(Order.status == "paid").all():
        paid_counts[o.customer_id] = paid_counts.get(o.customer_id, 0) + 1
    if segment == "con_compra":
        return [c for c in customers if paid_counts.get(c.id, 0) >= 1]
    if segment == "sin_compra":
        return [c for c in customers if paid_counts.get(c.id, 0) == 0]
    if segment == "recurrentes":
        return [c for c in customers if paid_counts.get(c.id, 0) >= 2]
    return customers  # all


@router.get("/api/campaign/audiences")
def api_campaign_audiences(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    segs = ["all", "con_compra", "sin_compra", "recurrentes"]
    result = {}
    for s in segs:
        cs = _segment_customers(db, s)
        result[s] = {
            "total": len(cs),
            "con_email": sum(1 for c in cs if c.email),
        }
    return result


@router.post("/api/campaign/send")
async def api_campaign_send(body: dict, token: str = Query(default=""),
                            authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    channel = body.get("channel", "email")     # 'email' | 'whatsapp'
    segment = body.get("segment", "all")
    subject = (body.get("subject") or "").strip()
    message = (body.get("body") or "").strip()
    if not message and channel != "whatsapp_template":
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    customers = _segment_customers(db, segment)
    sent, failed = 0, 0
    last_error = ""

    if channel == "email":
        from app.email_service import send_marketing_email
        for c in customers:
            if not c.email:
                continue
            ok = send_marketing_email(c.email, subject or "Vita Qualitat 🌿", message)
            if ok:
                sent += 1
            else:
                failed += 1
                last_error = "no se pudo enviar el email (revisa EMAIL_USER/EMAIL_PASSWORD en Railway)"
    elif channel == "whatsapp_template":
        # Marketing por PLANTILLA aprobada: llega aunque el cliente no haya escrito en 24h.
        from app.whatsapp.client import send_template_message
        template_name = (body.get("template_name") or "").strip()
        template_lang = (body.get("template_lang") or "es").strip()
        if not template_name:
            raise HTTPException(status_code=400, detail="Falta el nombre de la plantilla aprobada")
        for c in customers:
            nombre = (c.name or "").split()[0] if c.name else "🌿"
            ok, err = await send_template_message(
                c.phone_number, template_name, body_params=[nombre], language=template_lang,
            )
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
            ok, err = await send_text_with_result(c.phone_number, text)
            if ok:
                sent += 1
            else:
                failed += 1
                last_error = err or last_error

    logger.info("Campaña %s/%s: %d enviados, %d fallidos (%s)", channel, segment, sent, failed, last_error)
    return {"status": "ok", "sent": sent, "failed": failed, "error": last_error}


# ── API: Etiquetas de Clientes ─────────────────────────────────────────────────

@router.get("/api/tags")
def api_list_tags(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    # Ocultar las etiquetas internas de segmentación (seg:*); tienen su propia categoría
    return [t for t in crud.list_all_tags(db) if not t["tag"].startswith("seg:")]


@router.get("/api/customers/{phone}/tags")
def api_customer_tags(phone: str, token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    customer = crud.get_or_create_customer(db, phone)
    return [{"tag": t.tag, "color": t.color} for t in crud.get_customer_tags(db, customer.id)
            if not t.tag.startswith("seg:")]


@router.get("/api/segments")
def api_segments(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    return crud.list_segmented_customers(db)


class TagRequest(BaseModel):
    tag: str
    color: str = "p"


@router.post("/api/customers/{phone}/tags")
def api_add_tag(phone: str, body: TagRequest, token: str = Query(default=""),
                authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    customer = crud.get_or_create_customer(db, phone)
    crud.add_customer_tag(db, customer.id, body.tag, body.color)
    return {"status": "ok"}


@router.delete("/api/customers/{phone}/tags/{tag}")
def api_remove_tag(phone: str, tag: str, token: str = Query(default=""),
                   authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    customer = crud.get_or_create_customer(db, phone)
    crud.remove_customer_tag(db, customer.id, tag)
    return {"status": "ok"}


# ── API: Cerrar Conversación ───────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/close")
async def close_conv(
    conversation_id: int,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    crud.close_conversation(db, conversation_id)
    return {"status": "closed"}


@router.post("/conversations/{conversation_id}/archive")
async def archive_conv(conversation_id: int, body: dict | None = None,
                       token: str = Query(default=""), authorization: str = Header(default=""),
                       db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    archived = True if body is None else bool(body.get("archived", True))
    conv = crud.archive_conversation(db, conversation_id, archived=archived)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"status": "archived" if archived else "open"}


@router.post("/conversations/{conversation_id}/delete")
async def delete_conv(conversation_id: int, token: str = Query(default=""),
                      authorization: str = Header(default=""), db: Session = Depends(get_db)):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    ok = crud.delete_conversation(db, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"status": "deleted"}


# ── Panel Web Principal (SPA rediseñada) ───────────────────────────────────────

@router.get("/panel", response_class=HTMLResponse)
async def admin_panel(token: str = Query(default="")):
    if token != settings.admin_token:
        return HTMLResponse("<h2>🔒 Acceso denegado</h2>", status_code=401)
    from app.admin.ui import render_panel
    return HTMLResponse(render_panel(token))


@router.get("/icon-512.png")
def admin_icon():
    """Ícono del panel (para la pestaña y la app instalada en el celular)."""
    path = os.path.join(os.path.dirname(__file__), "static", "icon-512.png")
    try:
        with open(path, "rb") as f:
            return Response(content=f.read(), media_type="image/png",
                            headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        raise HTTPException(status_code=404, detail="Sin ícono")


@router.get("/manifest.webmanifest")
def admin_manifest(token: str = Query(default="")):
    """Manifiesto PWA para instalar el panel como app en el celular."""
    icon = f"/admin/icon-512.png"
    start = f"/admin/panel?token={token}" if token else "/admin/panel"
    return Response(content=__import__("json").dumps({
        "name": "Vita Qualitat — Panel",
        "short_name": "VitaPanel",
        "description": "Monitorea y atiende tu WhatsApp de Vita Qualitat",
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


@router.get("/_panel_old", response_class=HTMLResponse)
async def admin_panel_old(token: str = Query(default="")):
    if token != settings.admin_token:
        return HTMLResponse("<h2>🔒 Acceso denegado</h2>", status_code=401)

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vita Qualitat — Panel</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%); min-height: 100vh; }}
  .topbar {{ background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
             padding: 18px 28px; display: flex; align-items: center;
             justify-content: space-between; box-shadow: 0 4px 20px rgba(22, 163, 74, 0.25),
                                                          0 2px 8px rgba(0,0,0,0.1); }}
  .topbar-left {{ display: flex; align-items: center; gap: 14px; }}
  .logo {{ width: 40px; height: 40px; background: white; border-radius: 12px;
           display: flex; align-items: center; justify-content: center;
           font-size: 22px; font-weight: 900; color: #16a34a; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
  .topbar h1 {{ color: white; font-size: 20px; font-weight: 700; letter-spacing: -.5px; text-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
  .topbar p {{ color: rgba(255,255,255,0.85); font-size: 12px; margin-top: 2px; }}
  .live-dot {{ width: 8px; height: 8px; background: #86efac; border-radius: 50%;
               animation: pulse 2s infinite; display: inline-block; margin-right: 6px; box-shadow: 0 0 10px #86efac; }}
  @keyframes pulse {{ 0%,100% {{ opacity:1 }} 50% {{ opacity:.4 }} }}
  .stats {{ display: flex; gap: 14px; padding: 20px 28px; flex-wrap: wrap; }}
  .stat {{ background: white; border-radius: 14px; padding: 18px 24px;
           box-shadow: 0 2px 8px rgba(0,0,0,0.06); flex: 1; min-width: 130px;
           border-top: 3px solid #16a34a; }}
  .stat-num {{ font-size: 32px; font-weight: 800; color: #15803d; }}
  .stat-label {{ font-size: 12px; color: #9ca3af; margin-top: 6px; font-weight: 600; }}
  .container {{ padding: 0 28px 28px; max-width: 1400px; margin: 0 auto; }}
  .section-title {{ font-size: 11px; font-weight: 700; color: #9ca3af;
                    text-transform: uppercase; letter-spacing: .1em;
                    margin-bottom: 12px; }}
  .conv-list {{ display: flex; flex-direction: column; gap: 10px; }}
  .conv-card {{ background: white; border-radius: 16px; padding: 18px 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06); cursor: pointer;
                border-left: 4px solid #d1fae5; transition: all .25s cubic-bezier(0.4, 0, 0.2, 1);
                display: flex; align-items: center; gap: 16px; }}
  .conv-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(22, 163, 74, 0.15); border-left-color: #16a34a; }}
  .conv-card.human {{ border-left-color: #f59e0b; }}
  .conv-card.human:hover {{ border-left-color: #f59e0b; box-shadow: 0 8px 24px rgba(245, 158, 11, 0.15); }}
  .avatar {{ width: 48px; height: 48px; border-radius: 12px; background: #dcfce7;
             display: flex; align-items: center; justify-content: center;
             font-size: 20px; flex-shrink: 0; font-weight: 600; }}
  .avatar.human {{ background: #fef3c7; }}
  .conv-info {{ flex: 1; min-width: 0; }}
  .conv-phone {{ font-weight: 700; font-size: 15px; color: #111827; }}
  .conv-preview {{ font-size: 13px; color: #9ca3af; white-space: nowrap;
                   overflow: hidden; text-overflow: ellipsis; margin-top: 4px; }}
  .conv-meta {{ text-align: right; flex-shrink: 0; }}
  .badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px;
            border-radius: 20px; font-size: 11px; font-weight: 700; }}
  .badge.ai {{ background: #dcfce7; color: #15803d; }}
  .badge.human {{ background: #fef3c7; color: #92400e; }}
  .conv-time {{ font-size: 11px; color: #d1d5db; margin-top: 6px; font-weight: 500; }}
  .empty {{ text-align: center; padding: 80px 20px; color: #9ca3af; }}
  .empty-icon {{ font-size: 56px; margin-bottom: 16px; }}
  .empty-text {{ font-size: 16px; font-weight: 500; color: #6b7280; }}
  .toast {{ position: fixed; bottom: 20px; right: 20px; background: #16a34a;
            color: white; padding: 14px 20px; border-radius: 12px; font-size: 14px; font-weight: 500;
            display: none; box-shadow: 0 8px 24px rgba(22, 163, 74, 0.3); z-index: 100; }}
  @media (max-width: 600px) {{
    .stats {{ padding: 16px 20px; gap: 10px; }}
    .container {{ padding: 0 16px 20px; }}
    .topbar {{ padding: 14px 20px; }}
    .topbar h1 {{ font-size: 18px; }}
    .logo {{ width: 36px; height: 36px; font-size: 18px; }}
  }}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-left">
    <div class="logo">Q</div>
    <div>
      <h1>Vita Qualitat</h1>
      <p><span class="live-dot"></span>Panel en vivo</p>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <div style="color:rgba(255,255,255,0.9);font-size:13px" id="last-update"></div>
    <button id="btn-excel-panel" onclick="downloadExcelPanel()"
      style="background:#3b82f6;color:white;border:none;padding:8px 14px;border-radius:18px;
             font-size:13px;font-weight:600;cursor:pointer;text-decoration:none">📊 Excel</button>
    <a href="/admin/config?token={token}"
       style="color:white;font-size:13px;text-decoration:none;background:rgba(255,255,255,0.15);
              padding:6px 12px;border-radius:16px">⚙️ Config</a>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="stat-num" id="stat-total">—</div><div class="stat-label">Activas</div></div>
  <div class="stat"><div class="stat-num" id="stat-ai" style="color:#16a34a">—</div><div class="stat-label">Modo IA</div></div>
  <div class="stat"><div class="stat-num" id="stat-human" style="color:#d97706">—</div><div class="stat-label">Humano</div></div>
</div>

<div class="container">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px">
    <div class="section-title" style="margin:0">Conversaciones</div>
    <div style="display:flex;gap:6px;align-items:center">
      <button onclick="setFilter('open')" id="btn-open"
        style="font-size:12px;padding:6px 12px;border-radius:16px;border:none;cursor:pointer;
               font-weight:600;background:#16a34a;color:white;white-space:nowrap">Activas</button>
      <button onclick="setFilter('all')" id="btn-all"
        style="font-size:12px;padding:6px 12px;border-radius:16px;border:1px solid #d1d5db;
               cursor:pointer;font-weight:600;background:white;color:#374151;white-space:nowrap">Todas</button>
    </div>
  </div>
  <div class="conv-list" id="conv-list">
    <div class="empty"><div class="empty-icon">💬</div>Cargando conversaciones...</div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const TOKEN = '{token}';
let knownIds = new Set();
let firstLoad = true;
let currentFilter = 'open';

function setFilter(f) {{
  currentFilter = f;
  document.getElementById('btn-open').style.background = f === 'open' ? '#16a34a' : 'white';
  document.getElementById('btn-open').style.color = f === 'open' ? 'white' : '#374151';
  document.getElementById('btn-open').style.border = f === 'open' ? 'none' : '1px solid #d1d5db';
  document.getElementById('btn-all').style.background = f === 'all' ? '#16a34a' : 'white';
  document.getElementById('btn-all').style.color = f === 'all' ? 'white' : '#374151';
  document.getElementById('btn-all').style.border = f === 'all' ? 'none' : '1px solid #d1d5db';
  firstLoad = true;
  loadConversations();
}}

function timeAgo(iso) {{
  if (!iso) return '';
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'ahora';
  if (diff < 3600) return Math.floor(diff/60) + 'm';
  if (diff < 86400) return Math.floor(diff/3600) + 'h';
  return Math.floor(diff/86400) + 'd';
}}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.style.display = 'none', 3000);
}}

async function loadConversations() {{
  try {{
    const res = await fetch(`/admin/api/conversations?token=${{TOKEN}}&filter=${{currentFilter}}`);
    if (!res.ok) return;
    const convs = await res.json();

    const open = convs.filter(c => c.status === 'open');
    document.getElementById('stat-total').textContent = open.length;
    document.getElementById('stat-ai').textContent = open.filter(c => c.mode === 'ai').length;
    document.getElementById('stat-human').textContent = open.filter(c => c.mode === 'human').length;
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString('es-CO');

    if (!firstLoad) {{
      convs.forEach(c => {{
        if (!knownIds.has(c.id)) showToast('💬 Nueva conversación: ' + (c.customer_name || c.phone_number));
      }});
    }}
    knownIds = new Set(convs.map(c => c.id));
    firstLoad = false;

    const list = document.getElementById('conv-list');
    if (convs.length === 0) {{
      list.innerHTML = '<div class="empty"><div class="empty-icon">✅</div>Sin conversaciones</div>';
      return;
    }}
    list.innerHTML = convs.map(c => {{
      const isResolved = c.status === 'resolved';
      const displayMode = isResolved ? 'resolved' : c.mode;
      const avatar = isResolved ? '✅' : (c.mode === 'ai' ? '🤖' : '👤');
      const badgeClass = isResolved ? '' : c.mode;
      const badgeText = isResolved ? '✅ Cerrada' : (c.mode === 'ai' ? '🤖 IA' : '👤 Humano');
      const badgeBg = isResolved ? '#f3f4f6' : '';
      const name = c.customer_name || ('+' + c.phone_number);
      return `
      <div class="conv-card ${{isResolved ? '' : c.mode}}"
           style="${{isResolved ? 'opacity:.65;border-left-color:#e5e7eb' : ''}}"
           onclick="openConv(${{c.id}})">
        <div class="avatar ${{isResolved ? '' : c.mode}}">${{avatar}}</div>
        <div class="conv-info">
          <div class="conv-phone">${{name}}</div>
          <div style="font-size:11px;color:#9ca3af">+${{c.phone_number}}</div>
          <div class="conv-preview">${{c.last_message_preview || 'Sin mensajes'}}</div>
        </div>
        <div class="conv-meta">
          <div><span class="badge ${{badgeClass}}" style="${{badgeBg ? 'background:'+badgeBg : ''}}">${{badgeText}}</span></div>
          <div class="conv-time">${{timeAgo(c.last_message_at || c.updated_at)}}</div>
        </div>
      </div>`;
    }}).join('');
  }} catch(e) {{ console.error(e); }}
}}

function openConv(id) {{
  window.location.href = `/admin/conversations/${{id}}?token=${{TOKEN}}`;
}}

function downloadExcelPanel() {{
  const btn = document.getElementById('btn-excel-panel');
  btn.disabled = true;
  btn.textContent = '⏳ Generando...';

  fetch(`/admin/api/customers/export?token=${{TOKEN}}`)
    .then(res => {{
      if (!res.ok) throw new Error('Error descargando Excel');
      return res.blob();
    }})
    .then(blob => {{
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `clientes_vita_qualitat_${{new Date().toISOString().slice(0,10)}}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      alert('✅ Excel descargado. También fue enviado a vitaqualitat@gmail.com');
      btn.disabled = false;
      btn.textContent = '📊 Excel';
    }})
    .catch(err => {{
      alert('Error: ' + err.message);
      btn.disabled = false;
      btn.textContent = '📊 Excel';
    }});
}}

loadConversations();
setInterval(loadConversations, 5000);
</script>
</body></html>""")


# ── Vista de Conversación Individual ──────────────────────────────────────────

@router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
async def view_conversation(
    conversation_id: int,
    token: str = Query(default=""),
    db: Session = Depends(get_db),
):
    _check_token(token)
    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404)

    customer = crud.get_or_create_customer(db, conv.phone_number)

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chat - Conversación {conv.phone_number}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ height: 100%; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f172a; color: #e2e8f0; display: flex; flex-direction: column; height: 100vh; }}

  /* ─────── TOPBAR ─────── */
  .topbar {{ background: linear-gradient(135deg, #1a1f3a 0%, #0f172a 100%); padding: 12px 18px;
             display: flex; align-items: center; justify-content: space-between;
             border-bottom: 1px solid #334155; flex-shrink: 0; gap: 16px; }}
  .topbar-left {{ display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }}
  .topbar-avatar {{ width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
                   display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; }}
  .topbar-info {{ flex: 1; min-width: 0; }}
  .topbar-name {{ font-size: 15px; font-weight: 700; color: #f1f5f9; }}
  .topbar-status {{ font-size: 12px; color: #94a3b8; margin-top: 2px; }}
  .live-dot {{ width: 6px; height: 6px; background: #10b981; border-radius: 50%;
               display: inline-block; animation: pulse 2s infinite; margin-right: 4px; }}
  @keyframes pulse {{ 0%,100%{{opacity:1}}50%{{opacity:.4}} }}
  .topbar-right {{ display: flex; align-items: center; gap: 12px; }}
  .mode-badge {{ font-size: 11px; padding: 4px 10px; border-radius: 16px; font-weight: 600; }}
  .mode-badge.ai {{ background: rgba(196, 181, 253, 0.1); color: #c4b5fd; }}
  .mode-badge.human {{ background: rgba(34, 197, 94, 0.1); color: #86efac; }}
  .icon-btn {{ background: transparent; border: none; color: #94a3b8; cursor: pointer;
               font-size: 18px; transition: all .2s; padding: 6px; }}
  .icon-btn:hover {{ color: #e2e8f0; }}

  /* ─────── LAYOUT MAIN ─────── */
  .main {{ display: flex; flex: 1; min-height: 0; gap: 0; }}

  /* ─────── SIDEBAR ─────── */
  .sidebar {{ width: 280px; background: #1a1f3a; border-right: 1px solid #334155;
              display: flex; flex-direction: column; flex-shrink: 0; }}
  .sidebar-search {{ padding: 12px; border-bottom: 1px solid #334155; }}
  .search-input {{ width: 100%; background: #0f172a; border: 1px solid #334155;
                  border-radius: 8px; padding: 8px 12px; color: #e2e8f0;
                  font-size: 13px; outline: none; }}
  .search-input:focus {{ border-color: #7c3aed; }}
  .search-input::placeholder {{ color: #64748b; }}
  .sidebar-filters {{ padding: 8px; border-bottom: 1px solid #334155; display: flex; gap: 4px; flex-wrap: wrap; }}
  .filter-btn {{ background: transparent; border: 1px solid #334155; color: #94a3b8;
                 padding: 4px 10px; border-radius: 14px; font-size: 11px; cursor: pointer;
                 transition: all .2s; font-weight: 600; }}
  .filter-btn.active {{ border-color: #7c3aed; background: rgba(124, 58, 237, 0.1); color: #c4b5fd; }}
  .conv-list {{ flex: 1; overflow-y: auto; }}
  .conv-item {{ padding: 10px 12px; border-bottom: 1px solid #334155; cursor: pointer;
               transition: all .2s; display: flex; gap: 10px; }}
  .conv-item:hover {{ background: rgba(124, 58, 237, 0.05); }}
  .conv-item.active {{ background: rgba(124, 58, 237, 0.15); border-left: 3px solid #7c3aed; }}
  .conv-avatar {{ width: 40px; height: 40px; border-radius: 50%; background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
                 display: flex; align-items: center; justify-content: center; font-weight: 700; flex-shrink: 0; font-size: 16px; }}
  .conv-content {{ flex: 1; min-width: 0; }}
  .conv-name {{ font-size: 13px; font-weight: 600; color: #f1f5f9; }}
  .conv-msg {{ font-size: 12px; color: #94a3b8; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px; }}
  .conv-time {{ font-size: 11px; color: #64748b; text-align: right; flex-shrink: 0; }}
  .conv-badge {{ display: inline-block; background: #ef4444; color: white; border-radius: 50%;
                width: 18px; height: 18px; text-align: center; line-height: 18px; font-size: 10px; font-weight: 700; }}

  /* ─────── MESSAGES ─────── */
  .chat {{ flex: 1; display: flex; flex-direction: column; min-width: 0; }}
  .messages {{ flex: 1; overflow-y: auto; padding: 20px; display: flex;
               flex-direction: column; gap: 8px; }}
  .msg-group {{ display: flex; animation: fadeIn 0.3s ease-out; }}
  .msg-group.in {{ justify-content: flex-start; }}
  .msg-group.out {{ justify-content: flex-end; }}
  @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  .msg-bubble {{ max-width: 65%; padding: 10px 14px; border-radius: 12px;
                 font-size: 13px; line-height: 1.4; word-break: break-word; }}
  .msg-bubble.customer {{ background: #2d3748; color: #f1f5f9; border-radius: 12px 12px 12px 2px; }}
  .msg-bubble.ai {{ background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); color: white; border-radius: 12px 12px 2px 12px; }}
  .msg-bubble.human {{ background: #3b82f6; color: white; border-radius: 12px 12px 2px 12px; }}
  .msg-bubble.internal {{ background: #7c2d12; color: #fed7aa; border: 1px solid #92400e; border-radius: 12px 12px 2px 12px; }}
  .msg-time {{ font-size: 11px; color: #94a3b8; margin-top: 4px; opacity: 0.7; }}

  /* ─────── INPUT ─────── */
  .chat-actions {{ padding: 12px; border-top: 1px solid #334155; display: flex; gap: 8px; flex-wrap: wrap; flex-shrink: 0; }}
  .action-btn {{ background: transparent; border: 1px solid #334155; color: #94a3b8;
                 padding: 7px 12px; border-radius: 8px; font-size: 12px; cursor: pointer;
                 transition: all .2s; font-weight: 600; }}
  .action-btn:hover {{ border-color: #7c3aed; color: #c4b5fd; }}
  .input-bar {{ padding: 14px; border-top: 1px solid #334155; display: flex; gap: 10px; align-items: flex-end; flex-shrink: 0; }}
  .input-icons {{ display: flex; gap: 6px; align-items: center; }}
  .chat-input {{ flex: 1; background: #1a1f3a; border: 1px solid #334155; border-radius: 20px;
                padding: 10px 16px; color: #e2e8f0; font-size: 13px; resize: none;
                outline: none; max-height: 100px; font-family: inherit; line-height: 1.4;
                transition: border-color .2s; }}
  .chat-input:focus {{ border-color: #7c3aed; }}
  .chat-input::placeholder {{ color: #64748b; }}
  .send-btn {{ background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); color: white;
               border: none; border-radius: 50%; width: 40px; height: 40px; cursor: pointer;
               font-size: 16px; display: flex; align-items: center; justify-content: center;
               flex-shrink: 0; transition: all .2s; }}
  .send-btn:hover {{ transform: scale(1.05); }}
  .send-btn:disabled {{ background: #64748b; cursor: not-allowed; }}

  /* ─────── RIGHT PANEL ─────── */
  .right-panel {{ width: 320px; background: #1a1f3a; border-left: 1px solid #334155;
                 display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto; }}
  .panel-section {{ padding: 16px; border-bottom: 1px solid #334155; }}
  .panel-title {{ font-size: 12px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
                 letter-spacing: 0.05em; margin-bottom: 12px; }}
  .contact-header {{ text-align: center; padding-bottom: 12px; }}
  .contact-avatar {{ width: 56px; height: 56px; border-radius: 50%;
                    background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
                    display: flex; align-items: center; justify-content: center;
                    font-weight: 700; font-size: 22px; margin: 0 auto 10px; }}
  .contact-name {{ font-size: 15px; font-weight: 700; color: #f1f5f9; }}
  .contact-phone {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  .info-row {{ display: flex; justify-content: space-between; margin-bottom: 10px; }}
  .info-label {{ font-size: 12px; color: #94a3b8; }}
  .info-value {{ font-size: 13px; font-weight: 600; color: #f1f5f9; }}
  .tags-list {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .tag {{ background: rgba(124, 58, 237, 0.1); color: #c4b5fd; padding: 5px 10px;
         border-radius: 14px; font-size: 11px; font-weight: 600; border: 1px solid rgba(124, 58, 237, 0.2); }}
  .action-list {{ display: flex; flex-direction: column; gap: 8px; }}
  .action-list-btn {{ background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%); color: white;
                     border: none; padding: 10px 14px; border-radius: 8px; font-size: 12px;
                     font-weight: 600; cursor: pointer; transition: all .2s; }}
  .action-list-btn:hover {{ transform: translateY(-1px); }}
  .action-list-btn.secondary {{ background: transparent; border: 1px solid #334155; color: #94a3b8; }}
  .action-list-btn.secondary:hover {{ border-color: #7c3aed; color: #c4b5fd; }}

  /* ─────── SCROLLBAR ─────── */
  ::-webkit-scrollbar {{ width: 6px; }}
  ::-webkit-scrollbar-track {{ background: transparent; }}
  ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: #475569; }}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <div class="topbar-left">
    <a href="/admin/panel?token={token}" style="color: #7c3aed; text-decoration: none; font-size: 18px; line-height: 1;">←</a>
    <div class="topbar-avatar" id="header-avatar">M</div>
    <div class="topbar-info">
      <div class="topbar-name" id="header-name">+{conv.phone_number}</div>
      <div class="topbar-status"><span class="live-dot"></span> Conectado</div>
    </div>
  </div>
  <div class="topbar-right">
    <div class="mode-badge" id="mode-badge">Cargando...</div>
    <button class="icon-btn" id="star-btn" onclick="toggleStar()">☆</button>
    <button class="icon-btn" onclick="alert('Menú')">⋮</button>
  </div>
</div>

<!-- MAIN LAYOUT -->
<div class="main">

  <!-- SIDEBAR - CONVERSACIONES -->
  <div class="sidebar">
    <div class="sidebar-search">
      <input type="text" class="search-input" placeholder="Buscar conversaciones..." id="search-input">
    </div>
    <div class="sidebar-filters">
      <button class="filter-btn active" onclick="setFilter('all')">Todas</button>
      <button class="filter-btn" onclick="setFilter('unread')">Sin leer</button>
      <button class="filter-btn" onclick="setFilter('ai')">IA</button>
      <button class="filter-btn" onclick="setFilter('human')">Humanos</button>
    </div>
    <div class="conv-list" id="conv-list">
      <div style="padding: 20px; text-align: center; color: #64748b;">Cargando...</div>
    </div>
  </div>

  <!-- CHAT CENTER -->
  <div class="chat">
    <div class="messages" id="messages"></div>

    <div class="chat-actions" id="action-bar">
      <button class="action-btn" onclick="toggleImageForm()">🖼️ Imagen</button>
      <button class="action-btn" onclick="toggleEmailForm()">✉️ Email</button>
      <button class="action-btn" onclick="sendQR()">📱 QR Pago</button>
    </div>

    <div class="input-bar">
      <div class="input-icons">
        <button class="icon-btn" style="font-size:16px">📎</button>
        <button class="icon-btn" style="font-size:16px">😊</button>
      </div>
      <textarea class="chat-input" id="chat-input" rows="1"
        placeholder="Escribe un mensaje..."
        onkeydown="handleKey(event)"
        oninput="autoResize(this)"></textarea>
      <button class="send-btn" id="send-btn" onclick="sendMessage()">➤</button>
    </div>
  </div>

  <!-- RIGHT PANEL - INFO CLIENTE -->
  <div class="right-panel">
    <div class="panel-section">
      <div class="contact-header">
        <div class="contact-avatar" id="contact-avatar">M</div>
        <div class="contact-name" id="contact-name">María González</div>
        <div class="contact-phone" id="contact-phone">+57 300 123 4567</div>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-title">Datos del Cliente</div>
      <div class="info-row">
        <span class="info-label">Cédula</span>
        <span class="info-value" id="info-cedula">—</span>
      </div>
      <div class="info-row">
        <span class="info-label">Email</span>
        <span class="info-value" id="info-email" style="word-break: break-all;">—</span>
      </div>
      <div class="info-row">
        <span class="info-label">Dirección</span>
        <span class="info-value" id="info-address">—</span>
      </div>
      <div class="info-row">
        <span class="info-label">Última Compra</span>
        <span class="info-value" id="info-last-purchase">—</span>
      </div>
      <div class="info-row">
        <span class="info-label">Total Compras</span>
        <span class="info-value" id="info-total-purchases">$0</span>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-title">Etiquetas</div>
      <div class="tags-list" id="tags-list">
        <span class="tag">Interesado</span>
        <span class="tag">Muebles</span>
        <span class="tag">VIP</span>
      </div>
    </div>

    <div class="panel-section">
      <div class="panel-title">Acciones Rápidas</div>
      <div class="action-list">
        <button class="action-list-btn" onclick="toggleMode()" id="mode-btn-panel">Pasar a Humano</button>
        <button class="action-list-btn secondary" onclick="alert('Crear oportunidad')">+ Crear Oportunidad</button>
        <button class="action-list-btn secondary" onclick="alert('Enviar plantilla')">📄 Enviar Plantilla</button>
        <button class="action-list-btn secondary" style="color: #ef4444; border-color: #7f1d1d;" onclick="alert('Cerrar conversación')">❌ Cerrar Conv.</button>
      </div>
    </div>
  </div>

</div>

<!-- MODAL FORMS (hidden) -->
<div id="image-form" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center">
  <div style="background:#1a1f3a;border:1px solid #334155;border-radius:12px;padding:24px;max-width:400px;width:90%">
    <h3 style="color:#f1f5f9;margin-bottom:16px">Enviar Imagen</h3>
    <div onclick="document.getElementById('img-file').click()" style="border:2px dashed #7c3aed;border-radius:10px;padding:24px;text-align:center;cursor:pointer;background:rgba(124,58,237,0.05);margin-bottom:14px">
      <div style="font-size:32px;margin-bottom:8px">🖼️</div>
      <div style="font-size:13px;font-weight:600;color:#c4b5fd">Seleccionar imagen</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:4px">PNG, JPG · Máx 5MB</div>
      <input type="file" id="img-file" accept="image/*" style="display:none" onchange="onImgSelected(this)">
    </div>
    <input type="text" id="img-caption" placeholder="Pie de foto (opcional)" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 12px;color:#e2e8f0;margin-bottom:14px;font-size:12px;outline:none">
    <div style="display:flex;gap:8px">
      <button onclick="sendImage()" id="btn-send-img" style="flex:1;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:white;border:none;border-radius:8px;padding:10px;font-size:13px;font-weight:600;cursor:pointer">Enviar</button>
      <button onclick="toggleImageForm()" style="flex:1;background:#334155;color:#e2e8f0;border:none;border-radius:8px;padding:10px;font-size:13px;cursor:pointer">Cancelar</button>
    </div>
  </div>
</div>

<div id="email-form" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center">
  <div style="background:#1a1f3a;border:1px solid #334155;border-radius:12px;padding:24px;max-width:400px;width:90%">
    <h3 style="color:#f1f5f9;margin-bottom:16px">Enviar Email</h3>
    <input type="email" id="email-to" placeholder="Correo del cliente" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 12px;color:#e2e8f0;margin-bottom:10px;font-size:12px;outline:none">
    <input type="text" id="email-name" placeholder="Nombre del cliente" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 12px;color:#e2e8f0;margin-bottom:10px;font-size:12px;outline:none">
    <input type="text" id="email-summary" placeholder="Resumen del pedido (opcional)" style="width:100%;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:10px 12px;color:#e2e8f0;margin-bottom:14px;font-size:12px;outline:none">
    <div style="display:flex;gap:8px">
      <button onclick="sendEmail()" style="flex:1;background:linear-gradient(135deg,#7c3aed,#6d28d9);color:white;border:none;border-radius:8px;padding:10px;font-size:13px;font-weight:600;cursor:pointer">Enviar</button>
      <button onclick="toggleEmailForm()" style="flex:1;background:#334155;color:#e2e8f0;border:none;border-radius:8px;padding:10px;font-size:13px;cursor:pointer">Cancelar</button>
    </div>
  </div>
</div>

<script>
const TOKEN = '{token}';
const CONV_ID = {conversation_id};
let currentMode = '{conv.mode}';
let lastTimestamp = null;
let messagesDiv = document.getElementById('messages');
let allConversations = [];

function getInitials(name) {{
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
}}

function formatTime(iso) {{
  return new Date(iso).toLocaleTimeString('es-CO', {{hour:'2-digit', minute:'2-digit'}});
}}

function formatDate(iso) {{
  return new Date(iso).toLocaleDateString('es-CO');
}}

function appendMessages(msgs, prepend) {{
  msgs.forEach(m => {{
    const wrap = document.createElement('div');
    const isInbound = m.direction === 'inbound';
    wrap.className = 'msg-group ' + (isInbound ? 'in' : 'out');
    wrap.dataset.id = m.id;

    let bubbleClass = 'msg-bubble customer';
    if (!isInbound) {{
      if (m.is_internal) bubbleClass = 'msg-bubble internal';
      else if (m.sender === 'human_advisor') bubbleClass = 'msg-bubble human';
      else bubbleClass = 'msg-bubble ai';
    }}

    const content = m.content.replace('[NOTA INTERNA]', '').trim();
    wrap.innerHTML = `<div class="${{bubbleClass}}">
      ${{content}}
      <div class="msg-time">${{formatTime(m.timestamp)}}</div>
    </div>`;

    if (prepend) messagesDiv.prepend(wrap);
    else messagesDiv.appendChild(wrap);
    lastTimestamp = m.timestamp;
  }});
}}

function updateModeUI(mode) {{
  currentMode = mode;
  const badge = document.getElementById('mode-badge');
  const btn = document.getElementById('mode-btn-panel');

  badge.className = 'mode-badge ' + mode;
  badge.textContent = mode === 'ai' ? '🤖 IA Respondiendo' : '👤 Humano';
  btn.textContent = mode === 'ai' ? 'Pasar a Humano' : 'Devolver a IA';

  document.getElementById('action-bar').style.display = mode === 'human' ? 'flex' : 'none';
  document.getElementById('chat-input').style.display = mode === 'human' ? 'block' : 'none';
  document.getElementById('send-btn').style.display = mode === 'human' ? 'flex' : 'none';
}}

function autoResize(el) {{
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}}

function handleKey(e) {{
  if (e.key === 'Enter' && !e.shiftKey) {{
    e.preventDefault();
    sendMessage();
  }}
}}

async function sendMessage() {{
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  const btn = document.getElementById('send-btn');
  btn.disabled = true;
  try {{
    const res = await fetch(`/admin/conversations/${{CONV_ID}}/send_message?token=${{TOKEN}}`, {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json', 'Authorization': `Bearer ${{TOKEN}}`}},
      body: JSON.stringify({{ text }})
    }});
    if (res.ok) {{
      input.value = '';
      input.style.height = 'auto';
      await pollNew();
    }}
  }} finally {{
    btn.disabled = false;
    input.focus();
  }}
}}

function toggleImageForm() {{
  document.getElementById('image-form').style.display =
    document.getElementById('image-form').style.display === 'flex' ? 'none' : 'flex';
}}

function toggleEmailForm() {{
  document.getElementById('email-form').style.display =
    document.getElementById('email-form').style.display === 'flex' ? 'none' : 'flex';
}}

function onImgSelected(input) {{
  const file = input.files[0];
  if (file) {{
    const reader = new FileReader();
    reader.onload = e => {{
      // Preview image
    }};
    reader.readAsDataURL(file);
  }}
}}

async function sendImage() {{
  const fileInput = document.getElementById('img-file');
  const caption = document.getElementById('img-caption').value.trim();
  const file = fileInput.files[0];
  if (!file) {{ alert('Selecciona una imagen primero'); return; }}

  const btn = document.querySelector('#image-form button:first-of-type');
  btn.disabled = true;
  btn.textContent = '⏳ Subiendo...';

  try {{
    const form = new FormData();
    form.append('file', file);
    const uploadRes = await fetch(`/admin/conversations/${{CONV_ID}}/upload_and_send?token=${{TOKEN}}`, {{
      method: 'POST',
      headers: {{ 'Authorization': `Bearer ${{TOKEN}}` }},
      body: form
    }});
    if (!uploadRes.ok) {{
      const err = await uploadRes.json();
      alert('Error: ' + (err.detail || 'No se pudo enviar la imagen'));
      return;
    }}
    if (caption) {{
      await fetch(`/admin/conversations/${{CONV_ID}}/send_message?token=${{TOKEN}}`, {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json', 'Authorization': `Bearer ${{TOKEN}}`}},
        body: JSON.stringify({{ text: caption }})
      }});
    }}
    toggleImageForm();
    fileInput.value = '';
    document.getElementById('img-caption').value = '';
    await pollNew();
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Enviar';
  }}
}}

async function sendEmail() {{
  const toEmail = document.getElementById('email-to').value.trim();
  const name = document.getElementById('email-name').value.trim();
  const summary = document.getElementById('email-summary').value.trim();
  if (!toEmail || !name) {{ alert('Ingresa el correo y nombre del cliente'); return; }}
  const res = await fetch(`/admin/conversations/${{CONV_ID}}/send_email?token=${{TOKEN}}`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json', 'Authorization': `Bearer ${{TOKEN}}`}},
    body: JSON.stringify({{ to_email: toEmail, customer_name: name, order_summary: summary }})
  }});
  if (res.ok) {{
    toggleEmailForm();
    document.getElementById('email-to').value = '';
    document.getElementById('email-name').value = '';
    document.getElementById('email-summary').value = '';
    await pollNew();
  }}
}}

async function loadAll() {{
  const res = await fetch(`/admin/api/conversations/${{CONV_ID}}/messages?token=${{TOKEN}}`);
  const msgs = await res.json();
  messagesDiv.innerHTML = '';
  if (msgs.length) appendMessages(msgs, false);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
  updateModeUI(currentMode);

  // Update customer info
  const customerName = '{customer.name or "Cliente"}';
  const customerEmail = '{customer.email or "—"}';
  const customerCedula = '{customer.cedula or "—"}';
  const customerAddress = '{customer.address or "—"}';

  document.getElementById('header-name').textContent = customerName;
  document.getElementById('header-avatar').textContent = getInitials(customerName);
  document.getElementById('contact-avatar').textContent = getInitials(customerName);
  document.getElementById('contact-name').textContent = customerName;
  document.getElementById('contact-phone').textContent = '+{conv.phone_number}';
  document.getElementById('info-cedula').textContent = customerCedula;
  document.getElementById('info-email').textContent = customerEmail;
  document.getElementById('info-address').textContent = customerAddress;
}}

async function pollNew() {{
  if (!lastTimestamp) return;
  try {{
    const res = await fetch(`/admin/api/conversations/${{CONV_ID}}/messages?token=${{TOKEN}}&since=${{encodeURIComponent(lastTimestamp)}}`);
    const msgs = await res.json();
    if (msgs.length) {{
      appendMessages(msgs, false);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }}
  }} catch(e) {{}}
}}

async function sendQR() {{
  if (!confirm('¿Enviar el código QR de pago a este cliente?')) return;
  const res = await fetch(`/admin/conversations/${{CONV_ID}}/send_qr?token=${{TOKEN}}`, {{
    method: 'POST',
    headers: {{ 'Authorization': `Bearer ${{TOKEN}}` }},
  }});
  if (res.ok) {{
    await pollNew();
    alert('✅ QR enviado correctamente');
  }}
}}

async function toggleMode() {{
  const newMode = currentMode === 'ai' ? 'human' : 'ai';
  const res = await fetch(`/admin/conversations/${{CONV_ID}}/set_mode?token=${{TOKEN}}`, {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json', 'Authorization': `Bearer ${{TOKEN}}`}},
    body: JSON.stringify({{ mode: newMode, notify_customer: newMode === 'ai' }})
  }});
  if (res.ok) updateModeUI(newMode);
}}

function toggleStar() {{
  document.getElementById('star-btn').textContent =
    document.getElementById('star-btn').textContent === '☆' ? '★' : '☆';
}}

function setFilter(f) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
}}

loadAll();
setInterval(pollNew, 3000);
</script>
</body></html>""")


# ── Endpoint Cambiar Modo ──────────────────────────────────────────────────────

class SetModeRequest(BaseModel):
    mode: str
    reason: str | None = None
    advisor_name: str | None = None
    notify_customer: bool = True


@router.post("/conversations/{conversation_id}/set_mode")
async def set_conversation_mode(
    conversation_id: int,
    body: SetModeRequest,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    if body.mode not in ("ai", "human"):
        raise HTTPException(status_code=400, detail="mode debe ser 'ai' o 'human'")

    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    previous_mode = conv.mode
    crud.set_conversation_mode(db, conversation_id, body.mode, reason=body.reason, assigned_to=body.advisor_name)

    if body.mode == "ai" and previous_mode == "human":
        crud.close_advisor_session(db, conversation_id, handback_reason=body.reason)
        # No se envía mensaje al cliente — el bot responderá naturalmente en el próximo mensaje
        logger.info("Conversación %d devuelta a IA (silencioso).", conversation_id)

    if body.mode == "human" and previous_mode == "ai":
        crud.create_advisor_session(db, conversation_id, advisor_name=body.advisor_name)

    return {"conversation_id": conversation_id, "mode": body.mode, "previous_mode": previous_mode}


class AdvisorMessageRequest(BaseModel):
    text: str
    advisor_name: str | None = None


@router.post("/conversations/{conversation_id}/send_message")
async def send_advisor_message(
    conversation_id: int,
    body: AdvisorMessageRequest,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Send a WhatsApp message as human advisor from the admin panel."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")

    success = await send_text_message(conv.phone_number, text)
    if not success:
        raise HTTPException(status_code=502, detail="Error enviando mensaje por WhatsApp")

    crud.save_message(
        db,
        conversation_id=conversation_id,
        direction="outbound",
        sender="human_advisor",
        content=text,
    )
    logger.info("Asesor envió mensaje a conversación %d", conversation_id)
    return {"status": "sent"}


class EmailRequest(BaseModel):
    customer_name: str
    to_email: str
    order_summary: str = ""


@router.post("/conversations/{conversation_id}/send_email")
async def send_confirmation_email(
    conversation_id: int,
    body: EmailRequest,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Send order confirmation email to the customer."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    success = send_order_confirmation(
        to_email=body.to_email,
        customer_name=body.customer_name,
        order_summary=body.order_summary,
    )
    if not success:
        raise HTTPException(status_code=502, detail="Error enviando el correo. Revisa la configuración de email.")

    crud.save_message(
        db,
        conversation_id=conversation_id,
        direction="outbound",
        sender="human_advisor",
        content=f"[NOTA INTERNA] Email de confirmación enviado a {body.to_email}",
    )
    return {"status": "email_sent", "to": body.to_email}


# ── Configuración QR ──────────────────────────────────────────────────────────

@router.post("/conversations/{conversation_id}/send_qr")
async def send_qr_manually(
    conversation_id: int,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Send the configured QR image to the client from the admin panel."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    qr = crud.get_qr_config(db)
    if not qr.get("enabled"):
        raise HTTPException(status_code=400, detail="El QR no está habilitado. Actívalo en ⚙️ Config.")

    media_id = qr.get("media_id", "")
    caption = qr.get("caption", "")

    if not media_id:
        raise HTTPException(status_code=400, detail="No hay imagen QR configurada. Súbela en ⚙️ Config.")

    from app.whatsapp.client import send_image_by_id
    success = await send_image_by_id(conv.phone_number, media_id, caption)

    if not success:
        raise HTTPException(status_code=502, detail="No se pudo enviar el QR por WhatsApp")

    crud.save_message(
        db, conversation_id=conversation_id, direction="outbound",
        sender="human_advisor", content="[QR de pago enviado manualmente por asesor]",
    )
    return {"status": "sent"}


@router.get("/config", response_class=HTMLResponse)
async def config_page(token: str = Query(default=""), db: Session = Depends(get_db)):
    _check_token(token)
    qr = crud.get_qr_config(db)
    qr_enabled = "checked" if qr.get("enabled") else ""
    qr_caption = qr.get("caption", "")
    qr_has_image = bool(qr.get("media_id"))
    qr_filename = qr.get("filename", "")
    qr_preview_b64 = qr.get("preview_b64", "")
    qr_status = f"✅ Imagen cargada: {qr_filename}" if qr_has_image else "⚠️ Sin imagen configurada"
    qr_status_color = "#16a34a" if qr_has_image else "#d97706"
    preview_html = (f'<img src="data:image/jpeg;base64,{qr_preview_b64}" '
                    f'class="preview-img" style="display:block">') if qr_preview_b64 else ""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vita Qualitat — Configuración</title>
<style>
  * {{ box-sizing:border-box;margin:0;padding:0 }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(135deg,#f0fdf4,#ecfdf5);min-height:100vh }}
  .topbar {{ background:linear-gradient(135deg,#16a34a,#15803d);padding:16px 22px;
             display:flex;align-items:center;gap:14px;box-shadow:0 4px 20px rgba(22,163,74,0.25) }}
  .back {{ color:white;text-decoration:none;font-size:24px;opacity:0.9;transition:opacity .2s }}
  .back:hover {{ opacity:1 }}
  .topbar h1 {{ color:white;font-size:19px;font-weight:700;letter-spacing:-.5px }}
  .container {{ max-width:640px;margin:32px auto;padding:0 18px }}
  .card {{ background:white;border-radius:18px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,0.08);margin-bottom:20px;border-top:3px solid #16a34a }}
  .card h2 {{ font-size:18px;font-weight:700;color:#111827;margin-bottom:8px }}
  .card p {{ font-size:14px;color:#6b7280;margin-bottom:18px;line-height:1.6 }}
  .upload-zone {{ border:2px dashed #d1fae5;border-radius:14px;padding:36px;text-align:center;
                  cursor:pointer;transition:all .2s;background:#f0fdf4 }}
  .upload-zone:hover {{ border-color:#16a34a;background:#e8f8f2 }}
  .upload-zone input {{ display:none }}
  .upload-icon {{ font-size:44px;margin-bottom:10px }}
  .upload-label {{ font-size:15px;color:#374151;font-weight:600 }}
  .upload-hint {{ font-size:12px;color:#9ca3af;margin-top:6px }}
  .status-badge {{ display:inline-block;padding:6px 14px;border-radius:18px;font-size:12px;
                   font-weight:700;background:#f0fdf4;color:{qr_status_color};margin-bottom:18px }}
  .field {{ margin-bottom:16px }}
  .field label {{ display:block;font-size:13px;font-weight:700;color:#374151;margin-bottom:8px }}
  .field input[type=text] {{ width:100%;border:1.5px solid #e5e7eb;border-radius:10px;
                              padding:11px 14px;font-size:14px;outline:none;transition:border-color .2s }}
  .field input:focus {{ border-color:#16a34a;background:#f0fdf4 }}
  .toggle {{ display:flex;align-items:center;gap:12px;margin-bottom:18px;padding:12px;background:#f9fafb;border-radius:12px }}
  .toggle input[type=checkbox] {{ width:20px;height:20px;accent-color:#16a34a;cursor:pointer }}
  .toggle label {{ font-size:14px;font-weight:600;color:#374151;cursor:pointer }}
  .btn-save {{ background:linear-gradient(135deg,#16a34a,#15803d);color:white;border:none;border-radius:12px;padding:13px 26px;
               font-size:15px;font-weight:700;cursor:pointer;width:100%;transition:all .25s;box-shadow:0 2px 8px rgba(22,163,74,0.2) }}
  .btn-save:hover {{ transform:translateY(-1px);box-shadow:0 6px 16px rgba(22,163,74,0.3) }}
  .btn-save:disabled {{ background:#d1d5db;cursor:not-allowed;box-shadow:none }}
  .progress {{ display:none;text-align:center;padding:14px;color:#16a34a;font-size:14px;font-weight:600 }}
  .preview-img {{ max-width:200px;border-radius:12px;margin:14px auto;display:block;
                  box-shadow:0 4px 16px rgba(0,0,0,0.12) }}
</style>
</head>
<body>
<div class="topbar">
  <a href="/admin/panel?token={token}" class="back">←</a>
  <h1>⚙️ Configuración del Bot</h1>
</div>
<div class="container">
  <div class="card">
    <h2>📱 Código QR para pagos</h2>
    <p>Sube tu imagen de QR y el bot la enviará automáticamente cuando un cliente quiera pagar con QR.
       La imagen se guarda en WhatsApp y se envía exactamente como la subiste.</p>

    <div class="status-badge">{qr_status}</div>

    <div class="toggle">
      <input type="checkbox" id="qr-enabled" {qr_enabled}>
      <label for="qr-enabled">QR habilitado (el bot puede enviarlo)</label>
    </div>

    <div class="field">
      <label>Mensaje que acompaña el QR</label>
      <input type="text" id="qr-caption" value="{qr_caption}"
             placeholder="Ej: Aquí está nuestro QR para el pago 🌿">
    </div>

    {preview_html}
    <div class="upload-zone" onclick="document.getElementById('qr-file').click()">
      <div class="upload-icon">🖼️</div>
      <div class="upload-label">{'Cambiar imagen del QR' if qr_has_image else 'Seleccionar imagen del QR'}</div>
      <div class="upload-hint">PNG, JPG o JPEG · Máximo 5MB</div>
      <input type="file" id="qr-file" accept="image/png,image/jpeg,image/jpg" onchange="previewFile(this)">
    </div>
    <img id="preview" class="preview-img" style="display:none">

    <div class="progress" id="progress">⏳ Subiendo imagen a WhatsApp...</div>

    <br>
    <button class="btn-save" id="btn-save" onclick="saveConfig()">Guardar configuración</button>
  </div>

  <div class="card">
    <h2>📊 Reporte de Clientes</h2>
    <p>Descarga un Excel con toda la información de clientes y su historial de compras.
       El archivo se enviará automáticamente a vitaqualitat@gmail.com.</p>

    <button class="btn-save" id="btn-excel" style="background:#3b82f6;margin-bottom:8px" onclick="downloadExcel(event)">
      📥 Descargar Excel
    </button>
    <p style="font-size:12px;color:#9ca3af;margin:0">
      Incluye: resumen de clientes + historial detallado de compras
    </p>
  </div>
</div>

<script>
const TOKEN = '{token}';

function previewFile(input) {{
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = e => {{
    const img = document.getElementById('preview');
    img.src = e.target.result;
    img.style.display = 'block';
  }};
  reader.readAsDataURL(file);
}}

async function saveConfig() {{
  const btn = document.getElementById('btn-save');
  const progress = document.getElementById('progress');
  const enabled = document.getElementById('qr-enabled').checked;
  const caption = document.getElementById('qr-caption').value.trim();
  const fileInput = document.getElementById('qr-file');
  const file = fileInput.files[0];

  btn.disabled = true;

  let mediaId = null;
  if (file) {{
    progress.style.display = 'block';
    const form = new FormData();
    form.append('file', file);
    form.append('caption', caption);
    form.append('enabled', enabled);
    const res = await fetch(`/admin/config/qr/upload?token=${{TOKEN}}`, {{
      method: 'POST',
      headers: {{ 'Authorization': `Bearer ${{TOKEN}}` }},
      body: form
    }});
    progress.style.display = 'none';
    if (!res.ok) {{
      const err = await res.json();
      alert('Error subiendo imagen: ' + (err.detail || 'Error desconocido'));
      btn.disabled = false;
      return;
    }}
    const data = await res.json();
    mediaId = data.media_id;
    alert('✅ Imagen subida correctamente. Media ID: ' + mediaId);
  }} else {{
    // Solo guardar enabled y caption sin cambiar la imagen
    const res = await fetch(`/admin/config/qr?token=${{TOKEN}}`, {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json', 'Authorization': `Bearer ${{TOKEN}}` }},
      body: JSON.stringify({{ enabled, caption }})
    }});
    if (res.ok) alert('✅ Configuración guardada');
    else alert('Error guardando configuración');
  }}
  btn.disabled = false;
  location.reload();
}}

function downloadExcel(evt) {{
  evt.preventDefault();
  const btn = document.getElementById('btn-excel');
  btn.disabled = true;
  btn.textContent = '⏳ Generando...';

  fetch(`/admin/api/customers/export?token=${{TOKEN}}`)
    .then(res => {{
      if (!res.ok) throw new Error('Error descargando Excel');
      return res.blob();
    }})
    .then(blob => {{
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `clientes_vita_qualitat_${{new Date().toISOString().slice(0,10)}}.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      alert('✅ Excel descargado. También fue enviado a vitaqualitat@gmail.com');
      btn.disabled = false;
      btn.textContent = '📥 Descargar Excel';
    }})
    .catch(err => {{
      alert('Error: ' + err.message);
      btn.disabled = false;
      btn.textContent = '📥 Descargar Excel';
    }});
}}
</script>
</body></html>""")


@router.post("/conversations/{conversation_id}/upload_and_send")
async def upload_and_send_image(
    conversation_id: int,
    file: UploadFile = File(...),
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Adjuntar y enviar un archivo (foto, video o documento) al cliente, como WhatsApp.
    Se guarda el archivo y se envía por URL PÚBLICA (WhatsApp lo descarga), que es el
    método más fiable; si no hay URL pública, cae a subirlo por media_id."""
    import uuid
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    conv = crud.get_conversation_by_id(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")

    data = await file.read()
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo no puede superar 30MB")
    ctype = (file.content_type or "").lower()
    fname = file.filename or "archivo"

    # Decidir tipo de envío según el archivo y los límites de WhatsApp
    if ctype.startswith("image/"):
        if len(data) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB (límite de WhatsApp)")
        kind, wa = "image", "image"
    elif ctype.startswith("video/"):
        if len(data) > 16 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="El video no puede superar 16MB (límite de WhatsApp). Envíalo como documento o comprímelo.")
        kind, wa = "video", "video"
    else:
        kind, wa = "document", "document"  # cualquier otro archivo (hasta 30MB) va como documento

    key = f"chat-{uuid.uuid4().hex[:12]}"
    try:
        crud.save_media_blob(db, key, kind, data, ctype or "application/octet-stream")
    except Exception as exc:
        logger.error("No se pudo guardar el adjunto: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo")

    from app.runtime import public_base
    from app.whatsapp.client import (send_image_by_url, send_image_by_id, send_video_by_url,
                                     send_video_by_id, send_document_by_url, upload_media_to_whatsapp)
    base = public_base()
    url = f"{base}/admin/media/{key}/{kind}" if base else ""
    sent = False
    if url:
        if wa == "image":
            sent = await send_image_by_url(conv.phone_number, url)
        elif wa == "video":
            sent = await send_video_by_url(conv.phone_number, url)
        else:
            sent = await send_document_by_url(conv.phone_number, url, filename=fname)
    if not sent:  # respaldo por media_id
        media_id = await upload_media_to_whatsapp(data, ctype or "application/octet-stream", fname)
        if media_id:
            if wa == "image":
                sent = await send_image_by_id(conv.phone_number, media_id)
            elif wa == "video":
                sent = await send_video_by_id(conv.phone_number, media_id)
    if not sent:
        raise HTTPException(status_code=502, detail="No se pudo enviar el archivo a WhatsApp. Intenta de nuevo.")

    if kind in ("image", "video"):
        record = f"[[MEDIA|{kind}|{key}|{'Imagen' if kind=='image' else 'Video'}]]"
    else:
        record = f"📎 Documento enviado: {fname}"
    crud.save_message(db, conversation_id=conversation_id, direction="outbound",
                      sender="human_advisor", content=record)
    return {"status": "sent"}


@router.post("/config/qr/upload")
async def upload_qr_image(
    file: UploadFile = File(...),
    caption: str = "",
    enabled: str = "false",
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Upload QR image to WhatsApp and save media_id to the database (persists across deploys)."""
    import base64
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen (PNG, JPG)")

    image_bytes = await file.read()
    if len(image_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar 5MB")

    media_id = await upload_image_to_whatsapp(image_bytes, file.content_type, file.filename or "qr.jpg")
    if not media_id:
        raise HTTPException(status_code=502, detail="No se pudo subir la imagen a WhatsApp. Verifica el token de acceso.")

    # Store preview as base64 (for display in config page)
    preview_b64 = base64.b64encode(image_bytes).decode("utf-8")

    crud.save_qr_config(
        db,
        enabled=enabled.lower() in ("true", "1", "on"),
        media_id=media_id,
        caption=caption,
        filename=file.filename or "qr.jpg",
        preview_b64=preview_b64,
    )
    logger.info("QR imagen subida a WhatsApp y guardada en BD. Media ID: %s", media_id)
    return {"status": "ok", "media_id": media_id}


@router.post("/config/qr")
async def update_qr_config(
    body: dict,
    token: str = Query(default=""),
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
):
    """Update QR enabled/caption in the database without changing the image."""
    auth_token = authorization.removeprefix("Bearer ").strip() or token
    _check_token(auth_token)
    crud.save_qr_config(
        db,
        enabled=bool(body.get("enabled", False)),
        caption=body.get("caption", ""),
    )
    return {"status": "ok"}


@router.get("/conversations", dependencies=[Depends(verify_admin)])
def list_conversations(db: Session = Depends(get_db)):
    return crud.list_open_conversations(db)


def _generate_customers_excel(db: Session) -> bytes:
    """Generate Excel file with customers matching the Google Sheets template."""
    import json
    from app.db.models import Order

    customers = db.query(Customer).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"

    # Headers exactly as in Google Sheets template
    headers = ["Nombre", "Teléfono", "Cédula", "Email", "Dirección", "Fecha Registro", "Productos", "Compras", "Última Compra", "Monto Total"]
    ws.append(headers)

    # Data rows
    for customer in customers:
        # Solo pedidos pagados (ventas reales)
        orders = db.query(Order).filter(Order.customer_id == customer.id, Order.status == "paid").all()

        # Count purchases and calculate totals
        purchase_count = len(orders)
        last_purchase = max([o.created_at for o in orders], default=None)
        total_amount = sum([o.total or 0 for o in orders]) if orders else 0

        # Get all products purchased
        all_products = []
        for order in orders:
            try:
                items = json.loads(order.items_json) if order.items_json else []
                for item in items:
                    product_name = item.get('name', 'Producto')
                    quantity = item.get('quantity', 1)
                    all_products.append(f"{product_name} x{quantity} und")
            except:
                pass
        products_str = ", ".join(all_products) if all_products else ""

        ws.append([
            customer.name or "",
            customer.phone_number or "",
            customer.cedula or "",
            customer.email or "",
            customer.address or "",
            customer.created_at.strftime('%d/%m/%Y') if customer.created_at else "",
            products_str,
            purchase_count,
            last_purchase.strftime('%d/%m/%Y') if last_purchase else "",
            int(total_amount) if total_amount else 0,
        ])

    # Adjust column widths
    ws.column_dimensions['A'].width = 20  # Nombre
    ws.column_dimensions['B'].width = 15  # Teléfono
    ws.column_dimensions['C'].width = 15  # Cédula
    ws.column_dimensions['D'].width = 25  # Email
    ws.column_dimensions['E'].width = 30  # Dirección
    ws.column_dimensions['F'].width = 15  # Fecha Registro
    ws.column_dimensions['G'].width = 40  # Productos
    ws.column_dimensions['H'].width = 12  # Compras
    ws.column_dimensions['I'].width = 15  # Última Compra
    ws.column_dimensions['J'].width = 15  # Monto Total

    # Generate file
    excel_bytes = io.BytesIO()
    wb.save(excel_bytes)
    excel_bytes.seek(0)
    return excel_bytes.getvalue()


@router.get("/api/customers/export")
def export_customers_to_excel(
    token: str = Query(default=""),
    db: Session = Depends(get_db)
):
    """Export all customers with purchase history to Excel file and email it to vitaqualitat@gmail.com."""
    _check_token(token)
    excel_content = _generate_customers_excel(db)

    filename = f"clientes_vita_qualitat_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    # Send email to vitaqualitat@gmail.com with the Excel file
    try:
        from app.email_service import send_email_with_attachment
        send_email_with_attachment(
            to_email="vitaqualitat@gmail.com",
            subject=f"📊 Reporte de Clientes - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            body="Adjunto se encuentra el reporte detallado de clientes y su historial de compras.",
            attachment_content=excel_content,
            attachment_filename=filename,
        )
        logger.info("Excel enviado a vitaqualitat@gmail.com")
    except Exception as e:
        logger.error("Error enviando Excel por email: %s", e)

    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
