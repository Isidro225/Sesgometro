from datetime import datetime
from urllib.parse import urlparse

import trafilatura
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError
from fastapi import HTTPException

from app import robots
from app.config import settings
from app.schemas import ScrapedArticle


class ScrapingError(HTTPException):
    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(status_code=status_code, detail=detail)


async def fetch_html(url: str) -> str:
    # Antes de tocar el sitio, chequeamos su robots.txt. Si nos prohíbe
    # esta URL, salteamos limpiamente (raise) — el caller ya tiene try/except.
    if not await robots.is_allowed(url):
        raise ScrapingError(
            "robots.txt del sitio prohíbe scrapear esta URL.",
            status_code=403,
        )
    # impersonate="chrome" replica el fingerprint TLS/HTTP de Chrome, necesario
    # para portales detrás de Cloudflare con "Just a moment" (ej. La Voz).
    # Por eso NO se setea User-Agent manualmente — lo maneja curl_cffi en
    # coherencia con el resto del fingerprint.
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en;q=0.5",
    }
    try:
        async with AsyncSession(impersonate="chrome") as client:
            response = await client.get(
                url,
                headers=headers,
                timeout=settings.scraper_timeout_seconds,
                allow_redirects=True,
            )
    except RequestsError as exc:
        raise ScrapingError(f"No se pudo descargar la URL: {exc}") from exc

    if response.status_code >= 400:
        raise ScrapingError(
            f"El servidor del medio respondió {response.status_code} al pedir la URL.",
            status_code=response.status_code if response.status_code < 500 else 502,
        )

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        raise ScrapingError(f"La URL no devuelve HTML (content-type: {content_type}).")

    return response.text


def extract_article(html: str, url: str) -> ScrapedArticle:
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
    )
    if not extracted:
        raise ScrapingError("No se pudo extraer texto del artículo.")

    import json

    data = json.loads(extracted)
    text = (data.get("text") or "").strip()
    if len(text) < 200:
        raise ScrapingError(
            "El texto extraído es muy corto (<200 caracteres). "
            "La URL puede ser una portada o requerir login."
        )

    published_raw = data.get("date")
    published_at: datetime | None = None
    if published_raw:
        try:
            published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except ValueError:
            published_at = None

    return ScrapedArticle(
        url=url,
        title=data.get("title"),
        author=data.get("author"),
        site_name=data.get("sitename") or urlparse(url).netloc,
        published_at=published_at,
        text=text,
        word_count=len(text.split()),
    )


async def scrape(url: str) -> ScrapedArticle:
    html = await fetch_html(url)
    return extract_article(html, url)
