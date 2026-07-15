import asyncio
import logging
import re
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.db.database import SessionLocal
from app.db import crud
from app.agent.context import load_conversation_history
from app.agent.system_prompt import build_system_prompt
from app.agent.claude_client import get_ai_response
from app.whatsapp.client import (
    WhatsAppCreds,
    download_media_as_base64,
    download_media_bytes,
    send_text_message,
    send_image_message,
)
from app.agent.escalation import (
    check_escalation_keywords,
    check_ai_escalation,
)
from app.whatsapp.parser import IncomingMessage
from app.audio_service import transcribe_audio
from app.email_service import notify_new_order
from app.language_service import detect_language

logger = logging.getLogger(__name__)

_SESSION_RESET_HOURS = 6

# ── Agrupado de mensajes (debounce) ───────────────────────────────────────────
# Cuando el cliente envía varios mensajes seguidos (texto + fotos + audio), el bot
# espera unos segundos a que termine y responde UNA sola vez con todo el contexto,
# así no se contradice ni manda varios párrafos. Se comporta como un humano que
# lee todo antes de contestar.
_DEBOUNCE_SECONDS = 15
# conversation_id -> {"items": [...], "seq": int, "phone": str, "company_id": int}
_buffers: dict[int, dict] = {}
# Referencias fuertes a las tareas en vuelo (evita que el GC las cancele a media espera)
_flush_tasks: set = set()


def _creds_for(company) -> WhatsAppCreds:
    return WhatsAppCreds(phone_number_id=company.whatsapp_phone_number_id,
                         access_token=company.whatsapp_access_token)


# PSE/card keywords
_PSE_KEYWORDS = ["pse", "tarjeta", "tarjeta de crédito", "tarjeta de debito",
                  "débito", "crédito", "pago en línea", "link de pago", "pago online"]
_CREDIT_CARD_KEYWORDS = ["tarjeta de crédito", "tarjeta crédito", "crédito"]


def _detect_pse_request(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _PSE_KEYWORDS)


def _detect_credit_card_request(text: str) -> bool:
    """Detects if client specifically selected credit card payment."""
    lower = text.lower()
    return any(kw in lower for kw in _CREDIT_CARD_KEYWORDS)


_VOICE_KEYWORDS = ["audio", "nota de voz", "mensaje de voz", "en voz", "por voz",
                   "respóndeme hablando", "respondeme hablando", "mándame un audio",
                   "mandame un audio", "envíame un audio", "enviame un audio", "háblame", "hablame"]


def _detect_voice_request(text: str) -> bool:
    """Detecta si el cliente pide explícitamente que le respondan con un audio/nota de voz."""
    lower = (text or "").lower()
    return any(kw in lower for kw in _VOICE_KEYWORDS)


def _parse_kv(data_str: str) -> dict:
    """Parse 'clave=valor, clave2=valor2' (valores pueden tener espacios y acentos)."""
    import re
    pattern = r'(\w+)=([^,]+?)(?=,\s*\w+=|$)'
    out = {}
    for key, value in re.findall(pattern, data_str):
        out[key.strip().lower()] = value.strip()
    return out


def _parse_client_data(data_str: str) -> dict:
    """Datos del cliente -> campos del modelo Customer."""
    kv = _parse_kv(data_str)
    result = {}
    if kv.get('nombre'):
        result['name'] = kv['nombre']
    if kv.get('cedula'):
        result['cedula'] = kv['cedula']
    if kv.get('email') or kv.get('correo'):
        result['email'] = kv.get('email') or kv.get('correo')
    if kv.get('direccion') or kv.get('dirección'):
        result['address'] = kv.get('direccion') or kv.get('dirección')
    if kv.get('ciudad'):
        result['city'] = kv['ciudad']
    return result


def _money_to_int(s: str) -> int | None:
    """'$120.000 COP' -> 120000"""
    import re
    digits = re.sub(r'[^\d]', '', s or '')
    return int(digits) if digits else None


