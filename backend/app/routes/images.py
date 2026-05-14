"""Proxy + resize de imágenes de artículos.

Por qué proxy en vez de hotlink directo desde el medio:
- Servimos un thumb chico (webp, ancho fijo) → menos ancho de banda al medio.
- Robusto contra hotlink protection / Referer-blocking de algunos portales.
- Cache en disco: cada (url, width) se baja una sola vez.

Whitelist: solo se aceptan URLs cuyo host pertenezca al dominio registrable de
algún portal seed (incluye subdominios tipo CDN: `images.clarin.com`,
`media.lanacion.com.ar`). Sin esto sería un open proxy.
"""
from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.portals import PORTAL_SEEDS

logger = logging.getLogger("sesgometro.images")

router = APIRouter(prefix="/api/img", tags=["images"])

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "thumbs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_WIDTHS = {200, 400, 600, 900}
DEFAULT_WIDTH = 600
MAX_BYTES = 8 * 1024 * 1024
WEBP_QUALITY = 78
CACHE_HEADERS = {"Cache-Control": "public, max-age=604800, immutable"}


def _registrable_domain(host: str) -> str:
    """Aproximación: últimos 3 labels para SLDs tipo `.com.ar`, últimos 2 para `.com`."""
    parts = host.lower().split(".")
    if (
        len(parts) >= 3
        and parts[-2] in {"com", "co", "org", "gov", "net"}
        and len(parts[-1]) == 2
    ):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


_ALLOWED_DOMAINS: set[str] = {
    _registrable_domain(urlparse(seed.homepage_url).hostname or "")
    for seed in PORTAL_SEEDS
}


def _is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    return _registrable_domain(host) in _ALLOWED_DOMAINS


def _cache_path(url: str, width: int) -> Path:
    digest = hashlib.sha256(f"{url}|{width}".encode()).hexdigest()
    return CACHE_DIR / f"{digest}.webp"


@router.get("")
async def proxy_image(
    u: str = Query(..., description="URL de la imagen original (host whitelisted)."),
    w: int = Query(DEFAULT_WIDTH, description=f"Ancho objetivo. Permitidos: {sorted(ALLOWED_WIDTHS)}"),
):
    if w not in ALLOWED_WIDTHS:
        raise HTTPException(400, f"Ancho inválido. Permitidos: {sorted(ALLOWED_WIDTHS)}")
    if not _is_allowed(u):
        raise HTTPException(403, "URL no permitida (host fuera de la whitelist).")

    cache_file = _cache_path(u, w)
    if cache_file.exists():
        return FileResponse(cache_file, media_type="image/webp", headers=CACHE_HEADERS)

    try:
        async with AsyncSession(impersonate="chrome") as client:
            response = await client.get(
                u,
                timeout=settings.scraper_timeout_seconds,
                allow_redirects=True,
            )
    except RequestsError as exc:
        raise HTTPException(502, f"No se pudo descargar la imagen: {exc}") from exc

    if response.status_code >= 400:
        status = response.status_code if response.status_code < 500 else 502
        raise HTTPException(status, f"Origen respondió {response.status_code}.")

    content_type = response.headers.get("content-type", "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(415, f"La URL no es una imagen (content-type: {content_type}).")

    raw = response.content
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Imagen demasiado grande.")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(415, f"No se pudo decodificar la imagen: {exc}") from exc

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    elif img.mode == "RGBA":
        img = img.convert("RGB")

    if img.width > w:
        ratio = w / img.width
        img = img.resize((w, max(1, round(img.height * ratio))), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=WEBP_QUALITY, method=4)
    payload = buf.getvalue()
    cache_file.write_bytes(payload)

    return Response(content=payload, media_type="image/webp", headers=CACHE_HEADERS)
