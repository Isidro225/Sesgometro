"""Catálogo de portales seed (medios argentinos).

Cada portal puede declarar:
- `homepage_url`: portada que se rasca para descubrir artículos.
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
]


def get_seed(slug: str) -> PortalSeed | None:
    return next((p for p in PORTAL_SEEDS if p.slug == slug), None)
