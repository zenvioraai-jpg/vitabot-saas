"""URL pública del servicio.

WhatsApp puede DESCARGAR la multimedia si le pasamos una URL pública (más fiable que
subir un media_id, que a veces se acepta pero no se entrega). Aquí resolvemos esa URL:
1) variable de entorno PUBLIC_BASE_URL (si se configura a mano),
2) RAILWAY_PUBLIC_DOMAIN (la pone Railway sola),
3) la capturamos de las peticiones reales (panel/webhook) — así no requiere configuración.
"""
import os

_captured = ""


def remember_base(url: str) -> None:
    """Guarda el dominio público visto en una petición real (panel o webhook)."""
    global _captured
    u = (url or "").strip().rstrip("/")
    if u.startswith("http") and "localhost" not in u and "127.0.0.1" not in u and "0.0.0.0" not in u:
        _captured = u


def public_base() -> str:
    env = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if env:
        return env
    dom = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip().rstrip("/")
    if dom:
        return dom if dom.startswith("http") else "https://" + dom
    return _captured
