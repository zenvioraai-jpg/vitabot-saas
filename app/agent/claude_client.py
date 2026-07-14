import logging
import os
import json
import anthropic
from app.config import settings

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        os.environ.pop("SSLKEYLOGFILE", None)
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def get_ai_response(system_prompt: str, messages: list[dict]) -> str:
    """
    Call Claude and return the assistant's text response.
    messages must be in Anthropic format: [{"role": "user"|"assistant", "content": "..."}]
    """
    response = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        system=system_prompt,
        messages=messages,
    )
    text = response.content[0].text if response.content else ""
    logger.debug("Claude respondió (%d in, %d out tokens)", response.usage.input_tokens, response.usage.output_tokens)
    return text


def _load_product_list() -> str:
    """Load the product catalog as a readable list for vision prompts."""
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "products.json")
    try:
        with open(os.path.abspath(catalog_path), encoding="utf-8") as f:
            catalog = json.load(f)
        return "\n".join(
            f"- {p['name']} (SKU: {p['sku']}): {', '.join(p.get('benefits', [])[:3])}"
            for p in catalog.get("products", [])
        )
    except Exception as e:
        logger.warning("No se pudo cargar catálogo: %s", e)
        return "Catálogo no disponible"


def analyze_image(images, mime_type: str | None = None, customer_name: str | None = None,
                  expected_amount: int | None = None, order_time_str: str | None = None,
                  payment_config: dict | None = None, client_text: str | None = None) -> str:
    """
    Unified vision analysis. FIRST classifies the image, then responds appropriately:
      - COMPROBANTE (transferencia/pago): valida contra cuentas autorizadas de Vita Qualitat.
      - PRODUCTO: identifica el producto y explica sus beneficios (venta consultiva, sin presión).
      - OTRO: pregunta de forma natural qué necesita.

    `images` puede ser una lista de tuplas (base64, mime) o, por compatibilidad, un string
    base64 (en cuyo caso `mime_type` es su tipo). El orquestador lee [TIPO_IMAGEN: ...] y
    las etiquetas de comprobante.
    """
    # Normalizar a lista de (base64, mime)
    if isinstance(images, str):
        img_list = [(images, mime_type or "image/jpeg")]
    else:
        img_list = list(images)
    if not img_list:
        return ""

    name_ctx = f"El cliente se llama {customer_name}. " if customer_name else ""
    product_list = _load_product_list()
    text_ctx = ""
    if client_text and client_text.strip():
        text_ctx = (f"\nEl cliente escribió esto JUNTO con la(s) imagen(es): "
                    f"\"{client_text.strip()}\". Tenlo en cuenta para responder.\n")
    multi_ctx = ""
    if len(img_list) > 1:
        multi_ctx = (f"\nEl cliente envió {len(img_list)} imágenes a la vez. Mira TODAS y "
                     "responde UNA sola vez, sin repetirte ni contradecirte.\n")

    # Datos de validación de pago (configurables desde el panel).
    # Cuentas AUTORIZADAS por defecto (antifraude): Bancolombia 6843 y Davivienda 9532.
    titular = "Vita Qualitat SAS"
    accounts_txt = "  - Bancolombia term. 6843 a nombre de Vita Qualitat SAS\n  - Davivienda term. 9532 a nombre de Vita Qualitat SAS"
    if payment_config and payment_config.get("accounts"):
        titular = payment_config.get("titular", titular)
        lines = []
        for a in payment_config["accounts"]:
            if not a.get("enabled", True):
                continue
            bits = [a.get("bank", "")]
            if a.get("type"):
                bits.append(a["type"])
            if a.get("number"):
                bits.append(f"term. {a['number']}")
            if a.get("bre_b"):
                bits.append(f"Bre-B {a['bre_b']}")
            lines.append("  - " + " ".join(b for b in bits if b))
        if lines:
            accounts_txt = "\n".join(lines)
    amount_ctx = ""
    if expected_amount:
        amount_ctx = (
            f"\nIMPORTANTE — El total del pedido de este cliente es EXACTAMENTE "
            f"${expected_amount:,} COP. Si el monto del comprobante NO coincide con ese valor, "
            f"el comprobante es INVÁLIDO por monto incorrecto: usa "
            f"[COMPROBANTE_INVALIDO: razon=monto incorrecto] y dile amablemente que el valor "
            f"pagado no coincide con el total de su pedido (${expected_amount:,} COP), "
            f"pidiéndole verificar.\n"
        ).replace(",", ".")
    if order_time_str:
        amount_ctx += (
            f"\nVALIDACIÓN DE FECHA/HORA (anti-fraude) — El pedido se confirmó el {order_time_str} "
            f"(hora Colombia). El comprobante es VÁLIDO solo si su fecha y hora son IGUALES o POSTERIORES "
            f"a ese momento. Si el comprobante tiene una fecha de días anteriores, o es claramente un pago "
            f"antiguo/reutilizado, o la captura parece manipulada, márcalo como "
            f"[COMPROBANTE_INVALIDO: razon=comprobante antiguo o no corresponde a este pedido] y pide "
            f"amablemente el comprobante del pago realizado para ESTE pedido.\n"
        )

    prompt = (
        f"{name_ctx}Un cliente de Vita Qualitat (productos naturales para piel sensible, "
        "oncológica y diabética) envió esta imagen por WhatsApp. "
        "Tu PRIMERA tarea es CLASIFICARLA correctamente, luego responder.\n"
        f"{text_ctx}{multi_ctx}\n"

        "━━━ PASO 1: CLASIFICA LA IMAGEN ━━━\n"
        "Decide cuál de estas 3 es:\n\n"

        "A) COMPROBANTE DE PAGO / TRANSFERENCIA — señales claras:\n"
        "   • Pantallazo de app bancaria o billetera (Bancolombia, Nequi, Daviplata, PSE)\n"
        "   • Palabras como: 'Comprobante', 'Transferencia exitosa', 'Pago exitoso', "
        "'Envío exitoso', 'Recibo', 'Voucher', 'Soporte'\n"
        "   • Muestra: monto en pesos, fecha/hora, número de referencia/aprobación, "
        "cuenta o número de destino, titular/beneficiario\n\n"

        "B) FOTO DE PRODUCTO — señales claras:\n"
        "   • Muestra un producto físico (crema, loción, protector, kit), envase, etiqueta o catálogo\n"
        "   • NO tiene datos bancarios ni montos de transferencia\n\n"

        "C) OTRO — cualquier otra cosa (persona, lugar, mascota, documento no relacionado, captura sin contexto)\n\n"

        "━━━ PASO 2: RESPONDE SEGÚN EL TIPO ━━━\n\n"

        "▶ SI ES COMPROBANTE:\n"
        "Inicia tu respuesta con: [TIPO_IMAGEN: comprobante]\n"
        "Lee el comprobante como un sistema OCR antifraude y EXTRAE con precisión: destinatario/"
        "beneficiario, banco y cuenta de destino, monto, fecha/hora y número de referencia.\n\n"
        "⛔ VALIDACIÓN ANTIFRAUDE — revisa los 4 parámetros ANTES de aprobar:\n"
        f"  1) NOMBRE DEL DESTINATARIO: debe ser exactamente '{titular}' o un derivado claro "
        "(ej: 'Vita Qualitat', 'Vit*** Qua*** SAS***', parcialmente oculto). Si es otro nombre o "
        "no se puede leer, es INVÁLIDO.\n"
        f"  2) CUENTA DE DESTINO: solo son válidas las cuentas autorizadas de {titular}:\n{accounts_txt}\n"
        "     Si el dinero fue a otra cuenta/entidad, es INVÁLIDO.\n"
        "  3) FECHA: debe ser reciente y coherente con este pedido. Si es antigua, de otro día previo "
        "al pedido, o parece reutilizada/manipulada, es INVÁLIDO.\n"
        "  4) VALOR: debe coincidir EXACTAMENTE con el total del pedido. Si difiere, es INCONSISTENTE.\n\n"
        "Busca el destinatario en campos como: 'Para', 'Pago en', 'Producto destino', 'Enviado a', "
        "'Punto de venta', 'Titular', 'Beneficiario', 'Cuenta destino'.\n\n"
        "✅ SI TODO COINCIDE (nombre + cuenta autorizada + fecha válida + valor exacto):\n"
        "  agrega [COMPROBANTE_VALIDO: banco=BANCO, monto=MONTO, referencia=REF, fecha=FECHA]\n"
        "  y responde EXACTAMENTE con este tono:\n"
        "  '✅ Comprobante validado correctamente.\n\n"
        "  Verificamos que el pago fue realizado a Vita Qualitat SAS, a una cuenta autorizada, con una "
        "fecha válida y por el valor correcto. Tu pedido continúa con el proceso de preparación y despacho. 🌿'\n\n"
        "❌ SI HAY CUALQUIER INCONSISTENCIA (nombre/cuenta/fecha/valor) o no se distingue algún dato:\n"
        "  agrega [COMPROBANTE_INVALIDO: razon=RAZON]\n"
        "  y responde EXACTAMENTE con este tono:\n"
        "  '❌ No fue posible validar automáticamente el comprobante.\n\n"
        "  Detectamos una inconsistencia en uno o más de estos datos: nombre del destinatario, cuenta de "
        "destino, fecha o valor transferido. Un asesor lo revisará, o puedes enviar un comprobante corregido "
        "del pago realizado a Vita Qualitat SAS (Bancolombia term. 6843 o Davivienda term. 9532). 💚'\n"
        + amount_ctx + "\n"

        "▶ SI ES PRODUCTO:\n"
        "Inicia tu respuesta con: [TIPO_IMAGEN: producto]\n"
        f"Productos del catálogo:\n{product_list}\n"
        "Identifica cuál es (o el más parecido). NO digas que esto no es un comprobante. "
        "En lugar de eso, habla del PRODUCTO: para qué sirve, cómo AYUDA a la piel del cliente "
        "y sus principales beneficios, con tono cálido y profesional (como un asesor experto, no un vendedor). "
        "NO muestres precios ni métodos de pago todavía. "
        "Cierra preguntando con naturalidad si quiere conocer más o si le gustaría llevarlo. "
        "Ejemplo de cierre: '¿Te gustaría que te cuente más sobre cómo usarlo o prefieres llevarlo? 🌿'\n\n"

        "▶ SI ES OTRO:\n"
        "Inicia tu respuesta con: [TIPO_IMAGEN: otro]\n"
        "Pregunta con calidez en qué puedes ayudarle.\n\n"

        "Responde SIEMPRE en español colombiano, claro y cálido. Máximo 1 emoji (🌿)."
    )

    content = []
    for (b64, mime) in img_list:
        if (mime or "").lower() == "application/pdf":
            # Comprobante en PDF: Claude lo lee como documento
            content.append({"type": "document",
                            "source": {"type": "base64", "media_type": "application/pdf", "data": b64}})
        else:
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": mime, "data": b64}})
    content.append({"type": "text", "text": prompt})
    response = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=600,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text if response.content else ""