def _norm_txt(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def _canonical_product_name(db, company_id: int, text: str) -> str:
    """Convierte un nombre libre al nombre EXACTO del catálogo de la empresa (para que
    'Más vendidos' y el historial agrupen bien). Si no lo reconoce, deja el texto tal cual."""
    raw = (text or "").strip(" .-·")
    if not raw:
        return "Producto"
    low = _norm_txt(raw)
    for p in crud.list_products(db, company_id):
        nlow = _norm_txt(p.name)
        if nlow in low or low in nlow:
            return p.name
    return raw[:60]


def _parse_order_items(db, company_id: int, products_str: str, fallback_qty: int = 1) -> list[dict]:
    """Convierte 'Producto A x1; Producto B x2' -> [{name, quantity}, ...].
    Acepta ';' o ',' como separador y 'xN'/'N x' como cantidad. Normaliza al nombre del catálogo."""
    products_str = (products_str or "").strip()
    if not products_str:
        return []
    parts = re.split(r';', products_str) if ";" in products_str else re.split(r',', products_str)
    items: list[dict] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        qty = fallback_qty
        m = re.search(r'(?:x\s*(\d+)|(\d+)\s*(?:uds?|unidades?|x))\b', part, re.IGNORECASE)
        if m:
            qty = int(m.group(1) or m.group(2) or fallback_qty)
            part = re.sub(r'(?:x\s*\d+|\d+\s*(?:uds?|unidades?|x))\b', '', part, flags=re.IGNORECASE)
        name = _canonical_product_name(db, company_id, part)
        for it in items:
            if it["name"] == name:
                it["quantity"] += max(qty, 1)
                break
        else:
            items.append({"name": name, "quantity": max(qty, 1)})
    return items


def _order_signature(items: list[dict], total) -> tuple:
    """Firma comparable de un pedido: productos+cantidades ordenados y total."""
    sig = tuple(sorted((str(it.get("name", "")).strip().lower(), int(it.get("quantity", 1) or 1))
                       for it in (items or [])))
    return (sig, int(total or 0))


def _is_duplicate_order(db, conversation_id: int, order: dict) -> bool:
    """True si el último pedido de esta conversación es idéntico (mismos productos y total)
    y muy reciente (<20 min). Evita duplicados cuando la IA re-emite [PEDIDO_CONFIRMADO]
    (por ejemplo, al despedirse), sin bloquear recompras reales más adelante."""
    from datetime import timedelta
    last = crud.get_latest_order_for_conversation(db, conversation_id)
    if not last:
        return False
    if last.created_at and (datetime.utcnow() - last.created_at) > timedelta(minutes=20):
        return False
    try:
        import json as _json
        last_items = _json.loads(last.items_json) if last.items_json else []
    except Exception:
        last_items = []
    return _order_signature(last_items, last.total) == _order_signature(order["items"], order["total"])


def _parse_order_data(db, company_id: int, data_str: str) -> dict:
    """PEDIDO_CONFIRMADO -> dict con items (lista), total, pago, ciudad, cupon."""
    kv = _parse_kv(data_str)
    try:
        cantidad = int(re.sub(r'[^\d]', '', kv.get('cantidad', '1')) or '1')
    except Exception:
        cantidad = 1
    prod_str = kv.get('productos') or kv.get('producto') or ""
    items = _parse_order_items(db, company_id, prod_str, fallback_qty=cantidad)
    if not items:
        items = [{"name": "Producto", "quantity": cantidad}]
    return {
        "items": items,
        "total": _money_to_int(kv.get('total', '')),
        "pago": (kv.get('pago') or kv.get('metodo') or "").lower(),
        "ciudad": kv.get('ciudad') or kv.get('dirección') or kv.get('direccion') or "",
        "cupon": (kv.get('cupon') or kv.get('cupón') or "").strip().upper(),
    }


def _get_language_instruction(language: str) -> str:
    """Get language instruction to append to system prompt."""
    instructions = {
        "es": "━━━ IDIOMA ━━━\nResponde siempre en ESPAÑOL NEUTRO DE COLOMBIA, claro y accesible, con ortografía y tildes correctas. NO uses modismos ni palabras de otros países (España, México, Argentina, etc.) ni jerga muy regional de una sola zona de Colombia. Esta es la norma por defecto, salvo que Entrenamiento indique otro estilo.",
        "en": "━━━ LANGUAGE ━━━\nAlways respond in clear and accessible ENGLISH.",
        "pt": "━━━ IDIOMA ━━━\nResponda sempre em PORTUGUÊS claro e acessível.",
    }
    return instructions.get(language, instructions["es"])


def _get_error_message(language: str = "es") -> str:
    """Get technical error message in the specified language."""
    messages = {
        "es": "En este momento tengo un inconveniente técnico. Por favor intenta en unos minutos o escribe 'asesor' para que alguien te ayude. 🙏",
        "en": "I'm having a technical issue right now. Please try again in a few minutes or write 'advisor' for help. 🙏",
        "pt": "Estou tendo um problema técnico no momento. Tente novamente em alguns minutos ou escreva 'consultor' para obter ajuda. 🙏",
    }
    return messages.get(language, messages["es"])


def _get_audio_error(language: str = "es") -> str:
    """Get audio processing error message in the specified language."""
    messages = {
        "es": "Recibí tu mensaje de voz pero no pude procesarlo en este momento. ¿Puedes escribir tu consulta? 🙏",
        "en": "I received your voice message but couldn't process it right now. Can you write your question? 🙏",
        "pt": "Recebi sua mensagem de voz, mas não consegui processá-la no momento. Você pode escrever sua pergunta? 🙏",
    }
    return messages.get(language, messages["es"])


def _extract_tag(text: str, tag: str) -> tuple[bool, str, str]:
    """
    Check if text contains [TAG: value] or [TAG].
    Returns (found, value, clean_text).
    """
    import re
    pattern = rf'\[{tag}(?:: ([^\]]+))?\]'
    match = re.search(pattern, text)
    if match:
        value = match.group(1) or ""
        clean = re.sub(pattern, "", text).strip()
        return True, value.strip(), clean
    return False, "", text


def _notify_new_conversation(db, company_id: int, customer) -> None:
    """Avisa al administrador que alguien inició una conversación. Distingue si es un
    cliente NUEVO o uno que ya había comprado/escrito antes (según sus pedidos pagados)."""
    try:
        from app import notify
        last_order = crud.get_last_order_for_customer(db, customer.id)
        is_known = last_order is not None
        event = "returning" if is_known else "new_client"
        nombre = customer.name or "Sin nombre"
        lines = [
            f"👤 Cliente: {nombre}",
            f"📱 WhatsApp: +{customer.phone_number}",
            ("🔁 Ya había escrito/comprado antes." if is_known else "🆕 Es un cliente NUEVO."),
        ]
        subject = ("🔁 Cliente conocido escribió" if is_known else "🆕 Nuevo cliente escribió")
        notify.schedule(company_id, subject, lines, event)
    except Exception as exc:
        logger.error("No se pudo agendar notificación de nueva conversación: %s", exc)


def _notify_card_request(company_id: int, customer, message_text: str, is_card: bool) -> None:
    """Avisa al administrador (email + WhatsApp configurados) que un cliente quiere pagar
    con tarjeta o PSE, para que el equipo genere el link de pago manualmente."""
    try:
        from app import notify
        medio = "tarjeta de crédito/débito" if is_card else "PSE / pago en línea"
        lines = [
            f"👤 Cliente: {customer.name or 'Sin nombre'} (+{customer.phone_number})",
            f"💳 Quiere pagar con: {medio}",
            f"💬 Mensaje: \"{(message_text or '').strip()[:300]}\"",
            "➡️ Genera el link de pago y envíaselo por WhatsApp.",
        ]
        notify.schedule(company_id, "💳 Cliente quiere pagar con tarjeta/PSE", lines, "card")
    except Exception as exc:
        logger.error("No se pudo agendar notificación de pago con tarjeta: %s", exc)


def _notify_sale_closed(company_id: int, customer, items: list[dict], total, method: str, destino: str) -> None:
    """Avisa al administrador que se CERRÓ una venta, con método de pago, productos y destino."""
    try:
        from app import notify
        prods = "; ".join(f"{it.get('name','Producto')} x{it.get('quantity',1)}" for it in (items or [])) or "—"
        total_txt = f"${int(total):,} COP".replace(",", ".") if total else "—"
        lines = [
            f"👤 Cliente: {customer.name or 'Sin nombre'} (+{customer.phone_number})",
            f"🛒 Productos: {prods}",
            f"💵 Total: {total_txt}",
            f"💳 Método de pago: {method or '—'}",
            f"📍 Envío a: {destino or customer.city or '—'}",
        ]
        notify.schedule(company_id, "✅ Venta cerrada", lines, "sale")
    except Exception as exc:
        logger.error("No se pudo agendar notificación de venta: %s", exc)


async def process_incoming_message(incoming: IncomingMessage, company_id: int) -> None:
    """Recibe UN mensaje de UNA empresa, lo guarda y lo agrega al buffer del cliente. La
    respuesta real se genera unos segundos después (debounce), agrupando todos los
    mensajes seguidos para responder una sola vez con todo el contexto."""
    db = SessionLocal()
    conv_id = None
    phone = None
    try:
        if crud.is_duplicate_message(db, company_id, incoming.wa_message_id):
            logger.info("Mensaje duplicado ignorado: %s", incoming.wa_message_id)
            return

        customer = crud.get_or_create_customer(db, company_id, incoming.phone_number)
        if incoming.display_name and not customer.name:
            crud.update_customer(db, company_id, incoming.phone_number, name=incoming.display_name)

        # ── Detección de idioma (en CADA mensaje con texto suficiente) ─────────
        if incoming.text and len(incoming.text.strip()) > 8:
            detected_lang = detect_language(incoming.text)
            if detected_lang in ("es", "en", "pt") and detected_lang != customer.preferred_language:
                crud.update_customer(db, company_id, incoming.phone_number, preferred_language=detected_lang)
                customer.preferred_language = detected_lang
                logger.info("Idioma del cliente actualizado a: %s", detected_lang)

        # ── Gestión de sesión (SIEMPRE 1 conversación por número, por empresa) ──
        conversation = crud.get_or_reopen_conversation(db, company_id, incoming.phone_number, customer.id)

        # ¿Es el PRIMER mensaje de esta conversación? (para notificar al administrador)
        is_new_conversation = crud.get_last_message_time(db, conversation.id) is None

        # ── Guardar mensaje entrante ───────────────────────────────────────────
        try:
            crud.save_message(
                db, company_id=company_id, conversation_id=conversation.id, direction="inbound",
                sender="customer", content=incoming.text, wa_message_id=incoming.wa_message_id,
            )
        except IntegrityError:
            return

        # ── Notificar al administrador cuando alguien inicia una conversación ──
        if is_new_conversation:
            _notify_new_conversation(db, company_id, customer)

        # El cliente volvió a escribir: cancela cualquier recordatorio pendiente
        crud.cancel_reminders(db, conversation.id)

        if conversation.mode == "human":
            return

        # ── Pausa global: el bot no responde (se atiende a mano desde el panel) ─
        if crud.get_bot_paused(db, company_id):
            logger.info("Bot en pausa: no se responde automáticamente a %s", incoming.phone_number)
            return

        # ── PSE/Tarjeta: avisar al administrador por los canales configurados ──
        if _detect_pse_request(incoming.text):
            db.refresh(customer)
            _notify_card_request(company_id, customer, incoming.text,
                                 is_card=_detect_credit_card_request(incoming.text))

        # ── Escalación por keywords: actuar de inmediato ──────────────────────
        if check_escalation_keywords(incoming.text):
            _buffers.pop(conversation.id, None)  # descarta lo pendiente
            company = crud.get_company(db, company_id)
            await _escalate(db, company_id, _creds_for(company), conversation, customer.phone_number,
                            reason="Solicitud explícita del cliente", language=customer.preferred_language)
            return

        conv_id = conversation.id
        phone = customer.phone_number
    except Exception as exc:
        logger.exception("Error preparando mensaje de %s: %s", incoming.phone_number, exc)
        return
    finally:
        db.close()

    # ── Encolar y programar la respuesta agrupada ─────────────────────────────
    if conv_id is None:
        return
    buf = _buffers.setdefault(conv_id, {"items": [], "seq": 0, "phone": phone, "company_id": company_id})
    buf["phone"] = phone
    buf["company_id"] = company_id
    buf["items"].append({
        "text": incoming.text or "",
        "image_media_id": incoming.image_media_id,
        "audio_media_id": incoming.audio_media_id,
        "document_media_id": incoming.document_media_id,
    })
    buf["seq"] += 1
    seq = buf["seq"]
    task = asyncio.create_task(_debounce_and_flush(conv_id, seq))
    _flush_tasks.add(task)
    task.add_done_callback(_flush_tasks.discard)


async def _debounce_and_flush(conv_id: int, seq: int) -> None:
    """Espera el tiempo de debounce; si no llegó un mensaje más nuevo, responde al lote."""
    await asyncio.sleep(_DEBOUNCE_SECONDS)
    buf = _buffers.get(conv_id)
    if not buf or buf["seq"] != seq:
        return  # llegó otro mensaje después; ese task se encargará de responder
    items = buf["items"]
    phone = buf["phone"]
    company_id = buf["company_id"]
    _buffers.pop(conv_id, None)
    try:
        await _respond_to_batch(conv_id, company_id, phone, items)
    except Exception as exc:
        logger.exception("Error respondiendo al lote de %s: %s", phone, exc)


async def _respond_to_batch(conv_id: int, company_id: int, phone: str, items: list[dict]) -> None:
    """Genera UNA respuesta para todos los mensajes agrupados del cliente."""
    db = SessionLocal()
    try:
        conversation = crud.get_conversation_by_id(db, conv_id)
        if not conversation or conversation.mode == "human":
            return
        company = crud.get_company(db, company_id)
        if not company:
            return
        creds = _creds_for(company)
        customer = crud.get_or_create_customer(db, company_id, phone)

        texts = [it["text"].strip() for it in items if it.get("text") and it["text"].strip()]
        image_ids = [it["image_media_id"] for it in items if it.get("image_media_id")]
        image_ids += [it["document_media_id"] for it in items if it.get("document_media_id")]
        audio_ids = [it["audio_media_id"] for it in items if it.get("audio_media_id")]

        # ── Audios: transcribir y sumarlos al texto del cliente ───────────────
        for aid in audio_ids:
            result = await download_media_bytes(creds, aid)
            if not result:
                continue
            audio_bytes, mime_type = result
            transcribed = transcribe_audio(audio_bytes, mime_type)
            if transcribed:
                texts.append(transcribed)
                crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                                  sender="ai", content=f"[NOTA INTERNA] Audio transcrito: {transcribed}")

        client_text = "\n".join(texts).strip()

        # Si solo llegó audio y no se pudo transcribir nada, avisa amablemente
        if audio_ids and not client_text and not image_ids:
            await send_text_message(creds, phone, _get_audio_error(customer.preferred_language))
            return

        if image_ids:
            await _respond_with_images(db, company_id, creds, conversation, customer, image_ids, client_text)
        else:
            await _respond_text(db, company_id, creds, conversation, customer, client_text)
    finally:
        db.close()


