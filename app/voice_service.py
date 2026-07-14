import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)


def text_to_speech(text: str, voice_id: str) -> bytes | None:
    """
    Convertir texto a audio (mp3) usando ElevenLabs.
    Devuelve los bytes del mp3 o None si falla / no está configurado.
    """
    if not settings.elevenlabs_api_key or not voice_id:
        logger.info("ElevenLabs no configurado (falta API key o voice_id).")
        return None
    # Limitar longitud para no gastar créditos en mensajes enormes
    text = (text or "").strip()
    if not text:
        return None
    if len(text) > 800:
        text = text[:800]

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        # Normaliza números/símbolos para que no los lea de forma robótica
        "apply_text_normalization": "auto",
        "voice_settings": {
            # Baja estabilidad = entonación más viva y humana (no monótona/robótica)
            "stability": 0.3,
            "similarity_boost": 0.75,
            "style": 0.5,               # más emoción/expresividad
            "use_speaker_boost": True,
        },
    }
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.content
    except Exception as exc:
        logger.error("Error generando voz con ElevenLabs: %s", exc)
        return None
