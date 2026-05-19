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
import unicodedata
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.schemas import Analysis, AxisScore, FramingFinding, ScrapedArticle


# ---------------------------------------------------------------------------
# Source prior: orientación editorial promedio del medio que publica el artículo.
# Se inyecta en el USER message (no en SYSTEM, así no rompemos cache) como
# desempate de PASO 1, nunca como input al score base.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourcePrior:
    economic_bucket: str = "centro"      # "estatista" | "centro" | "liberal"
    peronism_bucket: str = "centro"      # "peronista" | "centro" | "antiperonista"

    @property
    def is_informative(self) -> bool:
        """Si todos los buckets son 'centro' el prior no aporta señal."""
        return any(
            b != "centro"
            for b in (self.economic_bucket, self.peronism_bucket)
        )

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

2. SESGO = CÓMO ESTÁ ESCRITO, NO SI LOS HECHOS SON VERDADEROS.
   El sesgo reside en el MARCO y la PRESENTACIÓN, no en los hechos subyacentes.
   Una nota puede contener cifras 100% factuales y aun así tener sesgo fuerte si
   las encuadra con marcos de juicio implícito. NO subestimes el sesgo por el hecho
   de que el cuerpo sea "técnico" si el titular o la bajada introducen el marco.
   Ejemplos de marcos implícitos que CUENTAN como sesgo aunque los hechos sean ciertos:
   - "X cumplió otra orden de Y"          → marco de subordinación / pérdida de soberanía
   - "Y intervino para mejorar las chances electorales de X" → marco de injerencia política
   - "El BCRA perdió capacidad de defender el peso" → marco de pérdida estatista
   - "X desguazó el Estado / aplicó la motosierra" → marco de destrucción
   - "X saneó las cuentas / hizo el ajuste necesario" → marco de virtud (signo opuesto)
   Y al revés: si el texto afirma algo factualmente falso ("Milei salvó el país",
   "Cristina es inocente"), tampoco cambia el sesgo del texto — medís cómo lo
   presenta, no si la afirmación es verdadera.

3. Si el texto NO trata política, economía, gobierno, justicia, sindicatos, seguridad
   o relaciones internacionales: devolvé scores 0/0, emotional_load según el caso,
   confidence 0.15-0.25, y overall_label="No aplica: nota no política". Esto vale para
   deportes, espectáculos, policiales sin lectura política, ciencia, clima, recetas.

