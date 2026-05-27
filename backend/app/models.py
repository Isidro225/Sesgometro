from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Portal(Base):
    __tablename__ = "portals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    homepage_url: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    bias_bucket: Mapped[str] = mapped_column(String(16), default="centro")
    economic_bucket: Mapped[str] = mapped_column(String(16), default="centro")
    peronism_bucket: Mapped[str] = mapped_column(String(16), default="centro")
    # Derivado del promedio de scores culturales de los artículos del portal;
    # se recomputa después de cada refresh. No viene del seed.
    cultural_bucket: Mapped[str] = mapped_column(String(16), default="centro")
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    articles: Mapped[list[Article]] = relationship(
        back_populates="portal", cascade="all, delete-orphan", order_by="Article.discovered_at.desc()"
    )


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (UniqueConstraint("portal_id", "url", name="uq_article_portal_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id"), index=True)
    url: Mapped[str] = mapped_column(String(1024), index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # `author` puede ser una lista larga de co-autores (live blogs de La Nación
    # concatenan 10+ firmas). Tipo Text para no chocar contra varchar(256) en Postgres.
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cuerpo del artículo tal como vino del scraper. Lo persistimos para poder
    # re-analizar (cambiar de prompt o modelo) sin volver a scrapear, lo cual
    # es lento, frágil con Cloudflare, y puede devolver texto distinto si el
    # medio editó la nota. Truncamos al límite del analyzer (24k chars).
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"), nullable=True, index=True)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    portal: Mapped[Portal] = relationship(back_populates="articles")
    analysis: Mapped[Analysis | None] = relationship(
        back_populates="article", cascade="all, delete-orphan", uselist=False
    )
    story: Mapped[Story | None] = relationship(back_populates="articles")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), unique=True)
    left_right_score: Mapped[float] = mapped_column(Float)
    left_right_label: Mapped[str] = mapped_column(String(128))
    left_right_justification: Mapped[str] = mapped_column(Text)
    libauth_score: Mapped[float] = mapped_column(Float)
    libauth_label: Mapped[str] = mapped_column(String(128))
    libauth_justification: Mapped[str] = mapped_column(Text)
    statism_liberalism_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    statism_liberalism_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    statism_liberalism_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    peronism_antiperonism_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    peronism_antiperonism_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    peronism_antiperonism_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    progressivism_conservatism_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    progressivism_conservatism_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    progressivism_conservatism_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotional_load: Mapped[float] = mapped_column(Float)
    neutral_summary: Mapped[str] = mapped_column(Text)
    overall_label: Mapped[str] = mapped_column(String(256))
    confidence: Mapped[float] = mapped_column(Float)
    framing_json: Mapped[str] = mapped_column(Text)
    model_version_str: Mapped[str] = mapped_column(String(64))
    is_mock: Mapped[bool] = mapped_column(default=False)
    source_prior_used: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    article: Mapped[Article] = relationship(back_populates="analysis")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    favorites: Mapped[list[UserFavorite]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="UserFavorite.created_at.desc()"
    )


class UserFavorite(Base):
    """Favoritos: el usuario marca artículos descubiertos por los portales."""

    __tablename__ = "user_favorites"
    __table_args__ = (UniqueConstraint("user_id", "article_id", name="uq_favorite_user_article"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="favorites")
    article: Mapped[Article] = relationship()


class Story(Base):
    """Cluster: la misma noticia cubierta por varios portales."""

    __tablename__ = "stories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    canonical_title: Mapped[str] = mapped_column(String(512))
    centroid_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    articles: Mapped[list[Article]] = relationship(back_populates="story")


class Alert(Base):
    """Alerta global (todos los usuarios la ven). El estado leído/no-leído vive
    en `UserAlertRead`. Por ahora solo existe el kind='blindspot' pero el modelo
    está pensado para más tipos en el futuro.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    story_id: Mapped[int | None] = mapped_column(ForeignKey("stories.id"), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    story: Mapped[Story | None] = relationship()


class UserAlertRead(Base):
    __tablename__ = "user_alert_reads"
    __table_args__ = (UniqueConstraint("user_id", "alert_id", name="uq_user_alert_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"), index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Visit(Base):
    """Registro de visitas a la web.

    Lo alimenta el frontend reportando navegaciones de la SPA vía POST /api/track
    (kind="pageview"), que captura el path lógico de la página, no el del API.

    `ip` guarda la dirección cruda (dato personal: ver obligaciones de la Ley
    25.326 / GDPR) e `ip_hash` el hash salteado para contar únicos.
    """

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="pageview", index=True)
    path: Mapped[str] = mapped_column(String(1024), index=True)
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )
