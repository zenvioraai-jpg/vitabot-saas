import io
import logging
from app.config import settings

logger = logging.getLogger(__name__)

def convert_to_ogg_opus(content: bytes, mime: str) -> tuple[bytes, str, str] | None:
    """Prepara un audio para enviarlo como NOTA DE VOZ de WhatsApp (OGG/Opus, el formato
    más fiable). Devuelve (bytes, mime, filename) listos para enviar, o None si no fue
    posible (falta ffmpeg con un formato distinto a ogg).

    - Si ya es OGG, se envía tal cual (se asume Opus, como graban los navegadores).
    - Cualquier otro formato (webm de Chrome/Android, mp4/m4a de iOS, mp3, etc.) se
      transcodifica a OGG/Opus con ffmpeg para garantizar que el cliente lo reciba."""
    base = (mime or "").split(";")[0].strip().lower()

    import subprocess, tempfile, os, shutil
    if not shutil.which("ffmpeg"):
        # Sin ffmpeg: si ya es OGG lo mandamos tal cual; cualquier otro formato no se puede preparar.
        logger.warning("ffmpeg no disponible; audio %s se envía sin transcodificar", base)
        return (content, "audio/ogg", "nota.ogg") if base == "audio/ogg" else None
    in_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".in", delete=False) as f:
            f.write(content)
            in_path = f.name
        out_path = in_path + ".ogg"
        # SIEMPRE transcodificamos a OGG/Opus MONO: es el formato exacto que WhatsApp
        # reproduce como nota de voz. -vn descarta cualquier pista de video/carátula
        # (iOS mete metadata en el mp4); -map_metadata -1 limpia metadatos que pueden
        # corromper la nota de voz.
        cmd = ["ffmpeg", "-y", "-i", in_path, "-vn", "-map_metadata", "-1",
               "-ac", "1", "-ar", "48000", "-c:a", "libopus", "-b:a", "32k",
               "-f", "ogg", out_path]
        res = subprocess.run(cmd, capture_output=True, timeout=60)
        if res.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            logger.error("ffmpeg falló (%s): %s", res.returncode, res.stderr.decode("utf-8", "ignore")[:300])
            return (content, "audio/ogg", "nota.ogg") if base == "audio/ogg" else None
        with open(out_path, "rb") as f:
            data = f.read()
        # Validar que sea un OGG real (empieza con la firma 'OggS'); si no, no lo enviamos
        if not data.startswith(b"OggS"):
            logger.error("La conversión no produjo un OGG válido (%d bytes)", len(data))
            return None
        logger.info("Audio convertido a OGG/Opus: %d bytes", len(data))
        return data, "audio/ogg", "nota.ogg"
    except Exception as exc:
        logger.error("Error convirtiendo audio: %s", exc)
        return None
    finally:
        for p in (in_path, out_path):
            try:
                if p and __import__("os").path.exists(p):
                    __import__("os").remove(p)
            except Exception:
                pass


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/ogg") -> str | None:
    """
    Transcribe audio bytes to text using Groq Whisper.
    Returns the transcribed text or None on failure.
    """
    if not settings.groq_api_key:
        logger.warning("GROQ_API_KEY no configurado. No se puede transcribir audio.")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=settings.groq_api_key)

        ext = "ogg"
        if "mp4" in mime_type or "m4a" in mime_type:
            ext = "m4a"
        elif "mpeg" in mime_type or "mp3" in mime_type:
            ext = "mp3"
        elif "wav" in mime_type:
            ext = "wav"
        elif "webm" in mime_type:
            ext = "webm"

        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3-turbo",
            file=(f"audio.{ext}", io.BytesIO(audio_bytes), mime_type),
            language="es",
            response_format="text",
        )
        result = str(transcription).strip()
        logger.info("Audio transcrito: %d caracteres", len(result))
        return result if result else None
    except Exception as exc:
        logger.error("Error transcribiendo audio con Groq: %s", exc)
        return None
