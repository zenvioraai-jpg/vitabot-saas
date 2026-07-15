from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.models import (Company, Customer, Conversation, Message, AdvisorSession, BotSetting, Order,
                           CustomerTag, PaymentReceipt, Followup, Coupon, ShippingGuide, Contact,
                           PaymentReceived, MediaBlob, Reminder, Product, PlatformSetting, Appointment)


# ─── Configuración de PLATAFORMA (panel maestro, no ligada a una empresa) ──────

def get_platform_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    return row.value if row else default


def set_platform_setting(db: Session, key: str, value: str) -> None:
    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(PlatformSetting(key=key, value=value))
    db.commit()


def get_master_profile(db: Session) -> dict:
    import json
    raw = get_platform_setting(db, "master_profile", "")
    if not raw:
        return {"name": "Administrador", "photo_b64": ""}
    try:
        return json.loads(raw)
    except Exception:
        return {"name": "Administrador", "photo_b64": ""}


def save_master_profile(db: Session, name: str, photo_b64: str | None = None) -> None:
    import json
    cur = get_master_profile(db)
    cur["name"] = (name or "").strip() or "Administrador"
    if photo_b64 is not None:
        cur["photo_b64"] = photo_b64
    set_platform_setting(db, "master_profile", json.dumps(cur, ensure_ascii=False))


# ─── Companies (empresas / tenants) ────────────────────────────────────────────

def create_company(db: Session, **fields) -> Company:
    c = Company(**fields)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def get_company(db: Session, company_id: int) -> Company | None:
    return db.query(Company).filter(Company.id == company_id).first()


def get_company_by_admin_token(db: Session, token: str) -> Company | None:
    if not token:
        return None
    return db.query(Company).filter(Company.admin_token == token).first()


def get_company_by_phone_number_id(db: Session, phone_number_id: str) -> Company | None:
    if not phone_number_id:
        return None
    return db.query(Company).filter(Company.whatsapp_phone_number_id == phone_number_id).first()


def get_company_by_webhook_verify_token(db: Session, token: str) -> Company | None:
    if not token:
        return None
    return db.query(Company).filter(Company.webhook_verify_token == token).first()


def list_companies(db: Session) -> list[Company]:
    return db.query(Company).order_by(Company.created_at.desc()).all()


def update_company(db: Session, company_id: int, **fields) -> Company | None:
    c = get_company(db, company_id)
    if c:
        for key, value in fields.items():
            setattr(c, key, value)
        db.commit()
        db.refresh(c)
    return c


def get_extra_config(db: Session, company_id: int) -> dict:
    """Campos extra propios del tipo de negocio (horario de restaurante, tallas de
    ropa, etc.), guardados en Company.extra_config."""
    import json
    company = get_company(db, company_id)
    if not company or not company.extra_config:
        return {}
    try:
        return json.loads(company.extra_config)
    except Exception:
        return {}


def save_extra_config(db: Session, company_id: int, data: dict) -> None:
    import json
    update_company(db, company_id, extra_config=json.dumps(data, ensure_ascii=False))


def set_company_status(db: Session, company_id: int, status: str) -> Company | None:
    return update_company(db, company_id, status=status)


# ─── Customers ────────────────────────────────────────────────────────────────

def get_or_create_customer(db: Session, company_id: int, phone_number: str) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.company_id == company_id, Customer.phone_number == phone_number)
        .first()
    )
    if not customer:
        customer = Customer(company_id=company_id, phone_number=phone_number)
        db.add(customer)
        db.commit()
        db.refresh(customer)
    return customer


def update_customer(db: Session, company_id: int, phone_number: str, **fields) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.company_id == company_id, Customer.phone_number == phone_number)
        .first()
    )
    if customer:
        for key, value in fields.items():
            setattr(customer, key, value)
        db.commit()
        db.refresh(customer)
    return customer


# ─── Reset / borrado de datos (protegido por clave en el router) ───────────────

def reset_customer(db: Session, company_id: int, customer_id: int) -> bool:
    """Borra un cliente y TODOS sus datos asociados (conversaciones, mensajes,
    pedidos, comprobantes, etiquetas, seguimientos, pagos)."""
    cust = db.query(Customer).filter(Customer.id == customer_id, Customer.company_id == company_id).first()
    if not cust:
        return False
    order_ids = [o.id for o in db.query(Order.id).filter(Order.customer_id == customer_id).all()]
    conv_ids = [c.id for c in db.query(Conversation.id).filter(Conversation.customer_id == customer_id).all()]

    db.query(Followup).filter(Followup.customer_id == customer_id).delete(synchronize_session=False)
    if order_ids:
        db.query(PaymentReceived).filter(PaymentReceived.order_id.in_(order_ids)).delete(synchronize_session=False)
    db.query(PaymentReceipt).filter(PaymentReceipt.customer_id == customer_id).delete(synchronize_session=False)
    if conv_ids:
        db.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        db.query(AdvisorSession).filter(AdvisorSession.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
    db.query(Order).filter(Order.customer_id == customer_id).delete(synchronize_session=False)
    db.query(CustomerTag).filter(CustomerTag.customer_id == customer_id).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.customer_id == customer_id).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.id == customer_id).delete(synchronize_session=False)
    db.commit()
    return True


