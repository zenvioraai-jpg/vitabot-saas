import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings


def _ensure_sqlite_dir(database_url: str) -> None:
    """Si la BD es SQLite con ruta absoluta (ej: el volumen /data), crea la carpeta."""
    if database_url.startswith("sqlite:///"):
        path = database_url.replace("sqlite:///", "", 1)
        # sqlite:////data/x.db -> /data/x.db  | sqlite:///./x.db -> ./x.db
        directory = os.path.dirname(path)
        if directory and directory not in (".", ""):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception:
                pass


_ensure_sqlite_dir(settings.database_url)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_connection, _connection_record):
    """Solo aplica a SQLite. Cuando se migre a PostgreSQL (ver plan de Fase 2), esto
    simplemente no se ejecuta — Postgres maneja concurrencia y llaves foráneas nativamente."""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns():
    """Migración ligera y SEGURA: agrega columnas que falten en tablas ya existentes.
    `create_all` crea tablas nuevas pero NUNCA altera las existentes; si en el volumen
    hay una tabla con esquema viejo (ej: media_blobs sin la columna `data`), esto la
    completa sin borrar datos. Solo AGREGA columnas, nunca las quita."""
    import logging
    from sqlalchemy import inspect, text
    log = logging.getLogger(__name__)
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.name not in existing:
                continue  # tabla nueva -> la crea create_all
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                try:
                    coltype = col.type.compile(dialect=engine.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {coltype}'))
                    log.info("Migración: columna agregada %s.%s (%s)", table.name, col.name, coltype)
                except Exception as exc:
                    log.warning("No se pudo agregar columna %s.%s: %s", table.name, col.name, exc)


def init_db():
    from app.db import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