async def _respond_text(db, company_id: int, creds: WhatsAppCreds, conversation, customer, client_text: str) -> None:
    """Camino de SOLO texto (y audios ya transcritos): una llamada al LLM y una respuesta."""
    # La conversación NUNCA se reinicia por inactividad: aunque el cliente tarde minutos
    # o días en responder, se continúa el mismo hilo con normalidad (sin re-saludo).
    is_returning = False

    history = load_conversation_history(db, conversation.id)
    db.refresh(customer)
    is_first_message = len(history) <= 1

    system_prompt = _build_customer_prompt(
        db, company_id, customer, is_first_message=is_first_message,
        is_returning=is_returning, previous_session_msgs=[],
    )
    lang_instruction = _get_language_instruction(customer.preferred_language)
    system_prompt = system_prompt + f"\n\n{lang_instruction}"

    try:
        ai_text = get_ai_response(system_prompt, history)
    except Exception as exc:
        logger.error("Error llamando a Claude: %s", exc)
        await send_text_message(creds, customer.phone_number, _get_error_message(customer.preferred_language))
        return

    await _process_ai_text(db, company_id, creds, conversation, customer, ai_text, client_text)


async def _process_ai_text(db, company_id: int, creds: WhatsAppCreds, conversation, customer,
                           ai_text: str, client_text: str) -> None:
    """Procesa la respuesta del LLM: etiquetas (nombre, datos, pedido, QR, media…) y la entrega."""
    # ── Escalación IA ─────────────────────────────────────────────────────────
    should_escalate, internal_note = check_ai_escalation(ai_text)
    if should_escalate:
        crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                          sender="ai", content=f"[NOTA INTERNA] {internal_note}")
        await _escalate(db, company_id, creds, conversation, customer.phone_number, reason=internal_note,
                        language=customer.preferred_language)
        return

    # ── Nombre del cliente ─────────────────────────────────────────────────────
    nombre_found, nombre_value, ai_text = _extract_tag(ai_text, "NOMBRE")
    if nombre_found and nombre_value and not customer.name:
        crud.update_customer(db, company_id, customer.phone_number, name=nombre_value)
        logger.info("Nombre del cliente actualizado: %s", nombre_value)

    # ── Datos del cliente ──────────────────────────────────────────────────────
    datos_found, datos_value, ai_text = _extract_tag(ai_text, "DATOS_CLIENTE")
    if datos_found and datos_value:
        client_data = _parse_client_data(datos_value)
        if client_data:
            crud.update_customer(db, company_id, customer.phone_number, **client_data)
            logger.info("Datos del cliente guardados: %s", client_data)

    # ── Segmentación del cliente ─────────────────────────────────────────────
    seg_found, seg_value, ai_text = _extract_tag(ai_text, "SEGMENTO")
    if seg_found and seg_value:
        key = crud.set_customer_segment(db, company_id, customer.id, seg_value)
        if key:
            logger.info("Cliente %s segmentado como: %s", customer.phone_number, key)

    # ── Pedido confirmado ──────────────────────────────────────────────────────
    auto_qr = False
    pedido_found, pedido_data, ai_text = _extract_tag(ai_text, "PEDIDO_CONFIRMADO")
    if pedido_found:
        db.refresh(customer)
        client_in_order = _parse_client_data(pedido_data)
        if client_in_order:
            crud.update_customer(db, company_id, customer.phone_number, **client_in_order)
            db.refresh(customer)

        order = _parse_order_data(db, company_id, pedido_data)
        es_contra_entrega = "contra" in order["pago"]
        if not es_contra_entrega:
            auto_qr = True
        # Evitar pedidos DUPLICADOS: si la IA re-emite la etiqueta (p.ej. al despedirse),
        # no crear otro pedido idéntico y reciente en la misma conversación.
        if _is_duplicate_order(db, conversation.id, order):
            logger.info("Pedido duplicado ignorado en conv %d (misma compra reciente)", conversation.id)
            pedido_found = False  # no notificar de nuevo
        try:
            if pedido_found:
                crud.create_order(
                    db,
                    company_id=company_id,
                    customer_id=customer.id,
                    conversation_id=conversation.id,
                    items=order["items"],
                    total=order["total"],
                    payment_method=order["pago"] or None,
                    shipping_city=order["ciudad"] or customer.city,
                    status="paid" if es_contra_entrega else "pending",
                )
                logger.info("Pedido creado para conv %d (%s): %s",
                            conversation.id, "PAGADO" if es_contra_entrega else "pendiente", order)
                # Contra entrega = venta CERRADA al confirmar -> notificar al administrador
                if es_contra_entrega:
                    _notify_sale_closed(company_id, customer, order["items"], order["total"],
                                        "Contra entrega", order["ciudad"] or customer.city or "")
            if pedido_found and order.get("cupon"):
                redeemed = crud.redeem_coupon(db, company_id, order["cupon"])
                if redeemed:
                    logger.info("Cupón %s aplicado (usos: %d)", redeemed.code, redeemed.uses)
        except Exception as exc:
            logger.error("No se pudo crear el pedido: %s", exc)

        if pedido_found:
            notify_new_order(
                company_id=company_id,
                phone_number=customer.phone_number,
                customer_name=customer.name or "",
                order_data=pedido_data,
            )

    # ── Recontacto ─────────────────────────────────────────────────────────────
    recon_found, recon_value, ai_text = _extract_tag(ai_text, "RECONTACTO")
    if recon_found and recon_value:
        try:
            kv = _parse_kv(recon_value)
            dias = int(re.sub(r'[^\d]', '', kv.get('dias', '') or kv.get('días', '')) or '0')
            if dias > 0:
                from datetime import timedelta
                due = datetime.utcnow() + timedelta(days=dias)
                crud.create_reminder(db, company_id=company_id, customer_id=customer.id,
                                     conversation_id=conversation.id, due_at=due, note=kv.get('motivo') or "")
                logger.info("Recordatorio agendado para conv %d en %d días", conversation.id, dias)
        except Exception as exc:
            logger.error("No se pudo agendar recordatorio: %s", exc)

    # ── Cita / reserva agendada por el bot ──────────────────────────────────────
    cita_found, cita_value, ai_text = _extract_tag(ai_text, "CITA_AGENDADA")
    if cita_found and cita_value:
        try:
            kv = _parse_kv(cita_value)
            fecha = (kv.get('fecha') or '').strip()
            hora = (kv.get('hora') or '').strip()
            scheduled_at = None
            if fecha and hora:
                try:
                    scheduled_at = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
                except ValueError:
                    scheduled_at = None
            notes = kv.get('notas') or ""
            if not scheduled_at:
                # No se pudo interpretar la fecha/hora: se guarda para revisión manual
                # en vez de perder la cita, dejando en notas lo que dijo el cliente.
                scheduled_at = datetime.utcnow()
                notes = f"⚠️ Revisar fecha/hora (texto original: fecha={fecha!r} hora={hora!r}). {notes}".strip()
            crud.create_appointment(
                db, company_id=company_id, scheduled_at=scheduled_at,
                customer_name=kv.get('nombre') or customer.name, customer_phone=customer.phone_number,
                service=kv.get('servicio') or "", notes=notes, source="bot",
                customer_id=customer.id, conversation_id=conversation.id, status="pending",
            )
            logger.info("Cita agendada por el bot para conv %d: %s", conversation.id, cita_value)
        except Exception as exc:
            logger.error("No se pudo agendar la cita: %s", exc)

    # ── QR ─────────────────────────────────────────────────────────────────────
    qr_found, _, ai_text = _extract_tag(ai_text, "ENVIAR_QR")
    if qr_found or auto_qr:
        await _send_qr(company_id, creds, customer.phone_number)

    # ── Media de productos ─────────────────────────────────────────────────────
    media_found, media_value, ai_text = _extract_tag(ai_text, "ENVIAR_MEDIA")
    video_found, video_value, ai_text = _extract_tag(ai_text, "ENVIAR_VIDEO")
    link_found, link_value, ai_text = _extract_tag(ai_text, "ENVIAR_LINK")
    voice_found, _, ai_text = _extract_tag(ai_text, "ENVIAR_VOZ")
    want_voice = voice_found or _detect_voice_request(client_text)

    await _deliver_response(db, company_id, creds, conversation, customer.phone_number, ai_text, want_voice=want_voice)

    if not video_found:
        await _handle_product_photos(db, company_id, creds, conversation, customer.phone_number,
                                     media_value, client_text, from_tag=media_found)
    if video_found and video_value:
        await _send_product_video(db, company_id, creds, customer.phone_number, video_value, conversation=conversation)
    if link_found and link_value:
        await _send_product_link(db, company_id, creds, customer.phone_number, link_value, conversation=conversation)


