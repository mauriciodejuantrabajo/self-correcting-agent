"""
El crítico: evalúa un borrador contra la rúbrica y devuelve un veredicto estructurado.

Le pedimos al LLM que responda en JSON (json_mode). Como un modelo nunca es 100%
fiable, parseamos de forma defensiva: si el JSON viene envuelto en ```json ... ```
lo limpiamos, y si no se puede parsear devolvemos un veredicto conservador (no
aprobado) en vez de romper el loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from .llm import LLMClient
from .prompts import CRITIC_SYSTEM, critic_user
from .tools import Tool, ToolResult, run_tools


@dataclass
class Verdict:
    """Resultado de la evaluación de un borrador."""

    approved: bool
    score: int
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    # Resultados de las tools de inspección que alimentaron esta evaluación.
    tool_runs: list[ToolResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "approved": self.approved,
            "score": self.score,
            "issues": self.issues,
            "summary": self.summary,
            "tool_runs": [t.to_dict() for t in self.tool_runs],
        }


def _strip_code_fence(text: str) -> str:
    """Quita un envoltorio ```json ... ``` si el modelo lo agregó igual."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def parse_verdict(raw: str, tool_runs: list[ToolResult] | None = None) -> Verdict:
    """Parsea la respuesta del crítico en un Verdict, de forma tolerante a fallos.

    Los `tool_runs` (inspecciones objetivas) se adjuntan al veredicto y, si alguna
    reportó problemas, se garantiza que el veredicto quede NO aprobado: las tools
    son hechos verificados, no opiniones del modelo.
    """
    tool_runs = tool_runs or []
    tool_findings = [f for t in tool_runs for f in t.findings]

    try:
        data = json.loads(_strip_code_fence(raw))
    except (json.JSONDecodeError, TypeError):
        # No pudimos parsear: asumimos que no está aprobado y seguimos iterando.
        return Verdict(
            approved=False,
            score=0,
            issues=["El revisor no devolvió un veredicto legible; se reintenta."]
            + tool_findings,
            summary="Veredicto ilegible.",
            tool_runs=tool_runs,
        )

    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    issues = [str(i) for i in issues]

    # Garantizamos que los hallazgos objetivos de las tools estén en los issues,
    # aunque el LLM los haya omitido.
    for f in tool_findings:
        if f not in issues:
            issues.append(f)

    approved = bool(data.get("approved", False))
    # Coherencia: si quedan problemas (del LLM o de las tools), no puede aprobarse.
    if issues and approved:
        approved = False

    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(100, score))
    # Si las tools encontraron problemas, el puntaje no puede ser de "aprobado".
    if tool_findings:
        score = min(score, 70)

    return Verdict(
        approved=approved,
        score=score,
        issues=issues,
        summary=str(data.get("summary", "")),
        tool_runs=tool_runs,
    )


def critique(
    client: LLMClient,
    question: str,
    draft: str,
    tools: list[Tool] | None = None,
    on_tools: Callable[[list[ToolResult]], None] | None = None,
) -> Verdict:
    """Evalúa `draft` para `question`: corre las tools y luego pide el veredicto al LLM.

    Las tools producen hallazgos objetivos (conteo, cuentas, legibilidad) que se le
    pasan al crítico como evidencia dura, y que también se adjuntan al veredicto
    para mostrarlos en la UI.

    `on_tools` se invoca con los resultados de las tools EN CUANTO terminan (que es
    casi instantáneo), antes de la llamada al LLM (que es lenta), para que la UI
    pueda mostrar la inspección sin esperar al veredicto.
    """
    tool_runs = run_tools(tools, draft, question) if tools else []
    if on_tools and tool_runs:
        on_tools(tool_runs)
    tool_findings = [f for t in tool_runs for f in t.findings]

    raw = client.complete(
        messages=[
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": critic_user(question, draft, tool_findings)},
        ],
        temperature=0.0,  # evaluar debe ser estable, no creativo
        json_mode=True,
    )
    return parse_verdict(raw, tool_runs)
