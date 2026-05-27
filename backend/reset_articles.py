"""Vacía las notas y todo lo derivado para re-recolectar desde cero.

Borra: articles, analyses, stories, alerts, user_alert_reads, user_favorites.
Conserva: portals (seed), users, visits.
Resetea portals.last_refreshed_at y cultural_bucket para que el próximo refresh
re-recolecte y recompute limpio.

Uso:
    python reset_articles.py            # pide confirmación
    python reset_articles.py --yes      # sin prompt (para automatizar)

Corre contra la BD que indique DATABASE_URL (¡puede ser producción!).
"""
from __future__ import annotations

import re
import sys

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal

# Orden FK-safe: primero las tablas que referencian a otras.
_DELETE_ORDER = [
    "user_alert_reads",   # -> alerts
    "alerts",             # -> stories
    "user_favorites",     # -> articles
    "analyses",           # -> articles
    "articles",           # -> stories, portals
    "stories",
]


def _masked_url() -> str:
    return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", settings.database_url)


def main() -> None:
    auto_yes = "--yes" in sys.argv

    with SessionLocal() as session:
        counts = {
            t: session.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            for t in _DELETE_ORDER
        }
        total = sum(c or 0 for c in counts.values())

        print(f"BD destino: {_masked_url()}")
        print("Se borrarán:")
        for t, c in counts.items():
            print(f"  {t:20} {c}")
        print(f"  {'TOTAL':20} {total}")
        print("Se conservan: portals, users, visits")

        if total == 0:
            print("Nada para borrar. Salgo.")
            return

        if not auto_yes:
            resp = input("\n¿Confirmás el borrado? Escribí 'BORRAR' para continuar: ")
            if resp.strip() != "BORRAR":
                print("Cancelado.")
                return

        for t in _DELETE_ORDER:
            session.execute(text(f"DELETE FROM {t}"))
        # Reset de portales: el próximo refresh recolecta y recomputa.
        session.execute(
            text("UPDATE portals SET last_refreshed_at = NULL, cultural_bucket = 'centro'")
        )
        session.commit()

    print("\nListo. Notas borradas; portales/usuarios/visitas intactos.")
    print("Corré un refresh (o levantá el backend con el scheduler) para re-recolectar con Haiku.")


if __name__ == "__main__":
    main()
