"""Analizador de orientación política.

Si hay `ANTHROPIC_API_KEY` configurada, llama a Claude con prompt caching y
herramienta `submit_analysis` para salida estructurada. Si no, devuelve un mock
determinista (basado en hash del texto) para poder desarrollar el frontend.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from anthropic import Anthropic

from app.config import settings
from app.schemas import Analysis, AxisScore, FramingFinding, ScrapedArticle

# ---------------------------------------------------------------------------
# System prompt — se cachea en cada llamada para abaratar tokens.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
Sos Sesgómetro, un analista de sesgo mediático especializado en prensa argentina.

Tu trabajo es leer un artículo y emitir un análisis estructurado de su orientación
política, basándote SOLO en el texto recibido. No uses conocimiento previo sobre
el medio que lo publica; juzgá el artículo en sí mismo. Si el texto es demasiado
ambiguo o puramente informativo, decilo y bajá la confianza.

Contexto argentino: no reduzcas el análisis a izquierda/derecha. Separá dos
dimensiones que suelen mezclarse: economía política (estatismo vs liberalismo)
y clivaje identitario argentino (peronismo vs antiperonismo). Tené en cuenta
lenguaje cargado típico: "casta", "kuka", "gorila", "facho", "populista",
"libertario", "ajuste", "modelo", "la gente", "movimiento nacional", "república".

Devolvés SIEMPRE el resultado llamando a la herramienta `submit_analysis`. Nunca
respondas en texto libre.

Rúbrica:

1. Eje estatismo-liberalismo (-5 a +5):
   -5 estatismo/intervencionismo fuerte · -2 más Estado · 0 ambiguo/neutro · +2 liberalismo económico · +5 liberalismo de mercado radical
   Mirá tratamiento de gasto público, impuestos, privatizaciones, regulación, sindicatos,
   mercado, déficit, subsidios y rol del Estado.
   Justificá con citas literales del texto.

2. Eje peronismo-antiperonismo (-5 a +5):
   Este eje mide IDENTIDAD política frente al peronismo/kirchnerismo, NO la
   posición frente al gobierno de turno. Es un eje estable que no rota con
   el ciclo electoral.
   -5 peronista/kirchnerista marcado · -2 simpatía peronista · 0 no toma posición ·
   +2 antiperonista moderado · +5 antiperonismo marcado
   Mirá qué valoración (positiva/negativa) hace el texto del peronismo,
   kirchnerismo, sindicalismo peronista, La Cámpora, CGT, Unión por la Patria.
   Y separadamente del PRO, radicalismo, libertarios, "republicanismo".

   IMPORTANTE — contexto 2026, La Libertad Avanza gobernando (Milei presidente,
   Caputo en Economía, Bullrich en Seguridad):
   - Criticar a Milei/Caputo/Bullrich/LLA NO es antiperonismo. Generalmente
     indica posición peronista o progresista — score NEGATIVO.
   - Defender el ajuste fiscal, el DNU 70/23, las privatizaciones o al gobierno
     actual NO es peronismo. Generalmente alinea con antiperonismo — score
     POSITIVO.
   - Para decidir el signo, preguntate: ¿qué le pasa al peronismo/kirchnerismo
     EN EL TEXTO? Si lo critica/ridiculiza/desacredita → positivo. Si lo
     defiende/reivindica → negativo. Si no aparece, mirá si valida o ataca el
     proyecto libertario (proxy invertido).
   - Una nota opositora al oficialismo libertario suele ser peronista, no
     antiperonista. Una nota oficialista hoy suele ser antiperonista, no
     peronista.

3. Carga emocional (0 a 1):
   0 = informativo seco · 1 = editorial muy cargado. Mirá adjetivos valorativos,
   apelaciones emotivas, dramatismo.

4. Framing — lista de hallazgos con `kind`:
   - "emphasis": qué se enfatiza desproporcionadamente
   - "omission": qué actor/contexto/dato relevante se omite
   - "loaded_language": términos cargados ("régimen" vs "gobierno", "casta" vs "dirigencia", etc.)
   - "source_selection": qué voces se citan y cuáles no
   Incluí `quote` literal cuando sea posible.

5. Resumen neutro: 2-4 frases describiendo el hecho de forma equidistante.

6. Etiqueta global: una frase corta como "Informativo con tono liberal moderado y antikirchnerista".

7. Confianza (0 a 1): 0.9+ si el texto es claramente sesgado; 0.4-0.6 si es ambiguo.

Sé honesto. No fuerces sesgo donde no lo hay. Un cable de agencia bien hecho
puede tener -0.5 a +0.5 en ambos ejes y carga emocional 0.1.
"""

# ---------------------------------------------------------------------------
# Definición de la tool que fuerza salida estructurada.
# ---------------------------------------------------------------------------
ANALYSIS_TOOL: dict[str, Any] = {
    "name": "submit_analysis",
    "description": "Envía el análisis estructurado del artículo.",
    "input_schema": {
        "type": "object",
        "properties": {
            "statism_liberalism": {
                "type": "object",
                "properties": {
                    "score": {"type": "number", "minimum": -5, "maximum": 5},
                    "label": {"type": "string"},
                    "justification": {"type": "string"},
                },
                "required": ["score", "label", "justification"],
            },
            "peronism_antiperonism": {
                "type": "object",
                "properties": {
                    "score": {"type": "number", "minimum": -5, "maximum": 5},
                    "label": {"type": "string"},
                    "justification": {"type": "string"},
                },
                "required": ["score", "label", "justification"],
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
    },
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


# ---------------------------------------------------------------------------
# Implementación real con Claude.
# ---------------------------------------------------------------------------
def _analyze_with_claude(article: ScrapedArticle) -> Analysis:
    client = Anthropic(api_key=settings.anthropic_api_key)
    user_text = _truncate(_build_user_message(article))

    response = client.messages.create(
        model=settings.analysis_model,
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "submit_analysis"},
        messages=[{"role": "user", "content": user_text}],
    )

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        raise RuntimeError("Claude no devolvió tool_use; respuesta inesperada.")

    payload = tool_block.input
    return Analysis(
        statism_liberalism=AxisScore(**payload["statism_liberalism"]),
        peronism_antiperonism=AxisScore(**payload["peronism_antiperonism"]),
        emotional_load=float(payload["emotional_load"]),
        framing=[FramingFinding(**f) for f in payload.get("framing", [])],
        neutral_summary=payload["neutral_summary"],
        overall_label=payload["overall_label"],
        confidence=float(payload["confidence"]),
        model_version=response.model,
        is_mock=False,
    )


# ---------------------------------------------------------------------------
# Mock determinista — para desarrollar UI sin gastar API.
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
                "Configura ANTHROPIC_API_KEY para análisis real con Claude."
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
            f"({article.word_count} palabras). Configura la API key para resumen real."
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
    return _analyze_with_claude(article)
