"""Notificaciones al ADMINISTRADOR de una empresa (para monitorear): nuevo cliente,
venta cerrada, etc.

Se envían por los canales configurados en el panel de ESA empresa:
- Email (canal confiable, vía Resend).
- WhatsApp a un número que elijas (best-effort: WhatsApp solo permite escribir libre a
  un número si ese número le escribió al bot en las últimas 24h; por eso el email es
  el canal garantizado).
"""
import logging
from app.db import crud
from app.email_service import notify_admin_email

logger = logging.getLogger(__name__)


def _emails(company, cfg: dict) -> list[str]:
    raw = (cfg.get("email") or "").strip() or (company.notification_email if company else "") or ""
    return [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]


def _phones(cfg: dict) -> list[str]:
    raw = (cfg.get("whatsapp") or "").strip()
    return [p.strip().lstrip("+") for p in raw.replace(";", ",").split(",") if p.strip()]


_tasks: set = set()


async def notify_event(company_id: int, subject: str, lines: list[str], event: str) -> None:
    """Notifica al administrador de UNA empresa según su configuración y el tipo de
    evento ('new_client' | 'returning' | 'sale' | 'card'). Abre su propia sesión de BD."""
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        company = crud.get_company(db, company_id)
        if not company:
            return
        cfg = crud.get_notif_config(db, company_id)
        if not cfg.get(event, False):
            return  # ese evento está desactivado
        body = "\n".join(lines)
        for email in _emails(company, cfg):
            try:
                notify_admin_email(company_id, email, subject, lines)
            except Exception as exc:
                logger.error("No se pudo notificar por email a %s: %s", email, exc)
        phones = _phones(cfg)
        if phones:
            from app.whatsapp.client import send_text_message, WhatsAppCreds
            creds = WhatsAppCreds(phone_number_id=company.whatsapp_phone_number_id,
                                  access_token=company.whatsapp_access_token)
            wa_text = f"{subject}\n\n{body}"
            for ph in phones:
                try:
                    await send_text_message(creds, ph, wa_text)
                except Exception as exc:
                    logger.error("No se pudo notificar por WhatsApp a %s: %s", ph, exc)
    finally:
        db.close()


def schedule(company_id: int, subject: str, lines: list[str], event: str) -> None:
    """Dispara la notificación en segundo plano (no bloquea la respuesta al cliente)."""
    import asyncio
    try:
        task = asyncio.create_task(notify_event(company_id, subject, lines, event))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    except RuntimeError:
        # Sin event loop (contexto síncrono): ejecutar de forma directa best-effort
        pass