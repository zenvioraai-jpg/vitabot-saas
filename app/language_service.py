"""Language detection and translation service for Vita Qualitat chatbot."""
import anthropic
import logging
from app.config import settings

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ["es", "en", "pt"]
LANGUAGE_NAMES = {"es": "Español", "en": "English", "pt": "Português"}


def detect_language(text: str) -> str:
    """
    Detect language from text. Returns 'es', 'en', or 'pt'.
    Falls back to 'es' if detection fails.
    """
    if not text or len(text) < 3:
        return "es"

    prompt = (
        f"Detecta el idioma de este texto en exactamente una palabra: es (español), en (inglés), o pt (portugués).\n"
        f"Texto: {text[:200]}\n"
        f"Responde SOLO con: es | en | pt"
    )

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )
        lang = response.content[0].text.strip().lower()
        if lang in SUPPORTED_LANGUAGES:
            return lang
    except Exception as e:
        logger.warning("Error detecting language: %s", e)

    return "es"


# ─── Translation strings ─────────────────────────────────────────────────────

STRINGS = {
    "greeting_new_customer": {
        "es": "¡Hola! Bienvenido(a) a Vita Qualitat 🌿 Con mucho gusto te ayudo. ¿Con quién tengo el placer de hablar?",
        "en": "Hi! Welcome to Vita Qualitat 🌿 I'm happy to help you. Who am I speaking with?",
        "pt": "Olá! Bem-vindo à Vita Qualitat 🌿 Fico feliz em ajudá-lo. Com quem tenho o prazer de falar?",
    },
    "shipping_data_request": {
        "es": "Para procesar tu pedido, envíame en un solo mensaje:\n📋 Nombre completo - Número de cédula - Número de teléfono - Correo electrónico - Dirección completa",
        "en": "To process your order, send me in a single message:\n📋 Full Name - ID Number - Phone Number - Email - Complete Address",
        "pt": "Para processar seu pedido, envie-me em uma única mensagem:\n📋 Nome Completo - Número de ID - Número de Telefone - Email - Endereço Completo",
    },
    "order_confirmed": {
        "es": "¡Perfecto! Tu pedido está registrado. Un asesor se contactará pronto para coordinar el despacho. 🌿",
        "en": "Perfect! Your order is registered. An advisor will contact you soon to coordinate delivery. 🌿",
        "pt": "Perfeito! Seu pedido foi registrado. Um consultor entrará em contato em breve para coordenar a entrega. 🌿",
    },
    "payment_link_waiting": {
        "es": "Perfecto. Nuestro equipo te enviará el link de pago en breve. Por favor espera un momento.",
        "en": "Perfect. Our team will send you the payment link shortly. Please wait a moment.",
        "pt": "Perfeito. Nossa equipe enviará o link de pagamento em breve. Por favor, aguarde um momento.",
    },
    "audio_error": {
        "es": "Recibí tu mensaje de voz pero no pude procesarlo en este momento. ¿Puedes escribir tu consulta? 🙏",
        "en": "I received your voice message but couldn't process it right now. Can you write your question? 🙏",
        "pt": "Recebi sua mensagem de voz, mas não consegui processá-la no momento. Você pode escrever sua pergunta? 🙏",
    },
    "image_error": {
        "es": "Recibí tu imagen pero no pude procesarla en este momento. Por favor intenta de nuevo o escribe 'asesor'. 🙏",
        "en": "I received your image but couldn't process it right now. Please try again or write 'advisor'. 🙏",
        "pt": "Recebi sua imagem, mas não consegui processá-la no momento. Tente novamente ou escreva 'consultor'. 🙏",
    },
    "general_error": {
        "es": "En este momento tengo un inconveniente técnico. Por favor intenta en unos minutos o escribe 'asesor' para que alguien te ayude. 🙏",
        "en": "I'm having a technical issue right now. Please try again in a few minutes or write 'advisor' for help. 🙏",
        "pt": "Estou tendo um problema técnico no momento. Tente novamente em alguns minutos ou escreva 'consultor' para obter ajuda. 🙏",
    },
    "escalation_message": {
        "es": "Entiendo que necesitas hablar con un asesor. Te estoy conectando ahora. Alguien se comunicará contigo en breve. 💚",
        "en": "I understand you need to speak with an advisor. Connecting you now. Someone will reach out shortly. 💚",
        "pt": "Entendo que você precisa falar com um consultor. Conectando-o agora. Alguém entrará em contato em breve. 💚",
    },
}


def get_string(key: str, language: str = "es") -> str:
    """Get translated string by key and language."""
    if key not in STRINGS:
        logger.warning("Translation key not found: %s", key)
        return key
    if language not in STRINGS[key]:
        language = "es"
    return STRINGS[key][language]
