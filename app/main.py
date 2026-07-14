import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.db.database import init_db, SessionLocal
from app.webhook.router import router as webhook_router
from app.admin.router import router as admin_router, run_followups, run_reminders
from app.master.router import router as master_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Intervalo del planificador interno (segundos). Cada hora revisa recordatorios;
# el postventa se ejecuta una vez al día. Corre para TODAS las empresas activas.
_SCHEDULER_INTERVAL = 3600
_last_followups_date = None


async def _scheduler_loop():
    """Tareas programadas internas (no requiere cron externo ni configuración).
    Corre dentro del mismo servidor mientras esté activo."""
    global _last_followups_date
    await asyncio.sleep(45)  # esperar a que el arranque se estabilice
    while True:
        # 1) Recordatorios de recontacto (cada hora)
        try:
            db = SessionLocal()
            try:
                res = await run_reminders(token=settings.master_admin_token, db=db)
                if res.get("sent"):
                    logger.info("Planificador: %d recordatorios enviados", res["sent"])
            finally:
                db.close()
        except Exception as exc:
            logger.error("Planificador (recordatorios): %s", exc)

        # 2) Postventa (una vez al día)
        try:
            today = datetime.utcnow().date()
            if _last_followups_date != today:
                db = SessionLocal()
                try:
                    res = await run_followups(token=settings.master_admin_token, db=db)
                    _last_followups_date = today
                    if res.get("sent"):
                        logger.info("Planificador: %d seguimientos postventa enviados", res["sent"])
                finally:
                    db.close()
        except Exception as exc:
            logger.error("Planificador (postventa): %s", exc)

        await asyncio.sleep(_SCHEDULER_INTERVAL)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Iniciando VitaBot SaaS...")
    init_db()
    logger.info("Base de datos inicializada.")
    import shutil
    ff = shutil.which("ffmpeg")
    logger.info("ffmpeg %s", f"disponible en {ff}" if ff else "NO DISPONIBLE (las notas de voz podrían fallar)")
    task = asyncio.create_task(_scheduler_loop())
    logger.info("Planificador interno iniciado (recordatorios + postventa, todas las empresas).")
    yield
    task.cancel()
    logger.info("Apagando servidor.")


app = FastAPI(
    title="VitaBot SaaS",
    description="Plataforma multi-empresa de agentes de WhatsApp con IA",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Cabeceras de seguridad básicas para todo el sitio (paneles y webhook)."""
    try:
        from app import runtime
        runtime.remember_base(str(request.base_url))
    except Exception:
        pass
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # microphone=(self) permite grabar notas de voz desde el PROPIO panel.
    # Con microphone=() el navegador lo bloquea para todos y no deja habilitarlo.
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=(self)"
    return response


app.include_router(webhook_router)
app.include_router(admin_router, prefix="/admin")
app.include_router(master_router, prefix="/master")


@app.get("/health")
async def health():
    import shutil
    from app import runtime
    return {"status": "ok", "service": "vitabot-saas",
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "public_base": runtime.public_base() or "(no detectada aún)"}
