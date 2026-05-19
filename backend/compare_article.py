"""Re-analiza una o varias notas contra el prompt actual y compara con producción.

NO escribe en la BD. Pensado para iterar prompt/modelo sobre notas concretas.

Lee scores 'viejos' del API de producción (Railway) por ID. Después scrapea
la URL y la analiza localmente con el prompt actual.

Uso típico (desde backend/, con venv activo y Ollama corriendo):
    python compare_article.py --ids 560
    python compare_article.py --ids 560,557,555,533,554

Si pasás --url se analiza esa URL sin comparar con producción (no hay baseline).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import httpx

# Consola de Windows usa cp1252 por default → rompe acentos y unicode.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

from app import analyzer, scraper
from app.db import SessionLocal
from app.models import Article, Portal
from app.schemas import ScrapedArticle

PROD_API = "https://luminous-renewal-production-7d9c.up.railway.app"


def _load_cached_by_url(url: str) -> ScrapedArticle | None:
    """Devuelve el ScrapedArticle desde la BD si el texto ya está cacheado."""
    with SessionLocal() as session:
        art = session.query(Article).filter(Article.url == url).first()
        if art is None or not art.text:
            return None
        portal = session.get(Portal, art.portal_id)
        return ScrapedArticle(
            url=art.url,
            title=art.title,
            author=art.author,
            site_name=(portal.name if portal else None),
            published_at=art.published_at,
            text=art.text,
            word_count=art.word_count or len(art.text.split()),
            image_url=art.image_url,
        )


def fetch_old(article_id: int) -> dict:
    """Trae article + analysis de producción por ID."""
    r = httpx.get(f"{PROD_API}/api/articles/{article_id}", timeout=15)
    r.raise_for_status()
    return r.json()


def _row(name: str, old: float | None, new: float) -> str:
    if old is None:
        return f"  {name:32s} {'-':>8s}  {'(sin baseline)':>18s}  {new:+.2f}"
    arrow = "->" if abs(new - old) < 0.01 else f"-> delta={new - old:+.2f}"
    return f"  {name:32s} {old:+.2f}    {arrow:>18s}  {new:+.2f}"


async def analyze_one(url: str, baseline: dict | None) -> None:
    cached = await asyncio.to_thread(_load_cached_by_url, url)
    if cached is not None:
        print(f"Cache hit: {url}")
        article = cached
    else:
        print(f"Scrapeando: {url}")
        article = await scraper.scrape(url)
    print(f"  Titular: {article.title}")
    print(f"  Medio:   {article.site_name}")
    print(f"  Palabras: {article.word_count}")

    print("Analizando (puede tardar 30-90s con thinking ON)...")
    t0 = time.time()
    new = await asyncio.to_thread(analyzer.analyze, article)
    elapsed = time.time() - t0
    print(f"Listo en {elapsed:.1f}s")

    if baseline is not None:
        old_an = baseline.get("analysis", {})
        old_sta = old_an.get("statism_liberalism", {}).get("score")
        old_per = old_an.get("peronism_antiperonism", {}).get("score")
        old_cul = old_an.get("progressivism_conservatism", {}).get("score")
        old_emo = old_an.get("emotional_load")
        old_conf = old_an.get("confidence")
        old_label = old_an.get("overall_label")
    else:
        old_sta = old_per = old_cul = old_emo = old_conf = None
        old_label = None

    print(f"\n  {'eje':32s} {'viejo':>8s}  {'':>18s}  {'nuevo':>6s}")
    print(_row("statism_liberalism", old_sta, new.statism_liberalism.score))
    print(_row("peronism_antiperonism", old_per, new.peronism_antiperonism.score))
    print(
        _row(
            "progressivism_conservatism",
            old_cul,
            new.progressivism_conservatism.score,
        )
    )
    print(_row("emotional_load", old_emo, new.emotional_load))
    print(_row("confidence", old_conf, new.confidence))

    print(f"\n  label viejo: {old_label or '(sin baseline)'}")
    print(f"  label nuevo: {new.overall_label}")

    print("\n  justificaciones nuevas:")
    print(f"    statism:  {new.statism_liberalism.justification}")
    print(f"    peronism: {new.peronism_antiperonism.justification}")
    print(f"    cultural: {new.progressivism_conservatism.justification}")

    print("\n  framing nuevo:")
    for f in new.framing:
        q = (f.quote or "").strip()
        if q:
            q = q[:90] + ("..." if len(q) > 90 else "")
        print(f"    [{f.kind}] {f.description[:80]}")
        if q:
            print(f'      quote: "{q}"')

    print(f"\n  resumen neutro nuevo: {new.neutral_summary}")
    print("\n" + "=" * 80 + "\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ids", help="IDs separados por coma. Trae URL+baseline del API prod.")
    parser.add_argument("--url", help="URL directa. Sin baseline.")
    args = parser.parse_args()

    if not args.ids and not args.url:
        parser.error("Pasá --ids o --url.")

    if args.url:
        await analyze_one(args.url, baseline=None)
        return 0

    ids = [int(x) for x in args.ids.split(",") if x.strip()]
    print(f"Procesando {len(ids)} notas contra prod API.\n")
    for aid in ids:
        try:
            baseline = fetch_old(aid)
            url = baseline["article"]["url"]
            print(f">>> ID {aid}")
            await analyze_one(url, baseline=baseline)
        except Exception as exc:
            print(f"ID {aid}: error {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
