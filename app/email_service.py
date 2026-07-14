import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def _company_row(company_id: int | None):
    if not company_id:
        return None
    from app.db.database import SessionLocal
    from app.db import crud
    db = SessionLocal()
    try:
        return crud.get_company(db, company_id)
    finally:
        db.close()


def _resend_api_key(company_id: int | None) -> str:
    """API key de Resend: primero la de la empresa (panel), si no hay usa la de
    plataforma (RESEND_API_KEY). Railway bloquea los puertos SMTP salientes
    (587/465/25), así que el correo se envía por HTTP (Resend) en vez de SMTP directo."""
    company = _company_row(company_id)
    if company and (company.resend_api_key or "").strip():
        return company.resend_api_key.strip()
    return (settings.resend_api_key or "").strip()


def _from_name(company_id: int | None) -> str:
    company = _company_row(company_id)
    return (company.name if company and company.name else settings.email_from_name) or "VitaBot"


def _send_via_resend(to_email: str, subject: str, html: str, text: str, api_key: str, from_name: str) -> tuple[bool, str]:
    from_addr = f"{from_name} <onboarding@resend.dev>"
    payload = {"from": from_addr, "to": [to_email], "subject": subject, "html": html, "text": text}
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=15,
        )
        if r.status_code in (200, 201, 202):
            return True, ""
        return False, f"Resend rechazó el correo ({r.status_code}): {r.text[:250]}"
    except Exception as exc:
        return False, f"error de red con Resend: {exc}"


def _send_raw(company_id: int | None, to_email: str, subject: str, html: str, text: str) -> tuple[bool, str]:
    """Envía el correo y devuelve (ok, motivo_de_error). Usa Resend (HTTP, puerto 443)."""
    if not to_email:
        return False, "No hay correo destino configurado."
    api_key = _resend_api_key(company_id)
    from_name = _from_name(company_id)
    if api_key:
        return _send_via_resend(to_email, subject, html, text, api_key, from_name)
    return False, ("Falta configurar la API key de Resend. Ponla en Configuración → Notificaciones.")


def _send(company_id: int | None, to_email: str, subject: str, html: str, text: str) -> bool:
    ok, _ = _send_raw(company_id, to_email, subject, html, text)
    return ok


def send_test_email(company_id: int, to_email: str) -> tuple[bool, str]:
    """Envía un correo de prueba y devuelve (ok, mensaje) para mostrar en el panel."""
    lines = [
        "✅ ¡Las notificaciones por correo funcionan!",
        "Recibirás avisos de nuevos clientes, clientes que regresan, ventas cerradas y pagos con tarjeta.",
    ]
    from_name = _from_name(company_id)
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
    <body style="font-family:-apple-system,sans-serif;background:#f9fafb;margin:0;padding:20px">
    <div style="max-width:560px;margin:0 auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
      {_header_html("Correo de prueba", from_name)}
      <div style="padding:24px 32px">
        <div style="background:#f0fdf4;border-radius:8px;padding:16px">
          {''.join(f"<p style='margin:0 0 6px;color:#374151;font-size:14px'>{ln}</p>" for ln in lines)}
        </div>
      </div>
      {_footer_html(from_name)}
    </div></body></html>"""
    ok, err = _send_raw(company_id, to_email, "🔔 Correo de prueba", html, "\n".join(lines))
    return ok, ("Correo de prueba enviado correctamente." if ok else err)


def send_marketing_email(company_id: int, to_email: str, subject: str, body_text: str) -> bool:
    """Envío genérico para campañas de email marketing (texto simple con plantilla)."""
    from_name = _from_name(company_id)
    safe = body_text.replace("\n", "<br>")
    html = (
        "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'></head>"
        "<body style=\"font-family:-apple-system,sans-serif;background:#f9fafb;margin:0;padding:20px\">"
        "<div style='max-width:560px;margin:0 auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)'>"
        + _header_html(subject, from_name)
        + f"<div style='padding:28px 32px;color:#374151;font-size:15px;line-height:1.6'>{safe}</div>"
        + _footer_html(from_name)
        + "</div></body></html>"
    )
    return _send(company_id, to_email, subject, html, body_text)


def _header_html(title: str, from_name: str = "VitaBot") -> str:
    return f"""<div style="background:linear-gradient(135deg,#16a34a,#15803d);padding:28px 32px;text-align:center">
      <h1 style="color:white;margin:0;font-size:20px;font-weight:700">{from_name}</h1>
      <p style="color:rgba(255,255,255,0.85);margin:4px 0 0;font-size:13px">{title}</p>
    </div>"""


def _footer_html(from_name: str = "VitaBot") -> str:
    return f"""<div style="background:#f9fafb;padding:16px 32px;text-align:center;border-top:1px solid #e5e7eb">
      <p style="color:#6b7280;font-size:11px;margin:0">{from_name}</p>
    </div>"""


# ─── Email al CLIENTE: confirmación de pedido ─────────────────────────────────

def send_order_confirmation(company_id: int, to_email: str, customer_name: str, order_summary: str = "") -> bool:
    from_name = _from_name(company_id)
    name_first = customer_name.split()[0] if customer_name else "Cliente"
    order_block = f"""<div style="background:#f0fdf4;border-radius:8px;padding:14px 16px;margin:16px 0">
      <p style="margin:0;color:#374151;font-size:14px;white-space:pre-wrap">{order_summary}</p>
    </div>""" if order_summary else ""

    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
    <body style="font-family:-apple-system,sans-serif;background:#f9fafb;margin:0;padding:20px">
    <div style="max-width:560px;margin:0 auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
      {_header_html("Tu pedido está en proceso", from_name)}
      <div style="padding:28px 32px">
        <h2 style="color:#111827;margin:0 0 8px;font-size:19px">¡Gracias, {name_first}! 🌿</h2>
        <p style="color:#374151;line-height:1.6;margin:0 0 12px">
          Hemos recibido tu pedido. Nuestro equipo lo está procesando y pronto
          un asesor se comunicará contigo para confirmar el pago y coordinar el despacho.
        </p>
        {order_block}
      </div>
      {_footer_html(from_name)}
    </div></body></html>"""

    text = f"Hola {name_first},\n\nHemos recibido tu pedido.\n{order_summary}\n\nGracias por confiar en nosotros."
    return _send(company_id, to_email, f"Tu pedido en {from_name} está en proceso 🌿", html, text)


