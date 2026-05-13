"""Migra todos los datos del SQLite local al Postgres de Railway.

DESTRUCTIVO: borra todas las tablas del target y las recrea desde cero antes de
copiar. Preserva IDs y resetea las sequences de Postgres al final.

Uso (desde la carpeta `backend/`):

    python migrate_to_postgres.py --target "postgresql://user:pass@host:port/db"
    python migrate_to_postgres.py --target "$env:DATABASE_URL"       # PowerShell
    python migrate_to_postgres.py --dry-run --target "..."           # sin escribir
    python migrate_to_postgres.py --yes --target "..."               # sin prompt

Source default: sqlite:///./sesgometro.db
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import (
    Alert,
    Analysis,
    Article,
    Portal,
    Story,
    User,
    UserAlertRead,
    UserFavorite,
)

# Orden por dependencias de FK: padres antes que hijos.
MODELS_IN_ORDER = [
    Portal,
    Story,
    User,
    Article,
    Analysis,
    UserFavorite,
    Alert,
    UserAlertRead,
]


def row_to_dict(instance) -> dict:
    mapper = inspect(instance).mapper
    return {col.key: getattr(instance, col.key) for col in mapper.column_attrs}


def normalize_url(url: str) -> str:
    # SQLAlchemy 1.4+ no acepta postgres://; Railway a veces lo entrega así.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


def count_rows(session: Session, model) -> int:
    return session.query(model).count()


def print_summary(label: str, url: str, session: Session, only_existing: bool = False) -> None:
    print(f"\n=== {label} ===")
    # Ocultar credenciales del URL al imprimir.
    safe = url.split("@")[-1] if "@" in url else url
    print(f"  {safe}")
    existing = set(inspect(session.bind).get_table_names()) if only_existing else None
    for model in MODELS_IN_ORDER:
        tname = model.__tablename__
        if only_existing and tname not in existing:
            print(f"  {tname:20s}     -   (no existe)")
            continue
        count = count_rows(session, model)
        print(f"  {tname:20s} {count:6d} filas")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="sqlite:///./sesgometro.db")
    parser.add_argument("--target", required=True, help="DATABASE_URL del Postgres destino")
    parser.add_argument("--yes", action="store_true", help="Saltar el prompt de confirmación")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar lo que haría")
    args = parser.parse_args()

    target_url = normalize_url(args.target)

    if not target_url.startswith("postgresql://"):
        print(f"ABORTO: el target no parece Postgres -> {target_url}")
        print("Esperaba postgresql://... (o postgres:// que se autocorrige).")
        return 1

    source_engine = create_engine(args.source, future=True)
    target_engine = create_engine(target_url, future=True)
    SourceSession = sessionmaker(bind=source_engine, future=True)
    TargetSession = sessionmaker(bind=target_engine, future=True)

    with SourceSession() as source:
        print_summary("SOURCE (SQLite, se lee)", args.source, source)

    with TargetSession() as target:
        print_summary("TARGET (Postgres, se BORRA)", target_url, target, only_existing=True)

    if args.dry_run:
        print("\n--dry-run: salgo sin tocar el target.")
        return 0

    if not args.yes:
        print("\n[!] Esto va a DROPEAR todas las tablas del target y reemplazarlas")
        print("    con los datos del SQLite. Escribí 'si' para continuar:")
        answer = input("> ").strip().lower()
        if answer != "si":
            print("Cancelado.")
            return 1

    print("\n[1/4] Drop tables en target…")
    Base.metadata.drop_all(target_engine)

    print("[2/4] Create schema en target…")
    Base.metadata.create_all(target_engine)

    print("[3/4] Copiando filas (preservando IDs)…")
    with SourceSession() as source, TargetSession() as target:
        for model in MODELS_IN_ORDER:
            rows = source.query(model).order_by(model.id).all()
            for row in rows:
                target.add(model(**row_to_dict(row)))
            target.flush()
            print(f"      {model.__tablename__:20s} {len(rows):6d} filas copiadas")
        target.commit()

    print("[4/4] Reseteando sequences de Postgres…")
    with TargetSession() as target:
        for model in MODELS_IN_ORDER:
            tname = model.__tablename__
            target.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{tname}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {tname}), 1))"
                )
            )
        target.commit()

    print("\nListo. Verificá con:")
    print(f"  python -c \"from sqlalchemy import create_engine, text; "
          f"e=create_engine('{target_url.split('@')[0]}@...'); "
          f"print(e.connect().execute(text('SELECT COUNT(*) FROM articles')).scalar())\"")
    print("o desde Railway con 'railway connect Postgres' y un SELECT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
