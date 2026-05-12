"""Endpoints de artículos: detalle individual + feed de últimas noticias."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.categories import CATEGORY_SLUGS, classify as classify_category
from app.db import get_session
from app.models import Analysis, Article, User, UserFavorite
from app.routes.portals import (
    _peronism_antiperonism_axis,
    _statism_liberalism_axis,
    _to_analysis_schema,
)
from app.schemas import ArticleDetail, ArticleFeedItem, ArticlePortalRef, ScrapedArticle
from app.security import get_optional_user

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=list[ArticleFeedItem])
def list_recent_articles(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    categoria: Annotated[
        str | None,
        Query(description=f"Filtrar por categoría. Slugs: {', '.join(CATEGORY_SLUGS)}"),
    ] = None,
) -> list[ArticleFeedItem]:
    """Feed reciente de artículos analizados (ordenado por discovered_at desc).

    Sólo devuelve artículos con `analysis` cargado para que cada card del feed
    pueda renderizar las chips de eje. Para el home y vistas tipo portal de
    noticias.
    """
    if categoria is not None and categoria not in CATEGORY_SLUGS:
        raise HTTPException(400, f"Categoría inválida: {categoria!r}. Permitidas: {CATEGORY_SLUGS}")

    needs_wider_fetch = categoria is not None
    stmt = (
        select(Article)
        .join(Analysis, Analysis.article_id == Article.id)
        .options(selectinload(Article.portal), selectinload(Article.analysis))
        .order_by(desc(Article.discovered_at))
        .limit(300 if needs_wider_fetch else limit)
    )

    articles = session.scalars(stmt).all()
    feed: list[ArticleFeedItem] = []
    for art in articles:
        portal = art.portal
        analysis = art.analysis
        if portal is None or analysis is None:
            continue
        if categoria is not None and classify_category(art.title) != categoria:
            continue
        statism = _statism_liberalism_axis(analysis)
        peronism = _peronism_antiperonism_axis(analysis)
        feed.append(
            ArticleFeedItem(
                id=art.id,
                title=art.title,
                url=art.url,
                discovered_at=art.discovered_at,
                published_at=art.published_at,
                portal_slug=portal.slug,
                portal_name=portal.name,
                bias_bucket=portal.bias_bucket,
                economic_bucket=portal.economic_bucket,
                peronism_bucket=portal.peronism_bucket,
                overall_label=analysis.overall_label,
                statism_liberalism_score=statism.score,
                peronism_antiperonism_score=peronism.score,
                emotional_load=analysis.emotional_load,
                is_mock=analysis.is_mock,
                story_id=art.story_id,
            )
        )
        if len(feed) >= limit:
            break
    return feed


@router.get("/{article_id}", response_model=ArticleDetail)
def get_article(
    article_id: int,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User | None, Depends(get_optional_user)],
) -> ArticleDetail:
    article = session.scalar(
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.portal), selectinload(Article.analysis))
    )
    if article is None or article.portal is None:
        raise HTTPException(404, f"Artículo {article_id} no existe.")

    is_fav = False
    if current_user is not None:
        is_fav = (
            session.scalar(
                select(UserFavorite).where(
                    UserFavorite.user_id == current_user.id,
                    UserFavorite.article_id == article.id,
                )
            )
            is not None
        )

    scraped = ScrapedArticle(
        url=article.url,
        title=article.title,
        author=article.author,
        site_name=article.portal.name,
        published_at=article.published_at,
        text="",  # no exponemos el body por la nota legal de scraping
        word_count=article.word_count or 0,
    )

    return ArticleDetail(
        article=scraped,
        analysis=_to_analysis_schema(article),
        is_favorite=is_fav,
        portal=ArticlePortalRef(
            slug=article.portal.slug,
            name=article.portal.name,
            bias_bucket=article.portal.bias_bucket,
            economic_bucket=article.portal.economic_bucket,
            peronism_bucket=article.portal.peronism_bucket,
        ),
        story_id=article.story_id,
    )