def _build_customer_prompt(db, company_id: int, customer, is_first_message: bool = False,
                           is_returning: bool = False, previous_session_msgs=None) -> str:
    """Construye el system prompt COMPLETO del cliente (catálogo, datos, pagos, cupones,
    entrenamiento, etc.). Lo usan tanto la ruta de texto como la de audio para que el bot
    tenga las mismas capacidades por cualquier canal."""
    saved_data = {
        "cedula": customer.cedula,
        "email": customer.email,
        "address": customer.address,
        "city": customer.city,
    }
    last_order_summary = None
    last_order = crud.get_last_order_for_customer(db, customer.id)
    if last_order:
        try:
            import json as _json
            items = _json.loads(last_order.items_json) if last_order.items_json else []
            prods = ", ".join(f"{it.get('name','Producto')} x{it.get('quantity',1)}" for it in items)
        except Exception:
            prods = "pedido anterior"
        total_txt = f" — Total ${int(last_order.total):,} COP".replace(",", ".") if last_order.total else ""
        estado = "pagado" if last_order.status == "paid" else "pendiente"
        last_order_summary = f"{prods}{total_txt} ({estado})"

    pv_cfg = crud.get_postventa_config(db, company_id)
    company = crud.get_company(db, company_id)
    products = crud.list_products(db, company_id)
    return build_system_prompt(
        company_name=company.name if company else "",
        business_type=company.business_type if company else "otro",
        products=[{"sku": p.sku, "name": p.name, "price": p.price, "description": p.description}
                 for p in products],
        customer_name=customer.name,
        is_first_message=is_first_message,
        is_returning=is_returning,
        previous_session_msgs=previous_session_msgs,
        saved_data=saved_data,
        last_order_summary=last_order_summary,
        review_info={"review_link": pv_cfg.get("review_link"), "incentive": pv_cfg.get("incentive"),
                     "incentive_custom": pv_cfg.get("incentive_custom")},
        catalog_overrides=crud.get_catalog_overrides(db, company_id),
        payment_config=crud.get_payment_config(db, company_id),
        coupons=[{"code": c.code, "kind": c.kind, "value": c.value} for c in crud.get_active_coupons(db, company_id)],
        training_notes=crud.get_training_notes(db, company_id),
        bot_name=crud.get_bot_name(db, company_id),
        extra_info=_format_extra_info(db, company_id),
    )


