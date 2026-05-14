import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import SessionLocal, init_db
from app.refresh import backfill_embeddings_and_stories, refresh_all, seed_portals
from app.routes import articles, auth, images, me, portals, stories
from app.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s")
logger = logging.getLogger("sesgometro")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as session:
        seed_portals(session)
        backfilled = backfill_embeddings_and_stories(session)
    logger.info("BD inicializada y portales sembrados. Backfill: %d artículos", backfilled)

    if settings.enable_scheduler:
        start_scheduler()
        if settings.run_initial_refresh:
            asyncio.create_task(refresh_all())
            logger.info("Refresco inicial lanzado en background.")
    else:
        logger.info("Scheduler deshabilitado (ENABLE_SCHEDULER=false). Backend en modo solo-lectura.")

    try:
        yield
    finally:
        if settings.enable_scheduler:
            shutdown_scheduler()


app = FastAPI(
    title="Sesgómetro API",
    description="Analiza la orientación política de artículos de noticias.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portals.router)
app.include_router(articles.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(stories.router)
app.include_router(images.router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "mock_analyzer": settings.use_mock_analyzer}
