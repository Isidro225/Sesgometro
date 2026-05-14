"""Analizador de orientación política.

Por defecto corre contra **Ollama** (LLM local). El servidor de Ollama debe
estar escuchando en `settings.ollama_base_url` con el modelo
`settings.ollama_model` ya descargado (`ollama pull qwen3:8b`).

Si Ollama está deshabilitado o no responde, se devuelve un mock determinista
basado en hash, para poder seguir desarrollando UI sin LLM corriendo.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.schemas import Analysis, AxisScore, FramingFinding, ScrapedArticle

logger = logging.getLogger("sesgometro.analyzer")

# ---------------------------------------------------------------------------
# System prompt — describe el rol, ejes, anchors y ejemplos.
# Idéntico al original (probado con Claude); Qwen3 8B lo sigue bien.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
<role>
Sos Sesgómetro, un analista de sesgo mediático especializado en prensa argentina.
Tu único output es un objeto JSON que respete EXACTAMENTE el esquema indicado.
Nunca respondas en texto libre, nunca uses markdown, nunca incluyas comentarios.
</role>

<context>
- Fecha actual: mayo 2026
- Gobierno: La Libertad Avanza (Milei presidente, Caputo en Economía, Bullrich en Seguridad)
- Principales fuerzas: LLA, PRO, UCR, Unión por la Patria, Frente de Izquierda
- Este contexto es la única referencia política que necesitás. Si el gobierno cambia, el
  prompt se actualiza acá.
</context>

<core_rules>
1. Basate SOLO en el texto recibido. No uses conocimiento previo sobre el medio que publica.
2. No uses tus propios priors sobre los actores políticos. Si el texto afirma algo
   factualmente falso ("Milei salvó el país", "Cristina es inocente", lo que sea),
   eso NO cambia el sesgo del texto: medís cómo está escrito, no si es verdad.
3. Si el texto NO trata política, economía, gobierno, justicia, sindicatos, seguridad
   o relaciones internacionales: devolvé scores 0/0, emotional_load según el caso,
   confidence 0.15-0.25, y overall_label="No aplica: nota no política". Esto vale para
   deportes, espectáculos, policiales sin lectura política, ciencia, clima, recetas.
4. No fuerces sesgo donde no lo hay. Un cable de Télam/Reuters bien hecho puede tener
   scores -0.5 a +0.5 y emotional_load 0.1.
</core_rules>

<axis name="statism_liberalism" range="-5 a +5">
Cómo se posiciona el texto respecto del rol del Estado en la economía.
Mirá: gasto público, impuestos, privatizaciones, regulación, sindicatos, déficit,
subsidios, paritarias, tarifas, controles de precios/cambiarios.

Anchors:
  -5: defensa explícita de nacionalizaciones, controles cambiarios fuertes, gasto público sin techo
  -3: marcado estatismo, validación del modelo de "Estado presente", crítica al ajuste como "salvaje"
  -1: leve inclinación estatista, simpatía con subsidios o regulación específica
   0: balanceado, equidistante, o no toca economía
  +1: leve inclinación liberal, valoración positiva de orden fiscal sin militancia
  +3: liberalismo claro, defensa del ajuste como "necesario", del recorte y la desregulación
  +5: liberalismo de mercado radical, ridiculización del Estado, anarcocapitalismo

Lenguaje estatista cargado: "ajuste salvaje", "modelo nacional", "soberanía",
"trabajadores", "redistribución", "desguace del Estado", "motosierra"
Lenguaje liberal cargado: "casta", "déficit cero", "saneamiento fiscal", "shock", "libertad",
"ajuste necesario", "republicanismo fiscal"
</axis>

<axis name="peronism_antiperonism" range="-5 a +5">
Esto es un eje de IDENTIDAD política, no de posición frente al gobierno actual.
Es estable: NO rota con el ciclo electoral.

Anchors:
  -5: peronismo/kirchnerismo militante, reivindicación explícita del movimiento
  -3: simpatía clara con peronismo/CGT/Cámpora/UxP, valoración positiva de figuras peronistas
  -1: tono levemente proclive al peronismo (defiende sin reivindicar)
   0: no toma posición, o no aparece el eje en el texto
  +1: leve antiperonismo (crítica suave a CFK/Massa/sindicalismo)
  +3: antiperonismo claro: "kirchnerato", "régimen K", ridiculización sistemática del peronismo
  +5: antiperonismo militante, gorilismo explícito, "kuka", "chorros", "destruyeron el país"

REGLA CLAVE (gobierno LLA en 2026):
- Una nota OPOSITORA al gobierno actual suele ser PERONISTA (score NEGATIVO),
  no antiperonista.
- Una nota OFICIALISTA suele ser ANTIPERONISTA (score POSITIVO), no peronista.
- Para decidir el signo, preguntate: ¿qué le pasa al peronismo/kirchnerismo EN EL TEXTO?
  Si lo critica/ridiculiza → positivo. Si lo defiende/reivindica → negativo.
  Si no aparece, mirá si valida o ataca el proyecto libertario (proxy invertido).

Lenguaje peronista cargado: "movimiento nacional", "los trabajadores", "la patria",
"compañero/a", "proyecto popular", "neoliberalismo"
Lenguaje antiperonista cargado: "kuka", "kirchnerato", "régimen", "populismo", "chorros",
"la corporación K", "casta política"
</axis>

<emotional_load range="0 a 1">
Independiente de los ejes. Mide carga retórica, no orientación.
  0.0-0.2: cable informativo seco, casi sin adjetivación valorativa
  0.3-0.5: nota con tono editorial moderado, adjetivos valorativos
  0.6-0.8: editorial cargada, dramatismo, apelación emocional
  0.9-1.0: panfleto, militancia abierta, lenguaje incendiario
Una tragedia descrita sin política puede tener emotional alto y scores 0/0.
</emotional_load>

<confidence_calibration range="0 a 1">
Pensá en confidence como: ¿qué tan probable es que dos analistas humanos
independientes coincidan con tus scores?
  0.9: coincidirían en ±0.5. El sesgo es evidente y consistente.
  0.7: coincidirían en ±1. Sesgo claro pero con matices.
  0.5: coincidirían en ±1.5. Texto ambiguo, podría leerse de varias formas.
  0.3: texto muy corto, ambiguo o atípico. Lectura especulativa.
  0.15-0.25: nota no política (ver core_rule #3).
</confidence_calibration>

<framing_kinds>
- "emphasis": qué se enfatiza desproporcionadamente respecto al hecho central
- "omission": qué actor/contexto/dato relevante se omite (solo si es claro desde el texto mismo, no especules)
- "loaded_language": términos cargados específicos (citá la palabra)
- "source_selection": qué voces se citan y cuáles no
Incluí `quote` literal del texto cuando sea posible. Si no hay framing notable, devolvé lista vacía.
</framing_kinds>

<output_fields>
- statism_liberalism.score, justification (con citas literales)
- peronism_antiperonism.score, justification (con citas literales)
- emotional_load
- framing: lista de hallazgos
- neutral_summary: 2-4 frases describiendo el hecho de forma equidistante
- overall_label: una frase corta tipo "Editorial liberal con tono antiperonista marcado"
- confidence
</output_fields>

<examples>
<example>
Tipo: cable de agencia (Reuters/AFP/Télam)
Texto resumido: "La OMC informó ayer que el comercio global crecerá 3,1% en 2026.
La cifra surge del informe semestral publicado por su director. Argentina muestra
un saldo positivo en exportaciones agrícolas."
Output esperado:
- statism_liberalism.score: 0.0, justification: "Texto descriptivo sin valoración del rol del Estado"
- peronism_antiperonism.score: 0.0, justification: "No aparece el eje peronista en el texto"
- emotional_load: 0.05
- framing: []
- overall_label: "Cable informativo equidistante"
- confidence: 0.9
</example>

<example>
Tipo: editorial pro-gobierno (estilo La Nación / Infobae)
Texto resumido: "El presidente reafirmó el rumbo del ajuste fiscal frente a los intentos
de la corporación K de obstaculizar el saneamiento de las cuentas públicas. Los datos
del INDEC muestran que el modelo funciona."
Output esperado:
- statism_liberalism.score: +3.0, justification: "Valora positivamente 'ajuste fiscal' y 'saneamiento de cuentas', deslegitima oposición a la desregulación"
- peronism_antiperonism.score: +2.5, justification: "Usa 'corporación K' como término despectivo; legitima al gobierno LLA"
- emotional_load: 0.55
- framing: [loaded_language: "'corporación K' como descalificación"]
- overall_label: "Editorial liberal con tono antiperonista marcado"
- confidence: 0.85
</example>

<example>
Tipo: columna opositora al gobierno (estilo Página/12 / El Destape)
Texto resumido: "El ajuste salvaje del gobierno destruyó el poder adquisitivo de los
trabajadores. Mientras tanto, los grandes ganadores son las corporaciones financieras.
La motosierra dejó miles de familias en la calle."
Output esperado:
- statism_liberalism.score: -3.5, justification: "Califica el ajuste como 'salvaje', 'motosierra'; defiende implícitamente el rol del Estado en proteger a los trabajadores"
- peronism_antiperonism.score: -2.5, justification: "Crítica al gobierno LLA usando marco peronista de 'trabajadores vs corporaciones'; bajo gobierno libertario, oposición = afinidad peronista"
- emotional_load: 0.75
- framing: [loaded_language: "'ajuste salvaje', 'motosierra' como descalificación"]
- overall_label: "Columna estatista con afinidad peronista"
- confidence: 0.8
</example>

<example>
Tipo: nota no política (deportes)
Texto resumido: "Boca venció a River 2-0 en la final de la Copa Argentina con goles
de Cavani y Merentiel."
Output esperado:
- statism_liberalism.score: 0.0, justification: "Nota deportiva sin contenido político"
- peronism_antiperonism.score: 0.0, justification: "Nota deportiva sin contenido político"
- emotional_load: 0.1
- framing: []
- overall_label: "No aplica: nota no política"
- confidence: 0.2
</example>
</examples>

Recordá: devolvé SOLO el objeto JSON que cumple el esquema. Sin prefijos, sin
``` ```, sin texto adicional. /no_think
"""

