from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.refresh import refresh_all

logger = logging.getLogger("sesgometro.scheduler")

_scheduler: AsyncIOScheduler | None = None


def _safe_refresh() -> None:
    try:
        asyncio.create_task(refresh_all())
    except Exception as exc:
        logger.error("Error agendando refresh_all: %s", exc)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        refresh_all,
        "interval",
        minutes=settings.refresh_interval_minutes,
        id="refresh_all_portals",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler arrancado (cada %d min)", settings.refresh_interval_minutes)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
