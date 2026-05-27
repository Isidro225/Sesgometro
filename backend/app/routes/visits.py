"""Endpoints de visitas: tracking de la SPA + lectura de estadísticas."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, Visit
from app.schemas import PathCount, TrackRequest, VisitStats
from app.security import get_current_user
from app.visits import _client_ip, is_bot, record_visit

router = APIRouter(prefix="/api", tags=["visits"])


@router.post("/track", status_code=status.HTTP_204_NO_CONTENT)
def track(payload: TrackRequest, request: Request) -> Response:
    """Registra una navegación de la SPA como pageview. Abierto (sin auth).

    Los bots no ejecutan JS y no llegan acá, pero igual filtramos por UA por las
    dudas, así un pageview siempre representa a un humano real."""
    user_agent = request.headers.get("user-agent")
    if not is_bot(user_agent):
        record_visit(
            kind="pageview",
            path=payload.path,
            ip=_client_ip(request),
            user_agent=user_agent,
            referrer=payload.referrer or request.headers.get("referer"),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/stats/visits", response_model=VisitStats)
def visit_stats(
    _current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    window_days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> VisitStats:
    """Resumen de visitas de los últimos `window_days` días. Requiere login."""
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    recent = Visit.created_at >= since

    total_requests = session.scalar(
        select(func.count()).select_from(Visit).where(recent, Visit.kind == "request")
    ) or 0
    total_pageviews = session.scalar(
        select(func.count()).select_from(Visit).where(recent, Visit.kind == "pageview")
    ) or 0
    # Visitantes únicos = humanos que vieron páginas (pageviews ya vienen sin
    # bots), contados por IP hasheada distinta.
    unique_visitors = session.scalar(
        select(func.count(func.distinct(Visit.ip_hash))).where(
            recent, Visit.kind == "pageview", Visit.ip_hash.is_not(None)
        )
    ) or 0

    top_rows = session.execute(
        select(Visit.path, func.count().label("n"))
        .where(recent, Visit.kind == "pageview")
        .group_by(Visit.path)
        .order_by(func.count().desc())
        .limit(10)
    ).all()

    return VisitStats(
        window_days=window_days,
        total_requests=total_requests,
        total_pageviews=total_pageviews,
        unique_visitors=unique_visitors,
        top_paths=[PathCount(path=p, count=n) for p, n in top_rows],
    )