def reset_all_customer_data(db: Session, company_id: int) -> dict:
    """Borra TODOS los clientes y sus datos (incluidas ventas) DE UNA empresa. No toca la
    configuración (cuentas de pago, cupones, catálogo, entrenamiento, etc.)."""
    cust_ids = [c.id for c in db.query(Customer.id).filter(Customer.company_id == company_id).all()]
    counts = {
        "clientes": len(cust_ids),
        "conversaciones": db.query(Conversation).filter(Conversation.company_id == company_id).count(),
        "pedidos": db.query(Order).filter(Order.company_id == company_id).count(),
        "comprobantes": db.query(PaymentReceipt).filter(PaymentReceipt.company_id == company_id).count(),
    }
    db.query(Followup).filter(Followup.company_id == company_id).delete(synchronize_session=False)
    db.query(PaymentReceived).filter(PaymentReceived.company_id == company_id).delete(synchronize_session=False)
    db.query(PaymentReceipt).filter(PaymentReceipt.company_id == company_id).delete(synchronize_session=False)
    db.query(Message).filter(Message.company_id == company_id).delete(synchronize_session=False)
    db.query(AdvisorSession).filter(AdvisorSession.company_id == company_id).delete(synchronize_session=False)
    db.query(Order).filter(Order.company_id == company_id).delete(synchronize_session=False)
    db.query(CustomerTag).filter(CustomerTag.company_id == company_id).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.company_id == company_id).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.company_id == company_id).delete(synchronize_session=False)
    db.commit()
    return counts


def clear_category(db: Session, company_id: int, name: str) -> int:
    """Borra toda la información de una categoría 'no preestablecida' DE UNA empresa.
    name: 'guias' | 'contactos' | 'cupones' | 'comprobantes'. Devuelve filas borradas."""
    mapping = {
        "guias": ShippingGuide,
        "contactos": Contact,
        "cupones": Coupon,
        # NOTA: los comprobantes NO se incluyen aquí: nunca deben poder borrarse.
    }
    model = mapping.get(name)
    if not model:
        return 0
    q = db.query(model).filter(model.company_id == company_id)
    n = q.count()
    q.delete(synchronize_session=False)
    db.commit()
    return n


# ─── Conversations ────────────────────────────────────────────────────────────

def get_open_conversation(db: Session, company_id: int, phone_number: str) -> Conversation | None:
    """Return the current open conversation for a phone number, or None."""
    return (
        db.query(Conversation)
        .filter(Conversation.company_id == company_id, Conversation.phone_number == phone_number,
                Conversation.status == "open")
        .first()
    )


def get_or_create_conversation(db: Session, company_id: int, phone_number: str, customer_id: int) -> Conversation:
    conv = get_open_conversation(db, company_id, phone_number)
    if not conv:
        conv = Conversation(company_id=company_id, phone_number=phone_number, customer_id=customer_id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def create_new_conversation(db: Session, company_id: int, phone_number: str, customer_id: int) -> Conversation:
    """Force-create a new open conversation (used when resetting a session)."""
    conv = Conversation(company_id=company_id, phone_number=phone_number, customer_id=customer_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def get_or_reopen_conversation(db: Session, company_id: int, phone_number: str, customer_id: int) -> Conversation:
    """Devuelve SIEMPRE la misma conversación del número (1 por persona, por empresa).

    Reutiliza la conversación existente más reciente del número; si estaba cerrada
    (resolved), la reabre. Solo crea una nueva si el número nunca ha escrito.
    Esto evita que cada vez que el cliente vuelve a escribir se cree un chat nuevo.
    """
    conv = (
        db.query(Conversation)
        .filter(Conversation.company_id == company_id, Conversation.phone_number == phone_number)
        .order_by(Conversation.created_at.desc())
        .first()
    )
    if conv:
        if conv.status != "open":
            conv.status = "open"
            conv.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(conv)
        return conv
    return create_new_conversation(db, company_id, phone_number, customer_id)


def close_conversation(db: Session, conversation_id: int):
    """Mark a conversation as resolved."""
    conv = get_conversation_by_id(db, conversation_id)
    if conv:
        conv.status = "resolved"
        conv.updated_at = datetime.utcnow()
        db.commit()


def archive_conversation(db: Session, conversation_id: int, archived: bool = True):
    """Archivar/desarchivar una conversación (queda oculta de la lista principal,
    visible en el filtro Archivadas). No borra nada."""
    conv = get_conversation_by_id(db, conversation_id)
    if conv:
        conv.status = "archived" if archived else "open"
        conv.updated_at = datetime.utcnow()
        db.commit()
    return conv


def delete_conversation(db: Session, conversation_id: int) -> bool:
    """Borra una conversación y su hilo (mensajes, sesiones de asesor, comprobantes,
    pedidos y seguimientos ligados a ESA conversación). No borra al cliente."""
    conv = get_conversation_by_id(db, conversation_id)
    if not conv:
        return False
    order_ids = [o.id for o in db.query(Order.id).filter(Order.conversation_id == conversation_id).all()]
    if order_ids:
        db.query(Followup).filter(Followup.order_id.in_(order_ids)).delete(synchronize_session=False)
        db.query(PaymentReceived).filter(PaymentReceived.order_id.in_(order_ids)).delete(synchronize_session=False)
    db.query(PaymentReceipt).filter(PaymentReceipt.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(Order).filter(Order.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(AdvisorSession).filter(AdvisorSession.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(Message).filter(Message.conversation_id == conversation_id).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.id == conversation_id).delete(synchronize_session=False)
    db.commit()
    return True


def get_last_message_time(db: Session, conversation_id: int) -> datetime | None:
    """Return the timestamp of the most recent message in a conversation."""
    msg = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.desc())
        .first()
    )
    return msg.timestamp if msg else None


def has_previous_conversations(db: Session, company_id: int, phone_number: str) -> bool:
    """Return True if this phone number has any past (resolved) conversations."""
    return (
        db.query(Conversation)
        .filter(Conversation.company_id == company_id, Conversation.phone_number == phone_number,
                Conversation.status == "resolved")
        .count()
        > 0
    )


def get_previous_session_messages(db: Session, company_id: int, phone_number: str, limit: int = 10) -> list[Message]:
    """Return the last N messages from the most recent resolved conversation for this phone."""
    prev_conv = (
        db.query(Conversation)
        .filter(Conversation.company_id == company_id, Conversation.phone_number == phone_number,
                Conversation.status == "resolved")
        .order_by(Conversation.updated_at.desc())
        .first()
    )
    if not prev_conv:
        return []
    return get_recent_messages(db, prev_conv.id, limit=limit)


def get_messages_since(db: Session, conversation_id: int, since_timestamp: datetime) -> list[Message]:
    """Return messages in a conversation after a given timestamp (for live polling)."""
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.timestamp > since_timestamp)
        .order_by(Message.timestamp.asc())
        .all()
    )