def _format_extra_info(db, company_id: int) -> str:
    """Campos extra propios del tipo de negocio (horario, tallas, zonas, etc.),
    cargados desde Configuración → Información del negocio, como texto legible."""
    from app.onboarding_templates import get_extra_fields
    company = crud.get_company(db, company_id)
    if not company:
        return ""
    labels = get_extra_fields(company.business_type)
    values = crud.get_extra_config(db, company_id)
    lines = [f"  • {labels.get(k, k)}: {v}" for k, v in values.items() if (v or "").strip()]
    return "\n".join(lines)


async def _deliver_response(db, company_id: int, creds: WhatsAppCreds, conversation, phone_number: str,
                            text: str, want_voice: bool = False) -> None:
    """
    Entrega la respuesta del bot. Si want_voice y la voz está configurada, envía SOLO la nota de voz
    (no el texto). Si no, envía texto. Siempre guarda el texto en la BD para el panel.
    """
    voice_sent = False
    if want_voice:
        try:
            cfg = crud.get_voice_config(db, company_id)
            if cfg.get("enabled") and cfg.get("voice_id"):
                from app.voice_service import text_to_speech
                from app.whatsapp.client import upload_audio_to_whatsapp, send_audio_by_id, send_audio_by_url
                from app.audio_service import convert_to_ogg_opus
                from app.runtime import public_base
                audio = text_to_speech(text, cfg["voice_id"])
                if audio:
                    # ElevenLabs entrega MP3; lo pasamos a OGG/Opus para que llegue como nota de voz
                    a_mime, a_name = "audio/mpeg", "voz.mp3"
                    converted = convert_to_ogg_opus(audio, a_mime)
                    if converted:
                        audio, a_mime, a_name = converted
                    # Preferir URL pública (se reproduce bien en celular y Business); respaldo media_id
                    import uuid as _uuid
                    base = public_base()
                    if base and a_mime == "audio/ogg":
                        key = f"aud-{_uuid.uuid4().hex[:12]}"
                        crud.save_media_blob(db, company_id, key, "audio", audio, "audio/ogg")
                        if await send_audio_by_url(creds, phone_number, f"{base}/media/{company_id}/{key}/audio"):
                            voice_sent = True
                    if not voice_sent:
                        media_id = await upload_audio_to_whatsapp(creds, audio, a_mime, a_name)
                        if media_id and await send_audio_by_id(creds, phone_number, media_id):
                            voice_sent = True
        except Exception as exc:
            logger.error("No se pudo enviar nota de voz: %s", exc)

    if not voice_sent:
        await send_text_message(creds, phone_number, text)

    crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                      sender="ai", content=text)


