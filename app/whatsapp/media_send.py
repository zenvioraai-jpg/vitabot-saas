"""Envío CONFIABLE de la foto/video de un producto.

Misma idea que la imagen del QR (que sí se envía sin problemas): tomar el archivo
guardado y mandarlo por WhatsApp. Para que NUNCA falle por un media_id caducado,
re-subimos el archivo guardado en la BD y obtenemos un media_id FRESCO justo antes
de enviarlo. Este módulo lo usan tanto el bot como el modo humano.

Multi-tenant: cada función recibe `company_id` (para leer/guardar la config e imagen
de LA empresa dueña del bot) y `creds` (WhatsAppCreds de esa misma empresa, para saber
por qué número/token se envía).
"""
import logging
from app.db import crud
from app.runtime import public_base
from app.whatsapp.client import (
    WhatsAppCreds,
    upload_media_to_whatsapp,
    send_image_by_id,
    send_image_by_url,
    send_image_message,
    send_video_by_id,
    send_video_by_url,
    send_text_message,
)

logger = logging.getLogger(__name__)


def _media_url(company_id: int, sku: str, kind: str) -> str:
    """URL pública (sin token) del archivo guardado, para que WhatsApp lo descargue."""
    base = public_base()
    return f"{base}/media/{company_id}/{sku}/{kind}" if base else ""


async def _fresh_media_id(db, company_id: int, creds: WhatsAppCreds, sku: str, kind: str) -> str | None:
    """Re-sube a WhatsApp el archivo guardado en la BD y devuelve un media_id fresco
    (que no caduca porque acaba de subirse). Actualiza también la config para reusarlo."""
    blob = crud.get_media_blob(db, company_id, sku, kind)
    if not blob:
        return None
    content, mime = blob
    ext = "mp4" if kind == "video" else ("png" if "png" in (mime or "") else "jpg")
    new_id = await upload_media_to_whatsapp(creds, content, mime or "image/jpeg", f"{sku}.{ext}")
    if new_id:
        key = "image_media_id" if kind == "image" else "video_media_id"
        cfg = crud.get_product_media(db, company_id)
        cfg.setdefault(sku, {})[key] = new_id
        crud.save_product_media(db, company_id, cfg)
    return new_id


async def send_product_photo(db, company_id: int, creds: WhatsAppCreds, phone_number: str,
                             sku: str, caption: str = "") -> bool:
    """Envía la foto del producto de la forma más confiable posible.
    Orden: 1) URL PÚBLICA del archivo (WhatsApp la descarga; método más fiable),
           2) media_id fresco re-subido desde la BD, 3) media_id guardado, 4) URL externa."""
    item = crud.get_product_media(db, company_id).get(sku, {})
    has_blob = crud.get_media_blob(db, company_id, sku, "image") is not None
    url = _media_url(company_id, sku, "image")
    if has_blob and url and await send_image_by_url(creds, phone_number, url, caption=caption):
        return True
    mid = await _fresh_media_id(db, company_id, creds, sku, "image")
    if mid and await send_image_by_id(creds, phone_number, mid, caption=caption):
        return True
    stored = item.get("image_media_id")
    if stored and stored != mid and await send_image_by_id(creds, phone_number, stored, caption=caption):
        return True
    if item.get("image_url"):
        return await send_image_message(creds, phone_number, image_url=item["image_url"], caption=caption)
    logger.error("No se pudo enviar la foto del producto %s (sin archivo guardado ni media_id válido)", sku)
    return False


async def test_send_product_media(db, company_id: int, creds: WhatsAppCreds, phone_number: str,
                                  sku: str, kind: str) -> tuple[bool, str]:
    """Envía una prueba REAL (foto o video) a un número de WhatsApp, devolviendo el motivo
    exacto si falla. Se usa desde el panel (categoría Multimedia) para poder diagnosticar
    por qué un envío no llega (sin archivo subido, número no autorizado, token vencido, etc.),
    en vez de que el envío falle en silencio dentro de una conversación real."""
    from app.whatsapp.client import send_image_by_url_with_result, send_video_by_url_with_result
    if crud.get_media_blob(db, company_id, sku, kind) is None:
        return False, "Este producto no tiene foto/video subido en Multimedia todavía."
    url = _media_url(company_id, sku, kind)
    if not url:
        return False, "No se pudo resolver la URL pública del servidor (revisa PUBLIC_BASE_URL en Railway)."
    if kind == "image":
        ok, err = await send_image_by_url_with_result(creds, phone_number, url, caption="📷 Prueba de Multimedia")
    else:
        ok, err = await send_video_by_url_with_result(creds, phone_number, url, caption="🎬 Prueba de Multimedia")
    if ok:
        return True, f"Enviado correctamente a +{phone_number}."
    return False, err or "WhatsApp rechazó el envío por un motivo desconocido."


async def send_product_video(db, company_id: int, creds: WhatsAppCreds, phone_number: str,
                             sku: str, caption: str = "Así se usa 🌿") -> bool:
    """Envía el video del producto (mismo criterio confiable que la foto)."""
    item = crud.get_product_media(db, company_id).get(sku, {})
    has_blob = crud.get_media_blob(db, company_id, sku, "video") is not None
    url = _media_url(company_id, sku, "video")
    if has_blob and url and await send_video_by_url(creds, phone_number, url, caption=caption):
        return True
    mid = await _fresh_media_id(db, company_id, creds, sku, "video")
    if mid and await send_video_by_id(creds, phone_number, mid, caption=caption):
        return True
    stored = item.get("video_media_id")
    if stored and stored != mid and await send_video_by_id(creds, phone_number, stored, caption=caption):
        return True
    if item.get("video_url"):
        return await send_text_message(creds, phone_number, f"🎥 Cómo se usa: {item['video_url']}")
    logger.error("No se pudo enviar el video del producto %s", sku)
    return False