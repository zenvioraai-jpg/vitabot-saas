from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, Float, ForeignKey, Index, LargeBinary, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


class Company(Base):
    """Una empresa cliente del SaaS (tenant). Cada una tiene su propio número de WhatsApp
    y sus propios datos, completamente aislados del resto."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    business_type: Mapped[str] = mapped_column(String, default="otro")
    whatsapp_phone_number_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    whatsapp_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_verify_token: Mapped[str] = mapped_column(String, default="")
    admin_token: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    notification_email: Mapped[str | None] = mapped_column(String)
    resend_api_key: Mapped[str | None] = mapped_column(String)
    claude_model: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="onboarding")  # onboarding | active | paused
    extra_config: Mapped[str] = mapped_column(Text, default="{}")      # JSON: campos extra por tipo de negocio
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("company_id", "phone_number", name="uq_customer_company_phone"),
        Index("idx_customers_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    cedula: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    preferred_language: Mapped[str] = mapped_column(String, default="es")  # 'es' | 'en' | 'pt'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="customer")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_company_phone", "company_id", "phone_number"),
        Index("idx_conversations_mode", "mode"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, default="ai")           # 'ai' | 'human'
    status: Mapped[str] = mapped_column(String, default="open")       # 'open' | 'resolved'
    assigned_to: Mapped[str | None] = mapped_column(String)
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.timestamp")
    orders: Mapped[list["Order"]] = relationship(back_populates="conversation")
    advisor_sessions: Mapped[list["AdvisorSession"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_conversation", "conversation_id"),
        Index("idx_messages_wa_id", "company_id", "wa_message_id"),
        UniqueConstraint("company_id", "wa_message_id", name="uq_message_company_wa_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    wa_message_id: Mapped[str | None] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, nullable=False)    # 'inbound' | 'outbound'
    sender: Mapped[str] = mapped_column(String, nullable=False)       # 'customer' | 'ai' | 'human_advisor'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("idx_orders_company", "company_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft")
    items_json: Mapped[str] = mapped_column(Text, nullable=False)
    subtotal: Mapped[float | None] = mapped_column(Float)
    shipping_cost: Mapped[float | None] = mapped_column(Float)
    total: Mapped[float | None] = mapped_column(Float)
    shipping_city: Mapped[str | None] = mapped_column(String)
    payment_method: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    conversation: Mapped["Conversation"] = relationship(back_populates="orders")


class AdvisorSession(Base):
    __tablename__ = "advisor_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    advisor_name: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    handback_reason: Mapped[str | None] = mapped_column(Text)

    conversation: Mapped["Conversation"] = relationship(back_populates="advisor_sessions")


class BotSetting(Base):
    """Key-value store de configuración del bot, por empresa (survives deploys)."""
    __tablename__ = "bot_settings"
    __table_args__ = (UniqueConstraint("company_id", "key", name="uq_bot_setting_company_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CustomerTag(Base):
    """Etiquetas asignadas a un cliente (ej: VIP, Oncológico, Mayorista)."""
    __tablename__ = "customer_tags"
    __table_args__ = (Index("idx_customer_tags_customer", "customer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    tag: Mapped[str] = mapped_column(String, nullable=False)
    color: Mapped[str] = mapped_column(String, default="p")  # clave de color en el panel
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentReceipt(Base):
    """Comprobante de pago enviado por un cliente (imagen + datos extraídos)."""
    __tablename__ = "payment_receipts"
    __table_args__ = (Index("idx_receipts_customer", "customer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("orders.id"))
    image_b64: Mapped[str | None] = mapped_column(Text)       # imagen del comprobante (base64)
    mime_type: Mapped[str] = mapped_column(String, default="image/jpeg")
    bank: Mapped[str | None] = mapped_column(String)
    amount: Mapped[int | None] = mapped_column(Integer)
    reference: Mapped[str | None] = mapped_column(String)
    receipt_date: Mapped[str | None] = mapped_column(String)  # fecha/hora tal como aparece en el comprobante
    is_valid: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Coupon(Base):
    """Cupón / descuento gestionable desde el panel."""
    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("company_id", "code", name="uq_coupon_company_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="percent")  # percent | fixed | free_shipping
    value: Mapped[int] = mapped_column(Integer, default=0)        # % o monto en COP
    active: Mapped[bool] = mapped_column(default=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=0)     # 0 = ilimitado
    uses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ShippingGuide(Base):
    """Guía de transportadora para rastrear un pedido."""
    __tablename__ = "shipping_guides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_phone: Mapped[str | None] = mapped_column(String)
    customer_name: Mapped[str | None] = mapped_column(String)
    carrier: Mapped[str] = mapped_column(String, default="")        # Coordinadora, Servientrega...
    guide_number: Mapped[str] = mapped_column(String, default="")
    tracking_link: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Contact(Base):
    """Contacto de proveedor o distribuidor."""
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, default="")
    kind: Mapped[str] = mapped_column(String, default="proveedor")  # proveedor | distribuidor
    company: Mapped[str | None] = mapped_column(String)
    phone: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PaymentReceived(Base):
    """Marca que el pago de un pedido (ej: contra entrega) fue efectivamente recibido."""
    __tablename__ = "payments_received"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Followup(Base):
    """Registro de seguimiento postventa enviado a un cliente."""
    __tablename__ = "followups"
    __table_args__ = (Index("idx_followups_order", "order_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String, default="postventa")  # 'postventa' | 'resena'
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MediaBlob(Base):
    """Archivo (foto/video) de un producto guardado dentro de la BD, por empresa.

    Guardar los bytes aquí (no solo el media_id de WhatsApp, que caduca) permite
    previsualizarlos en el panel y re-subirlos a WhatsApp al enviar, sin que falle nunca.
    """
    __tablename__ = "media_blobs"
    __table_args__ = (Index("idx_media_blobs_company_sku_kind", "company_id", "sku", "kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)   # 'image' | 'video'
    mime: Mapped[str] = mapped_column(String, default="image/jpeg")
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Reminder(Base):
    """Recordatorio de recontacto: el cliente dijo que volvería en X días.
    Si no escribe para esa fecha, el bot le recuerda lo pendiente."""
    __tablename__ = "reminders"
    __table_args__ = (Index("idx_reminders_due", "due_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id"), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)        # qué quedó pendiente
    status: Mapped[str] = mapped_column(String, default="pending")  # pending | sent | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Product(Base):
    """Catálogo de productos/servicios de una empresa (reemplaza el catalog/products.json
    de un solo archivo compartido: cada empresa tiene su propio catálogo en la BD)."""
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "sku", name="uq_product_company_sku"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    data_json: Mapped[str] = mapped_column(Text, default="{}")  # campos libres (variantes, tallas, etc.)
    in_stock: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)