async def _respond_with_images(db, company_id: int, creds: WhatsAppCreds, conversation, customer,
                               image_ids: list[str], client_text: str) -> None:
    """Analiza UNA o VARIAS imágenes del cliente (junto con el texto que las acompaña)
    en una sola llamada de visión, y responde una sola vez. Clasifica comprobante /
    producto / otro y conserva la lógica de validación de pagos."""
    _IMG_ERROR = (
        "Recibí tu imagen pero no pude procesarla en este momento. "
        "Por favor intenta de nuevo o escribe 'asesor'. 🙏"
    )
    # Descargar todas las imágenes (en base64) para enviarlas juntas a la visión
    images: list[tuple[str, str]] = []
    for mid in image_ids:
        result = await download_media_as_base64(creds, mid)
        if result:
            images.append(result)
    if not images:
        await send_text_message(creds, customer.phone_number, _IMG_ERROR)
        return
    # La imagen guardada como comprobante es la primera (suele ser la única)
    image_b64, mime_type = images[0]
    try:
        from app.agent.claude_client import analyze_image

        # Monto esperado + hora del pedido pendiente de esta conversación (si existe)
        pending_order = crud.get_latest_order_for_conversation(db, conversation.id)
        expected_amount = pending_order.total if (pending_order and pending_order.total) else None
        order_time_str = None
        if pending_order and pending_order.created_at:
            from datetime import timedelta
            co_time = pending_order.created_at - timedelta(hours=5)  # UTC -> Colombia
            order_time_str = co_time.strftime("%d/%m/%Y %I:%M %p")

        # Una sola llamada de visión con TODAS las imágenes + el texto del cliente.
        response_text = analyze_image(images, customer_name=customer.name,
                                      expected_amount=int(expected_amount) if expected_amount else None,
                                      order_time_str=order_time_str,
                                      payment_config=crud.get_payment_config(db, company_id),
                                      client_text=client_text)

        # Extraer la clasificación y las etiquetas de comprobante
        _, image_type, response_text = _extract_tag(response_text, "TIPO_IMAGEN")
        receipt_valid, receipt_data, response_text = _extract_tag(response_text, "COMPROBANTE_VALIDO")
        receipt_invalid, invalid_reason, response_text = _extract_tag(response_text, "COMPROBANTE_INVALIDO")
        _, _, response_text = _extract_tag(response_text, "PRODUCTO")
        # Por si la imagen viene acompañada de intención de compra, respeta las etiquetas de venta
        media_found, media_value, response_text = _extract_tag(response_text, "ENVIAR_MEDIA")
        link_found, link_value, response_text = _extract_tag(response_text, "ENVIAR_LINK")

        image_type = (image_type or "").strip().lower()
        es_comprobante = bool(receipt_valid or receipt_invalid or image_type == "comprobante")

        if receipt_valid and receipt_data:
            logger.info("Comprobante de pago VÁLIDO recibido para %s: %s", customer.phone_number, receipt_data)
            paid_order = crud.mark_order_paid(db, conversation.id)
            crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                              sender="ai", content=f"[NOTA INTERNA] Comprobante VÁLIDO recibido. Venta cerrada: {receipt_data}")
            # Venta cerrada por transferencia/QR -> notificar al administrador
            if paid_order:
                try:
                    import json as _json
                    p_items = _json.loads(paid_order.items_json) if paid_order.items_json else []
                except Exception:
                    p_items = []
                _notify_sale_closed(company_id, customer, p_items, paid_order.total,
                                    paid_order.payment_method or "Transferencia",
                                    paid_order.shipping_city or customer.city or "")
        elif receipt_invalid and invalid_reason:
            logger.warning("Comprobante de pago INVÁLIDO para %s: %s", customer.phone_number, invalid_reason)
        elif image_type == "producto":
            logger.info("Imagen de PRODUCTO recibida de %s", customer.phone_number)

        # Guardar el comprobante (imagen + datos) para el archivo del cliente
        if es_comprobante:
            try:
                kv = _parse_kv(receipt_data) if receipt_valid else {}
                crud.save_receipt(
                    db,
                    company_id=company_id,
                    customer_id=customer.id,
                    conversation_id=conversation.id,
                    image_b64=image_b64,
                    mime_type=mime_type,
                    bank=kv.get("banco"),
                    amount=_money_to_int(kv.get("monto", "")),
                    reference=kv.get("referencia"),
                    receipt_date=kv.get("fecha"),
                    is_valid=bool(receipt_valid),
                    order_id=pending_order.id if pending_order else None,
                )
            except Exception as exc:
                logger.error("No se pudo guardar el comprobante: %s", exc)
    except Exception as exc:
        logger.error("Error analizando imagen: %s", exc)
        await send_text_message(creds, customer.phone_number, _IMG_ERROR)
        return

    await send_text_message(creds, customer.phone_number, response_text)
    crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                      sender="ai", content=response_text)

    # Si la respuesta de visión pidió mostrar foto/link de un producto, hazlo
    if media_found:
        await _handle_product_photos(db, company_id, creds, conversation, customer.phone_number,
                                     media_value, client_text, from_tag=True)
    if link_found and link_value:
        await _send_product_link(db, company_id, creds, customer.phone_number, link_value, conversation=conversation)


