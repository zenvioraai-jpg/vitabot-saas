import base64
import logging
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)

_API_VERSION = "v19.0"


@dataclass(frozen=True)
class WhatsAppCreds:
    """Credenciales de WhatsApp de UNA empresa. Cada función de este módulo recibe esto
    en vez de leer constantes globales, para que 200+ empresas puedan enviar cada una
    con su propio número/token desde el mismo proceso."""
    phone_number_id: str
    access_token: str

    @property
    def api_url(self) -> str:
        return f"https://graph.facebook.com/{_API_VERSION}/{self.phone_number_id}/messages"

    @property
    def media_upload_url(self) -> str:
        return f"https://graph.facebook.com/{_API_VERSION}/{self.phone_number_id}/media"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    @property
    def media_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}


async def send_text_with_result(creds: WhatsAppCreds, phone_number: str, text: str) -> tuple[bool, str]:
    """Como send_text_message pero devuelve (ok, motivo_error) para campañas/diagnóstico."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": phone_number, "type": "text", "text": {"preview_url": True, "body": text},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            return True, ""
        except httpx.HTTPStatusError as exc:
            txt = exc.response.text
            if "131047" in txt or "24 hours" in txt or "re-engagement" in txt.lower():
                return False, "fuera de la ventana de 24h (requiere plantilla aprobada por Meta)"
            return False, f"WhatsApp rechazó el mensaje ({exc.response.status_code})"
        except httpx.RequestError as exc:
            return False, f"error de red: {exc}"


async def send_template_message(
    creds: WhatsAppCreds,
    phone_number: str,
    template_name: str,
    body_params: list[str] | None = None,
    language: str = "es",
) -> tuple[bool, str]:
    """Enviar una PLANTILLA aprobada por Meta.

    Las plantillas son la única forma de escribir a un cliente FUERA de la ventana
    de 24h (postventa a los 15 días, marketing, etc.). `body_params` son los valores
    para las variables {{1}}, {{2}}, ... del cuerpo, en orden.
    Devuelve (ok, motivo_error).
    """
    components = []
    if body_params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in body_params],
        })
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language},
            "components": components,
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Plantilla '%s' enviada a %s", template_name, phone_number)
            return True, ""
        except httpx.HTTPStatusError as exc:
            txt = exc.response.text
            logger.error("Error enviando plantilla '%s' a %s: %s — %s",
                         template_name, phone_number, exc.response.status_code, txt)
            if "132001" in txt or "does not exist" in txt.lower():
                return False, f"la plantilla '{template_name}' no existe o no está aprobada en Meta"
            if "132000" in txt or "number of parameters" in txt.lower():
                return False, "el número de variables no coincide con la plantilla aprobada"
            return False, f"WhatsApp rechazó la plantilla ({exc.response.status_code})"
        except httpx.RequestError as exc:
            return False, f"error de red: {exc}"


async def send_text_message(creds: WhatsAppCreds, phone_number: str, text: str) -> bool:
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "text",
        "text": {"preview_url": True, "body": text},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Texto enviado a %s", phone_number)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Error enviando texto a %s: %s — %s", phone_number, exc.response.status_code, exc.response.text)
            return False
        except httpx.RequestError as exc:
            logger.error("Error de red enviando texto a %s: %s", phone_number, exc)
            return False


async def send_image_by_url(creds: WhatsAppCreds, phone_number: str, image_url: str, caption: str = "") -> bool:
    """Send an image using a public URL."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "image",
        "image": {"link": image_url, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Imagen (URL) enviada a %s", phone_number)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Error enviando imagen (URL) a %s: %s — %s", phone_number, exc.response.status_code, exc.response.text)
            return False
        except httpx.RequestError as exc:
            logger.error("Error de red enviando imagen a %s: %s", phone_number, exc)
            return False