def get_conversations_updated_since(db: Session, company_id: int, since_timestamp: datetime) -> list[Conversation]:
    """Return open conversations updated after a given timestamp."""
    return (
        db.query(Conversation)
        .filter(Conversation.company_id == company_id, Conversation.status == "open",
                Conversation.updated_at > since_timestamp)
        .all()
    )


def list_all_conversations(db: Session, company_id: int, limit: int = 200) -> list[Conversation]:
    """Return all conversations (open and resolved) of a company, most recent first."""
    return (
        db.query(Conversation)
        .filter(Conversation.company_id == company_id)
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .all()
    )


def get_conversation_by_id(db: Session, conversation_id: int) -> Conversation | None:
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def set_conversation_mode(
    db: Session,
    conversation_id: int,
    mode: str,
    reason: str | None = None,
    assigned_to: str | None = None,
) -> Conversation | None:
    conv = get_conversation_by_id(db, conversation_id)
    if not conv:
        return None
    conv.mode = mode
    if mode == "human":
        conv.escalation_reason = reason
        conv.escalated_at = datetime.utcnow()
        if assigned_to:
            conv.assigned_to = assigned_to
    else:
        conv.assigned_to = None
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)
    return conv


def list_open_conversations(db: Session, company_id: int) -> list[Conversation]:
    return db.query(Conversation).filter(Conversation.company_id == company_id, Conversation.status == "open").all()


# ─── Messages ─────────────────────────────────────────────────────────────────

def is_duplicate_message(db: Session, company_id: int, wa_message_id: str) -> bool:
    if not wa_message_id:
        return False
    return (
        db.query(Message)
        .filter(Message.company_id == company_id, Message.wa_message_id == wa_message_id)
        .first()
        is not None
    )