async def _send_qr(company_id: int, creds: WhatsAppCreds, phone_number: str) -> None:
    try:
        db = SessionLocal()
        try:
            qr = crud.get_qr_config(db, company_id)
        finally:
            db.close()
        if not qr.get("enabled"):
            logger.info("QR deshabilitado en la base de datos")
            return
        caption = qr.get("caption", "")
        media_id = qr.get("media_id", "")
        if media_id:
            await send_image_message(creds, phone_number, caption=caption, media_id=media_id)
        else:
            logger.warning("QR habilitado pero sin imagen configurada en la BD")
    except Exception as exc:
        logger.error("Error enviando QR: %s", exc)


def _resolve_sku(db, company_id: int, token: str, media_cfg: dict) -> str | None:
    """Devuelve un SKU válido a partir de un token que puede ser el SKU o un nombre
    (busca coincidencia exacta de SKU, o por nombre dentro del catálogo de la empresa)."""
    token = (token or "").strip()
    if not token:
        return None
    if token in media_cfg:
        return token
    low = _norm_txt(token)
    for p in crud.list_products(db, company_id):
        if _norm_txt(p.name) in low or low in _norm_txt(p.name):
            return p.sku
    return None


def _skus_from_text(db, company_id: int, text: str) -> list[str]:
    """SKUs de productos mencionados en un texto (para enviar la foto al preguntar)."""
    low = _norm_txt(text or "")
    found = []
    for p in crud.list_products(db, company_id):
        if _norm_txt(p.name) in low and p.sku not in found:
            found.append(p.sku)
    return found[:2]


