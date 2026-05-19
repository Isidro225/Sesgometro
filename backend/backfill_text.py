"""One-shot: scrapea y guarda el cuerpo de todos los artículos sin `text`.

Después de agregar la columna `articles.text`, los artículos existentes quedan
con NULL. Este script los visita en serie (con tolerancia a fallos) y persiste
el texto para que los próximos re-análisis no tengan que volver a scrapear.

Uso:
    python backfill_text.py             # backfill todos los que falten
    python backfill_text.py --limit 10  # solo los primeros 10 (testing)
    python backfill_text.py --ids 1,2,3 # solo IDs específicos
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

from sqlalchemy import select

from app import scraper
from app.config import settings
from app.db import SessionLocal
from app.models import Article

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def _list_targets(ids: list[int] | None, limit: int | None) -> list[tuple[int, str]]:
    with SessionLocal() as session:
        stmt = select(Article.id, Article.url).where(Article.text.is_(None))
        if ids:
            stmt = stmt.where(Article.id.in_(ids))
        stmt = stmt.order_by(Article.id)
        if limit:
            stmt = stmt.limit(limit)
        return [(r[0], r[1]) for r in session.execute(stmt).all()]


def _save_text(aid: int, text: str) -> None:
    with SessionLocal() as session:
        art = session.get(Article, aid)
        if art is None:
            return
        art.text = text
        session.commit()


async def backfill_one(aid: int, url: str) -> tuple[bool, int]:
    try:
        scraped = await scraper.scrape(url)
    except Exception as exc:
        print(f"  id={aid} FAIL: {str(exc)[:120]}", flush=True)
        return False, 0
    await asyncio.to_thread(_save_text, aid, scraped.text)
    chars = len(scraped.text)
    print(f"  id={aid} OK  chars={chars}  ({url[:80]})", flush=True)
    return True, chars


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--limit", type=int, help="Tope de artículos a procesar")
    parser.add_argument("--ids", help="IDs específicos separados por coma")
    args = parser.parse_args()

    ids = [int(x) for x in args.ids.split(",")] if args.ids else None
    safe_db = settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url
    print(f"DB target: {safe_db}")

    targets = _list_targets(ids, args.limit)
    print(f"A backfillear: {len(targets)} artículos sin text.\n")
    if not targets:
        return 0

    ok = fail = total_chars = 0
    t0 = time.time()
    for aid, url in targets:
        success, chars = await backfill_one(aid, url)
        if success:
            ok += 1
            total_chars += chars
        else:
            fail += 1

    elapsed = time.time() - t0
    print(
        f"\nOK={ok}  FAIL={fail}  total_chars={total_chars:,}  tiempo={elapsed:.1f}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