def analyze_payment_image(image_base64: str, mime_type: str, customer_name: str | None = None) -> str:
    """
    Use Claude Vision to analyze a payment receipt image.
    Validates against Vita Qualitat authorized accounts:
    - Bancolombia (terminación 6843)
    - Davivienda (terminación 9532)
    Returns validation result in Spanish.
    """
    name_ctx = f"El cliente se llama {customer_name}." if customer_name else ""
    prompt = (
        f"{name_ctx} El cliente envió un comprobante de transferencia bancaria. "
        "Analiza la imagen y extrae EXACTAMENTE esta información:\n"
        "1. Titular/Beneficiario (nombre de quién recibió el dinero)\n"
        "2. Número de cuenta o terminación visible\n"
        "3. Banco/Entidad financiera\n"
        "4. Monto transferido\n"
        "5. Fecha de la transacción\n"
        "6. Número de referencia/confirmación\n\n"
        "VALIDACIÓN DE VITA QUALITAT:\n"
        "✓ Titular debe ser: Vita Qualitat SAS\n"
        "✓ Cuentas autorizadas:\n"
        "  - Bancolombia (terminación: 6843)\n"
        "  - Davivienda (terminación: 9532)\n\n"
        "Si el comprobante es VÁLIDO (titular correcto + cuenta autorizada):\n"
        "Responde: 'VÁLIDO [COMPROBANTE_VALIDO: banco=BANCO, monto=MONTO, referencia=REF, fecha=FECHA]'\n"
        "Luego agrega un mensaje amigable confirmando que hemos validado el comprobante.\n\n"
        "Si el comprobante es INVÁLIDO (titular incorrecto O cuenta no autorizada):\n"
        "Responde: 'INVÁLIDO [COMPROBANTE_INVALIDO: razon=RAZON]'\n"
        "Luego pide al cliente verificar los datos.\n\n"
        "Si NO es un comprobante: responde naturalmente preguntando qué necesita.\n"
        "Responde en español colombiano, claro y conciso."
    )

    response = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.content[0].text if response.content else ""