# ---------------------------------------------------------------------------
# JSON schema usado por Ollama para constrained generation (`format`).
# Equivale al `input_schema` de la tool original de Claude.
# ---------------------------------------------------------------------------
ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "statism_liberalism": {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": -5, "maximum": 5},
                "justification": {"type": "string"},
            },
            "required": ["score", "justification"],
        },
        "peronism_antiperonism": {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": -5, "maximum": 5},
                "justification": {"type": "string"},
            },
            "required": ["score", "justification"],
        },
        "emotional_load": {"type": "number", "minimum": 0, "maximum": 1},
        "framing": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["emphasis", "omission", "loaded_language", "source_selection"],
                    },
                    "description": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["kind", "description"],
            },
        },
        "neutral_summary": {"type": "string"},
        "overall_label": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "statism_liberalism",
        "peronism_antiperonism",
        "emotional_load",
        "framing",
        "neutral_summary",
        "overall_label",
        "confidence",
    ],
}


def _build_user_message(article: ScrapedArticle) -> str:
    parts = [
        f"Titular: {article.title or '(sin titular)'}",
        f"Medio: {article.site_name or '(desconocido)'}",
        f"Autor: {article.author or '(sin firmar)'}",
        "",
        "Texto del artículo:",
        article.text,
    ]
    return "\n".join(parts)