def delete_message(db: Session, conversation_id: int, message_id: int) -> bool:
    """Borra un mensaje del historial del panel (no lo borra del WhatsApp del cliente)."""
    n = (
        db.query(Message)
        .filter(Message.id == message_id, Message.conversation_id == conversation_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return n > 0


def save_message(
    db: Session,
    company_id: int,
    conversation_id: int,
    direction: str,
    sender: str,
    content: str,
    wa_message_id: str | None = None,
) -> Message:
    msg = Message(
        company_id=company_id,
        conversation_id=conversation_id,
        direction=direction,
        sender=sender,
        content=content,
        wa_message_id=wa_message_id,
    )
    db.add(msg)
    try:
        db.commit()
        db.refresh(msg)
    except IntegrityError:
        db.rollback()
        raise
    return msg


def get_recent_messages(db: Session, conversation_id: int, limit: int = 15) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
        .all()[::-1]  # reverse to chronological order
    )


# ─── Advisor Sessions ─────────────────────────────────────────────────────────

def create_advisor_session(db: Session, company_id: int, conversation_id: int,
                           advisor_name: str | None = None) -> AdvisorSession:
    session = AdvisorSession(company_id=company_id, conversation_id=conversation_id, advisor_name=advisor_name)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def close_advisor_session(db: Session, conversation_id: int, handback_reason: str | None = None):
    session = (
        db.query(AdvisorSession)
        .filter(AdvisorSession.conversation_id == conversation_id, AdvisorSession.ended_at.is_(None))
        .first()
    )
    if session:
        session.ended_at = datetime.utcnow()
        session.handback_reason = handback_reason
        db.commit()


# ─── Bot Settings (key-value persistente, por empresa) ────────────────────────

def get_setting(db: Session, company_id: int, key: str, default: str = "") -> str:
    row = db.query(BotSetting).filter(BotSetting.company_id == company_id, BotSetting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, company_id: int, key: str, value: str) -> None:
    row = db.query(BotSetting).filter(BotSetting.company_id == company_id, BotSetting.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        row = BotSetting(company_id=company_id, key=key, value=value)
        db.add(row)
    db.commit()


def get_product_media(db: Session, company_id: int) -> dict:
    """Media por SKU: {sku: {image_url, video_url, link}}."""
    import json
    raw = get_setting(db, company_id, "product_media", "{}")
    try:
        return json.loads(raw)
    except Exception:
        return {}


def save_product_media(db: Session, company_id: int, data: dict) -> None:
    import json
    set_setting(db, company_id, "product_media", json.dumps(data, ensure_ascii=False))


def photo_already_sent(db: Session, conversation_id: int, sku: str) -> bool:
    """True si en esta conversación ya se le envió la foto de ese producto.
    Se guarda en un setting (no como mensaje) para no ensuciar el chat del panel."""
    conv = get_conversation_by_id(db, conversation_id)
    if not conv:
        return False
    raw = get_setting(db, conv.company_id, f"pphoto_{conversation_id}", "")
    return sku in [s for s in raw.split(",") if s]


def mark_photo_sent(db: Session, conversation_id: int, sku: str) -> None:
    conv = get_conversation_by_id(db, conversation_id)
    if not conv:
        return
    raw = get_setting(db, conv.company_id, f"pphoto_{conversation_id}", "")
    skus = [s for s in raw.split(",") if s]
    if sku not in skus:
        skus.append(sku)
        set_setting(db, conv.company_id, f"pphoto_{conversation_id}", ",".join(skus))


# ─── Media blobs (foto/video del producto guardados en la BD, por empresa) ─────

def save_media_blob(db: Session, company_id: int, sku: str, kind: str, data: bytes, mime: str) -> None:
    blob = (
        db.query(MediaBlob)
        .filter(MediaBlob.company_id == company_id, MediaBlob.sku == sku, MediaBlob.kind == kind)
        .first()
    )
    if blob:
        blob.data = data
        blob.mime = mime
    else:
        db.add(MediaBlob(company_id=company_id, sku=sku, kind=kind, data=data, mime=mime))
    db.commit()


def get_media_blob(db: Session, company_id: int, sku: str, kind: str) -> tuple[bytes, str] | None:
    blob = (
        db.query(MediaBlob)
        .filter(MediaBlob.company_id == company_id, MediaBlob.sku == sku, MediaBlob.kind == kind)
        .first()
    )
    return (blob.data, blob.mime) if blob else None


def delete_media_blob(db: Session, company_id: int, sku: str, kind: str) -> None:
    (
        db.query(MediaBlob)
        .filter(MediaBlob.company_id == company_id, MediaBlob.sku == sku, MediaBlob.kind == kind)
        .delete(synchronize_session=False)
    )
    db.commit()


def media_blob_skus(db: Session, company_id: int) -> set[tuple[str, str]]:
    """Conjunto de (sku, kind) que tienen archivo guardado en la BD, de una empresa."""
    rows = db.query(MediaBlob.sku, MediaBlob.kind).filter(MediaBlob.company_id == company_id).all()
    return {(b.sku, b.kind) for b in rows}


# ─── Catálogo de productos (reemplaza el products.json de un solo archivo) ────

def list_products(db: Session, company_id: int) -> list[Product]:
    return db.query(Product).filter(Product.company_id == company_id).order_by(Product.id).all()


def get_product(db: Session, company_id: int, sku: str) -> Product | None:
    return db.query(Product).filter(Product.company_id == company_id, Product.sku == sku).first()


def upsert_product(db: Session, company_id: int, sku: str, **fields) -> Product:
    p = get_product(db, company_id, sku)
    if p:
        for k, v in fields.items():
            setattr(p, k, v)
    else:
        p = Product(company_id=company_id, sku=sku, **fields)
        db.add(p)
    db.commit()
    db.refresh(p)
    return p


def delete_product(db: Session, company_id: int, sku: str) -> None:
    db.query(Product).filter(Product.company_id == company_id, Product.sku == sku).delete()
    db.commit()


# ─── Recordatorios de recontacto ───────────────────────────────────────────────

def create_reminder(db: Session, company_id: int, customer_id: int, conversation_id: int,
                    due_at: datetime, note: str | None = None) -> Reminder:
    # Reemplaza cualquier recordatorio pendiente previo de esta conversación
    db.query(Reminder).filter(Reminder.conversation_id == conversation_id,
                              Reminder.status == "pending").update({"status": "cancelled"})
    r = Reminder(company_id=company_id, customer_id=customer_id, conversation_id=conversation_id,
                 due_at=due_at, note=note)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def due_reminders(db: Session) -> list[Reminder]:
    """Recordatorios vencidos de TODAS las empresas (el cron los procesa a todos;
    cada Reminder ya trae su company_id para saber con qué credenciales avisar)."""
    return (
        db.query(Reminder)
        .filter(Reminder.status == "pending", Reminder.due_at <= datetime.utcnow())
        .all()
    )


def mark_reminder_sent(db: Session, reminder_id: int) -> None:
    r = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if r:
        r.status = "sent"
        db.commit()


def cancel_reminders(db: Session, conversation_id: int) -> None:
    """El cliente volvió a escribir: cancela recordatorios pendientes de esa conversación."""
    db.query(Reminder).filter(Reminder.conversation_id == conversation_id,
                              Reminder.status == "pending").update({"status": "cancelled"})
    db.commit()


_DEFAULT_PAYMENT = {
    "titular": "",
    "accounts": [
        {"bank": "", "type": "Ahorros", "number": "", "bre_b": "", "enabled": True},
    ],
}


def get_payment_config(db: Session, company_id: int) -> dict:
    """Cuentas bancarias / Bre-B editables desde el panel, por empresa."""
    import json
    raw = get_setting(db, company_id, "payment_accounts", "")
    if not raw:
        return _DEFAULT_PAYMENT
    try:
        data = json.loads(raw)
        if not data.get("accounts"):
            data["accounts"] = _DEFAULT_PAYMENT["accounts"]
        if not data.get("titular"):
            data["titular"] = _DEFAULT_PAYMENT["titular"]
        return data
    except Exception:
        return _DEFAULT_PAYMENT


def save_payment_config(db: Session, company_id: int, data: dict) -> None:
    import json
    set_setting(db, company_id, "payment_accounts", json.dumps(data, ensure_ascii=False))


# ─── Contactos (proveedores / distribuidores) ──────────────────────────────────

def create_contact(db: Session, company_id: int, **fields) -> Contact:
    c = Contact(company_id=company_id, **fields)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_contacts(db: Session, company_id: int) -> list[Contact]:
    return db.query(Contact).filter(Contact.company_id == company_id).order_by(Contact.created_at.desc()).all()


def delete_contact(db: Session, contact_id: int) -> None:
    db.query(Contact).filter(Contact.id == contact_id).delete()
    db.commit()


# ─── Pago recibido (contra entrega) ────────────────────────────────────────────

def mark_payment_received(db: Session, company_id: int, order_id: int) -> None:
    existing = db.query(PaymentReceived).filter(PaymentReceived.order_id == order_id).first()
    if not existing:
        db.add(PaymentReceived(company_id=company_id, order_id=order_id))
        db.commit()


def is_payment_received(db: Session, order_id: int) -> bool:
    return db.query(PaymentReceived).filter(PaymentReceived.order_id == order_id).first() is not None


# ─── Cupones / Descuentos ──────────────────────────────────────────────────────

def create_coupon(db: Session, company_id: int, code: str, kind: str, value: int, max_uses: int = 0) -> Coupon | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    existing = db.query(Coupon).filter(Coupon.company_id == company_id, Coupon.code == code).first()
    if existing:
        existing.kind = kind
        existing.value = value
        existing.max_uses = max_uses
        existing.active = True
        db.commit()
        db.refresh(existing)
        return existing
    c = Coupon(company_id=company_id, code=code, kind=kind, value=value, max_uses=max_uses)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def list_coupons(db: Session, company_id: int) -> list[Coupon]:
    return db.query(Coupon).filter(Coupon.company_id == company_id).order_by(Coupon.created_at.desc()).all()


def delete_coupon(db: Session, company_id: int, code: str) -> None:
    db.query(Coupon).filter(Coupon.company_id == company_id, Coupon.code == code.strip().upper()).delete()
    db.commit()


def get_active_coupons(db: Session, company_id: int) -> list[Coupon]:
    return [c for c in db.query(Coupon).filter(Coupon.company_id == company_id, Coupon.active.is_(True)).all()
            if c.max_uses == 0 or c.uses < c.max_uses]


def redeem_coupon(db: Session, company_id: int, code: str) -> Coupon | None:
    c = (
        db.query(Coupon)
        .filter(Coupon.company_id == company_id, Coupon.code == code.strip().upper(), Coupon.active.is_(True))
        .first()
    )
    if not c:
        return None
    if c.max_uses and c.uses >= c.max_uses:
        return None
    c.uses += 1
    db.commit()
    db.refresh(c)
    return c


def get_voice_config(db: Session, company_id: int) -> dict:
    return {
        "enabled": get_setting(db, company_id, "voice_enabled", "false").lower() == "true",
        "voice_id": get_setting(db, company_id, "voice_id", ""),
    }


def save_voice_config(db: Session, company_id: int, enabled: bool, voice_id: str = "") -> None:
    set_setting(db, company_id, "voice_enabled", "true" if enabled else "false")
    if voice_id is not None:
        set_setting(db, company_id, "voice_id", voice_id)


def get_catalog_overrides(db: Session, company_id: int) -> dict:
    """Overrides editables desde el panel: {sku: {price_cop, in_stock}}."""
    import json
    raw = get_setting(db, company_id, "catalog_overrides", "{}")
    try:
        return json.loads(raw)
    except Exception:
        return {}


def save_catalog_overrides(db: Session, company_id: int, data: dict) -> None:
    import json
    set_setting(db, company_id, "catalog_overrides", json.dumps(data, ensure_ascii=False))


def get_postventa_config(db: Session, company_id: int) -> dict:
    return {
        "enabled": get_setting(db, company_id, "pv_enabled", "false").lower() == "true",
        "days_after": int(get_setting(db, company_id, "pv_days_after", "3") or "3"),
        "message": get_setting(db, company_id, "pv_message",
            "Hola *{nombre}* 🌿 esperamos que estés disfrutando tu compra. "
            "¿Cómo te ha ido? Tu opinión nos ayuda muchísimo 💚"),
        "review_link": get_setting(db, company_id, "pv_review_link", ""),
        # incentive: ninguno | descuento_7 | envio_gratis | personalizado
        "incentive": get_setting(db, company_id, "pv_incentive", "descuento_7"),
        "incentive_custom": get_setting(db, company_id, "pv_incentive_custom", ""),
        # Plantilla de Meta para enviar fuera de la ventana de 24h.
        # Si está vacío usa texto libre (solo funciona dentro de las 24h).
        "template_name": get_setting(db, company_id, "pv_template_name", ""),
        "template_lang": get_setting(db, company_id, "pv_template_lang", "es"),
        # Plantilla para los recordatorios de recontacto ("vuelvo en X días")
        "recontacto_template": get_setting(db, company_id, "pv_recontacto_template", ""),
    }


def save_postventa_config(db: Session, company_id: int, **fields) -> None:
    mapping = {
        "enabled": ("pv_enabled", lambda v: "true" if v else "false"),
        "days_after": ("pv_days_after", lambda v: str(int(v))),
        "message": ("pv_message", str),
        "review_link": ("pv_review_link", str),
        "incentive": ("pv_incentive", str),
        "incentive_custom": ("pv_incentive_custom", str),
        "template_name": ("pv_template_name", str),
        "template_lang": ("pv_template_lang", str),
        "recontacto_template": ("pv_recontacto_template", str),
    }
    for key, value in fields.items():
        if key in mapping and value is not None:
            setting_key, conv = mapping[key]
            set_setting(db, company_id, setting_key, conv(value))


def orders_pending_followup(db: Session, company_id: int, days_after: int) -> list[Order]:
    """Pedidos pagados con más de `days_after` días y sin seguimiento postventa enviado."""
    cutoff = datetime.utcnow() - timedelta(days=days_after)
    sent_order_ids = {f.order_id for f in db.query(Followup).filter(Followup.kind == "postventa").all()}
    paid = (
        db.query(Order)
        .filter(Order.company_id == company_id, Order.status == "paid", Order.updated_at <= cutoff)
        .all()
    )
    return [o for o in paid if o.id not in sent_order_ids]


def mark_followup(db: Session, company_id: int, order_id: int, customer_id: int, kind: str = "postventa") -> None:
    db.add(Followup(company_id=company_id, order_id=order_id, customer_id=customer_id, kind=kind))
    db.commit()


def _load_training_default(business_type: str = "otro") -> str:
    """Plantilla de entrenamiento por defecto según el tipo de negocio (ver
    app/onboarding_templates.py). Se usa solo si la empresa aún no escribió nada propio."""
    from app.onboarding_templates import get_default_training
    return get_default_training(business_type)


def get_quick_replies(db: Session, company_id: int) -> list:
    """Respuestas rápidas (plantillas de texto) para uso del asesor humano."""
    import json
    raw = get_setting(db, company_id, "quick_replies", "")
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_quick_replies(db: Session, company_id: int, items: list) -> None:
    import json
    clean = []
    for it in items or []:
        title = (it.get("title") or "").strip()
        text = (it.get("text") or "").strip()
        if title and text:
            clean.append({"title": title[:60], "text": text[:1500]})
    set_setting(db, company_id, "quick_replies", json.dumps(clean, ensure_ascii=False))


def get_bot_name(db: Session, company_id: int) -> str:
    """Nombre con el que el bot se presenta (editable desde el panel)."""
    return get_setting(db, company_id, "bot_name", "Asistente") or "Asistente"


def save_bot_name(db: Session, company_id: int, name: str) -> None:
    set_setting(db, company_id, "bot_name", (name or "").strip() or "Asistente")


# ─── Pausa global del bot ──────────────────────────────────────────────────────

def get_bot_paused(db: Session, company_id: int) -> bool:
    """Si está en True, el bot NO responde automáticamente (se atiende solo a mano)."""
    return get_setting(db, company_id, "bot_paused", "false").lower() == "true"


def set_bot_paused(db: Session, company_id: int, paused: bool) -> None:
    set_setting(db, company_id, "bot_paused", "true" if paused else "false")


# ─── Notificaciones al administrador ───────────────────────────────────────────

def get_notif_config(db: Session, company_id: int) -> dict:
    import json
    raw = get_setting(db, company_id, "notif_config", "")
    cfg = {"email": "", "whatsapp": "", "new_client": True, "returning": False,
           "sale": True, "card": True, "smtp_user": "", "smtp_pass": "",
           "smtp_host": "", "smtp_port": "", "resend_api_key": ""}
    if raw:
        try:
            cfg.update(json.loads(raw))
        except Exception:
            pass
    return cfg


def save_notif_config(db: Session, company_id: int, cfg: dict) -> None:
    import json
    cur = get_notif_config(db, company_id)
    keys = ("email", "whatsapp", "new_client", "returning", "sale", "card",
            "smtp_user", "smtp_pass", "smtp_host", "smtp_port", "resend_api_key")
    for k in keys:
        if k in cfg:
            cur[k] = cfg[k]
    set_setting(db, company_id, "notif_config", json.dumps(cur, ensure_ascii=False))


def get_training_notes(db: Session, company_id: int) -> str:
    """Directrices de entrenamiento editables desde el panel (inyectadas en el prompt)."""
    saved = get_setting(db, company_id, "training_notes", "")
    if saved:
        return saved
    company = get_company(db, company_id)
    return _load_training_default(company.business_type if company else "otro")


def save_training_notes(db: Session, company_id: int, text: str) -> None:
    set_setting(db, company_id, "training_notes", text or "")


def get_promo_config(db: Session, company_id: int) -> dict:
    """Config de la campaña de promoción/marketing, editable desde el panel."""
    return {
        "message": get_setting(db, company_id, "promo_message",
            "Hola *{nombre}* 🌿 tenemos novedades para ti. "
            "Por ser cliente tienes un beneficio especial en tu próxima compra. ¿Quieres que te cuente? 💚"),
        "template_name": get_setting(db, company_id, "promo_template_name", ""),
        "template_lang": get_setting(db, company_id, "promo_template_lang", "es"),
    }


def save_promo_config(db: Session, company_id: int, **fields) -> None:
    mapping = {
        "message": ("promo_message", str),
        "template_name": ("promo_template_name", str),
        "template_lang": ("promo_template_lang", str),
    }
    for key, value in fields.items():
        if key in mapping and value is not None:
            setting_key, conv = mapping[key]
            set_setting(db, company_id, setting_key, conv(value))


def get_qr_config(db: Session, company_id: int) -> dict:
    """Return QR payment configuration from the database."""
    return {
        "enabled": get_setting(db, company_id, "qr_enabled", "false").lower() == "true",
        "media_id": get_setting(db, company_id, "qr_media_id", ""),
        "caption": get_setting(db, company_id, "qr_caption",
            "Aquí están nuestros datos de pago. Una vez realizada la transferencia, envíanos el comprobante. 🌿"),
        "filename": get_setting(db, company_id, "qr_filename", ""),
        "preview_b64": get_setting(db, company_id, "qr_preview_b64", ""),
    }


def save_qr_config(db: Session, company_id: int, enabled: bool, media_id: str = "", caption: str = "",
                   filename: str = "", preview_b64: str = "") -> None:
    set_setting(db, company_id, "qr_enabled", "true" if enabled else "false")
    if media_id:
        set_setting(db, company_id, "qr_media_id", media_id)
    if caption:
        set_setting(db, company_id, "qr_caption", caption)
    if filename:
        set_setting(db, company_id, "qr_filename", filename)
    if preview_b64:
        set_setting(db, company_id, "qr_preview_b64", preview_b64)


# ─── Orders ───────────────────────────────────────────────────────────────────

def create_order(
    db: Session,
    company_id: int,
    customer_id: int,
    conversation_id: int,
    items: list[dict],
    subtotal: float | None = None,
    shipping_cost: float | None = None,
    total: float | None = None,
    payment_method: str | None = None,
    shipping_city: str | None = None,
    status: str = "pending",
) -> Order:
    """Crear un pedido en la BD. items = [{'name': X, 'quantity': N}, ...]"""
    import json
    order = Order(
        company_id=company_id,
        customer_id=customer_id,
        conversation_id=conversation_id,
        items_json=json.dumps(items, ensure_ascii=False),
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        total=total,
        payment_method=payment_method,
        shipping_city=shipping_city,
        status=status,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_latest_order_for_conversation(db: Session, conversation_id: int) -> Order | None:
    return (
        db.query(Order)
        .filter(Order.conversation_id == conversation_id)
        .order_by(Order.created_at.desc())
        .first()
    )


def get_last_order_for_customer(db: Session, customer_id: int) -> Order | None:
    return (
        db.query(Order)
        .filter(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
        .first()
    )


def mark_order_paid(db: Session, conversation_id: int) -> Order | None:
    """Marcar el pedido más reciente de la conversación como pagado (venta cerrada)."""
    order = get_latest_order_for_conversation(db, conversation_id)
    if order:
        order.status = "paid"
        order.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
    return order


# ─── Payment Receipts (Comprobantes) ──────────────────────────────────────────

def save_receipt(
    db: Session,
    company_id: int,
    customer_id: int,
    conversation_id: int,
    image_b64: str | None = None,
    mime_type: str = "image/jpeg",
    bank: str | None = None,
    amount: int | None = None,
    reference: str | None = None,
    receipt_date: str | None = None,
    is_valid: bool = False,
    order_id: int | None = None,
) -> PaymentReceipt:
    r = PaymentReceipt(
        company_id=company_id, customer_id=customer_id, conversation_id=conversation_id, order_id=order_id,
        image_b64=image_b64, mime_type=mime_type, bank=bank, amount=amount,
        reference=reference, receipt_date=receipt_date, is_valid=is_valid,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def list_receipts(db: Session, company_id: int, customer_id: int | None = None, limit: int = 200) -> list[PaymentReceipt]:
    q = db.query(PaymentReceipt).filter(PaymentReceipt.company_id == company_id)
    if customer_id:
        q = q.filter(PaymentReceipt.customer_id == customer_id)
    return q.order_by(PaymentReceipt.created_at.desc()).limit(limit).all()


def receipt_metrics(db: Session, company_id: int) -> dict:
    receipts = db.query(PaymentReceipt).filter(PaymentReceipt.company_id == company_id).all()
    validos = [r for r in receipts if r.is_valid]
    return {
        "total_recibidos": len(receipts),
        "total_validos": len(validos),
        "valor_total_validado": sum(r.amount or 0 for r in validos),
    }


# ─── Customer Tags (Etiquetas) ────────────────────────────────────────────────

def add_customer_tag(db: Session, company_id: int, customer_id: int, tag: str, color: str = "p") -> CustomerTag | None:
    tag = (tag or "").strip()
    if not tag:
        return None
    exists = (
        db.query(CustomerTag)
        .filter(CustomerTag.customer_id == customer_id, CustomerTag.tag == tag)
        .first()
    )
    if exists:
        return exists
    row = CustomerTag(company_id=company_id, customer_id=customer_id, tag=tag, color=color)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def remove_customer_tag(db: Session, customer_id: int, tag: str) -> None:
    db.query(CustomerTag).filter(
        CustomerTag.customer_id == customer_id, CustomerTag.tag == tag
    ).delete()
    db.commit()


def get_customer_tags(db: Session, customer_id: int) -> list[CustomerTag]:
    return db.query(CustomerTag).filter(CustomerTag.customer_id == customer_id).all()


def list_all_tags(db: Session, company_id: int) -> list[dict]:
    """Lista de etiquetas únicas con su conteo de clientes, de una empresa."""
    rows = db.query(CustomerTag).filter(CustomerTag.company_id == company_id).all()
    counts: dict[str, dict] = {}
    for r in rows:
        key = r.tag
        if key not in counts:
            counts[key] = {"tag": r.tag, "color": r.color, "count": 0}
        counts[key]["count"] += 1
    return sorted(counts.values(), key=lambda x: x["count"], reverse=True)


# ─── Segmentación de clientes ──────────────────────────────────────────────────
# El bot clasifica al cliente según lo que necesita. Se guarda como una etiqueta
# especial (prefijo 'seg:') para poder listarla aparte de las etiquetas manuales.
# Los segmentos por defecto son genéricos; cada tipo de negocio puede tener los suyos
# (ver app/onboarding_templates.py) — aquí se mantienen 3 genéricos de referencia.
SEGMENTS = {
    "interesado": "Interesado",
    "recurrente": "Cliente recurrente",
    "vip": "VIP",
}
_SEG_PREFIX = "seg:"


def _norm_segment(value: str) -> str | None:
    """Mapea texto libre del bot a una clave de segmento (acepta cualquier clave que
    el negocio haya definido, no solo las 3 genéricas de referencia)."""
    v = (value or "").strip().lower()
    if not v:
        return None
    return v


def set_customer_segment(db: Session, company_id: int, customer_id: int, value: str) -> str | None:
    """Asigna el segmento del cliente (único). Devuelve la clave asignada o None."""
    key = _norm_segment(value)
    if not key:
        return None
    # quitar cualquier segmento anterior
    db.query(CustomerTag).filter(
        CustomerTag.customer_id == customer_id,
        CustomerTag.tag.like(f"{_SEG_PREFIX}%"),
    ).delete(synchronize_session=False)
    db.add(CustomerTag(company_id=company_id, customer_id=customer_id, tag=f"{_SEG_PREFIX}{key}", color="g"))
    db.commit()
    return key


def get_customer_segment(db: Session, customer_id: int) -> str | None:
    row = (
        db.query(CustomerTag)
        .filter(CustomerTag.customer_id == customer_id, CustomerTag.tag.like(f"{_SEG_PREFIX}%"))
        .first()
    )
    if not row:
        return None
    return row.tag[len(_SEG_PREFIX):]


def list_segmented_customers(db: Session, company_id: int) -> dict:
    """Devuelve los clientes agrupados por segmento, para la categoría 'Segmentación'."""
    rows = (
        db.query(CustomerTag)
        .filter(CustomerTag.company_id == company_id, CustomerTag.tag.like(f"{_SEG_PREFIX}%"))
        .all()
    )
    by_cust = {r.customer_id: r.tag[len(_SEG_PREFIX):] for r in rows}
    out: dict[str, list] = {}
    if not by_cust:
        return {"segments": SEGMENTS, "groups": out}
    customers = db.query(Customer).filter(Customer.id.in_(list(by_cust.keys()))).all()
    for c in customers:
        key = by_cust.get(c.id)
        out.setdefault(key, [])
        out[key].append({
            "id": c.id, "name": c.name or "", "phone_number": c.phone_number,
            "city": c.city or "",
        })
    return {"segments": SEGMENTS, "groups": out}


# ─── Citas / Reservas (agendadas por el bot o manualmente) ─────────────────────

def create_appointment(
    db: Session,
    company_id: int,
    scheduled_at: datetime,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    service: str | None = None,
    notes: str | None = None,
    source: str = "manual",
    customer_id: int | None = None,
    conversation_id: int | None = None,
    status: str = "pending",
) -> Appointment:
    a = Appointment(
        company_id=company_id, scheduled_at=scheduled_at, customer_name=customer_name,
        customer_phone=customer_phone, service=service, notes=notes, source=source,
        customer_id=customer_id, conversation_id=conversation_id, status=status,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def list_appointments(db: Session, company_id: int, upcoming_only: bool = False) -> list[Appointment]:
    q = db.query(Appointment).filter(Appointment.company_id == company_id)
    if upcoming_only:
        q = q.filter(Appointment.scheduled_at >= datetime.utcnow(), Appointment.status != "cancelled")
    return q.order_by(Appointment.scheduled_at.asc()).all()


def set_appointment_status(db: Session, company_id: int, appointment_id: int, status: str) -> Appointment | None:
    a = db.query(Appointment).filter(Appointment.id == appointment_id, Appointment.company_id == company_id).first()
    if a:
        a.status = status
        db.commit()
        db.refresh(a)
    return a


def delete_appointment(db: Session, company_id: int, appointment_id: int) -> bool:
    n = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.company_id == company_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return n > 0