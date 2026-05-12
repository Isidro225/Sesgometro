"""Filtro de relevancia política para el pipeline de noticias.

Sesgómetro no intenta ser un agregador general: sólo debería persistir noticias
con impacto o disputa política. El filtro es heurístico y transparente; prioriza
no guardar deportes, lifestyle, cotizaciones sueltas o policiales aisladas.
"""
from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    text = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", text)


_word_boundary_cache: dict[frozenset[str], re.Pattern[str]] = {}


def _contains_any(text: str, patterns: set[str]) -> bool:
    """Match con \b word boundaries. Para siglas cortas como 'pro' o 'lla'
    que de otro modo matchean dentro de palabras como 'polvo' o 'ella'.
    """
    key = frozenset(patterns)
    regex = _word_boundary_cache.get(key)
    if regex is None:
        escaped = sorted((re.escape(p) for p in patterns), key=len, reverse=True)
        regex = re.compile(r"\b(?:" + "|".join(escaped) + r")\b")
        _word_boundary_cache[key] = regex
    return regex.search(text) is not None


def _contains_any_substr(text: str, patterns: set[str]) -> bool:
    """Match de substring puro. Para fragmentos de URL como '/politica/'
    donde \b no funciona (las barras son non-word chars).
    """
    return any(pattern in text for pattern in patterns)


POLITICAL_SECTIONS = {
    "/politica/",
    "/politics/",
    "/actualidad-politica/",
    "/poder/",
}

NON_POLITICAL_SECTIONS = {
    "/deportes/",
    "/sports/",
    "/espectaculos/",
    "/show/",
    "/television/",
    "/tecno/",
    "/tecnologia/",
    "/turismo/",
    "/lifestyle/",
    "/recetas/",
    "/horoscopo/",
}

POLITICAL_ACTORS = {
    "adorni",
    "bullrich",
    "caputo",
    "cristina",
    "francos",
    "kicillof",
    "macri",
    "massa",
    "milei",
    "petri",
    "santilli",
    "villarruel",
}

POLITICAL_INSTITUTIONS = {
    "afip",
    "anses",
    "banco central",
    "casa rosada",
    "congreso",
    "corte suprema",
    "diputados",
    "dnu",
    "fmi",
    "gobernador",
    "gobernadores",
    "gobierno",
    "indec",
    "intendente",
    "jefatura de gabinete",
    "justicia federal",
    "legislatura",
    "ministerio",
    "ministro",
    "municipio",
    "presidente",
    "senado",
}

POLITICAL_PARTIES_AND_MOVEMENTS = {
    "campora",
    "cgt",
    "fit",
    "juntos por el cambio",
    "kirchnerismo",
    "la libertad avanza",
    "lla",
    "peronismo",
    "pro",
    "radicalismo",
    "ucr",
    "union por la patria",
}

POLICY_TERMS = {
    "ajuste",
    "decreto",
    "deficit",
    "deuda",
    "elecciones",
    "federal",
    "impuesto",
    "impuestos",
    "inflacion",
    "ley",
    "marcha federal",
    "paritaria",
    "paritarias",
    "presupuesto",
    "privatizacion",
    "privatizaciones",
    "reforma laboral",
    "reforma previsional",
    "regulacion",
    "retenciones",
    "subsidio",
    "subsidios",
    "tarifa",
    "tarifas",
}

SECURITY_POLICY_TERMS = {
    "fuerzas federales",
    "inseguridad",
    "narcotrafico",
    "protocolo antipiquetes",
    "seguridad",
    "servicio penitenciario",
}

NON_POLITICAL_TERMS = {
    "cascada",
    "champions",
    "cine",
    "cocina",
    "cotizacion",
    "dolar blue hoy",
    "entretenimiento",
    "horoscopo",
    "libertadores",
    "mascotas",
    "mundial",
    "netflix",
    "receta",
    "restaurante",
    "seleccion argentina",
    "streaming",
    "tendencia",
    "turismo",
}

HARD_NON_POLITICAL_TITLE_TERMS = {
    "champions",
    "copa libertadores",
    "futbol",
    "libertadores",
    "mundial",
    "receta",
    "restaurante",
    "seleccion argentina",
    "torneo apertura",
}


def is_political_news(title: str | None, text: str | None = None, url: str | None = None) -> bool:
    """Devuelve True si una nota califica para Sesgómetro.

    `text` puede ser body completo, resumen neutro o una concatenación de campos.
    """
    title_norm = _normalize(title or "")
    body_norm = _normalize(text or "")
    url_norm = _normalize(url or "")
    haystack = f"{title_norm} {body_norm} {url_norm}"

    has_political_section = _contains_any_substr(url_norm, POLITICAL_SECTIONS)
    has_non_political_section = _contains_any_substr(url_norm, NON_POLITICAL_SECTIONS)
    has_actor = _contains_any(haystack, POLITICAL_ACTORS)
    has_institution = _contains_any(haystack, POLITICAL_INSTITUTIONS)
    has_party = _contains_any(haystack, POLITICAL_PARTIES_AND_MOVEMENTS)
    title_has_actor = _contains_any(title_norm, POLITICAL_ACTORS)
    title_has_institution = _contains_any(title_norm, POLITICAL_INSTITUTIONS)
    title_has_party = _contains_any(title_norm, POLITICAL_PARTIES_AND_MOVEMENTS)
    title_is_explicitly_political = title_has_actor or title_has_institution or title_has_party
    has_policy = _contains_any(haystack, POLICY_TERMS)
    has_security_policy = _contains_any(haystack, SECURITY_POLICY_TERMS) and (
        has_institution or has_actor or has_policy
    )
    is_rate_ticker = "dolar" in title_norm and (
        "a cuanto" in title_norm
        or "cotizacion" in title_norm
        or "minuto a minuto" in title_norm
        or "precio" in title_norm
    )
    is_hard_non_political_title = _contains_any(title_norm, HARD_NON_POLITICAL_TITLE_TERMS) or is_rate_ticker
    looks_non_political = _contains_any(title_norm, NON_POLITICAL_TERMS) or (
        has_non_political_section and not (has_actor or has_institution or has_party)
    )

    if is_hard_non_political_title and not (title_is_explicitly_political or has_political_section):
        return False

    if has_non_political_section and not (title_is_explicitly_political or has_political_section):
        return False

    if looks_non_political and not (has_actor or has_institution or has_party or has_political_section):
        return False

    if has_political_section:
        return True
    if has_actor or has_party:
        return True
    if has_institution and (has_policy or has_security_policy):
        return True
    if has_policy and (has_institution or has_security_policy):
        return True

    return False
