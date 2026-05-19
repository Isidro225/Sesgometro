from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class ScrapedArticle(BaseModel):
    url: HttpUrl
    title: str | None
    author: str | None
    site_name: str | None
    published_at: datetime | None
    text: str
    word_count: int
    image_url: str | None = None


class AxisScore(BaseModel):
    score: float = Field(..., ge=-5, le=5)
    # `label` se deriva del score en el frontend; mantenemos el campo opcional para
    # compatibilidad con análisis viejos guardados en BD.
    label: str | None = None
    justification: str


class FramingFinding(BaseModel):
    kind: Literal["emphasis", "omission", "loaded_language", "source_selection"]
    description: str
    quote: str | None = None


class Analysis(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    statism_liberalism: AxisScore
    peronism_antiperonism: AxisScore
    # Opcional porque análisis viejos (anteriores a 2026-05-15) no lo traen.
    # Para análisis nuevos lo seteamos siempre.
    progressivism_conservatism: AxisScore | None = None
    emotional_load: float = Field(..., ge=0, le=1)
    framing: list[FramingFinding]
    neutral_summary: str
    overall_label: str
    confidence: float = Field(..., ge=0, le=1)
    model_version: str
    is_mock: bool
    # True si el analyzer recibió source_prior informativo (no centro/centro/centro)
    # como desempate de PASO 1. Default False para compat con análisis viejos.
    source_prior_used: bool = False


# ---------------------------------------------------------------------------
# Esquemas para listados de portales (Fase 2).
# ---------------------------------------------------------------------------


class PortalAggregate(BaseModel):
    """Resumen agregado de la orientación detectada para un portal."""

    avg_statism_liberalism: float | None
    avg_peronism_antiperonism: float | None
    avg_progressivism_conservatism: float | None = None
    avg_emotional_load: float | None
    article_count: int
    analyzed_count: int
    # Alias legacy para clientes viejos.
    avg_left_right: float | None = None
    avg_libauth: float | None = None


class PortalSummary(BaseModel):
    slug: str
    name: str
    homepage_url: str
    description: str | None
    bias_bucket: str
    economic_bucket: str
    peronism_bucket: str
    # Derivado de avg_progressivism_conservatism sobre los artículos del portal,
    # no hardcodeado en el seed. Se recalcula en cada refresh.
    cultural_bucket: str = "centro"
    last_refreshed_at: datetime | None
    aggregate: PortalAggregate


class ArticleSummary(BaseModel):
    id: int
    url: str
    title: str | None
    author: str | None
    published_at: datetime | None
    word_count: int | None
    discovered_at: datetime
    analysis: Analysis | None
    is_favorite: bool = False
    image_url: str | None = None


class PortalDetail(PortalSummary):
    articles: list[ArticleSummary]


class ArticleFeedItem(BaseModel):
    """Item compacto para el feed de últimas noticias del home."""

    id: int
    title: str | None
    url: str
    discovered_at: datetime
    published_at: datetime | None
    portal_slug: str
    portal_name: str
    bias_bucket: str
    economic_bucket: str
    peronism_bucket: str
    cultural_bucket: str = "centro"
    overall_label: str | None
    statism_liberalism_score: float | None
    peronism_antiperonism_score: float | None
    progressivism_conservatism_score: float | None = None
    emotional_load: float | None
    is_mock: bool
    story_id: int | None = None
    image_url: str | None = None


class ArticlePortalRef(BaseModel):
    slug: str
    name: str
    bias_bucket: str
    economic_bucket: str
    peronism_bucket: str
    cultural_bucket: str = "centro"


class ArticleDetail(BaseModel):
    """Detalle de un artículo persistido en la BD (descubierto vía scraping)
    junto con su análisis. No exponemos el body completo del artículo (solo
    metadata) por la nota legal de scraping; el `text` viene en blanco."""

    article: ScrapedArticle
    analysis: Analysis | None
    is_favorite: bool = False
    portal: ArticlePortalRef
    story_id: int | None = None


# ---------------------------------------------------------------------------
# Auth + historial + favoritos (Fase 3).
# ---------------------------------------------------------------------------


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    created_at: datetime


class AuthResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserPublic


class FavoriteRequest(BaseModel):
    article_id: int


# ---------------------------------------------------------------------------
# Stories + blindspot (Fase 4).
# ---------------------------------------------------------------------------


class BucketCoverage(BaseModel):
    bucket: str
    portal_count: int
    article_count: int
    sample_portals: list[str]


class AxisCoverage(BaseModel):
    axis: Literal[
        "statism_liberalism",
        "peronism_antiperonism",
        "progressivism_conservatism",
    ]
    coverage: list[BucketCoverage]
    blindspots: list[str]


class StoryArticle(BaseModel):
    article_id: int
    portal_slug: str
    portal_name: str
    bias_bucket: str
    economic_bucket: str
    peronism_bucket: str
    cultural_bucket: str = "centro"
    title: str | None
    url: str
    published_at: datetime | None
    overall_label: str | None
    statism_liberalism_score: float | None
    peronism_antiperonism_score: float | None
    progressivism_conservatism_score: float | None = None
    # Alias legacy para clientes viejos.
    left_right_score: float | None = None


class StorySummary(BaseModel):
    id: int
    canonical_title: str
    article_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    axis_coverage: list[AxisCoverage]
    coverage: list[BucketCoverage]
    blindspots: list[str]


class StoryDetail(StorySummary):
    articles: list[StoryArticle]


# ---------------------------------------------------------------------------
# Alertas (Fase 5)
# ---------------------------------------------------------------------------


class AlertItem(BaseModel):
    id: int
    kind: Literal["blindspot"]
    created_at: datetime
    read: bool
    story_id: int | None
    story_title: str | None
    blindspots: list[str]
    axis_blindspots: list[AxisCoverage]
    article_count: int


class AlertsResponse(BaseModel):
    unread_count: int
    items: list[AlertItem]