def analyze_product_image(image_base64: str, mime_type: str) -> str:
    """
    Use Claude Vision to identify Vita Qualitat products from images.
    Supports photos, screenshots, PDFs, catalogs.
    Returns product info (name, SKU, presentation, quantity detected) in Spanish.
    """
    # Load catalog for reference
    catalog_path = os.path.join(os.path.dirname(__file__), "..", "..", "catalog", "products.json")
    try:
        with open(os.path.abspath(catalog_path), encoding="utf-8") as f:
            catalog = json.load(f)
        product_list = "\n".join([f"- {p['name']} (SKU: {p['sku']}, ${p['price_cop']:,} COP) - Presentaciones: {', '.join(p.get('presentations', []))}" for p in catalog.get("products", [])])
    except Exception as e:
        logger.warning("No se pudo cargar catálogo: %s", e)
        product_list = "Catálogo no disponible"

    prompt = (
        "Analiza esta imagen para identificar productos de Vita Qualitat (marca de cuidado natural para pieles sensibles).\n\n"
        f"Productos disponibles:\n{product_list}\n\n"
        "Extrae de la imagen:\n"
        "1. Nombre del producto (debe coincidir con el catálogo)\n"
        "2. SKU o código si es visible\n"
        "3. Presentación detectada (pequeña, mediana, grande, etc.)\n"
        "4. Cantidad de unidades (si hay múltiples en la imagen)\n"
        "5. Precio si es visible\n\n"
        "Si reconoces el producto, responde: 'Detecté: [PRODUCTO: nombre=X, sku=Y, presentacion=Z, cantidad=N, precio=P COP]'\n"
        "Si no es un producto Vita Qualitat, responde amablemente preguntando qué necesita.\n"
        "Responde en español colombiano, de forma clara y concisa."
    )

    response = _get_client().messages.create(
        model=settings.claude_model,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.content[0].text if response.content else ""
