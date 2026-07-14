"""Almacenamiento en disco de las fotos/videos de productos.

Guardar el archivo (no solo el media_id de WhatsApp) permite:
  1) Previsualizarlo en el panel.
  2) Reenviarlo a WhatsApp cuando el media_id expire o falle (los media_id de WhatsApp
     caducan ~30 días). Así el envío de fotos/videos es a prueba de fallos.

Los archivos viven junto a la base de datos (en el volumen /data de Railway si está
configurado), por lo que persisten entre despliegues.
"""
import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def media_dir() -> str:
    """Carpeta donde se guardan los archivos de media. Se crea si no existe."""
    env = os.environ.get("MEDIA_DIR")
    if env:
        base = env
    else:
        url = settings.database_url
        if url.startswith("sqlite:///"):
            db_path = url.replace("sqlite:///", "", 1)
            base = os.path.join(os.path.dirname(os.path.abspath(db_path)) or ".", "media")
        else:
            base = os.path.join(".", "data", "media")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception as exc:
        logger.error("No se pudo crear la carpeta de media %s: %s", base, exc)
    return base


def _ext_for(kind: str, mime: str) -> str:
    if kind == "video":
        return "mp4"
    if mime:
        if "png" in mime:
            return "png"
        if "webp" in mime:
            return "webp"
    return "jpg"


def save_file(sku: str, kind: str, content: bytes, mime: str) -> str:
    """Guarda el archivo y devuelve su nombre (relativo a media_dir)."""
    ext = _ext_for(kind, mime)
    safe_sku = "".join(c for c in sku if c.isalnum() or c in "-_") or "item"
    filename = f"{safe_sku}_{kind}.{ext}"
    path = os.path.join(media_dir(), filename)
    with open(path, "wb") as f:
        f.write(content)
    return filename


def file_path(filename: str) -> str | None:
    """Ruta absoluta de un archivo guardado, o None si no existe."""
    if not filename:
        return None
    path = os.path.join(media_dir(), filename)
    return path if os.path.exists(path) else None


def read_file(filename: str) -> tuple[bytes, str] | None:
    """Lee un archivo guardado. Devuelve (bytes, mime) o None."""
    path = file_path(filename)
    if not path:
        return None
    ext = path.rsplit(".", 1)[-1].lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "mp4": "video/mp4"}.get(ext, "application/octet-stream")
    try:
        with open(path, "rb") as f:
            return f.read(), mime
    except Exception:
        return None


def delete_file(filename: str) -> None:
    path = file_path(filename)
    if path:
        try:
            os.remove(path)
        except Exception:
            pass
