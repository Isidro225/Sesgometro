"""Endpoints de historias (clusters multi-portal) + blindspot."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.categories import CATEGORY_SLUGS, classify as classify_category
from app.db import get_session
from app.models import Article, Portal, Story
from app.refresh import purge_non_political_articles, recluster_stories as run_recluster_stories
from app.routes.portals import (
    _peronism_antiperonism_axis,
    _progressivism_conservatism_axis,
    _statism_liberalism_axis,
)
from app.schemas import AxisCoverage, BucketCoverage, StoryArticle, StoryDetail, StorySummary

router = APIRouter(prefix="/api/stories", tags=["stories"])

ALL_BUCKETS = ("izq", "centro", "der")
AXIS_BUCKETS = {
    "statism_liberalism": ("estatista", "centro", "liberal"),
    "peronism_antiperonism": ("peronista", "centro", "antiperonista"),
    "progressivism_conservatism": ("progresista", "centro", "conservador"),
}
AXIS_PORTAL_ATTR = {
    "statism_liberalism": "economic_bucket",
    "peronism_antiperonism": "peronism_bucket",
    "progressivism_conservatism": "cultural_bucket",
}
MIN_ARTICLES_FOR_BLINDSPOT = 3


def _coverage_for_attr(
    story: Story, buckets: tuple[str, ...], portal_attr: str
) -> tuple[list[BucketCoverage], list[str]]:
    per_bucket: dict[str, dict] = {b: {"portals": set(), "articles": 0} for b in buckets}

    for art in story.articles:
        portal = art.portal
        if portal is None:
            continue
        bucket = getattr(portal, portal_attr, None) or "centro"
        if bucket not in per_bucket:
            per_bucket[bucket] = {"portals": set(), "articles": 0}
        per_bucket[bucket]["portals"].add(portal.slug)
        per_bucket[bucket]["articles"] += 1

    coverage = [
        BucketCoverage(
            bucket=b,
            portal_count=len(per_bucket[b]["portals"]),
            article_count=per_bucket[b]["articles"],
            sample_portals=sorted(per_bucket[b]["portals"])[:5],
        )
        for b in buckets
    ]

    total = sum(c.article_count for c in coverage)
    if total < MIN_ARTICLES_FOR_BLINDSPOT:
        return coverage, []
    blindspots = [c.bucket for c in coverage if c.portal_count == 0]
    return coverage, blindspots


def _coverage_for(story: Story) -> tuple[list[BucketCoverage], list[str]]:
    """Devuelve cobertura legacy por izquierda/centro/derecha."""
    return _coverage_for_attr(story, ALL_BUCKETS, "bias_bucket")


def _axis_coverage_for(story: Story) -> list[AxisCoverage]:
    out: list[AxisCoverage] = []
    for axis, buckets in AXIS_BUCKETS.items():
        coverage, blindspots = _coverage_for_attr(story, buckets, AXIS_PORTAL_ATTR[axis])
        out.append(AxisCoverage(axis=axis, coverage=coverage, blindspots=blindspots))
    return out


def _story_articles(story: Story) -> list[StoryArticle]:
    out: list[StoryArticle] = []
    for a in story.articles:
        portal = a.portal
        analysis = a.analysis
        statism = _statism_liberalism_axis(analysis) if analysis else None
        peronism = _peronism_antiperonism_axis(analysis) if analysis else None
        cultural = _progressivism_conservatism_axis(analysis) if analysis else None
        out.append(
            StoryArticle(
                article_id=a.id,
                portal_slug=portal.slug if portal else "",
                portal_name=portal.name if portal else "",
                bias_bucket=portal.bias_bucket if portal else "centro",
                economic_bucket=portal.economic_bucket if portal else "centro",
                peronism_bucket=portal.peronism_bucket if portal else "centro",
                cultural_bucket=portal.cultural_bucket if portal else "centro",
                title=a.title,
                url=a.url,
                published_at=a.published_at,
                overall_label=analysis.overall_label if analysis else None,
                statism_liberalism_score=statism.score if statism else None,
                peronism_antiperonism_score=peronism.score if peronism else None,
                progressivism_conservatism_score=cultural.score if cultural else None,
                left_right_score=peronism.score if peronism else None,
            )
        )
    out.sort(key=lambda x: (x.published_at is None, x.published_at), reverse=False)
    return out


def _to_summary(story: Story) -> StorySummary:
    coverage, blindspots = _coverage_for(story)
    axis_coverage = _axis_coverage_for(story)
    return StorySummary(
        id=story.id,
        canonical_title=story.canonical_title,
        article_count=story.article_count,
        first_seen_at=story.first_seen_at,
        last_seen_at=story.last_seen_at,
        axis_coverage=axis_coverage,
        coverage=coverage,
        blindspots=blindspots,
    )


@router.get("", response_model=list[StorySummary])
def list_stories(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    only_multi: Annotated[bool, Query(description="Solo historias con >=2 artículos")] = True,
    with_blindspot: Annotated[bool, Query(description="Solo historias con al menos un blindspot")] = False,
    categoria: Annotated[
        str | None,
        Query(description=f"Filtrar por categoría temática. Slugs: {', '.join(CATEGORY_SLUGS)}"),
    ] = None,
) -> list[StorySummary]:
    if categoria is not None and categoria not in CATEGORY_SLUGS:
        raise HTTPException(400, f"Categoría inválida: {categoria!r}. Permitidas: {CATEGORY_SLUGS}")

    needs_wider_fetch = with_blindspot or categoria is not None
    stmt = (
        select(Story)
        .options(
            selectinload(Story.articles).selectinload(Article.portal),
            selectinload(Story.articles).selectinload(Article.analysis),
        )
        .order_by(desc(Story.last_seen_at))
        .limit(500 if needs_wider_fetch else limit)
    )
    if only_multi:
        stmt = stmt.where(Story.article_count >= 2)

    stories = session.scalars(stmt).all()
    summaries = [_to_summary(s) for s in stories]
    if with_blindspot:
        summaries = [s for s in summaries if any(axis.blindspots for axis in s.axis_coverage)]
    if categoria is not None:
        summaries = [s for s in summaries if classify_category(s.canonical_title) == categoria]
    return summaries[:limit]


@router.post("/recluster")
def recluster_stories_endpoint(
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    return run_recluster_stories(session)


@router.post("/purge-non-political")
def purge_non_political_endpoint(
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int | list[int]]:
    return purge_non_political_articles(session)


@router.get("/{story_id}", response_model=StoryDetail)
def get_story(
    story_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> StoryDetail:
    story = session.scalar(
        select(Story)
        .where(Story.id == story_id)
        .options(
            selectinload(Story.articles).selectinload(Article.portal),
            selectinload(Story.articles).selectinload(Article.analysis),
        )
    )
    if story is None:
        raise HTTPException(404, f"Story {story_id} no existe.")

    summary = _to_summary(story)
    return StoryDetail(**summary.model_dump(), articles=_story_articles(story))


# Para que las rutas referencian Portal sin "unused import" del linter.
_ = Portal
