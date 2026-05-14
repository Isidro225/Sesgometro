"""Descubre URLs de artículos a partir de la portada de un portal."""
from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin, urlparse

from selectolax.parser import HTMLParser

from app.portals import PortalSeed
from app.scraper import fetch_html

# Patrón genérico de fallback: URLs que parezcan artículo (segmentos con fecha o
# slug largo terminado en .html / .shtml o slug largo con guiones).
_GENERIC_ARTICLE_PATTERN = re.compile(
    r"/(?:\d{4}/\d{2}/\d{2}|\d{8})/[a-z0-9-_]+|/[a-z0-9-]{20,}\.s?html?$",
    re.IGNORECASE,
)

# URLs a excluir siempre (secciones, etiquetas, autores, multimedia, etc.).
_GLOBAL_EXCLUDE = re.compile(
    r"/(?:autor|autores|tag|tags|seccion|secciones|video|videos|fotos|directo|en-directo|"
    r"hemeroteca|servicios|suscri|suscripcion|newsletter|registro|login|tienda|"
    r"opinion/blogs|temas|firmas|programa|programas|tv|radio)/|"
    r"#|^javascript:|^mailto:",
    re.IGNORECASE,
)


def discover_article_urls(homepage_html: str, seed: PortalSeed, limit: int) -> list[str]:
    """Devuelve hasta `limit` URLs únicas de artículos candidatos."""
    tree = HTMLParser(homepage_html)
    pattern = re.compile(seed.link_pattern) if seed.link_pattern else _GENERIC_ARTICLE_PATTERN
    exclude = re.compile(seed.exclude_pattern) if seed.exclude_pattern else None
    home_host = urlparse(seed.effective_discovery_url).netloc

    seen: set[str] = set()
    found: list[str] = []

    for node in tree.css("a[href]"):
        href = node.attributes.get("href")
        if not href:
            continue
        absolute = urljoin(seed.effective_discovery_url, href)
        absolute, _ = urldefrag(absolute)
        if absolute in seen:
            continue

        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        # Mismo dominio (o subdominio del medio)
        if not (parsed.netloc == home_host or parsed.netloc.endswith("." + home_host)):
            continue
        if _GLOBAL_EXCLUDE.search(parsed.path):
            continue
        if exclude and exclude.search(absolute):
            continue
        if not pattern.search(absolute):
            continue

        seen.add(absolute)
        found.append(absolute)
        if len(found) >= limit:
            break

    return found


async def discover_for_portal(seed: PortalSeed, limit: int) -> list[str]:
    html = await fetch_html(seed.effective_discovery_url)
    return discover_article_urls(html, seed, limit)