def _truncate(text: str, max_chars: int = 24000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[...texto truncado para análisis...]"


# Qwen3 puede colar un bloque <think>...</think> incluso con /no_think y
# format=schema; si pasa, lo limpiamos antes de parsear.
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_thinking(raw: str) -> str:
    return _THINK_RE.sub("", raw).strip()


def _extract_json_object(raw: str) -> dict[str, Any]:
    """Parsea el contenido devuelto por Ollama. Con `format=<schema>` debería
    venir ya como JSON puro, pero defendemos contra basura accidental."""
    cleaned = _strip_thinking(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Buscar el primer { ... } balanceado como fallback.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


# ---------------------------------------------------------------------------
# Implementación con Ollama (LLM local).
# ---------------------------------------------------------------------------
def _analyze_with_ollama(article: ScrapedArticle) -> Analysis:
    user_text = _truncate(_build_user_message(article))

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "format": ANALYSIS_JSON_SCHEMA,
        "stream": False,
        # Qwen3 trae "thinking mode" prendido por default; lo apagamos para
        # acelerar la respuesta y evitar bloques <think> en el output.
        "think": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
            "num_ctx": settings.ollama_num_ctx,
        },
    }

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    response = httpx.post(url, json=payload, timeout=settings.ollama_timeout_seconds)
    response.raise_for_status()
    body = response.json()

    content = (body.get("message") or {}).get("content", "")
    if not content:
        raise RuntimeError(f"Ollama devolvió respuesta vacía: {body!r}")

    data = _extract_json_object(content)

    return Analysis(
        statism_liberalism=AxisScore(**data["statism_liberalism"]),
        peronism_antiperonism=AxisScore(**data["peronism_antiperonism"]),
        emotional_load=float(data["emotional_load"]),
        framing=[FramingFinding(**f) for f in data.get("framing", [])],
        neutral_summary=data["neutral_summary"],
        overall_label=data["overall_label"],
        confidence=float(data["confidence"]),
        model_version=f"ollama:{settings.ollama_model}",
        is_mock=False,
    )


