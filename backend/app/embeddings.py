"""Embeddings ligeros para clustering de noticias.

Optamos por TF (term frequency) sparse sobre unigramas + bigramas del título y
las primeras N palabras del cuerpo. No usamos modelos neuronales para no meter
PyTorch en el stack: para clustering de noticias del mismo evento, los titulares
y la primera entradilla comparten léxico suficiente para que TF + coseno
funcione decentemente (entidades, lugares, números, vocabulario).

El vector se serializa como JSON `{token: peso}` y se compara por similitud
coseno. El centroide de una historia es la media (también sparse) de los
vectores de sus artículos.

Si más adelante queremos calidad estilo Ground News real conviene reemplazar
esto por embeddings de un modelo (Voyage, sentence-transformers multilingüe).
La interfaz pública (`embed_article`, `cosine`, `mean_centroid`) está pensada
para ser drop-in.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter

Vector = dict[str, float]

_STOPWORDS = frozenset(
    """
    a al algo algun alguna algunas alguno algunos algun ante antes aquel aquella
    aquellas aquello aquellos aqui asi aun aunque cada como con contra cual
    cuales cualquier cuando cuanta cuantas cuanto cuantos de del desde donde
    dos durante el ella ellas ellos en entre era erais eran eras eres es esa
    esas ese eso esos esta estaba estabais estaban estabas estad estada estadas
    estado estados estamos estan estar estas este esto estos estoy etc fue
    fuera fueron fui fuimos ha haber habia habian habias has hasta hay he hubo
    la las le les lo los mas me mi mia mias mientras mio mios mis misma mismas
    mismo mismos mucha muchas mucho muchos muy nada ni no nos nosotras nosotros
    nuestra nuestras nuestro nuestros o otra otras otro otros para pero poco
    por porque pues que quien quienes se sea seais sean seas segun ser sera
    seran seras serian seria si sido siempre sin sobre solo somos son soy su
    sus suya suyas suyo suyos tal tambien tanto te tenga tengamos tengan
    tengas tener tengo ti tiempo tiene tienen tienes todo todos tu tus tuya
    tuyas tuyo tuyos un una unas uno unos vosotras vosotros vuestra vuestras
    vuestro vuestros y ya yo
    """.split()
)


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def _tokenize(text: str) -> list[str]:
    text = _strip_accents(text.lower())
    tokens = re.findall(r"[a-z0-9]+", text)
    return [t for t in tokens if len(t) >= 3 and t not in _STOPWORDS]


def embed_text(title: str | None, body: str | None, body_chars: int = 800) -> Vector:
    """Devuelve un vector sparse normalizado (norma L2 = 1)."""
    # El título pesa el doble que el body — concentra entidades.
    title_tokens = _tokenize(title or "")
    body_tokens = _tokenize((body or "")[:body_chars])

    counter: Counter[str] = Counter()
    for tok in title_tokens:
        counter[tok] += 2
    for tok in body_tokens:
        counter[tok] += 1
    # Bigramas (solo del título; más estables que del cuerpo).
    for i in range(len(title_tokens) - 1):
        counter[f"{title_tokens[i]}_{title_tokens[i + 1]}"] += 2

    if not counter:
        return {}

    norm = math.sqrt(sum(v * v for v in counter.values()))
    return {k: v / norm for k, v in counter.items()}


def cosine(a: Vector, b: Vector) -> float:
    """Similitud coseno entre dos vectores ya normalizados."""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def mean_centroid(vectors: list[Vector]) -> Vector:
    if not vectors:
        return {}
    sum_v: dict[str, float] = {}
    for v in vectors:
        for k, val in v.items():
            sum_v[k] = sum_v.get(k, 0.0) + val
    norm = math.sqrt(sum(val * val for val in sum_v.values()))
    if norm == 0:
        return {}
    return {k: val / norm for k, val in sum_v.items()}


def dumps(vec: Vector) -> str:
    return json.dumps(vec, ensure_ascii=False)


def loads(raw: str | None) -> Vector:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}
