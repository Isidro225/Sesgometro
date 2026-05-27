import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import SessionLocal, init_db
from app.refresh import backfill_embeddings_and_stories, refresh_all, seed_portals
from app.routes import articles, auth, images, me, portals, stories, visits
from app.scheduler import shutdown_scheduler, start_scheduler
from app.visits import _client_ip, record_visit, should_log_request

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
app.include_router(visits.router)


@app.middleware("http")
async def log_visits(request: Request, call_next):
    """Registra cada request HTTP real en la tabla `visits` (kind='request').

    Corre después de resolver el response para poder guardar el status code. El
    registro va a una sesión de BD propia y está blindado contra errores, así que
    nunca afecta la respuesta al cliente.
    """
    response = await call_next(request)
    if should_log_request(request):
        record_visit(
            kind="request",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            referrer=request.headers.get("referer"),
        )
    return response


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "analyzer_provider": settings.analyzer_provider}
