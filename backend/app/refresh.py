"""Lógica de refresco: descubrir + analizar artículos por portal y persistir."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from anyio import to_thread
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import alerts, analyzer, clustering, discovery, embeddings, politics_filter, scraper
from app.config import settings
from app.db import SessionLocal
from app.models import Analysis as AnalysisModel
from app.models import Alert, Article, Portal, Story, UserAlertRead, UserFavorite
from app.portals import PORTAL_SEEDS, PortalSeed
from app.schemas import Analysis as AnalysisSchema, ScrapedArticle

logger = logging.getLogger("sesgometro.refresh")

# Ollama corre local y procesa una request a la vez. Si lanzamos N análisis en
# paralelo, los últimos timeoutean haciendo cola. Este semáforo serializa las
# llamadas al analyzer a lo largo de todo el refresh (incluso entre portales).
_ANALYZER_SEMAPHORE = asyncio.Semaphore(1)


def seed_portals(session: Session) -> None:
    """Sincroniza los portales hardcodeados con la BD.

    Inserta los que falten, actualiza los existentes (por si cambia nombre o
    descripción) y borra los que ya no estén en `PORTAL_SEEDS` (con sus
    artículos y análisis en cascada).
    """
    seeds_by_slug = {s.slug: s for s in PORTAL_SEEDS}
    existing = {p.slug: p for p in session.scalars(select(Portal)).all()}

    # Borrar portales que ya no están en el catálogo
    for slug, portal in existing.items():
        if slug not in seeds_by_slug:
            logger.info("Borrando portal obsoleto: %s", slug)
            session.delete(portal)

    # Insertar o actualizar
    for seed in PORTAL_SEEDS:
        portal = existing.get(seed.slug)
        if portal is None:
            session.add(
                Portal(
                    slug=seed.slug,
                    name=seed.name,
                    homepage_url=seed.homepage_url,
                    description=seed.description,
                    bias_bucket=seed.bias_bucket,
                    economic_bucket=seed.economic_bucket,
                    peronism_bucket=seed.peronism_bucket,
                )
            )
        else:
            portal.name = seed.name
            portal.homepage_url = seed.homepage_url
            portal.description = seed.description
            portal.bias_bucket = seed.bias_bucket
            portal.economic_bucket = seed.economic_bucket
            portal.peronism_bucket = seed.peronism_bucket

    session.commit()


def _persist_article_and_analysis(
    session: Session,
    portal: Portal,
    article_url: str,
    analysis: AnalysisSchema,
    scraped_meta: dict,
    article_text: str,
) -> None:
    article = session.scalar(
        select(Article).where(Article.portal_id == portal.id, Article.url == article_url)
    )
    if article is None:
        article = Article(
            portal_id=portal.id,
            url=article_url,
            title=scraped_meta.get("title"),
            author=scraped_meta.get("author"),
            published_at=scraped_meta.get("published_at"),
            word_count=scraped_meta.get("word_count"),
        )
        session.add(article)
        session.flush()
    else:
        article.title = scraped_meta.get("title") or article.title
        article.author = scraped_meta.get("author") or article.author
        article.published_at = scraped_meta.get("published_at") or article.published_at
        article.word_count = scraped_meta.get("word_count") or article.word_count

    framing_payload = [f.model_dump() for f in analysis.framing]

    # `label` ahora viene None del analyzer (lo derivamos del score en el frontend).
    # Las columnas legacy libauth_label / left_right_label son NOT NULL, así que las
    # rellenamos con "" para no chocar contra el constraint de la BD.
    stat_label = analysis.statism_liberalism.label
    peron_label = analysis.peronism_antiperonism.label

    if article.analysis is None:
        session.add(
            AnalysisModel(
                article_id=article.id,
                left_right_score=analysis.peronism_antiperonism.score,
                left_right_label=peron_label or "",
                left_right_justification=analysis.peronism_antiperonism.justification,
                libauth_score=analysis.statism_liberalism.score,
                libauth_label=stat_label or "",
                libauth_justification=analysis.statism_liberalism.justification,
                statism_liberalism_score=analysis.statism_liberalism.score,
                statism_liberalism_label=stat_label,
                statism_liberalism_justification=analysis.statism_liberalism.justification,
                peronism_antiperonism_score=analysis.peronism_antiperonism.score,
                peronism_antiperonism_label=peron_label,
                peronism_antiperonism_justification=analysis.peronism_antiperonism.justification,
                emotional_load=analysis.emotional_load,
                neutral_summary=analysis.neutral_summary,
                overall_label=analysis.overall_label,
                confidence=analysis.confidence,
                framing_json=json.dumps(framing_payload, ensure_ascii=False),
                model_version_str=analysis.model_version,
                is_mock=analysis.is_mock,
            )
        )
    else:
        a = article.analysis
        a.left_right_score = analysis.peronism_antiperonism.score
        a.left_right_label = peron_label or ""
        a.left_right_justification = analysis.peronism_antiperonism.justification
        a.libauth_score = analysis.statism_liberalism.score
        a.libauth_label = stat_label or ""
        a.libauth_justification = analysis.statism_liberalism.justification
        a.statism_liberalism_score = analysis.statism_liberalism.score
        a.statism_liberalism_label = stat_label
        a.statism_liberalism_justification = analysis.statism_liberalism.justification
        a.peronism_antiperonism_score = analysis.peronism_antiperonism.score
        a.peronism_antiperonism_label = peron_label
        a.peronism_antiperonism_justification = analysis.peronism_antiperonism.justification
        a.emotional_load = analysis.emotional_load
        a.neutral_summary = analysis.neutral_summary
        a.overall_label = analysis.overall_label
        a.confidence = analysis.confidence
        a.framing_json = json.dumps(framing_payload, ensure_ascii=False)
        a.model_version_str = analysis.model_version
        a.is_mock = analysis.is_mock

    # Embedding + clustering en historias + posible alerta de blindspot.
    # Usamos el `neutral_summary` (no el body scrapeado) para que el embedding
    # se concentre en el evento puntual y no en el vocabulario político
    # genérico del cuerpo. Así dos notas del mismo día sobre temas distintos
    # no quedan juntas sólo porque comparten "gobierno", "comunicado", etc.
    summary_text = analysis.neutral_summary or article_text
    vec = embeddings.embed_text(article.title, summary_text)
    if vec:
        article.embedding_json = embeddings.dumps(vec)
        session.flush()
        story = clustering.assign_to_story(session, article, vec)
        alerts.maybe_alert_blindspot(session, story)


def _already_analyzed(portal_id: int, article_url: str) -> bool:
    """¿Tenemos ya un Article con análisis para esta (portal_id, url)?

    Sirve para no re-scrapear ni re-llamar a Claude por artículos que siguen
    en la portada entre refreshes. Solo se considera "ya hecho" si el Article
    existe Y tiene un Analysis asociado — si quedó a medias, lo reintentamos.
    """
    with SessionLocal() as session:
        article = session.scalar(
            select(Article).where(Article.portal_id == portal_id, Article.url == article_url)
        )
        return article is not None and article.analysis is not None


async def _process_article(seed: PortalSeed, portal_id: int, article_url: str) -> int:
    """Devuelve 1 si se hizo trabajo (scrape + analyze), 0 si se saltó."""
    if await to_thread.run_sync(_already_analyzed, portal_id, article_url):
        logger.debug("Skip ya analizado: %s", article_url)
        return 0

    try:
        article_data = await scraper.scrape(article_url)
        if not politics_filter.is_political_news(article_data.title, article_data.text, article_url):
            logger.info("Skip no político: %s", article_url)
            return 0
        async with _ANALYZER_SEMAPHORE:
            analysis = await to_thread.run_sync(analyzer.analyze, article_data)
    except Exception as exc:
        logger.warning("Falló análisis de %s: %s", article_url, exc)
        return 0

    def _save() -> None:
        with SessionLocal() as session:
            portal = session.get(Portal, portal_id)
            if portal is None:
                return
            _persist_article_and_analysis(
                session,
                portal,
                article_url,
                analysis,
                {
                    "title": article_data.title,
                    "author": article_data.author,
                    "published_at": article_data.published_at,
                    "word_count": article_data.word_count,
                },
                article_data.text,
            )
            session.commit()

    await to_thread.run_sync(_save)
    return 1


async def refresh_portal(seed: PortalSeed) -> int:
    """Descubre y analiza hasta N artículos del portal. Devuelve nº procesados."""
    try:
        urls = await discovery.discover_for_portal(seed, settings.articles_per_portal)
    except Exception as exc:
        logger.warning("Falló descubrimiento de %s: %s", seed.slug, exc)
        return 0

    if not urls:
        logger.info("%s: 0 URLs descubiertas", seed.slug)
        return 0

    def _get_portal_id() -> int | None:
        with SessionLocal() as session:
            p = session.scalar(select(Portal).where(Portal.slug == seed.slug))
            return p.id if p else None

    portal_id = await to_thread.run_sync(_get_portal_id)
    if portal_id is None:
        return 0

    results = await asyncio.gather(*(_process_article(seed, portal_id, u) for u in urls))
    new_count = sum(r if isinstance(r, int) else 0 for r in results)
    skipped = len(urls) - new_count

    def _stamp() -> None:
        with SessionLocal() as session:
            p = session.get(Portal, portal_id)
            if p:
                p.last_refreshed_at = datetime.utcnow()
                session.commit()

    await to_thread.run_sync(_stamp)
    logger.info("%s: %d nuevos, %d ya analizados", seed.slug, new_count, skipped)
    return new_count


def backfill_embeddings_and_stories(session: Session) -> int:
    """Para artículos antiguos (sin embedding/story), embebe usando título +
    resumen neutro almacenado en Analysis, y los asigna a historias.

    Devuelve la cantidad de artículos procesados.
    """
    pending = session.scalars(
        select(Article).where(Article.embedding_json.is_(None)).order_by(Article.discovered_at.asc())
    ).all()
    if not pending:
        return 0

    processed = 0
    touched_stories: set[int] = set()
    for article in pending:
        summary = article.analysis.neutral_summary if article.analysis else ""
        vec = embeddings.embed_text(article.title, summary)
        if not vec:
            continue
        article.embedding_json = embeddings.dumps(vec)
        session.flush()
        story = clustering.assign_to_story(session, article, vec)
        touched_stories.add(story.id)
        processed += 1

    # Después de adjuntar todo, recién ahora chequeamos blindspot por story.
    for story_id in touched_stories:
        story = session.get(Story, story_id)
        if story is not None:
            alerts.maybe_alert_blindspot(session, story)

    session.commit()
    logger.info("Backfill de embeddings/stories: %d artículos procesados", processed)
    return processed


def recluster_stories(session: Session) -> dict[str, int]:
    """Reconstruye stories/alertas desde cero, re-embebiendo todo.

    Útil cuando cambia el umbral o la lógica de clustering. Borra los clusters
    y alertas derivadas, preservando portales, artículos, análisis y favoritos.

    Re-calcula cada `embedding_json` desde `analysis.neutral_summary` antes de
    clusterizar, así todos los embeddings provienen de la misma fuente
    (event-specific, sin el ruido del body scrapeado completo). Los artículos
    sin análisis quedan sin embedding y sin cluster.
    """
    all_articles = session.scalars(select(Article)).all()

    session.execute(delete(UserAlertRead))
    session.execute(delete(Alert))
    for article in all_articles:
        article.story_id = None
    session.flush()
    session.execute(delete(Story))
    session.flush()

    re_embedded = 0
    for article in all_articles:
        analysis = article.analysis
        if analysis is None or not analysis.neutral_summary:
            article.embedding_json = None
            continue
        vec = embeddings.embed_text(article.title, analysis.neutral_summary)
        article.embedding_json = embeddings.dumps(vec) if vec else None
        if vec:
            re_embedded += 1
    session.flush()
    logger.info("Reclustering: %d artículos re-embebidos desde neutral_summary", re_embedded)

    articles = session.scalars(
        select(Article)
        .where(Article.embedding_json.is_not(None))
        .order_by(Article.published_at.asc(), Article.discovered_at.asc(), Article.id.asc())
    ).all()

    processed = 0
    touched_stories: set[int] = set()
    for article in articles:
        vec = embeddings.loads(article.embedding_json)
        if not vec:
            continue
        story = clustering.assign_to_story(
            session,
            article,
            vec,
            reference_time=article.published_at or article.discovered_at,
        )
        touched_stories.add(story.id)
        processed += 1

    alerts_created = 0
    for story_id in touched_stories:
        story = session.get(Story, story_id)
        if story is not None and alerts.maybe_alert_blindspot(session, story) is not None:
            alerts_created += 1

    session.commit()
    logger.info(
        "Reclustering completado: %d artículos, %d stories, %d alertas",
        processed,
        len(touched_stories),
        alerts_created,
    )
    return {
        "processed": processed,
        "stories": len(touched_stories),
        "alerts_created": alerts_created,
    }


def purge_non_political_articles(session: Session) -> dict[str, int | list[int]]:
    """Borra artículos existentes que no califican como políticos."""
    articles = session.scalars(select(Article).order_by(Article.id.asc())).all()
    to_delete: list[Article] = []

    for article in articles:
        analysis = article.analysis
        context_parts = [
            analysis.neutral_summary if analysis else "",
            analysis.overall_label if analysis else "",
            analysis.left_right_justification if analysis else "",
            analysis.libauth_justification if analysis else "",
        ]
        if not politics_filter.is_political_news(
            article.title,
            " ".join(part for part in context_parts if part),
            article.url,
        ):
            to_delete.append(article)

    deleted_ids = [article.id for article in to_delete]
    if not deleted_ids:
        return {
            "deleted": 0,
            "deleted_article_ids": [],
            "processed": 0,
            "stories": 0,
            "alerts_created": 0,
        }

    session.execute(delete(UserFavorite).where(UserFavorite.article_id.in_(deleted_ids)))
    for article in to_delete:
        session.delete(article)
    session.commit()

    recluster = recluster_stories(session)
    return {
        "deleted": len(deleted_ids),
        "deleted_article_ids": deleted_ids,
        **recluster,
    }


async def refresh_all() -> dict[str, int]:
    """Refresca los 10 portales en paralelo."""
    logger.info("Iniciando refresco completo (mock=%s)", settings.use_mock_analyzer)
    results = await asyncio.gather(
        *(refresh_portal(seed) for seed in PORTAL_SEEDS), return_exceptions=True
    )
    summary: dict[str, int] = {}
    for seed, res in zip(PORTAL_SEEDS, results):
        summary[seed.slug] = res if isinstance(res, int) else 0
    logger.info("Refresco completo: %s", summary)
    return summary
