"""Clustering de artículos en historias (stories).

Algoritmo simple (greedy):

1. Calcular el vector del artículo nuevo.
2. Buscar candidatos: historias con `last_seen_at >= now - time_window` y que
   tengan al menos un artículo de un portal distinto al actual (para favorecer
   clusters multi-fuente).
3. Para cada candidato calcular coseno(vec_nuevo, centroide_historia).
4. Si la mejor sim ≥ threshold → adjuntar el artículo a esa historia y
   recalcular centroide + counters. Si no → crear historia nueva.

Esto no es perfecto (es greedy, depende del orden), pero para volumen bajo
(decenas-cientos de artículos/día) sobra. Reagrupar lotes enteros se podría
hacer offline más adelante.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import embeddings
from app.config import settings
from app.embeddings import Vector
from app.models import Article, Story

logger = logging.getLogger("sesgometro.clustering")


def _article_vector(article: Article) -> Vector:
    return embeddings.loads(article.embedding_json)


def _recompute_centroid(session: Session, story: Story) -> None:
    articles = session.scalars(select(Article).where(Article.story_id == story.id)).all()
    vectors = [_article_vector(a) for a in articles if a.embedding_json]
    if not vectors:
        return
    story.centroid_json = embeddings.dumps(embeddings.mean_centroid(vectors))
    story.article_count = len(articles)
    pub_dates = [a.published_at for a in articles if a.published_at]
    if pub_dates:
        story.last_seen_at = max(pub_dates)


def assign_to_story(
    session: Session,
    article: Article,
    article_vec: Vector,
    reference_time: datetime | None = None,
) -> Story:
    """Asigna el artículo a una historia existente o crea una nueva.

    El artículo ya debe estar persistido (tiene id) y con embedding_json puesto.
    No hace commit — el caller decide cuándo.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    reference = reference_time or now
    cutoff = reference - timedelta(hours=settings.cluster_time_window_hours)

    candidates = session.scalars(
        select(Story).where(Story.last_seen_at >= cutoff).order_by(Story.last_seen_at.desc())
    ).all()

    best_story: Story | None = None
    best_sim = 0.0
    for story in candidates:
        centroid = embeddings.loads(story.centroid_json)
        sim = embeddings.cosine(article_vec, centroid)
        if sim > best_sim:
            best_sim = sim
            best_story = story

    if best_story is not None and best_sim >= settings.cluster_similarity_threshold:
        article.story_id = best_story.id
        session.flush()
        _recompute_centroid(session, best_story)
        logger.info(
            "Artículo %s adjuntado a story %s (sim=%.2f)",
            article.id,
            best_story.id,
            best_sim,
        )
        return best_story

    # Crear historia nueva
    title = (article.title or "Sin título")[:512]
    seen_at = article.published_at or now
    story = Story(
        canonical_title=title,
        centroid_json=embeddings.dumps(article_vec),
        article_count=1,
        first_seen_at=seen_at,
        last_seen_at=seen_at,
    )
    session.add(story)
    session.flush()
    article.story_id = story.id
    logger.info("Nueva story %s creada para artículo %s: %s", story.id, article.id, title[:60])
    return story
