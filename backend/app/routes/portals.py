from __future__ import annotations

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import Article, Portal, User, UserFavorite
from app.portals import get_seed
from app.refresh import refresh_portal
from app.schemas import (
    Analysis,
    ArticleSummary,
    AxisScore,
    FramingFinding,
    PortalAggregate,
    PortalDetail,
    PortalSummary,
)
from app.security import get_optional_user

router = APIRouter(prefix="/api", tags=["portals"])


def _aggregate(articles: list[Article]) -> PortalAggregate:
    analyzed = [a for a in articles if a.analysis is not None]
    if not analyzed:
        return PortalAggregate(
            avg_statism_liberalism=None,
            avg_peronism_antiperonism=None,
            avg_emotional_load=None,
            article_count=len(articles),
            analyzed_count=0,
        )
    n = len(analyzed)
    avg_statism = sum(_statism_liberalism_axis(a.analysis).score for a in analyzed) / n
    avg_peronism = sum(_peronism_antiperonism_axis(a.analysis).score for a in analyzed) / n
    return PortalAggregate(
        avg_statism_liberalism=avg_statism,
        avg_peronism_antiperonism=avg_peronism,
        avg_emotional_load=sum(a.analysis.emotional_load for a in analyzed) / n,
        article_count=len(articles),
        analyzed_count=n,
        avg_left_right=avg_peronism,
        avg_libauth=avg_statism,
    )


def _statism_label(score: float) -> str:
    if score <= -3:
        return "Estatismo marcado"
    if score <= -1:
        return "Más Estado"
    if score < 1:
        return "Centro / neutro"
    if score < 3:
        return "Liberalismo moderado"
    return "Liberalismo marcado"


def _peronism_label(score: float) -> str:
    if score <= -3:
        return "Peronismo marcado"
    if score <= -1:
        return "Afinidad peronista"
    if score < 1:
        return "Centro / no alineado"
    if score < 3:
        return "Antiperonismo moderado"
    return "Antiperonismo marcado"


def _statism_liberalism_axis(a) -> AxisScore:
    score = a.statism_liberalism_score if a.statism_liberalism_score is not None else a.libauth_score
    return AxisScore(
        score=score,
        label=a.statism_liberalism_label or _statism_label(score),
        justification=a.statism_liberalism_justification or a.libauth_justification,
    )


def _peronism_antiperonism_axis(a) -> AxisScore:
    score = (
        a.peronism_antiperonism_score
        if a.peronism_antiperonism_score is not None
        else a.left_right_score
    )
    return AxisScore(
        score=score,
        label=a.peronism_antiperonism_label or _peronism_label(score),
        justification=a.peronism_antiperonism_justification or a.left_right_justification,
    )


def _to_analysis_schema(article: Article) -> Analysis | None:
    a = article.analysis
    if a is None:
        return None
    try:
        framing = [FramingFinding(**f) for f in json.loads(a.framing_json or "[]")]
    except json.JSONDecodeError:
        framing = []
    return Analysis(
        statism_liberalism=_statism_liberalism_axis(a),
        peronism_antiperonism=_peronism_antiperonism_axis(a),
        emotional_load=a.emotional_load,
        framing=framing,
        neutral_summary=a.neutral_summary,
        overall_label=a.overall_label,
        confidence=a.confidence,
        model_version=a.model_version_str,
        is_mock=a.is_mock,
    )


def _favorites_for(user: User | None, session: Session) -> set[int]:
    if user is None:
        return set()
    rows = session.scalars(
        select(UserFavorite.article_id).where(UserFavorite.user_id == user.id)
    ).all()
    return set(rows)


@router.get("/portals", response_model=list[PortalSummary])
def list_portals(session: Annotated[Session, Depends(get_session)]) -> list[PortalSummary]:
    portals = (
        session.scalars(
            select(Portal).options(selectinload(Portal.articles).selectinload(Article.analysis))
        )
        .unique()
        .all()
    )
    return [
        PortalSummary(
            slug=p.slug,
            name=p.name,
            homepage_url=p.homepage_url,
            description=p.description,
            bias_bucket=p.bias_bucket,
            economic_bucket=p.economic_bucket,
            peronism_bucket=p.peronism_bucket,
            last_refreshed_at=p.last_refreshed_at,
            aggregate=_aggregate(list(p.articles)),
        )
        for p in portals
    ]


@router.get("/portals/{slug}", response_model=PortalDetail)
def get_portal(
    slug: str,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
) -> PortalDetail:
    portal = session.scalar(
        select(Portal)
        .where(Portal.slug == slug)
        .options(selectinload(Portal.articles).selectinload(Article.analysis))
    )
    if portal is None:
        raise HTTPException(status_code=404, detail=f"Portal '{slug}' no existe.")

    favorites = _favorites_for(current_user, session)
    articles = list(portal.articles)
    article_summaries = [
        ArticleSummary(
            id=a.id,
            url=a.url,
            title=a.title,
            author=a.author,
            published_at=a.published_at,
            word_count=a.word_count,
            discovered_at=a.discovered_at,
            analysis=_to_analysis_schema(a),
            is_favorite=a.id in favorites,
        )
        for a in articles
    ]

    return PortalDetail(
        slug=portal.slug,
        name=portal.name,
        homepage_url=portal.homepage_url,
        description=portal.description,
        bias_bucket=portal.bias_bucket,
        economic_bucket=portal.economic_bucket,
        peronism_bucket=portal.peronism_bucket,
        last_refreshed_at=portal.last_refreshed_at,
        aggregate=_aggregate(articles),
        articles=article_summaries,
    )


@router.post("/portals/{slug}/refresh", status_code=202)
async def refresh_single_portal(slug: str) -> dict[str, str | int]:
    seed = get_seed(slug)
    if seed is None:
        raise HTTPException(status_code=404, detail=f"Portal '{slug}' no existe.")
    count = await refresh_portal(seed)
    return {"slug": slug, "processed": count}


@router.post("/portals/refresh-all", status_code=202)
async def refresh_all_portals_endpoint() -> dict[str, str]:
    from app.refresh import refresh_all

    asyncio.create_task(refresh_all())
    return {"status": "refresh lanzado en background"}
