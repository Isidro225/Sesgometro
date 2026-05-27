"""Proxy + resize de imágenes de artículos.

Por qué proxy en vez de hotlink directo desde el medio:
- Servimos un thumb chico (webp, ancho fijo) → menos ancho de banda al medio.
- Robusto contra hotlink protection / Referer-blocking de algunos portales.
- Cache en disco: cada (url, width) se baja una sola vez.

Whitelist: solo se sirven URLs que nosotros mismos scrapeamos y guardamos como
`articles.image_url`. El frontend nunca pide otra cosa (ver `thumbUrl` en
api.ts). Validar contra la BD —en vez de contra el dominio de la homepage—
evita el open proxy y a la vez soporta los CDN de terceros: medios sobre Arc
Publishing (Infobae, La Nación, TN, Cronista) sirven imágenes desde dominios
ajenos (`*.cloudfront.net`, `arc-anglerfish-*.s3.amazonaws.com`, `arcdc.net`)
que una whitelist por homepage rechazaba con 403.
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
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import SessionLocal
from app.models import Article

logger = logging.getLogger("sesgometro.images")

router = APIRouter(prefix="/api/img", tags=["images"])

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "thumbs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_WIDTHS = {200, 400, 600, 900}
DEFAULT_WIDTH = 600
MAX_BYTES = 8 * 1024 * 1024
WEBP_QUALITY = 78
CACHE_HEADERS = {"Cache-Control": "public, max-age=604800, immutable"}


def _is_known_image(url: str) -> bool:
    """True si `url` figura como imagen de algún artículo en la BD.

    Es la whitelist real: solo servimos imágenes que nosotros scrapeamos, sin
    importar el CDN que las hostee. Query corto e indexado-suficiente; corre en
    threadpool porque la sesión es síncrona y esto se llama desde un endpoint
    async (y solo en cache miss)."""
    if urlparse(url).scheme not in ("http", "https"):
        return False
    with SessionLocal() as session:
        return session.scalar(
            select(Article.id).where(Article.image_url == url).limit(1)
        ) is not None


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
    if not await run_in_threadpool(_is_known_image, u):
        raise HTTPException(403, "URL no permitida (no es una imagen registrada).")

    cache_file = _cache_path(u, w)
    if cache_file.exists():
        return FileResponse(cache_file, media_type="image/webp", headers=CACHE_HEADERS)

    # impersonate="chrome" da fingerprint TLS de Chrome (necesario para CDNs
    # tras Cloudflare). Pero el Accept default de Chrome incluye image/avif,
    # y Arc Publishing (Infobae, La Nación, TN, Cronista) sirve AVIF cuando lo
    # ve — formato que Pillow no decodifica sin pillow-avif-plugin. Pisamos
    # Accept para que el CDN negocie a webp/jpeg/png.
    headers = {
        "Accept": "image/webp,image/jpeg,image/png,image/gif,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.5",
    }
    try:
        async with AsyncSession(impersonate="chrome") as client:
            response = await client.get(
                u,
                headers=headers,
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
