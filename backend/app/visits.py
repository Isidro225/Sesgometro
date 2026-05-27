"""Registro de visitas a la web.

Solo registramos pageviews reportados por la SPA vía POST /api/track. El
escritor nunca debe romper el request que lo originó: todo va envuelto en
try/except y usa su propia sesión de BD de corta vida.
"""
from __future__ import annotations

import hashlib
import logging

from fastapi import Request

from app.config import settings
from app.db import SessionLocal
from app.models import Visit

logger = logging.getLogger("sesgometro.visits")

# Marcadores de user-agent de bots/crawlers/monitores. Si alguno aparece (o no
# hay UA), no contamos la visita. Match por substring en minúsculas.
_BOT_UA_MARKERS = (
    "bot", "crawl", "spider", "slurp", "facebookexternalhit", "embedly",
    "pinterest", "redditbot", "applebot", "yandex", "baiduspider", "bingpreview",
    "semrush", "ahrefs", "mj12", "dotbot", "petalbot", "scrapy", "python-requests",
    "curl/", "wget", "go-http-client", "okhttp", "java/", "libwww", "httpclient",
    "headless", "lighthouse", "pingdom", "uptimerobot", "statuscake", "monitor",
)


def is_bot(user_agent: str | None) -> bool:
    """True si el UA parece un bot/crawler/monitor (o no hay UA: casi siempre
    un script o health-probe, no un navegador real)."""
    if not user_agent:
        return True
    ua = user_agent.lower()
    return any(marker in ua for marker in _BOT_UA_MARKERS)


def _client_ip(request: Request) -> str | None:
    """IP del cliente respetando el proxy de Railway (X-Forwarded-For)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # El primer valor es el cliente original; el resto son proxies.
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def hash_ip(ip: str | None) -> str | None:
    """Hash con salt del servidor: permite contar únicos sin guardar la IP."""
    if not ip:
        return None
    salted = f"{ip}:{settings.effective_jwt_secret}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()[:32]


def record_visit(
    *,
    kind: str,
    path: str,
    method: str | None = None,
    status_code: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
) -> None:
    """Inserta una fila en `visits`. Silencioso ante cualquier error."""
    try:
        with SessionLocal() as session:
            session.add(
                Visit(
                    kind=kind,
                    path=path[:1024],
                    method=method,
                    status_code=status_code,
                    ip=(ip or "")[:45] or None,
                    ip_hash=hash_ip(ip),
                    user_agent=(user_agent or "")[:512] or None,
                    referrer=(referrer or "")[:1024] or None,
                )
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001 — logging nunca debe tumbar el request
        logger.warning("No se pudo registrar la visita (%s): %s", path, exc)