async def _send_one_photo(db, company_id: int, creds: WhatsAppCreds, phone_number: str, sku: str) -> bool:
    """Envía la foto de UN producto, igual que el QR: re-sube el archivo guardado y lo
    manda por un media_id fresco (a prueba de caducidad). Devuelve True si se envió."""
    from app.whatsapp.media_send import send_product_photo
    return await send_product_photo(db, company_id, creds, phone_number, sku)


_SEE_PHOTO_KEYWORDS = [
    "foto", "fotos", "muéstra", "muestra", "muéstrame", "muestrame", "muéstramelo", "muestramelo",
    "verlo", "verla", "ver el producto", "ver la", "imagen", "imágenes", "imagenes",
    "enséña", "ensena", "enséñame", "ensename", "cómo se ve", "como se ve", "cómo es", "como es",
    "mándame la foto", "mandame la foto", "envíame la foto", "enviame la foto", "pásame la foto", "pasame la foto",
]


def _wants_to_see_photo(text: str) -> bool:
    """El cliente pide EXPLÍCITAMENTE ver el producto (permite reenviar la foto)."""
    low = (text or "").lower()
    return any(k in low for k in _SEE_PHOTO_KEYWORDS)


async def _handle_product_photos(db, company_id: int, creds: WhatsAppCreds, conversation, phone_number: str,
                                 tag_value: str, client_text: str, from_tag: bool) -> None:
    """Envía la foto del producto en SOLO dos casos:
      1) Mostrar el producto por el que pregunta el cliente: UNA sola vez por conversación.
      2) Si el cliente pide ver la foto explícitamente: se envía aunque ya se haya enviado.
    """
    media_cfg = crud.get_product_media(db, company_id)
    blobs = crud.media_blob_skus(db, company_id)
    # Candidatos: del tag del bot, o (si no hay tag) de los productos nombrados por el cliente
    if from_tag and tag_value:
        raw = [s.strip() for s in re.split(r'[,\s]+', tag_value) if s.strip()]
    else:
        raw = _skus_from_text(db, company_id, client_text)

    explicit = _wants_to_see_photo(client_text)
    skus, seen = [], set()
    for tok in raw:
        sku = _resolve_sku(db, company_id, tok, media_cfg)
        if sku and sku not in seen:
            seen.add(sku); skus.append(sku)

    for sku in skus:
        item = media_cfg.get(sku, {})
        tiene_foto = bool(item.get("image_media_id") or (sku, "image") in blobs)
        if not tiene_foto:
            continue  # sin foto cargada
        if not explicit and crud.photo_already_sent(db, conversation.id, sku):
            continue  # ya se envió en esta conversación y no la pidió explícitamente
        ok = await _send_one_photo(db, company_id, creds, phone_number, sku)
        if ok:
            crud.mark_photo_sent(db, conversation.id, sku)
            # Registrar en el historial del chat (se muestra como miniatura en el panel)
            from app.catalog_util import media_marker
            product_name = next((p.name for p in crud.list_products(db, company_id) if p.sku == sku), sku)
            crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                              sender="ai", content=media_marker("image", sku, product_name))


async def _send_product_link(db, company_id: int, creds: WhatsAppCreds, phone_number: str,
                             skus_str: str, conversation=None) -> None:
    """Enviar SOLO el link de compra directa del producto (configurado en el panel)."""
    media_cfg = crud.get_product_media(db, company_id)
    raw = [s.strip() for s in re.split(r'[,\s]+', skus_str) if s.strip()]
    for tok in raw:
        sku = _resolve_sku(db, company_id, tok, media_cfg)
        item = media_cfg.get(sku) if sku else None
        if item and item.get("link"):
            product_name = next((p.name for p in crud.list_products(db, company_id) if p.sku == sku), sku)
            msg = f"🛒 {product_name}: {item['link']}"
            await send_text_message(creds, phone_number, msg)
            if conversation is not None:
                crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                                  sender="ai", content=msg)


async def _send_product_video(db, company_id: int, creds: WhatsAppCreds, phone_number: str,
                              skus_str: str, conversation=None) -> None:
    """Enviar SOLO el video de modo de uso del producto (envío confiable estilo QR)."""
    from app.whatsapp.media_send import send_product_video
    from app.catalog_util import media_marker
    media_cfg = crud.get_product_media(db, company_id)
    raw = [s.strip() for s in re.split(r'[,\s]+', skus_str) if s.strip()]
    skus, seen = [], set()
    for tok in raw:
        sku = _resolve_sku(db, company_id, tok, media_cfg)
        if sku and sku not in seen:
            seen.add(sku); skus.append(sku)
    for sku in skus:
        ok = await send_product_video(db, company_id, creds, phone_number, sku)
        if ok and conversation is not None:
            product_name = next((p.name for p in crud.list_products(db, company_id) if p.sku == sku), sku)
            crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                              sender="ai", content=media_marker("video", sku, product_name))


async def _escalate(db, company_id: int, creds: WhatsAppCreds, conversation, phone_number: str,
                    reason: str, language: str = "es") -> None:
    escalation_messages = {
        "es": "Entiendo que necesitas hablar con un asesor. Te estoy conectando ahora. Alguien se comunicará contigo en breve. 💚",
        "en": "I understand you need to speak with an advisor. Connecting you now. Someone will reach out shortly. 💚",
        "pt": "Entendo que você precisa falar com um consultor. Conectando-o agora. Alguém entrará em contato em breve. 💚",
    }
    msg = escalation_messages.get(language, escalation_messages["es"])
    crud.set_conversation_mode(db, conversation.id, "human", reason=reason)
    crud.create_advisor_session(db, company_id, conversation.id)
    await send_text_message(creds, phone_number, msg)
    crud.save_message(db, company_id=company_id, conversation_id=conversation.id, direction="outbound",
                      sender="ai", content=msg)
    logger.info("Conversación %d escalada: %s", conversation.id, reason)