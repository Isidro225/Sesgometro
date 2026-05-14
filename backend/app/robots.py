"""Respeto a robots.txt para el scraper.

Cachea por host el resultado del parsing y consulta `can_fetch` antes de
cualquier descarga (homepage de discovery + URL de cada artículo).

Comportamiento:
- Si robots.txt no existe (404) o falla la descarga, asumimos allow-all
  (criterio estándar y conservador para crawlers respetuosos).
- Si el archivo prohíbe explícitamente la URL para nuestro UA, devolvemos
  `False` y el caller debe saltear la URL sin scraperarla.

Notas:
- Nos identificamos a robots.txt como `SesgometroBot`, aunque el fetch real
  use el fingerprint de Chrome de curl_cffi (necesario para pasar Cloudflare).
  robots.txt es una declaración de intención: cumplimos lo que el medio pida
  para nuestro bot — o, en su defecto, lo que pida para `*`.
- El cache vive en memoria por la duración del proceso. Como el backend se
  reinicia seguido, eso ya da una "ventana de refresco" implícita.
"""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError
from protego import Protego

logger = logging.getLogger("sesgometro.robots")

# Identificador público del bot. Si un medio quiere bloquearnos puntualmente,
# puede escribir `User-agent: Sesgometro` en su robots.txt y nos abstenemos.
#
# Importante: NO incluir "Bot" en el nombre. Protego (y otros parsers) hacen
# matching por substring, y robots.txt populares tienen entradas como `oBot`,
# `BLEXBot`, etc. que matchearían cualquier UA terminado en "Bot" — incluso
# uno legítimo como el nuestro.
ROBOTS_UA = "Sesgometro"

_cache: dict[str, Protego] = {}
_locks: dict[str, asyncio.Lock] = {}


async def _fetch_robots_text(host: str, scheme: str) -> str | None:
    """Descarga robots.txt. Devuelve el texto, `""` si no existe, o `None`
    si la descarga falló (errores transitorios → asumimos allow-all)."""
    url = f"{scheme}://{host}/robots.txt"
    try:
        async with AsyncSession(impersonate="chrome") as client:
            response = await client.get(url, timeout=10, allow_redirects=True)
    except RequestsError as exc:
        logger.warning("No se pudo descargar %s: %s — asumo allow-all", url, exc)
        return None

    if response.status_code == 404:
        return ""
    if response.status_code >= 400:
        logger.warning("%s respondió %d — asumo allow-all", url, response.status_code)
        return None
    return response.text


async def _get_parser(host: str, scheme: str) -> Protego:
    if host in _cache:
        return _cache[host]

    lock = _locks.setdefault(host, asyncio.Lock())
    async with lock:
        if host in _cache:
            return _cache[host]

        text = await _fetch_robots_text(host, scheme)
        # Protego con texto vacío = allow-all. Usamos esto cuando no pudimos
        # descargar el archivo o cuando devolvió 404.
        parser = Protego.parse(content=text or "")
        _cache[host] = parser
        return parser


async def is_allowed(url: str) -> bool:
    """Devuelve True si robots.txt permite scrapear `url` con nuestro UA."""
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return True  # URL rara; mejor dejar pasar y que falle el fetch real
    parser = await _get_parser(host, parsed.scheme or "https")
    return parser.can_fetch(url, ROBOTS_UA)
