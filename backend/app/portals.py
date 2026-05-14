"""Catálogo de portales seed (medios argentinos).

Cada portal puede declarar:
- `homepage_url`: URL pública del portal (mostrada al usuario, link "Visitar sitio").
- `discovery_url`: opcional. URL que se rasca para descubrir artículos. Si no se
   declara, se usa `homepage_url`. Útil cuando la portada del medio no lista
   notas (ej: La Izquierda Diario tiene un feed dedicado en /Últimas-noticias).
- `link_pattern`: regex que la URL del enlace debe cumplir para considerarse artículo.
- `exclude_pattern`: regex de URLs a excluir (secciones, autor, tags, etc.).
- `bias_bucket`: bucket coarse de orientación política (`izq` | `centro` | `der`).
   Es un rating editorial estable a nivel medio, separado del análisis por
   artículo. Sirve para calcular el blindspot estilo Ground News (qué bucket
   no cubre una historia).
- `economic_bucket`: posición editorial coarse en estatismo/centro/liberalismo.
- `peronism_bucket`: posición editorial coarse en peronismo/centro/antiperonismo.

Si no se declaran patrones, se usa una heurística genérica.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BiasBucket = Literal["izq", "centro", "der"]
EconomicBucket = Literal["estatista", "centro", "liberal"]
PeronismBucket = Literal["peronista", "centro", "antiperonista"]


@dataclass(frozen=True)
class PortalSeed:
    slug: str
    name: str
    homepage_url: str
    description: str
    bias_bucket: BiasBucket = "centro"
    economic_bucket: EconomicBucket = "centro"
    peronism_bucket: PeronismBucket = "centro"
    link_pattern: str | None = None
    exclude_pattern: str | None = None
    discovery_url: str | None = None

    @property
    def effective_discovery_url(self) -> str:
        return self.discovery_url or self.homepage_url


PORTAL_SEEDS: list[PortalSeed] = [
    PortalSeed(
        slug="clarin",
        name="Clarín",
        homepage_url="https://www.clarin.com/",
        description="Diario generalista del Grupo Clarín. Línea editorial centro-derecha.",
        bias_bucket="der",
        economic_bucket="liberal",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://www\.clarin\.com/[a-z0-9-/]+/[a-z0-9-]+_0_[A-Za-z0-9]+\.html$",
    ),
    PortalSeed(
        slug="la-nacion",
        name="La Nación",
        homepage_url="https://www.lanacion.com.ar/",
        description="Diario generalista tradicional. Línea editorial liberal-conservadora.",
        bias_bucket="der",
        economic_bucket="liberal",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://www\.lanacion\.com\.ar/[a-z0-9-/]+/[a-z0-9-]+-nid\d{8}/?$",
    ),
    PortalSeed(
        slug="infobae",
        name="Infobae",
        homepage_url="https://www.infobae.com/",
        description="Diario digital líder. Línea editorial centro-derecha.",
        bias_bucket="der",
        economic_bucket="liberal",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://www\.infobae\.com/[a-z0-9-/]+/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/?$",
    ),
    PortalSeed(
        slug="pagina12",
        name="Página/12",
        homepage_url="https://www.pagina12.com.ar/",
        description="Diario progresista. Línea editorial kirchnerista / izquierda peronista.",
        bias_bucket="izq",
        economic_bucket="estatista",
        peronism_bucket="peronista",
        link_pattern=r"^https?://www\.pagina12\.com\.ar/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/?$",
    ),
    PortalSeed(
        slug="tn",
        name="TN",
        homepage_url="https://tn.com.ar/",
        description="Portal de noticias del Grupo Clarín. Línea editorial centro-derecha.",
        bias_bucket="der",
        economic_bucket="liberal",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://tn\.com\.ar/[a-z0-9-/]+/\d{4}/\d{2}/\d{2}/[a-z0-9-]+/?$",
    ),
    PortalSeed(
        slug="perfil",
        name="Perfil",
        homepage_url="https://www.perfil.com/",
        description="Diario generalista. Línea editorial centro-derecha.",
        bias_bucket="centro",
        economic_bucket="centro",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://www\.perfil\.com/noticias/[a-z-]+/[a-z0-9-]+\.phtml$",
    ),
    PortalSeed(
        slug="ambito",
        name="Ámbito",
        homepage_url="https://www.ambito.com/",
        description="Diario económico-financiero. Línea editorial centro / centro-derecha.",
        bias_bucket="der",
        economic_bucket="liberal",
        peronism_bucket="centro",
        link_pattern=r"^https?://www\.ambito\.com/[a-z0-9-/]+/[a-z0-9-]+-n\d{6,}$",
    ),
    PortalSeed(
        slug="cronista",
        name="El Cronista",
        homepage_url="https://www.cronista.com/",
        description="Diario económico. Línea editorial liberal centro-derecha.",
        bias_bucket="der",
        economic_bucket="liberal",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://www\.cronista\.com/[a-z0-9-/]+/[a-z0-9-]{30,}/?$",
    ),
    PortalSeed(
        slug="tiempo-argentino",
        name="Tiempo Argentino",
        homepage_url="https://www.tiempoar.com.ar/",
        description="Diario cooperativo. Línea editorial peronista / izquierda.",
        bias_bucket="izq",
        economic_bucket="estatista",
        peronism_bucket="peronista",
        link_pattern=r"^https?://www\.tiempoar\.com\.ar/ta_article/[a-z0-9-]+/?$",
    ),
    PortalSeed(
        slug="la-voz",
        name="La Voz del Interior",
        homepage_url="https://www.lavoz.com.ar/",
        description="Principal diario de Córdoba. Línea editorial centro / centro-derecha.",
        bias_bucket="centro",
        economic_bucket="centro",
        peronism_bucket="antiperonista",
        link_pattern=r"^https?://www\.lavoz\.com\.ar/[a-z0-9-/]+/[a-z0-9-]+_0_[A-Za-z0-9]+\.html$",
    ),
    PortalSeed(
        slug="izquierda-diario",
        name="La Izquierda Diario",
        homepage_url="https://www.laizquierdadiario.com/",
        # La portada del medio muestra secciones geográficas en vez de notas;
        # el feed real está en /Últimas-noticias.
        discovery_url="https://www.laizquierdadiario.com/%C3%9Altimas-noticias",
        description="Diario del PTS / FIT-U. Línea editorial trotskista, anti-capitalista; crítica al peronismo desde la izquierda.",
        bias_bucket="izq",
        economic_bucket="estatista",
        peronism_bucket="centro",
        # LID no usa fecha ni ID en las URLs de notas, sólo el slug del titular.
        # Notas reales: 6+ palabras en el slug (ej: /Bullrich-se-diferencia-de-Milei-...).
        # Secciones (/Politica, /La-Pampa, /Provincia-de-Buenos-Aires) y autores
        # (/Nancy-Mendez, /Juan-Manuel-Astiazaran) tienen 1-4 palabras → quedan fuera.
        link_pattern=r"^https?://www\.laizquierdadiario\.com/[\w]+(?:-[\w]+){5,}/?$",
    ),
]


def get_seed(slug: str) -> PortalSeed | None:
    return next((p for p in PORTAL_SEEDS if p.slug == slug), None)
