import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from app.config import settings
from app.webhook.models import WebhookPayload
from app.whatsapp.parser import extract_message
from app.agent.orchestrator import process_incoming_message

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    """Verificación de Meta. Un solo endpoint compartido por TODAS las empresas: se acepta
    el token de plataforma o el de cualquier empresa registrada (cada una puede traer su
    propio Meta App con su propio verify_token)."""
    if hub_mode != "subscribe":
        raise HTTPException(status_code=403, detail="Token inválido")
    if hub_verify_token and hub_verify_token == settings.webhook_verify_token:
        logger.info("Webhook verificado (token de plataforma).")
        return PlainTextResponse(hub_challenge)
    from app.db.database import SessionLocal
    from app.db import crud
    db = SessionLocal()
    try:
        if crud.get_company_by_webhook_verify_token(db, hub_verify_token):
            logger.info("Webhook verificado (token de una empresa).")
            return PlainTextResponse(hub_challenge)
    finally:
        db.close()
    logger.warning("Intento de verificación con token inválido.")
    raise HTTPException(status_code=403, detail="Token inválido")


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    """Un solo endpoint compartido por TODAS las empresas. Se resuelve a qué empresa
    pertenece el mensaje por el phone_number_id que Meta manda en el payload
    (value.metadata.phone_number_id) — ese es el número que RECIBIÓ el mensaje."""
    # Always return 200 immediately — Meta retries if we're slow
    try:
        body = await request.json()
        payload = WebhookPayload.model_validate(body)
        incoming = extract_message(payload)
        if incoming and incoming.receiving_phone_number_id:
            from app.db.database import SessionLocal
            from app.db import crud
            db = SessionLocal()
            try:
                company = crud.get_company_by_phone_number_id(db, incoming.receiving_phone_number_id)
            finally:
                db.close()
            if not company:
                logger.warning("Mensaje de un phone_number_id no registrado: %s",
                               incoming.receiving_phone_number_id)
            elif company.status == "paused":
                logger.info("Empresa '%s' pausada: mensaje ignorado.", company.name)
            else:
                background_tasks.add_task(process_incoming_message, incoming, company.id)
        elif incoming:
            logger.warning("Mensaje sin phone_number_id en el payload; no se puede enrutar a una empresa.")
    except Exception as exc:
        logger.error("Error procesando webhook: %s", exc)
    return {"status": "ok"}