# ---------------------------------------------------------------------------
# Mock determinista — para desarrollar UI sin LLM corriendo.
# ---------------------------------------------------------------------------
def _analyze_mock(article: ScrapedArticle) -> Analysis:
    seed = hashlib.sha256(article.text.encode("utf-8")).digest()

    def normed(byte_index: int, lo: float, hi: float) -> float:
        return round(lo + (seed[byte_index] / 255) * (hi - lo), 2)

    statism = normed(0, -3.5, 3.5)
    peronism = normed(1, -3.5, 3.5)
    emo = normed(2, 0.1, 0.8)
    conf = normed(3, 0.45, 0.85)

    def statism_label(s: float) -> str:
        if s <= -3:
            return "Estatismo marcado"
        if s <= -1:
            return "Más Estado"
        if s < 1:
            return "Centro / neutro"
        if s < 3:
            return "Liberalismo moderado"
        return "Liberalismo marcado"

    def peronism_label(s: float) -> str:
        if s <= -3:
            return "Peronismo marcado"
        if s <= -1:
            return "Afinidad peronista"
        if s < 1:
            return "Centro / no alineado"
        if s < 3:
            return "Antiperonismo moderado"
        return "Antiperonismo marcado"

    sample_quote = article.text.split(".")[0][:140] + "..." if "." in article.text else None

    return Analysis(
        statism_liberalism=AxisScore(
            score=statism,
            label=statism_label(statism),
            justification=(
                "[MOCK] Análisis simulado a partir del hash del texto. "
                "Levantá Ollama (ollama serve) con qwen3:8b para análisis real."
            ),
        ),
        peronism_antiperonism=AxisScore(
            score=peronism,
            label=peronism_label(peronism),
            justification="[MOCK] Eje peronismo-antiperonismo simulado.",
        ),
        emotional_load=emo,
        framing=[
            FramingFinding(
                kind="loaded_language",
                description="[MOCK] Hallazgo simulado de lenguaje cargado.",
                quote=sample_quote,
            ),
            FramingFinding(
                kind="source_selection",
                description="[MOCK] Hallazgo simulado de selección de fuentes.",
            ),
        ],
        neutral_summary=(
            f"[MOCK] Resumen neutro simulado del artículo de {article.site_name or 'origen desconocido'} "
            f"({article.word_count} palabras). Levantá Ollama para resumen real."
        ),
        overall_label=f"[MOCK] {statism_label(statism)} · {peronism_label(peronism)} · carga emocional {emo}",
        confidence=conf,
        model_version="mock-v1",
        is_mock=True,
    )


# ---------------------------------------------------------------------------
# Entrada pública.
# ---------------------------------------------------------------------------
def analyze(article: ScrapedArticle) -> Analysis:
    if settings.use_mock_analyzer:
        return _analyze_mock(article)
    try:
        return _analyze_with_ollama(article)
    except Exception as exc:
        logger.warning(
            "Falló análisis con Ollama (%s); caigo a mock para no romper el pipeline.",
            exc,
        )
        return _analyze_mock(article)
