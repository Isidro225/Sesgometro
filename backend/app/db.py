from collections.abc import Iterator
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger("sesgometro.db")

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# Railway (y proxies en general) tiran conexiones idle. Sin pool_pre_ping,
# SQLAlchemy reusa la conexión muerta y el primer query falla con
# "server closed the connection unexpectedly".
# pool_recycle baja del default infinito a 5 min para reciclar antes de que
# el proxy cierre por idle.
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


# Columnas que se fueron agregando a tablas existentes a medida que el proyecto
# avanzó por fases. SQLite acepta `ALTER TABLE ADD COLUMN` simple, así que las
# parcheamos en init_db en lugar de meter Alembic.
_INCREMENTAL_COLUMNS: dict[str, dict[str, str]] = {
    "portals": {
        "bias_bucket": "VARCHAR(16) NOT NULL DEFAULT 'centro'",
        "economic_bucket": "VARCHAR(16) NOT NULL DEFAULT 'centro'",
        "peronism_bucket": "VARCHAR(16) NOT NULL DEFAULT 'centro'",
    },
    "analyses": {
        "statism_liberalism_score": "FLOAT",
        "statism_liberalism_label": "VARCHAR(128)",
        "statism_liberalism_justification": "TEXT",
        "peronism_antiperonism_score": "FLOAT",
        "peronism_antiperonism_label": "VARCHAR(128)",
        "peronism_antiperonism_justification": "TEXT",
    },
    "articles": {
        "story_id": "INTEGER REFERENCES stories(id)",
        "embedding_json": "TEXT",
        "image_url": "VARCHAR(1024)",
    },
    "stories": {
        "alerted_at": "DATETIME",
    },
}


def _patch_existing_tables() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _INCREMENTAL_COLUMNS.items():
            if table not in existing_tables:
                continue
            current = {col["name"] for col in inspector.get_columns(table)}
            for col_name, col_def in columns.items():
                if col_name in current:
                    continue
                logger.info("ALTER TABLE %s ADD COLUMN %s %s", table, col_name, col_def)
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col_name} {col_def}'))


def init_db() -> None:
    from app import models  # noqa: F401 — registra las tablas

    Base.metadata.create_all(bind=engine)
    _patch_existing_tables()


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
