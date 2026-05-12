"""Clasificación heurística de historias por categoría temática.

Las categorías son user-facing (aparecen en /categorias del frontend). La
clasificación es por keywords aplicados sobre el título del cluster, en orden
de especificidad: ambiente → salud → seguridad → internacional → economía →
política (fallback). Si ningún match específico aparece, cae a `politica`
porque `is_political_news` ya filtró los no-políticos antes de persistir.

Reemplazable a futuro por una clasificación con haiku-4-5 (cacheable).
"""
from __future__ import annotations

import re
import unicodedata

CATEGORY_SLUGS: tuple[str, ...] = (
    "politica",
    "economia",
    "seguridad",
    "internacional",
    "salud",
    "ambiente",
)

# Orden de evaluación: las más específicas primero. `politica` no está acá
# porque es el fallback (no requiere match).
_PRIORITY: tuple[str, ...] = ("ambiente", "salud", "seguridad", "internacional", "economia")

# Las keywords se comparan sobre el título normalizado (lowercase, sin tildes).
# Frases con espacio se buscan como substring; palabras sueltas con bordes
# de palabra (\b) para evitar matches parciales tipo "salud" en "saludar".
_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ambiente": (
        "ambiental", "ambientalista", "medio ambiente",
        "cambio climatico", "climatico", "calentamiento global",
        "incendio", "incendios", "sequia", "inundacion", "inundaciones",
        "contaminacion", "ecologico", "ecologica", "biodiversidad",
        "deforestacion", "vaca muerta", "litio", "mineria", "minero",
        "energia renovable", "eolica", "eolico", "petroleo", "yacimiento",
        "humedal", "humedales", "glaciar", "glaciares", "reciclaje", "fauna",
    ),
    "salud": (
        "medico", "medica", "medicos", "hospital", "hospitales",
        "clinica", "clinicas", "sanatorio", "enfermeria", "enfermero",
        "paciente", "pacientes", "vacuna", "vacunacion", "vacunas",
        "pandemia", "epidemia", "enfermedad", "enfermedades",
        "dengue", "sarampion", "covid", "gripe",
        "garrahan", "pami", "obra social", "obras sociales",
        "sanitario", "sanitaria", "medicamento", "medicamentos",
        "farmaceutico", "farmacia",
    ),
    "seguridad": (
        "policia", "policial", "policias", "gendarmeria", "prefectura",
        "narcotrafico", "narcomenudeo", "narco",
        "crimen", "asesinato", "asesino", "homicidio", "femicidio",
        "robo", "asalto", "secuestro", "tiroteo",
        "fiscalia", "condena", "condenado", "carcel", "carceles",
        "detenido", "detenidos", "detencion", "allanamiento", "allanamientos",
        "delito", "delincuencia", "inseguridad",
        "bullrich", "marset",
    ),
    "internacional": (
        "trump", "biden", "putin", "zelenski", "netanyahu",
        "israel", "palestina", "gaza", "hamas",
        "ucrania", "rusia", "china", "taiwan",
        "ee.uu", "estados unidos",
        "brasil", "lula", "bolsonaro",
        "venezuela", "maduro",
        "boric", "petro", "sheinbaum",
        "macron", "merz", "meloni", "starmer",
        "iran", "corea del norte",
        "naciones unidas", "union europea", "otan",
        "g20", "diplomacia", "cumbre", "cumbres",
    ),
    "economia": (
        "inflacion", "dolar", "dolares",
        "bcra", "banco central", "fmi",
        "paritaria", "paritarias", "salario", "salarios", "sueldo", "sueldos",
        "jubilacion", "jubilaciones", "jubilado", "jubilados",
        "pobreza", "indigencia", "desempleo",
        "pyme", "pymes",
        "exportacion", "exportaciones", "importacion", "importaciones",
        "recesion", "pbi", "deficit fiscal", "superavit",
        "tributario", "impuesto", "impuestos", "iva", "ganancias",
        "arca", "afip",
        "tipo de cambio", "reservas", "cepo", "devaluacion",
        "plazo fijo", "bonos", "merval", "riesgo pais",
        "caputo", "sturzenegger",
        "tarifa", "tarifas", "subsidio", "subsidios",
    ),
}


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _matches(text_norm: str, keywords: tuple[str, ...]) -> bool:
    for kw in keywords:
        if " " in kw or "." in kw:
            if kw in text_norm:
                return True
        else:
            if re.search(rf"\b{re.escape(kw)}\b", text_norm):
                return True
    return False


def classify(title: str | None) -> str:
    """Devuelve uno de CATEGORY_SLUGS. Fallback: 'politica'."""
    if not title:
        return "politica"
    text_norm = _norm(title)
    for cat in _PRIORITY:
        if _matches(text_norm, _KEYWORDS[cat]):
            return cat
    return "politica"
