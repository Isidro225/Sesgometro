"""Registro de visitas a la web.

Lógica compartida entre el middleware HTTP (que loguea cada request) y el
endpoint POST /api/track (que loguea pageviews reportados por la SPA).

El escritor nunca debe romper el request que lo originó: todo va envuelto en
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

# Paths que no cuentan como visita real: health-check, preflight CORS, el propio
# endpoint de tracking (lo registra el handler como pageview, no como request) y
# la lectura de estadísticas.
_SKIP_PREFIXES = ("/health", "/api/track", "/api/stats/visits")


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


def should_log_request(request: Request) -> bool:
    if request.method in ("OPTIONS", "HEAD"):
        return False
    return not any(request.url.path.startswith(p) for p in _SKIP_PREFIXES)


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
                    ip_hash=hash_ip(ip),
                    user_agent=(user_agent or "")[:512] or None,
                    referrer=(referrer or "")[:1024] or None,
                )
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001 — logging nunca debe tumbar el request
        logger.warning("No se pudo registrar la visita (%s): %s", path, exc)