# ─── Email INTERNO: notificación genérica al administrador ────────────────────

def notify_admin_email(company_id: int, to_email: str, subject: str, lines: list[str]) -> bool:
    """Notificación al administrador (nuevo cliente, venta cerrada, etc.)."""
    from_name = _from_name(company_id)
    rows = "".join(
        f"<p style='margin:0 0 6px;color:#374151;font-size:14px'>{ln}</p>" for ln in lines
    )
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
    <body style="font-family:-apple-system,sans-serif;background:#f9fafb;margin:0;padding:20px">
    <div style="max-width:560px;margin:0 auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
      {_header_html(subject, from_name)}
      <div style="padding:24px 32px">
        <div style="background:#f0fdf4;border-radius:8px;padding:16px">{rows}</div>
      </div>
      {_footer_html(from_name)}
    </div></body></html>"""
    text = subject + "\n\n" + "\n".join(lines)
    return _send(company_id, to_email, subject, html, text)


# ─── Email INTERNO: nuevo pedido confirmado ───────────────────────────────────

def notify_new_order(company_id: int, phone_number: str, customer_name: str, order_data: str) -> bool:
    company = _company_row(company_id)
    to_email = (company.notification_email if company else "") or ""
    if not to_email:
        return False
    from_name = _from_name(company_id)
    subject = f"🛍️ Nuevo pedido — {customer_name or phone_number}"
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"></head>
    <body style="font-family:-apple-system,sans-serif;background:#f9fafb;margin:0;padding:20px">
    <div style="max-width:560px;margin:0 auto;background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08)">
      {_header_html("Nuevo pedido recibido", from_name)}
      <div style="padding:28px 32px">
        <h2 style="color:#111827;margin:0 0 16px;font-size:18px">🛍️ Nuevo pedido confirmado</h2>
        <div style="background:#f0fdf4;border-radius:8px;padding:16px;margin-bottom:16px">
          <p style="margin:0 0 8px;font-size:13px;color:#6b7280">CLIENTE</p>
          <p style="margin:0;font-weight:700;color:#111827">{customer_name or "Sin nombre"}</p>
          <p style="margin:4px 0 0;color:#374151">📱 {phone_number}</p>
        </div>
        <div style="background:#fff7ed;border-radius:8px;padding:16px">
          <p style="margin:0 0 8px;font-size:13px;color:#6b7280">DATOS DEL PEDIDO</p>
          <p style="margin:0;color:#374151;white-space:pre-wrap;font-size:14px">{order_data}</p>
        </div>
      </div>
      {_footer_html(from_name)}
    </div></body></html>"""
    text = f"Nuevo pedido\nCliente: {customer_name}\nTeléfono: {phone_number}\n\n{order_data}"
    return _send(company_id, to_email, subject, html, text)


def send_email_with_attachment(company_id: int, to_email: str, subject: str, body: str,
                               attachment_content: bytes, attachment_filename: str) -> bool:
    """Envía email con archivo adjunto (usado para Excel de reportes) vía Resend
    (adjuntos en base64), igual que el resto del correo — no SMTP directo."""
    import base64
    api_key = _resend_api_key(company_id)
    if not api_key or not to_email:
        logger.warning("No se pudo enviar email con adjunto: falta API key de Resend o destinatario.")
        return False
    from_name = _from_name(company_id)
    payload = {
        "from": f"{from_name} <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "text": body,
        "attachments": [{
            "filename": attachment_filename,
            "content": base64.b64encode(attachment_content).decode("ascii"),
        }],
    }
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload, timeout=30,
        )
        if r.status_code in (200, 201, 202):
            return True
        logger.error("Resend rechazó el email con adjunto (%s): %s", r.status_code, r.text[:250])
        return False
    except Exception as exc:
        logger.error("Error enviando email con adjunto a %s: %s", to_email, exc)
        return False