async def send_image_by_id(creds: WhatsAppCreds, phone_number: str, media_id: str, caption: str = "") -> bool:
    """Send an image using a WhatsApp media_id (previously uploaded)."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "image",
        "image": {"id": media_id, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Imagen (media_id) enviada a %s", phone_number)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Error enviando imagen (id) a %s: %s — %s", phone_number, exc.response.status_code, exc.response.text)
            return False
        except httpx.RequestError as exc:
            logger.error("Error de red enviando imagen a %s: %s", phone_number, exc)
            return False


async def send_image_by_url_with_result(creds: WhatsAppCreds, phone_number: str, image_url: str,
                                        caption: str = "") -> tuple[bool, str]:
    """Como send_image_by_url pero devuelve (ok, motivo_error) para diagnóstico desde el panel."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": phone_number, "type": "image", "image": {"link": image_url, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            return True, ""
        except httpx.HTTPStatusError as exc:
            return False, f"WhatsApp rechazó la imagen ({exc.response.status_code}): {exc.response.text[:250]}"
        except httpx.RequestError as exc:
            return False, f"error de red: {exc}"


async def send_video_by_url_with_result(creds: WhatsAppCreds, phone_number: str, video_url: str,
                                        caption: str = "") -> tuple[bool, str]:
    """Como send_video_by_url pero devuelve (ok, motivo_error) para diagnóstico desde el panel."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": phone_number, "type": "video", "video": {"link": video_url, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            return True, ""
        except httpx.HTTPStatusError as exc:
            return False, f"WhatsApp rechazó el video ({exc.response.status_code}): {exc.response.text[:250]}"
        except httpx.RequestError as exc:
            return False, f"error de red: {exc}"


async def send_image_message(creds: WhatsAppCreds, phone_number: str, image_url: str = "", caption: str = "",
                              media_id: str = "") -> bool:
    """Send image using media_id if provided, otherwise use URL."""
    if media_id:
        return await send_image_by_id(creds, phone_number, media_id, caption)
    return await send_image_by_url(creds, phone_number, image_url, caption)


async def upload_image_to_whatsapp(creds: WhatsAppCreds, image_bytes: bytes, mime_type: str, filename: str) -> str | None:
    """
    Upload an image to WhatsApp servers and return the media_id.
    The media_id can be reused to send the image multiple times.
    Returns None on failure.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            files = {
                "file": (filename, image_bytes, mime_type),
                "messaging_product": (None, "whatsapp"),
                "type": (None, mime_type),
            }
            r = await client.post(
                creds.media_upload_url,
                headers=creds.media_headers,
                files=files,
            )
            r.raise_for_status()
            data = r.json()
            media_id = data.get("id")
            if media_id:
                logger.info("Imagen subida a WhatsApp. Media ID: %s", media_id)
            return media_id
        except httpx.HTTPStatusError as exc:
            logger.error("Error subiendo imagen a WhatsApp: %s — %s", exc.response.status_code, exc.response.text)
            return None
        except Exception as exc:
            logger.error("Error subiendo imagen: %s", exc)
            return None


async def upload_audio_to_whatsapp(creds: WhatsAppCreds, audio_bytes: bytes, mime_type: str = "audio/mpeg",
                                   filename: str = "voz.mp3") -> str | None:
    """Subir audio a WhatsApp y devolver el media_id."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            files = {
                "file": (filename, audio_bytes, mime_type),
                "messaging_product": (None, "whatsapp"),
                "type": (None, mime_type),
            }
            r = await client.post(creds.media_upload_url, headers=creds.media_headers, files=files)
            r.raise_for_status()
            return r.json().get("id")
        except Exception as exc:
            logger.error("Error subiendo audio a WhatsApp: %s", exc)
            return None


async def send_audio_by_id(creds: WhatsAppCreds, phone_number: str, media_id: str) -> bool:
    """Enviar una nota de voz/audio usando un media_id ya subido."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "audio",
        "audio": {"id": media_id},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Audio enviado a %s", phone_number)
            return True
        except Exception as exc:
            logger.error("Error enviando audio: %s", exc)
            return False


async def upload_media_to_whatsapp(creds: WhatsAppCreds, file_bytes: bytes, mime_type: str, filename: str) -> str | None:
    """Subir cualquier media (imagen/video) a WhatsApp y devolver el media_id."""
    return await upload_image_to_whatsapp(creds, file_bytes, mime_type, filename)


async def send_video_by_id(creds: WhatsAppCreds, phone_number: str, media_id: str, caption: str = "") -> bool:
    """Enviar un video usando un media_id ya subido."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": phone_number,
        "type": "video",
        "video": {"id": media_id, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Video enviado a %s", phone_number)
            return True
        except Exception as exc:
            logger.error("Error enviando video: %s", exc)
            return False


async def send_audio_by_url(creds: WhatsAppCreds, phone_number: str, audio_url: str) -> bool:
    """Enviar una nota de voz usando una URL pública (WhatsApp la descarga). Más fiable
    que subir un media_id: evita el 'este audio ya no está disponible' en el celular."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": phone_number, "type": "audio", "audio": {"link": audio_url},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Audio (URL) enviado a %s", phone_number)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Error enviando audio (URL) a %s: %s — %s", phone_number, exc.response.status_code, exc.response.text)
            return False
        except httpx.RequestError as exc:
            logger.error("Error de red enviando audio (URL) a %s: %s", phone_number, exc)
            return False


