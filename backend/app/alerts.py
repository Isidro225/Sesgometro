"""Detector de blindspot → genera un Alert global cuando una historia cruza
el umbral por primera vez.

Reglas (mismas que las del endpoint /api/stories):
- La historia tiene al menos `MIN_ARTICLES_FOR_BLINDSPOT` artículos analizados.
- Hay al menos un bucket (`izq`/`centro`/`der`) sin cobertura.
- Solo se dispara una vez por historia (chequea `story.alerted_at`).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Alert, Article, Story

logger = logging.getLogger("sesgometro.alerts")

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


def maybe_alert_blindspot(session: Session, story: Story) -> Alert | None:
    """Si la historia tiene blindspot y todavía no se alertó, crea un Alert.

    No hace commit — el caller decide. El centroide/article_count del story
    ya deben estar actualizados (lo hace `clustering.assign_to_story`).
    """
    if story.alerted_at is not None:
        return None
    if story.article_count < MIN_ARTICLES_FOR_BLINDSPOT:
        return None

    articles = session.scalars(
        select(Article)
        .where(Article.story_id == story.id)
        .options(selectinload(Article.portal))
    ).all()

    legacy_covered = {a.portal.bias_bucket for a in articles if a.portal is not None}
    legacy_blindspots = [b for b in ALL_BUCKETS if b not in legacy_covered]

    axis_blindspots = []
    for axis, buckets in AXIS_BUCKETS.items():
        attr = AXIS_PORTAL_ATTR[axis]
        covered = {getattr(a.portal, attr, "centro") for a in articles if a.portal is not None}
        missing = [b for b in buckets if b not in covered]
        if missing:
            axis_blindspots.append({"axis": axis, "coverage": [], "blindspots": missing})

    if not axis_blindspots:
        return None

    story.alerted_at = datetime.utcnow()
    alert = Alert(
        kind="blindspot",
        story_id=story.id,
        payload_json=json.dumps(
            {
                "blindspots": legacy_blindspots,
                "axis_blindspots": axis_blindspots,
                "article_count": story.article_count,
                "title": story.canonical_title,
            },
            ensure_ascii=False,
        ),
    )
    session.add(alert)
    logger.info(
        "Alert blindspot creada para story %s (%s · falta: %s)",
        story.id,
        story.canonical_title[:60],
        ",".join(f"{x['axis']}:{','.join(x['blindspots'])}" for x in axis_blindspots),
    )
    return alert
