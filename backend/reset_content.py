"""Script de uso único: borra contenido scrapeado/analizado.

Conserva `portals` y `users`. Pensado para correr antes de re-scrapear con
código nuevo (ej: prompt actualizado, filtro de alucinaciones). Después del
reset, levantá refresh-all desde el endpoint o reiniciá el server con
`run_initial_refresh=True`.

Uso (desde `backend/`):
    python reset_content.py
"""
from __future__ import annotations

from sqlalchemy import text

from app.db import SessionLocal


TABLES_TO_TRUNCATE = [
    # Orden importa: hijos antes que padres por las FKs.
    "user_alert_reads",
    "alerts",
    "user_favorites",
    "analyses",
    "articles",
    "stories",
]


def main() -> None:
    with SessionLocal() as session:
        for table in TABLES_TO_TRUNCATE:
            result = session.execute(text(f"DELETE FROM {table}"))
            print(f"  {table:20s}: {result.rowcount:5d} filas borradas")

        # Limpiar último refresh para que refresh-all reprocese todos los portales.
        session.execute(text("UPDATE portals SET last_refreshed_at = NULL"))
        session.commit()

    print("\nListo. Disparar refresh-all para repoblar:")
    print("  curl -X POST http://localhost:8000/api/portals/refresh-all")


if __name__ == "__main__":
    main()
