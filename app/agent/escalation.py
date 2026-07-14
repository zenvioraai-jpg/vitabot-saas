ESCALATION_KEYWORDS = [
    "asesor",
    "asesora",
    "persona real",
    "persona humana",
    "humano",
    "humana",
    "quiero hablar con",
    "hablar con alguien",
    "agente",
    "representante",
    "vendedor",
    "vendedora",
    "no me ayudas",
    "no me estás ayudando",
    "no entiendes",
    "necesito ayuda de verdad",
]

ESCALATION_PREFIX = "[ESCALAR]"

ESCALATION_MESSAGE = (
    "Con gusto te conecto con uno de nuestros asesores de Vita Qualitat. "
    "En breve alguien del equipo te atenderá personalmente. 🌿"
)

HANDBACK_MESSAGE = None  # No se envía mensaje al cliente al devolver a IA


GREETING_KEYWORDS = [
    "hola", "buenas", "buenos días", "buenos dias", "buenas tardes",
    "buenas noches", "buen día", "buen dia", "hey", "hi", "saludos",
    "hello", "qué tal", "que tal", "cómo están", "como estan",
]


def is_greeting(text: str) -> bool:
    """Return True if the message is (or starts with) a greeting."""
    lower = text.lower().strip()
    return any(lower == kw or lower.startswith(kw + " ") or lower.startswith(kw + ",")
               for kw in GREETING_KEYWORDS)


def check_escalation_keywords(text: str) -> bool:
    """Return True if the message contains an explicit escalation request."""
    lower = text.lower()
    return any(kw in lower for kw in ESCALATION_KEYWORDS)


def check_ai_escalation(ai_response: str) -> tuple[bool, str]:
    """
    Check if Claude self-reported that it cannot help.
    Returns (should_escalate, clean_message_to_send).
    """
    if ai_response.startswith(ESCALATION_PREFIX):
        clean = ai_response[len(ESCALATION_PREFIX):].strip()
        return True, clean
    return False, ai_response