async def send_video_by_url(creds: WhatsAppCreds, phone_number: str, video_url: str, caption: str = "") -> bool:
    """Enviar un video usando una URL pública (WhatsApp lo descarga). No depende de media_ids."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": phone_number, "type": "video",
        "video": {"link": video_url, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Video (URL) enviado a %s", phone_number)
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Error enviando video (URL) a %s: %s — %s", phone_number, exc.response.status_code, exc.response.text)
            return False
        except httpx.RequestError as exc:
            logger.error("Error de red enviando video (URL) a %s: %s", phone_number, exc)
            return False


async def send_document_by_url(creds: WhatsAppCreds, phone_number: str, doc_url: str, filename: str = "guia.pdf",
                               caption: str = "") -> bool:
    """Enviar un documento (PDF de la guía) usando una URL pública."""
    payload = {
        "messaging_product": "whatsapp", "recipient_type": "individual",
        "to": phone_number, "type": "document",
        "document": {"link": doc_url, "filename": filename, "caption": caption},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            r = await client.post(creds.api_url, headers=creds.headers, json=payload)
            r.raise_for_status()
            logger.info("Documento enviado a %s", phone_number)
            return True
        except Exception as exc:
            logger.error("Error enviando documento a %s: %s", phone_number, exc)
            return False


async def _download_media(creds: WhatsAppCreds, media_id: str) -> tuple[bytes, str] | None:
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            meta = await client.get(
                f"https://graph.facebook.com/{_API_VERSION}/{media_id}",
                headers=creds.media_headers,
            )
            meta.raise_for_status()
            info = meta.json()
            url = info.get("url")
            mime = info.get("mime_type", "application/octet-stream")
            if not url:
                return None
            file_resp = await client.get(url, headers=creds.media_headers)
            file_resp.raise_for_status()
            return file_resp.content, mime
        except Exception as exc:
            logger.error("Error descargando media %s: %s", media_id, exc)
            return None


async def download_media_as_base64(creds: WhatsAppCreds, media_id: str) -> tuple[str, str] | None:
    result = await _download_media(creds, media_id)
    if not result:
        return None
    raw_bytes, mime = result
    return base64.standard_b64encode(raw_bytes).decode("utf-8"), mime


async def download_media_bytes(creds: WhatsAppCreds, media_id: str) -> tuple[bytes, str] | None:
    return await _download_media(creds, media_id)