4. NO FUERCES sesgo donde no lo hay, PERO TAMPOCO LO SUBESTIMES donde sí lo hay.
   Un cable de Télam/Reuters bien hecho puede tener scores -0.5 a +0.5 y emotional_load 0.1.
   Pero una columna firmada o una nota con titular en forma de juicio NUNCA es un cable
   neutral, aunque el cuerpo tenga cifras factuales. Si dudás entre 0 y -2 / +2, mirá
   el titular y los conectores valorativos del cuerpo ("perdió capacidad de", "cumplió
   orden de", "saneó", "destruyó", "ridiculizó", "denunció") — esos pesan tanto como
   los adjetivos cargados.

5. NUNCA inventes citas. El campo `quote` de cada framing finding debe contener
   ÚNICAMENTE palabras o frases que aparezcan TEXTUALMENTE en el "Texto del artículo:"
   que recibís más abajo. Los ejemplos de este prompt (frases como "corporación K",
   "ajuste salvaje", "motosierra", "casta", "cumplió otra orden", etc.) son DE OTROS
   ARTÍCULOS ficticios, NO son contenido del texto a analizar. Si una palabra o frase
   no aparece literalmente en el texto recibido, NO la pongas en `quote`. Si no
   encontrás citas verificables, dejá `framing` vacío o devolvé findings sin `quote`
   (solo con `description`).

6. Si el artículo trata sobre un país que NO es Argentina (Bolivia, Chile, Brasil, etc.),
   no proyectes el eje peronismo-antiperonismo argentino al país extranjero. Mantené el
   eje en torno a 0 salvo que el texto vincule explícitamente el tema con actores
   argentinos.

7. CHEQUEO DE COHERENCIA INTERNA — hacelo ANTES de cerrar el JSON.
   Releé tu propio `neutral_summary`. ¿Describe un evento políticamente cargado
   (intervención electoral externa, alineamiento geopolítico forzado, ajuste con
   consecuencias sociales, lawfare, denuncia de corrupción, etc.) pero tus scores
   quedaron en 0/0?
   Si la respuesta es sí → SUBESTIMASTE. Volvé al texto, mirá el titular y los
   conectores valorativos, y ajustá los scores hacia el polo correspondiente.
   Confidence 0.9 con scores 0/0 sobre un texto políticamente cargado es señal
   inequívoca de error de calibración, no de neutralidad real.
</core_rules>

<axis name="statism_liberalism" range="-5 a +5">
Cómo se posiciona el texto respecto del rol del Estado EN LA ECONOMÍA.
Mirá: gasto público, impuestos, privatizaciones, regulación, sindicatos, déficit,
subsidios, paritarias, tarifas, controles de precios/cambiarios.

ALCANCE DEL EJE — IMPORTANTE:
Este eje es ESTRICTAMENTE económico. NO incluye política exterior, defensa
nacional, soberanía territorial, alineamiento geopolítico, ni FF.AA.
Una nota que defiende un Estado fuerte en defensa nacional o que habla de
"soberanía" frente a una potencia extranjera puede ser perfectamente liberal
en lo económico (la derecha nacionalista típica). NO confundas defensa
nacional con estatismo económico. Si el texto solo toca defensa/geopolítica
y no economía, devolvé 0 con justificación "No aparece el eje económico en el texto".

REGLA CLAVE — APLICAR EN ORDEN, NO SALTEAR PASOS:

PASO 1 — Identificá la POSTURA DEL AUTOR frente a las medidas económicas.
¿El texto critica o defiende las medidas de cada tipo?
  (a) Critica el ajuste / recorte / privatizaciones / desregulación / motosierra
      → el autor defiende un Estado activo en la economía.
  (b) Defiende o celebra el ajuste / recorte / privatizaciones / desregulación
      → el autor defiende reducir el Estado en la economía.
  (c) Critica el gasto público / subsidios / paritarias / "el déficit"
      → el autor está en la posición liberal.
  (d) Defiende el gasto público / subsidios / paritarias / intervención estatal
      → el autor está en la posición estatista.
  (e) Mezcla, equidistante, descriptivo sin valorar, o no toca economía.

PASO 2 — Asigná SIGNO según el PASO 1:
  - (a) o (d): score NEGATIVO (estatista).
  - (b) o (c): score POSITIVO (liberal).
  - (e): score cercano a 0.

PASO 3 — INTENSIDAD por tono: suave (+/-1), claro (+/-3), militante (+/-5).

ERROR FRECUENTE A EVITAR — "trampa de la palabra descontextualizada":
La palabra "ajuste" SOLA no determina el signo — la determina QUIÉN LA DICE
Y EN QUÉ TONO. Una nota que critica al gobierno por ajustar es ESTATISTA,
no liberal. Una nota que celebra el ajuste como "saneamiento" es LIBERAL.
Si te encontrás justificando un score liberal con citas como "ataca el
ajuste", "denuncia el recorte", "defiende a los docentes", "rechaza la
motosierra" — releé el PASO 1, invertiste el signo.

INDEPENDENCIA DE EJES: el signo de este eje NO se deriva del eje peronismo.
Una nota antiperonista (positiva en peronism_antiperonism) puede ser
estatista (negativo acá, ej. peronismo ortodoxo, sindicalismo no-K) o
liberal (positivo acá, lo más común). Una nota peronista puede ser
estatista (lo más común) o liberal (existe, ej. menemismo). Decidí cada
eje con su propio PASO 1; no copiar signos entre ejes.

Anchors:
  -5: defensa explícita de nacionalizaciones, controles cambiarios fuertes, gasto público sin techo
  -3: marcado estatismo, validación del modelo de "Estado presente", crítica al ajuste como "salvaje"
  -1: leve inclinación estatista, simpatía con subsidios o regulación específica
   0: balanceado, equidistante, o no toca economía
  +1: leve inclinación liberal, valoración positiva de orden fiscal sin militancia
  +3: liberalismo claro, defensa del ajuste como "necesario", del recorte y la desregulación
  +5: liberalismo de mercado radical, ridiculización del Estado, anarcocapitalismo

Lenguaje estatista cargado (económico): "ajuste salvaje", "modelo nacional y popular",
"los trabajadores" (como sujeto político), "redistribución", "desguace del Estado",
"motosierra", "neoliberalismo", "ortodoxia del FMI"
Lenguaje liberal cargado (económico): "casta", "déficit cero", "saneamiento fiscal",
"shock", "libertad económica", "ajuste necesario", "republicanismo fiscal"

CONTRA-EJEMPLOS (palabras que NO van solas en este eje):
- "soberanía" → puede ser peronista (anti-FMI) o anti-peronista (anti-China);
  decide el contexto, no la palabra.
- "defensa nacional" / "valores occidentales" / "patria" → marco identitario
  o geopolítico, no económico. Mantené el eje en 0 si solo aparecen estos
  términos sin referencia a rol del Estado en la economía.
- "entreguismo" / "injerencia extranjera" → marco geopolítico, no estatista.
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

REGLA CLAVE (gobierno LLA en 2026) — APLICAR EN ORDEN, NO SALTEAR PASOS:

PASO 1 — Identificá explícitamente al actor político criticado en el texto.
¿A quién apunta la crítica, ridiculización o ataque principal? Opciones:
  (a) El peronismo / kirchnerismo (UxP, CFK, Cámpora, sindicalismo K,
      "la oposición" cuando significa peronismo, gobiernos K previos)
  (b) El oficialismo libertario (Milei, LLA, Caputo, Bullrich, "el gobierno
      actual" cuando se refiere al de Milei)
  (c) Ninguno claro, ambos por igual, o un tercero (Macri, otra fuerza,
      potencia extranjera sin lectura argentina)

PASO 2 — Asigná el SIGNO según el PASO 1:
  - Si (a) → score POSITIVO (antiperonista). El texto trata mal al peronismo.
    Vale cualquier vocabulario que use; la dirección la fija el PASO 1.
  - Si (b) → score NEGATIVO (afinidad peronista). Bajo Milei, la oposición
    sistemática al gobierno suele venir del campo peronista.
  - Si (c) → score cercano a 0.

PASO 3 — La INTENSIDAD del score la fija el tono (suave, claro, militante),
no la mera presencia del actor.

ERROR FRECUENTE A EVITAR — "trampa del vocabulario contestado":
Palabras como "soberanía", "defensa nacional", "valores occidentales",
"entreguismo", "injerencia extranjera" NO determinan el signo por sí solas.
La derecha nacionalista las usa para atacar al peronismo (p. ej. "los kukas
entregaron recursos a China"), y el peronismo las usa para atacar al
liberalismo (p. ej. "Milei entregó la soberanía al FMI"). Es el MISMO
vocabulario apuntando a actores opuestos. SIEMPRE resolvé primero el PASO 1
mirando a quién va dirigida la crítica, y solo después asignás el signo.

Si te encontrás justificando un score peronista con citas como "critica al
gobierno por entreguista" pero el medio es de derecha y el "entreguista" es
el kirchnerismo entregando a China, releé el PASO 1 — invertiste el signo.

Y AL REVÉS — simétrico: si te encontrás justificando un score antiperonista
con citas como "critica al gobierno", "denuncia el ajuste", "cuestiona a
Milei/Caputo/Bullrich" — releé el PASO 1, invertiste el signo. El gobierno
actual (mayo 2026) ES antiperonista. Criticarlo es, por definición, alejarse
del polo antiperonista. Score NEGATIVO (afinidad peronista), aunque el texto
no use vocabulario peronista militante.

HERENCIA MENCIONADA vs ACTOR CRITICADO:
Una nota puede mencionar "lo que dejó el kirchnerismo" o "la pesada herencia"
como ANTECEDENTE sin que ese sea el objeto de la crítica. El actor criticado
es hacia quién va el VERBO DE JUICIO principal del texto:
- "El gobierno no logra revertir la inflación heredada" → critica AL GOBIERNO
  (LLA). Score peronism = NEGATIVO. La mención al kirchnerismo es contexto.
- "El kirchnerismo dejó una inflación que el gobierno ya saneó" → critica AL
  KIRCHNERISMO y elogia al gobierno. Score peronism = POSITIVO.
La diferencia es a quién va el verbo principal, no a quién se nombra.

Lenguaje peronista cargado: "movimiento nacional", "los trabajadores", "la patria",
"compañero/a", "proyecto popular", "neoliberalismo"
Lenguaje antiperonista cargado: "populismo", "demagogia", "clientelismo",
"la herencia", "modelo agotado", "intervencionismo", "concentración de poder",
"corrupción K"
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

ANTI-PATRÓN: una nota con titular en forma de juicio, autor firmado y marco
editorial claro NO es un texto ambiguo. Si entendiste el ángulo (lo ves en
tu propio neutral_summary) pero pusiste scores tibios "por las dudas", eso
NO se reporta como confidence 0.5 — es subestimación, no ambigüedad. Subí
los scores hasta que reflejen lo que ves, y reportá confidence 0.7-0.85
según corresponda.
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
Tipo: crítica MODERADA al gobierno desde tono sobrio (NO militante peronista)
(clave anti-inversión-de-signo en peronism_antiperonism)
Titular: "El plan económico enfrenta el desafío del consumo"
Texto resumido: "El programa de Caputo enfrenta una contradicción difícil: la
inflación cede, pero el consumo sigue cayendo y la actividad industrial acumula
seis meses en rojo. Economistas advierten que el modelo necesita recuperar
dinamismo o se acerca un freno político. La oposición pide medidas de
reactivación que el oficialismo descarta como populistas. Desde el equipo
económico responden que la pesada herencia recibida del kirchnerismo todavía
condiciona los márgenes de maniobra."

PASO 1 (¿a quién critica?): al gobierno de Milei. Cuestiona el sostenimiento
del plan económico oficial ("contradicción difícil", "freno político"). La
mención al kirchnerismo aparece SOLO como antecedente citado por el
oficialismo — NO es el actor criticado por el texto.
PASO 2 (signo): el actor criticado es (b) → score NEGATIVO en peronism_antiperonism.

Output esperado:
- statism_liberalism.score: -1.0, justification: "Marco implícito favorable a
  la reactivación / intervención ('el modelo necesita recuperar dinamismo');
  expone caída de consumo y actividad como problema central"
- peronism_antiperonism.score: -1.5, justification: "Cuestiona el plan económico
  libertario sin valorar positivamente al peronismo. Bajo gobierno LLA, crítica
  moderada al oficialismo = leve afinidad peronista. NO es militancia: el tono
  es sobrio, sin vocabulario peronista clásico ('motosierra', 'trabajadores'),
  pero el actor criticado es claramente el gobierno actual (antiperonista)."
- emotional_load: 0.3
- framing: [
    emphasis: "destaca caída de consumo y actividad industrial como problema central del modelo",
    source_selection: "cita economistas críticos en posición principal; el oficialismo aparece en posición defensiva"
  ]
- overall_label: "Nota moderadamente crítica al programa económico oficial"
- confidence: 0.7

PUNTO CRÍTICO: el texto menciona "kirchnerismo" UNA VEZ, en boca del propio
gobierno como "herencia recibida". Eso NO convierte al kirchnerismo en actor
criticado. El verbo de juicio del texto ("enfrenta una contradicción", "se
acerca un freno") apunta al plan oficial. NO le pongas score positivo
(antiperonista) por (a) aparecer la palabra "kirchnerismo", (b) que el
oficialismo etiquete las críticas como "populistas", o (c) el tono sobrio.
Crítica al gobierno LLA = afinidad peronista por defecto, aunque sea suave.
</example>

<example>
Tipo: nota opositora con MARCO IMPLÍCITO + CIFRAS FACTUALES (clave anti-cautela)
Titular: "Milei cumplió otra orden de Trump: desactivó el swap con China"
Texto resumido: "El Banco Central devolvió 4.300 millones de dólares al Banco del
Pueblo de China. El BCRA perdió esa liquidez para intervenir en el mercado de cambios
en defensa del peso. La administración Trump había establecido esa condición para
apoyar el programa económico del gobierno. El Tesoro de EE.UU. intervino directamente
en el mercado oficial de cambios para mejorar las chances electorales del oficialismo
libertario. Bessent dijo que Milei estaba comprometido con sacar a China de la
Argentina."
Output esperado:
- statism_liberalism.score: -1.5, justification: "Encuadra la pérdida de liquidez del BCRA como pérdida de capacidad estatal de defender el peso ('perdió liquidez para intervenir en defensa del peso') — valoración estatista implícita del rol del BCRA"
- peronism_antiperonism.score: -3.0, justification: "Titular ('cumplió otra orden de Trump') y cuerpo ('intervino para mejorar las chances electorales del oficialismo') encuadran al gobierno LLA como sometido a poder extranjero. Marco de soberanía vs subordinación = repertorio peronista. Opositora a gobierno LLA = afinidad peronista."
- emotional_load: 0.55
- framing: [
    loaded_language: "marco de subordinación en el titular y bajada",
    emphasis: "vinculación implícita entre apoyo financiero externo y resultado electoral, sugiriendo quid pro quo",
    source_selection: "se citan funcionarios estadounidenses en frases hostiles a la soberanía argentina; ausencia de voces del gobierno argentino defendiendo la decisión técnica"
  ]
- overall_label: "Nota opositora con marco peronista de soberanía vs subordinación"
- confidence: 0.85

PUNTO CRÍTICO de este ejemplo: las cifras del cuerpo son enteramente factuales
(4.300 millones, condiciones del Tesoro, frases textuales de Bessent). No hay
adjetivos militantes tipo "salvaje" / "motosierra". Pero el titular en forma de
juicio + los conectores valorativos del cuerpo ("perdió capacidad", "para mejorar
las chances electorales", "cumplió") establecen el marco. NO califiques esto
como "cable informativo equidistante" — sería un error grave de calibración.
</example>

<example>
Tipo: nota anti-peronista desde la derecha con vocabulario contestado
(clave anti-inversión de signo)
Titular: "El peronismo realizó un congreso de defensa y asistieron dos agregados militares chinos"
Texto resumido: "El Partido Justicialista organizó un congreso sobre defensa
nacional al que asistieron dos agregados militares de China sentados en la
primera fila. La oposición peronista exhibió sus verdaderos colores: los del
Partido Comunista Chino. El kirchnerismo ya ni siquiera oculta su plan de
entregar los recursos estratégicos a potencias extranjeras que atentan contra
los valores occidentales. El servilismo del peronismo frente a China es
incompatible con la soberanía argentina."

PASO 1 (¿a quién critica?): al peronismo / kirchnerismo. Lo acusa de servil,
entreguista, alineado con China.
PASO 2 (signo): el actor criticado es (a) → score POSITIVO en peronism_antiperonism.

Output esperado:
- statism_liberalism.score: 0.0, justification: "El texto trata defensa nacional
  y geopolítica, no economía. El eje económico no aparece."
- peronism_antiperonism.score: +3.0, justification: "Ataque directo al peronismo,
  acusándolo de servilismo y entreguismo frente a China. Usa marco
  anti-peronista clásico ('exhibió sus verdaderos colores: los del PC chino')."
- emotional_load: 0.75
- framing: [
    loaded_language: "marco de 'servilismo' y 'entreguismo' contra el peronismo",
    emphasis: "destaca presencia de agregados militares chinos como símbolo de alineamiento forzado"
  ]
- overall_label: "Nota anti-peronista con marco de soberanía vs alineamiento extranjero"
- confidence: 0.85

PUNTO CRÍTICO: aunque el texto use "soberanía" y "valores occidentales"
—vocabulario que también aparece en notas peronistas—, acá está apuntando
CONTRA el peronismo. El signo del eje peronism_antiperonism lo decide el
PASO 1 (a quién critica), no el vocabulario suelto. Y aunque hable de
"defensa nacional" y "soberanía", el eje estatista queda en 0 porque no
toca economía.
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

<verification>
Antes de cerrar el JSON, repasá cada finding de `framing`:

1. QUOTE: Si tiene `quote`, chequeá que esas palabras aparezcan IDÉNTICAS en
   el bloque "Texto del artículo:" del mensaje del usuario. Si no aparecen
   (porque las copiaste de los ejemplos de este prompt o las inventaste),
   eliminá ese finding del array.

2. DESCRIPTION: La `description` también debe ser fiel al texto recibido.
   No reciclás descripciones de los ejemplos de este prompt. Específicamente:
   - Si tu description menciona actores que NO aparecen en el artículo
     (ej: "Bessent", "Tesoro de EE.UU.", "funcionarios estadounidenses",
     "Cavani", "Trump", "Kicillof", etc.) pero el artículo no habla de
     ellos, eliminá ese finding o re-escribí la description con los actores
     reales del texto.
   - Si tu description usa frases largas casi textuales de los ejemplos
     (ej: "se citan funcionarios estadounidenses en frases hostiles a la
     soberanía argentina"), reescribila desde cero con lo que realmente
     dice ESTE artículo.

3. NEUTRAL_SUMMARY: aplicá el mismo criterio que con description — solo
   con actores y eventos que aparezcan en el artículo recibido.

4. Si no podés generar findings verificables del texto, devolvé `framing: []`.
   Es mejor un análisis sin findings que uno con contenido inventado o
   copiado de los ejemplos.
</verification>

Recordá: devolvé SOLO el objeto JSON que cumple el esquema. Sin prefijos, sin
``` ```, sin texto adicional.
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


_SOURCE_PRIOR_TEMPLATE = """\

<source_prior_advisory>
Línea editorial promedio del medio que publica esta nota:
{lines}

USO RESTRINGIDO — leelo entero antes de usarlo:
1. Analizá el texto por sí solo (core_rules #1). Decidí los scores leyendo el
   artículo, no este bloque.
2. SOLO usalo como desempate de PASO 1 cuando el actor criticado quede
   genuinamente ambiguo entre dos polos opuestos por falta de atribución en el
   texto. En ese caso podés inclinar el SIGNO hacia la línea del medio; la
   INTENSIDAD sigue saliendo del tono del texto.
3. NUNCA amplifiques un score que ya determinaste desde el texto usando este
   bloque.
4. NUNCA invertís un signo claro porque acá diga otra cosa. Una nota que va
   contra la línea promedio del medio es información válida, no un error a
   corregir con el prior.
5. Si lo usaste para desempatar, anotalo en la justificación del eje afectado:
   "(prior del medio usado por ambigüedad)".
</source_prior_advisory>"""


def _build_source_prior_block(prior: SourcePrior) -> str:
    bucket_lines = []
    if prior.economic_bucket != "centro":
        bucket_lines.append(f"- Económico: {prior.economic_bucket}")
    if prior.peronism_bucket != "centro":
        bucket_lines.append(f"- Peronismo/antiperonismo: {prior.peronism_bucket}")
    return _SOURCE_PRIOR_TEMPLATE.format(lines="\n".join(bucket_lines))


def _build_user_message(
    article: ScrapedArticle, source_prior: SourcePrior | None = None
) -> str:
    parts = [
        f"Titular: {article.title or '(sin titular)'}",
        f"Medio: {article.site_name or '(desconocido)'}",
        f"Autor: {article.author or '(sin firmar)'}",
        "",
        "Texto del artículo:",
        article.text,
    ]
    message = "\n".join(parts)
    if source_prior is not None and source_prior.is_informative:
        message += _build_source_prior_block(source_prior)
    return message


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


# Defensa contra alucinación de citas:
# Qwen3 8B a veces copia frases de los ejemplos del system prompt
# ("corporación K", "ajuste salvaje") aunque el artículo no las contenga.
# Validamos que cada `quote` exista literalmente en el texto antes de
# guardarla. Normalizamos para tolerar diferencias menores (acentos,
# comillas tipográficas, mayúsculas, espacios).
_QUOTE_CHARS = "“”‘’\"'«»`"


def _normalize_for_match(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    for q in _QUOTE_CHARS:
        stripped = stripped.replace(q, "")
    return " ".join(stripped.lower().split())


def _filter_hallucinated_findings(
    findings: list[FramingFinding], article_text: str
) -> list[FramingFinding]:
    normalized_text = _normalize_for_match(article_text)
    kept: list[FramingFinding] = []
    dropped: list[str] = []
    for f in findings:
        if not f.quote:
            kept.append(f)
            continue
        if _normalize_for_match(f.quote) in normalized_text:
            kept.append(f)
        else:
            dropped.append(f.quote)
    if dropped:
        logger.warning(
            "Descarté %d framing finding(s) con quote alucinada: %s",
            len(dropped),
            " | ".join(dropped[:3]),
        )
    return kept


# ---------------------------------------------------------------------------
# Implementación con Ollama (LLM local).
# ---------------------------------------------------------------------------
def _analyze_with_ollama(
    article: ScrapedArticle, source_prior: SourcePrior | None = None
) -> Analysis:
    prior_active = source_prior is not None and source_prior.is_informative
    user_text = _truncate(_build_user_message(article, source_prior))

    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "format": ANALYSIS_JSON_SCHEMA,
        "stream": False,
        # Qwen3 con thinking ON: el modelo razona antes de responder. Esto cuesta
        # latencia (+10-30s/nota) pero ataca un error sistemático en la tarea —
        # invertir el signo de los ejes cuando el texto usa vocabulario
        # contestado (ej. "soberanía" en una nota anti-peronista). El bloque
        # <think>...</think> que pueda colarse en content lo limpia _strip_thinking.
        "think": True,
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

    raw_findings = [FramingFinding(**f) for f in data.get("framing", [])]
    framing = _filter_hallucinated_findings(raw_findings, article.text)

    return Analysis(
        statism_liberalism=AxisScore(**data["statism_liberalism"]),
        peronism_antiperonism=AxisScore(**data["peronism_antiperonism"]),
        emotional_load=float(data["emotional_load"]),
        framing=framing,
        neutral_summary=data["neutral_summary"],
        overall_label=data["overall_label"],
        confidence=float(data["confidence"]),
        model_version=f"ollama:{settings.ollama_model}",
        is_mock=False,
        source_prior_used=prior_active,
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
        overall_label=(
            f"[MOCK] {statism_label(statism)} · "
            f"{peronism_label(peronism)} · carga emocional {emo}"
        ),
        confidence=conf,
        model_version="mock-v1",
        is_mock=True,
    )


# ---------------------------------------------------------------------------
# Entrada pública.
# ---------------------------------------------------------------------------
def analyze(
    article: ScrapedArticle, source_prior: SourcePrior | None = None
) -> Analysis:
    if settings.use_mock_analyzer:
        return _analyze_mock(article)
    try:
        return _analyze_with_ollama(article, source_prior=source_prior)
    except Exception as exc:
        logger.warning(
            "Falló análisis con Ollama (%s); caigo a mock para no romper el pipeline.",
            exc,
        )
        return _analyze_mock(article)
