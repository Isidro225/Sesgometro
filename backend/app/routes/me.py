from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import Alert, Article, User, UserAlertRead, UserFavorite
from app.routes.portals import _to_analysis_schema
from app.schemas import AlertItem, AlertsResponse, ArticleSummary
from app.security import get_current_user

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("/favorites", response_model=list[ArticleSummary])
def list_favorites(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ArticleSummary]:
    rows = session.scalars(
        select(UserFavorite)
        .where(UserFavorite.user_id == current_user.id)
        .options(selectinload(UserFavorite.article).selectinload(Article.analysis))
        .order_by(UserFavorite.created_at.desc())
    ).all()

    out: list[ArticleSummary] = []
    for fav in rows:
        a = fav.article
        if a is None:
            continue
        out.append(
            ArticleSummary(
                id=a.id,
                url=a.url,
                title=a.title,
                author=a.author,
                published_at=a.published_at,
                word_count=a.word_count,
                discovered_at=a.discovered_at,
                analysis=_to_analysis_schema(a),
                is_favorite=True,
            )
        )
    return out


@router.post("/favorites/{article_id}", status_code=status.HTTP_201_CREATED)
def add_favorite(
    article_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, bool]:
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artículo no existe.")
    existing = session.scalar(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id, UserFavorite.article_id == article_id
        )
    )
    if existing is not None:
        return {"added": False}
    session.add(UserFavorite(user_id=current_user.id, article_id=article_id))
    session.commit()
    return {"added": True}


@router.delete("/favorites/{article_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_favorite(
    article_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    fav = session.scalar(
        select(UserFavorite).where(
            UserFavorite.user_id == current_user.id, UserFavorite.article_id == article_id
        )
    )
    if fav is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Favorito no encontrado.")
    session.delete(fav)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Alertas (Fase 5)
# ---------------------------------------------------------------------------


def _alert_to_item(alert: Alert, read_ids: set[int]) -> AlertItem:
    try:
        payload = json.loads(alert.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    axis_blindspots = payload.get("axis_blindspots")
    if not axis_blindspots:
        legacy = payload.get("blindspots", [])
        axis_blindspots = (
            [{"axis": "peronism_antiperonism", "coverage": [], "blindspots": legacy}]
            if legacy
            else []
        )
    return AlertItem(
        id=alert.id,
        kind=alert.kind,
        created_at=alert.created_at,
        read=alert.id in read_ids,
        story_id=alert.story_id,
        story_title=payload.get("title") or (alert.story.canonical_title if alert.story else None),
        blindspots=payload.get("blindspots", []),
        axis_blindspots=axis_blindspots,
        article_count=int(payload.get("article_count", 0)),
    )


@router.get("/alerts", response_model=AlertsResponse)
def list_alerts(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> AlertsResponse:
    alerts = session.scalars(
        select(Alert).options(selectinload(Alert.story)).order_by(Alert.created_at.desc()).limit(100)
    ).all()
    read_ids = set(
        session.scalars(
            select(UserAlertRead.alert_id).where(UserAlertRead.user_id == current_user.id)
        ).all()
    )
    items = [_alert_to_item(a, read_ids) for a in alerts]
    unread = sum(1 for i in items if not i.read)
    return AlertsResponse(unread_count=unread, items=items)


@router.post("/alerts/{alert_id}/read", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def mark_alert_read(
    alert_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alerta no existe.")
    existing = session.scalar(
        select(UserAlertRead).where(
            UserAlertRead.user_id == current_user.id, UserAlertRead.alert_id == alert_id
        )
    )
    if existing is None:
        session.add(UserAlertRead(user_id=current_user.id, alert_id=alert_id))
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/alerts/read-all", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def mark_all_alerts_read(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
):
    all_alert_ids = set(session.scalars(select(Alert.id)).all())
    read_ids = set(
        session.scalars(
            select(UserAlertRead.alert_id).where(UserAlertRead.user_id == current_user.id)
        ).all()
    )
    for alert_id in all_alert_ids - read_ids:
        session.add(UserAlertRead(user_id=current_user.id, alert_id=alert_id))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
