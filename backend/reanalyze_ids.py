"""Re-analiza artículos seleccionados por filtros (IDs, portal, fecha, confidence).

Pensado para correr después de cambiar el prompt o para limpiar análisis viejos.
Es SECUENCIAL con backoff exponencial ante 429 para no saturar la API.

Apunta a la base configurada en settings.database_url (env var DATABASE_URL o
el .env del backend). Para reanalizar contra el Postgres de Railway en vez del
SQLite local:

    $env:DATABASE_URL = "postgresql://..."   (PowerShell)
    python reanalyze_ids.py --ids 253,247

Filtros (se combinan con AND):
    --ids 1,2,3                IDs explícitos
    --portal slug              todos los del portal (ej: lanacion)
    --before YYYY-MM-DD        descubiertos antes de la fecha
    --after  YYYY-MM-DD        descubiertos después
    --confidence-below X       analyses con confidence < X (ej: 0.5)
    --label-contains TXT       overall_label que contenga TXT (case-insensitive)
    --all-mock                 análisis que quedaron en is_mock=True
    --limit N                  procesar como mucho N artículos

Flags:
    --dry-run                  listar IDs sin reanalizar
    --yes                      saltar confirmación interactiva
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

from anthropic import APIStatusError
from sqlalchemy import select

from app import analyzer, scraper
from app.config import settings
from app.db import SessionLocal
from app.models import Analysis as AnalysisModel
from app.models import Article, Portal
from app.schemas import ScrapedArticle


async def analyze_with_retry(article_data, source_prior=None, max_retries: int = 5):
    delay = 5
    for attempt in range(max_retries):
        try:
            return await asyncio.to_thread(
                analyzer.analyze, article_data, source_prior
            )
        except APIStatusError as exc:
            if exc.status_code == 429 and attempt < max_retries - 1:
                print(
                    f"    429 rate limit, esperando {delay}s "
                    f"(intento {attempt+1}/{max_retries})",
                    flush=True,
                )
                await asyncio.sleep(delay)
                delay *= 2
                continue
            raise


def build_targets(args) -> list[tuple[int, str]]:
    stmt = (
        select(Article.id, Article.url)
        .join(AnalysisModel, AnalysisModel.article_id == Article.id, isouter=True)
    )

    if args.ids:
        ids = [int(x) for x in args.ids.split(",") if x.strip()]
        stmt = stmt.where(Article.id.in_(ids))

    if args.portal:
        stmt = stmt.join(Portal, Portal.id == Article.portal_id).where(
            Portal.slug == args.portal
        )

    if args.before:
        stmt = stmt.where(Article.discovered_at < datetime.fromisoformat(args.before))

    if args.after:
        stmt = stmt.where(Article.discovered_at >= datetime.fromisoformat(args.after))

    if args.confidence_below is not None:
        stmt = stmt.where(AnalysisModel.confidence < args.confidence_below)

    if args.label_contains:
        stmt = stmt.where(
            AnalysisModel.overall_label.ilike(f"%{args.label_contains}%")
        )

    if args.all_mock:
        stmt = stmt.where(AnalysisModel.is_mock.is_(True))

    stmt = stmt.order_by(Article.id)

    if args.limit:
        stmt = stmt.limit(args.limit)

    with SessionLocal() as session:
        rows = session.execute(stmt).all()
    return [(r[0], r[1]) for r in rows]


def _load_cached_article(
    aid: int,
) -> tuple[ScrapedArticle, analyzer.SourcePrior | None] | None:
    """Si el Article tiene texto cacheado en BD, devolvé un ScrapedArticle + prior
    derivado del portal. Devuelve None si falta texto (caller debe scrape + persist)."""
    with SessionLocal() as session:
        art = session.get(Article, aid)
        if art is None or not art.text:
            return None
        portal = session.get(Portal, art.portal_id)
        scraped = ScrapedArticle(
            url=art.url,
            title=art.title,
            author=art.author,
            site_name=(portal.name if portal else None),
            published_at=art.published_at,
            text=art.text,
            word_count=art.word_count or len(art.text.split()),
            image_url=art.image_url,
        )
        prior = _prior_from_portal(portal) if portal is not None else None
        return scraped, prior


def _prior_from_portal(portal: Portal) -> analyzer.SourcePrior | None:
    if not settings.use_source_prior:
        return None
    return analyzer.SourcePrior(
        economic_bucket=portal.economic_bucket,
        peronism_bucket=portal.peronism_bucket,
    )


def _portal_prior_by_article_id(aid: int) -> analyzer.SourcePrior | None:
    """Para artículos que requieren re-scrape: cargamos solo el portal y armamos prior."""
    with SessionLocal() as session:
        art = session.get(Article, aid)
        if art is None:
            return None
        portal = session.get(Portal, art.portal_id)
        return _prior_from_portal(portal) if portal is not None else None


def _persist_scraped_text(aid: int, text: str) -> None:
    """Guarda el texto recién scrapeado en la BD para evitar re-scrapeos futuros."""
    with SessionLocal() as session:
        art = session.get(Article, aid)
        if art is not None:
            art.text = text
            session.commit()


async def reanalyze_one(aid: int, url: str) -> bool:
    cached = await asyncio.to_thread(_load_cached_article, aid)
    if cached is not None:
        article_data, prior = cached
    else:
        try:
            article_data = await scraper.scrape(url)
        except Exception as exc:
            print(f"  id={aid} scrape_fail: {str(exc)[:120]}", flush=True)
            return False
        # Cacheamos el texto recién scrapeado para los próximos re-análisis.
        await asyncio.to_thread(_persist_scraped_text, aid, article_data.text)
        prior = await asyncio.to_thread(_portal_prior_by_article_id, aid)
    try:
        analysis = await analyze_with_retry(article_data, source_prior=prior)
    except Exception as exc:
        print(f"  id={aid} analyze_fail: {str(exc)[:120]}", flush=True)
        return False

    def _save() -> None:
        with SessionLocal() as session:
            an = session.scalar(
                select(AnalysisModel).where(AnalysisModel.article_id == aid)
            )
            if an is None:
                an = AnalysisModel(article_id=aid)
                session.add(an)
            an.statism_liberalism_score = analysis.statism_liberalism.score
            an.statism_liberalism_label = analysis.statism_liberalism.label
            an.statism_liberalism_justification = (
                analysis.statism_liberalism.justification
            )
            an.libauth_score = analysis.statism_liberalism.score
            an.libauth_label = analysis.statism_liberalism.label or ""
            an.libauth_justification = analysis.statism_liberalism.justification
            an.peronism_antiperonism_score = analysis.peronism_antiperonism.score
            an.peronism_antiperonism_label = analysis.peronism_antiperonism.label
            an.peronism_antiperonism_justification = (
                analysis.peronism_antiperonism.justification
            )
            an.left_right_score = analysis.peronism_antiperonism.score
            an.left_right_label = analysis.peronism_antiperonism.label or ""
            an.left_right_justification = analysis.peronism_antiperonism.justification
            an.emotional_load = analysis.emotional_load
            an.neutral_summary = analysis.neutral_summary
            an.overall_label = analysis.overall_label
            an.confidence = analysis.confidence
            an.framing_json = json.dumps(
                [f.model_dump() for f in analysis.framing], ensure_ascii=False
            )
            an.model_version_str = analysis.model_version
            an.is_mock = analysis.is_mock
            an.source_prior_used = analysis.source_prior_used
            session.commit()

    await asyncio.to_thread(_save)
    label = (analysis.overall_label or "")[:60]
    print(
        f"  id={aid} OK  per={analysis.peronism_antiperonism.score:+.1f}  "
        f"lib={analysis.statism_liberalism.score:+.1f}  "
        f"conf={analysis.confidence:.2f}  \"{label}\"",
        flush=True,
    )
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--ids", help="IDs separados por coma: 1,2,3")
    parser.add_argument("--portal", help="Slug del portal (ej: lanacion)")
    parser.add_argument("--before", help="Discovered_at < YYYY-MM-DD")
    parser.add_argument("--after", help="Discovered_at >= YYYY-MM-DD")
    parser.add_argument("--confidence-below", type=float, help="Confidence < X")
    parser.add_argument("--label-contains", help="overall_label contiene texto")
    parser.add_argument("--all-mock", action="store_true", help="Solo is_mock=True")
    parser.add_argument("--limit", type=int, help="Tope de artículos a procesar")
    parser.add_argument("--dry-run", action="store_true", help="Listar sin reanalizar")
    parser.add_argument("--yes", action="store_true", help="Saltar confirmación")
    args = parser.parse_args()

    has_filter = any(
        [
            args.ids,
            args.portal,
            args.before,
            args.after,
            args.confidence_below is not None,
            args.label_contains,
            args.all_mock,
        ]
    )
    if not has_filter:
        print("ABORTO: pasá al menos un filtro (--ids, --portal, --before, etc.).")
        print("Para reanalizar TODO usá reanalyze.py.")
        return 1

    safe_db = (
        settings.database_url.split("@")[-1]
        if "@" in settings.database_url
        else settings.database_url
    )
    print(f"DB target: {safe_db}")

    targets = build_targets(args)
    if not targets:
        print("Ningún artículo coincide con los filtros.")
        return 0

    print(f"Coincidencias: {len(targets)} artículos.")
    for aid, url in targets[:10]:
        print(f"  id={aid}  {url[:100]}")
    if len(targets) > 10:
        print(f"  ... y {len(targets) - 10} más.")

    if args.dry_run:
        print("\n--dry-run: salgo sin tocar nada.")
        return 0

    if not args.yes:
        print(f"\nReanalizar estos {len(targets)} artículos? ('si' para continuar):")
        if input("> ").strip().lower() != "si":
            print("Cancelado.")
            return 1

    ok = fail = 0
    t0 = time.time()
    for aid, url in targets:
        if await reanalyze_one(aid, url):
            ok += 1
        else:
            fail += 1
    elapsed = time.time() - t0
    print(f"\nOK={ok}  FAIL={fail}  tiempo={elapsed:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
