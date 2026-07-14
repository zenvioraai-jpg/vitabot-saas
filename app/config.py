from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de PLATAFORMA (compartida por todas las empresas). Las credenciales
    de WhatsApp, el token de panel y demás configuración de CADA empresa viven en la
    tabla `Company` (BD), no aquí — ver app/db/models.py::Company."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig")

    # Anthropic (billing de plataforma; cada empresa puede fijar su propio claude_model)
    anthropic_api_key: str
    claude_model: str = "claude-haiku-4-5-20251001"

    # Database
    database_url: str = "sqlite:///./vitabot_saas.db"

    # Panel MAESTRO (dueño del SaaS) — el panel de cada empresa usa su propio
    # Company.admin_token, no este.
    master_admin_token: str

    # Verificación del webhook de Meta: cada empresa puede traer su propio
    # webhook_verify_token (Company.webhook_verify_token); este es el valor de
    # PLATAFORMA que también se acepta (útil para pruebas o un solo Meta App compartido).
    webhook_verify_token: str = ""

    # Email de plataforma (fallback si una empresa no configuró su propio Resend)
    email_from_name: str = "VitaBot"
    resend_api_key: str = ""

    # Groq (transcripción de voz con Whisper) y ElevenLabs (voz) — de plataforma por ahora
    groq_api_key: str = ""
    elevenlabs_api_key: str = ""

    # App
    max_history_messages: int = 15


settings = Settings()