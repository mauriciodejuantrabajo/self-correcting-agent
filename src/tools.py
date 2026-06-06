"""
Herramientas (tools) de inspección objetiva para el agente auto-corrector.

A diferencia de un agente con tool-calling clásico (donde el LLM decide invocar
APIs), aquí las tools cumplen un rol específico para la **auto-corrección de texto**:
producen **hallazgos objetivos y verificables** sobre un borrador —cosas que un LLM
juzga mal o "alucina"—, y esos hallazgos se le pasan al crítico como evidencia dura.

Así el veredicto no es solo opinión del modelo: se apoya en mediciones reales
(¿cuántas palabras tiene?, ¿las cuentas dan bien?, ¿hay oraciones ilegibles?).

Cada tool implementa la interfaz `Tool`:
    .name           identificador corto
    .label          nombre legible para la UI
    .run(draft, question) -> ToolResult

El conjunto de tools es **ajustable**: `DEFAULT_TOOLS` es el set por defecto, pero
el agente acepta cualquier lista (ver `SelfCorrectingAgent(tools=...)`).
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolResult:
    """Lo que devuelve una tool tras inspeccionar un borrador."""

    tool: str                       # nombre de la tool
    label: str                      # nombre legible
    findings: list[str] = field(default_factory=list)   # problemas objetivos detectados
    summary: str = ""               # una línea con lo medido (siempre, haya o no findings)

    @property
    def ok(self) -> bool:
        """True si la tool no encontró problemas."""
        return not self.findings

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "label": self.label,
            "findings": self.findings,
            "summary": self.summary,
            "ok": self.ok,
        }


class Tool(Protocol):
    """Interfaz de una herramienta de inspección."""

    name: str
    label: str

    def run(self, draft: str, question: str) -> ToolResult: ...


# --------------------------------------------------------------------------- #
# Utilidades de texto                                                         #
# --------------------------------------------------------------------------- #

_WORD_RE = re.compile(r"\b[\wáéíóúñü']+\b", re.IGNORECASE)
# Divide en oraciones por . ! ? … respetando que no toda abreviatura corta.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
# Números con separadores de miles/decimales, para la verificación aritmética.
_NUMBER_RE = re.compile(r"-?\d[\d.,]*")


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    # Ignoramos el contenido de bloques de código para no contar líneas como oraciones.
    without_code = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    parts = [s.strip() for s in _SENTENCE_SPLIT_RE.split(without_code)]
    return [s for s in parts if s]


# --------------------------------------------------------------------------- #
# Tool 1: conteo de palabras y restricciones de longitud                      #
# --------------------------------------------------------------------------- #

# Detecta restricciones explícitas en la petición, p. ej. "en 100 palabras",
# "máximo 3 oraciones", "en una sola frase".
_MAXWORDS_RE = re.compile(
    r"(?:en|máximo|max|maximo|menos de|hasta|no más de|no mas de)\s+(\d+)\s*palabras",
    re.IGNORECASE,
)
_MAXSENT_RE = re.compile(
    r"(?:en|máximo|max|maximo|menos de|hasta|no más de|no mas de)\s+(\d+)\s*"
    r"(?:oraciones|oración|oracion|frases|frase)",
    re.IGNORECASE,
)
_ONE_SENTENCE_RE = re.compile(
    r"\b(?:una sola|en una|en 1)\s+(?:oración|oracion|frase)\b", re.IGNORECASE
)


class WordCountTool:
    """Cuenta palabras/oraciones y verifica restricciones de longitud de la petición."""

    name = "word_count"
    label = "Conteo de texto"

    def run(self, draft: str, question: str) -> ToolResult:
        words = count_words(draft)
        sentences = split_sentences(draft)
        n_sent = len(sentences)
        findings: list[str] = []

        m = _MAXWORDS_RE.search(question)
        if m:
            limit = int(m.group(1))
            # Margen del 15%: pedir "100 palabras" no exige exactamente 100.
            if words > limit * 1.15:
                findings.append(
                    f"La petición pide ~{limit} palabras y el borrador tiene {words} "
                    f"(se pasa por {words - limit}). Hay que acortarlo."
                )

        ms = _MAXSENT_RE.search(question)
        if ms:
            limit = int(ms.group(1))
            if n_sent > limit:
                findings.append(
                    f"La petición pide máximo {limit} oraciones y el borrador tiene "
                    f"{n_sent}. Hay que condensarlo."
                )

        if _ONE_SENTENCE_RE.search(question) and n_sent > 1:
            findings.append(
                f"La petición pide una sola oración y el borrador tiene {n_sent}."
            )

        return ToolResult(
            tool=self.name,
            label=self.label,
            findings=findings,
            summary=f"{words} palabras, {n_sent} oración(es).",
        )


# --------------------------------------------------------------------------- #
# Tool 2: legibilidad (oraciones excesivamente largas)                        #
# --------------------------------------------------------------------------- #


class ReadabilityTool:
    """Detecta oraciones demasiado largas, que suelen ser densas y difíciles de leer."""

    name = "readability"
    label = "Legibilidad"
    # Umbral por encima del cual una oración se considera demasiado larga.
    MAX_WORDS_PER_SENTENCE = 45

    def run(self, draft: str, question: str) -> ToolResult:
        sentences = split_sentences(draft)
        findings: list[str] = []
        longest = 0
        for s in sentences:
            n = count_words(s)
            longest = max(longest, n)
            if n > self.MAX_WORDS_PER_SENTENCE:
                preview = (s[:60] + "…") if len(s) > 60 else s
                findings.append(
                    f"Oración de {n} palabras (demasiado larga, densa de leer): "
                    f"«{preview}». Conviene partirla."
                )

        return ToolResult(
            tool=self.name,
            label=self.label,
            findings=findings,
            summary=f"Oración más larga: {longest} palabras.",
        )


# --------------------------------------------------------------------------- #
# Tool 3: verificación aritmética segura                                       #
# --------------------------------------------------------------------------- #

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def safe_eval(expr: str) -> float:
    """Evalúa una expresión aritmética con un parser de AST seguro.

    Solo permite números y los operadores + - * / // % ** y paréntesis. NO ejecuta
    código: rechaza variables, llamadas, atributos, imports, etc. Lanza ValueError
    si la expresión no es aritmética pura.
    """

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            raise ValueError("Constante no numérica.")
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
            return _ALLOWED_BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
            return _ALLOWED_UNARY[type(node.op)](_eval(node.operand))
        raise ValueError("Expresión no permitida.")

    tree = ast.parse(expr, mode="eval")
    return _eval(tree)


# Captura igualdades aritméticas escritas en el texto, p. ej. "12 + 30 = 42" o
# "12 * 25 = 300". Toleramos separadores de miles quitándolos antes de evaluar.
_EQUATION_RE = re.compile(
    r"([0-9][0-9\s+\-*/().,%]*?[0-9])\s*=\s*(-?[0-9][\d.,]*)"
)


def _normalize_number(token: str) -> str:
    """Convierte '1.234,56' o '1,234.56' a un float parseable. Heurística simple."""
    token = token.strip()
    # Si tiene ambos separadores, el último es el decimal.
    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        # Coma sola: si parece decimal (1-2 dígitos tras la coma) la tratamos así.
        if re.match(r"^-?\d+,\d{1,2}$", token):
            token = token.replace(",", ".")
        else:
            token = token.replace(",", "")
    return token


class CalcCheckTool:
    """Verifica las igualdades aritméticas que aparezcan en el texto.

    Busca patrones como «12 + 30 = 42» y comprueba que la cuenta esté bien.
    Es una de las cosas donde los LLM más fallan: dan una operación y un total
    que no se corresponden.
    """

    name = "calc_check"
    label = "Verificación aritmética"

    def run(self, draft: str, question: str) -> ToolResult:
        findings: list[str] = []
        checked = 0
        for lhs_raw, rhs_raw in _EQUATION_RE.findall(draft):
            lhs_expr = _normalize_number(lhs_raw) if lhs_raw.replace(" ", "").replace(
                ".", ""
            ).replace(",", "").lstrip("-").isdigit() else lhs_raw
            # Normalizamos solo los números del lado izquierdo, conservando operadores.
            lhs_norm = re.sub(
                r"-?\d[\d.,]*", lambda m: _normalize_number(m.group(0)), lhs_raw
            )
            try:
                left = safe_eval(lhs_norm)
                right = float(_normalize_number(rhs_raw))
            except (ValueError, SyntaxError, ZeroDivisionError):
                continue  # no era una igualdad aritmética evaluable; la ignoramos
            checked += 1
            if abs(left - right) > 1e-6:
                # Mostramos el resultado correcto con formato limpio.
                correct = int(left) if left == int(left) else round(left, 4)
                findings.append(
                    f"Cuenta incorrecta: «{lhs_raw.strip()} = {rhs_raw.strip()}», "
                    f"pero el resultado correcto es {correct}."
                )

        if checked == 0:
            summary = "No se encontraron cuentas para verificar."
        else:
            summary = f"{checked} cuenta(s) verificada(s); {len(findings)} con error."
        return ToolResult(
            tool=self.name, label=self.label, findings=findings, summary=summary
        )


# --------------------------------------------------------------------------- #
# Registro de tools                                                            #
# --------------------------------------------------------------------------- #

# Set por defecto. El agente acepta otra lista para ajustar qué se inspecciona.
DEFAULT_TOOLS: list[Tool] = [
    WordCountTool(),
    ReadabilityTool(),
    CalcCheckTool(),
]

# Mapa nombre -> instancia, para construir sets a la carta desde la API/CLI.
TOOL_REGISTRY: dict[str, Tool] = {t.name: t for t in DEFAULT_TOOLS}


def get_tools(names: list[str] | None = None) -> list[Tool]:
    """Devuelve las tools por nombre; si `names` es None, el set por defecto."""
    if names is None:
        return list(DEFAULT_TOOLS)
    return [TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY]


def run_tools(tools: list[Tool], draft: str, question: str) -> list[ToolResult]:
    """Corre todas las tools sobre un borrador y devuelve sus resultados."""
    return [t.run(draft, question) for t in tools]
