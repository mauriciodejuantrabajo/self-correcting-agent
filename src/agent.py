"""
El agente auto-corrector (Reflexion).

Idea: en vez de devolver la primera respuesta del modelo, la sometemos a un ciclo
de autocrítica. El loop es:

    1. GENERAR un borrador para la petición.
    2. CRITICAR ese borrador contra una rúbrica (-> Verdict con issues y score).
    3. Si está aprobado (o agotamos las iteraciones), terminar.
       Si no, REESCRIBIR el borrador resolviendo los issues y volver al paso 2.

El agente emite eventos por un callback `on_event` para que la CLI o el backend web
puedan mostrar el progreso EN VIVO (cada borrador, cada crítica, cada reescritura).

El presupuesto de iteraciones (`max_iters`) acota el costo y evita loops infinitos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

from .critic import Verdict, critique
from .llm import LLMClient, get_client
from .prompts import (
    GENERATOR_SYSTEM,
    REVISER_SYSTEM,
    generator_user,
    reviser_user,
)
from .tools import DEFAULT_TOOLS, Tool

EventKind = Literal[
    "start", "phase", "draft", "tools", "critique", "revise",
    "accepted", "exhausted", "info"
]

# Fases del trabajo del agente, para mostrar EN VIVO qué está haciendo ahora mismo
# (cada una precede a un paso lento: una llamada al modelo o la inspección).
Phase = Literal["generating", "inspecting", "critiquing", "revising"]


@dataclass
class Event:
    """Un evento del loop, pensado para mostrarse en vivo."""

    kind: EventKind
    iteration: int
    message: str = ""
    # Solo presentes según el tipo de evento:
    text: str | None = None          # borrador / respuesta
    verdict: dict | None = None      # veredicto del crítico
    tool_runs: list[dict] | None = None  # resultados de las tools de inspección
    phase: Phase | None = None       # qué está haciendo el agente ahora (eventos "phase")


@dataclass
class Attempt:
    """Un intento completo: el borrador y la crítica que recibió."""

    iteration: int
    draft: str
    verdict: Verdict


@dataclass
class Result:
    """Resultado final del agente."""

    answer: str
    approved: bool
    iterations: int
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def final_verdict(self) -> Verdict | None:
        return self.attempts[-1].verdict if self.attempts else None


class SelfCorrectingAgent:
    """Agente que genera, critica y reescribe su propia salida."""

    def __init__(
        self,
        client: LLMClient | None = None,
        max_iters: int = 3,
        on_event: Callable[[Event], None] | None = None,
        tools: list[Tool] | None = None,
    ) -> None:
        self.client = client or get_client()
        # Al menos una pasada de generación; tope para acotar el costo.
        self.max_iters = max(1, max_iters)
        self.on_event = on_event
        # Tools de inspección que alimentan al crítico (ajustables). Lista vacía =
        # crítico solo-LLM; None = set por defecto.
        self.tools = DEFAULT_TOOLS if tools is None else tools

    def _emit(self, event: Event) -> None:
        if self.on_event:
            self.on_event(event)

    def _phase(self, phase: str, iteration: int, message: str) -> None:
        """Anuncia qué va a hacer el agente AHORA (antes de un paso lento)."""
        self._emit(Event(kind="phase", iteration=iteration, phase=phase, message=message))

    def _generate(self, question: str) -> str:
        return self.client.complete(
            messages=[
                {"role": "system", "content": GENERATOR_SYSTEM},
                {"role": "user", "content": generator_user(question)},
            ],
            temperature=0.4,
        )

    def _revise(self, question: str, draft: str, issues: list[str]) -> str:
        return self.client.complete(
            messages=[
                {"role": "system", "content": REVISER_SYSTEM},
                {"role": "user", "content": reviser_user(question, draft, issues)},
            ],
            temperature=0.4,
        )

    def run(self, question: str) -> Result:
        """Ejecuta el loop completo y devuelve la mejor respuesta obtenida."""
        question = question.strip()
        self._emit(Event(kind="start", iteration=0, message=question))

        attempts: list[Attempt] = []
        # Fase: generando el primer borrador (paso lento).
        self._phase("generating", 1, "Generando el primer borrador…")
        draft = self._generate(question)
        self._emit(Event(kind="draft", iteration=1, text=draft))

        for i in range(1, self.max_iters + 1):
            # Fase: inspección con tools (rápida) — emitimos las tools en cuanto están.
            if self.tools:
                self._phase("inspecting", i, "Inspeccionando el borrador con herramientas…")

            def _on_tools(tool_runs, _i=i):
                self._emit(
                    Event(
                        kind="tools",
                        iteration=_i,
                        message="Inspección automática del borrador.",
                        tool_runs=[t.to_dict() for t in tool_runs],
                    )
                )
                # Fase: ahora el crítico LLM evalúa (paso lento).
                self._phase("critiquing", _i, "El crítico está evaluando el borrador…")

            # Si no hay tools, anunciamos directamente la fase de crítica.
            if not self.tools:
                self._phase("critiquing", i, "El crítico está evaluando el borrador…")

            verdict = critique(self.client, question, draft, self.tools, on_tools=_on_tools)
            # El veredicto del crítico.
            self._emit(
                Event(
                    kind="critique",
                    iteration=i,
                    message=verdict.summary,
                    verdict=verdict.to_dict(),
                )
            )
            attempts.append(Attempt(iteration=i, draft=draft, verdict=verdict))

            if verdict.approved:
                self._emit(
                    Event(
                        kind="accepted",
                        iteration=i,
                        message=f"Aprobado con puntaje {verdict.score}/100.",
                        text=draft,
                    )
                )
                return Result(
                    answer=draft, approved=True, iterations=i, attempts=attempts
                )

            if i == self.max_iters:
                # Se agotó el presupuesto sin aprobación: devolvemos lo mejor que hay.
                best = max(attempts, key=lambda a: a.verdict.score)
                self._emit(
                    Event(
                        kind="exhausted",
                        iteration=i,
                        message=(
                            f"Se alcanzó el máximo de {self.max_iters} iteraciones. "
                            f"Se devuelve el mejor intento ({best.verdict.score}/100)."
                        ),
                        text=best.draft,
                    )
                )
                return Result(
                    answer=best.draft,
                    approved=False,
                    iterations=i,
                    attempts=attempts,
                )

            # Hay problemas y queda presupuesto: reescribir.
            self._emit(
                Event(
                    kind="revise",
                    iteration=i + 1,
                    message=f"Reescribiendo para resolver {len(verdict.issues)} problema(s).",
                )
            )
            # Fase: reescribiendo el borrador (paso lento).
            self._phase("revising", i + 1, "Reescribiendo el borrador con la crítica…")
            draft = self._revise(question, draft, verdict.issues)
            self._emit(Event(kind="draft", iteration=i + 1, text=draft))

        # Inalcanzable (el loop siempre retorna dentro), pero por seguridad de tipos:
        return Result(answer=draft, approved=False, iterations=self.max_iters,
                      attempts=attempts)
