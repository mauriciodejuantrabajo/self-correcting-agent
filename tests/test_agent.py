"""
Tests del loop del agente con un LLM falso (sin red real).

`FakeClient.complete` devuelve respuestas predefinidas en orden. El agente alterna
llamadas generador/crítico, así que la secuencia de respuestas modela un escenario:
generación, luego veredicto (JSON), luego reescritura, luego veredicto, etc.
"""

from __future__ import annotations

import json

from src.agent import SelfCorrectingAgent


class FakeClient:
    """Cliente LLM falso: devuelve respuestas en el orden en que se le pidan."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(self, messages, temperature=0.4, json_mode=False) -> str:
        self.calls.append({"json_mode": json_mode, "messages": messages})
        return self._responses.pop(0)


def _verdict(approved: bool, score: int, issues=None) -> str:
    return json.dumps(
        {
            "approved": approved,
            "score": score,
            "issues": issues or [],
            "summary": "ok" if approved else "revisar",
        }
    )


def test_aprueba_en_primera_iteracion():
    client = FakeClient(
        [
            "Borrador inicial perfecto.",      # generador
            _verdict(True, 95),                 # crítico aprueba
        ]
    )
    agent = SelfCorrectingAgent(client=client, max_iters=3)
    result = agent.run("pregunta")

    assert result.approved is True
    assert result.iterations == 1
    assert result.answer == "Borrador inicial perfecto."
    assert len(result.attempts) == 1


def test_reescribe_y_luego_aprueba():
    client = FakeClient(
        [
            "Borrador 1 con un error.",         # generador
            _verdict(False, 60, ["corregir el error"]),  # crítico rechaza
            "Borrador 2 corregido.",            # reescritura
            _verdict(True, 92),                  # crítico aprueba
        ]
    )
    agent = SelfCorrectingAgent(client=client, max_iters=3)
    result = agent.run("pregunta")

    assert result.approved is True
    assert result.iterations == 2
    assert result.answer == "Borrador 2 corregido."
    assert len(result.attempts) == 2


def test_agota_iteraciones_y_devuelve_el_mejor_intento():
    client = FakeClient(
        [
            "Borrador 1.",
            _verdict(False, 40, ["problema A"]),
            "Borrador 2.",
            _verdict(False, 70, ["problema B"]),  # mejor score
        ]
    )
    agent = SelfCorrectingAgent(client=client, max_iters=2)
    result = agent.run("pregunta")

    assert result.approved is False
    assert result.iterations == 2
    # Devuelve el borrador con mejor puntaje (el 2, score 70).
    assert result.answer == "Borrador 2."


def test_emite_eventos_en_orden():
    client = FakeClient(
        [
            "Borrador 1.",
            _verdict(False, 50, ["arreglar"]),
            "Borrador 2.",
            _verdict(True, 90),
        ]
    )
    eventos = []
    # tools=[] para aislar el flujo del loop de la inspección de herramientas.
    agent = SelfCorrectingAgent(client=client, max_iters=3, on_event=eventos.append, tools=[])
    agent.run("pregunta")

    kinds = [e.kind for e in eventos]
    assert kinds == [
        "start",
        "phase",      # generating
        "draft",      # borrador 1
        "phase",      # critiquing
        "critique",   # rechazo
        "revise",     # se reescribe
        "phase",      # revising
        "draft",      # borrador 2
        "phase",      # critiquing
        "critique",   # aprobación
        "accepted",
    ]


def test_emite_fases_de_trabajo():
    # Cada paso lento debe anunciarse con un evento "phase" antes de ejecutarse.
    client = FakeClient(["Borrador único.", _verdict(True, 90)])
    eventos = []
    agent = SelfCorrectingAgent(client=client, max_iters=1, on_event=eventos.append)
    agent.run("pregunta")

    phases = [e.phase for e in eventos if e.kind == "phase"]
    # Con tools por defecto: generar -> inspeccionar -> criticar.
    assert phases == ["generating", "inspecting", "critiquing"]


def test_emite_evento_tools_antes_de_cada_critica():
    client = FakeClient(["Borrador único.", _verdict(True, 90)])
    eventos = []
    # Con el set de tools por defecto, debe emitirse un evento "tools" por iteración.
    agent = SelfCorrectingAgent(client=client, max_iters=1, on_event=eventos.append)
    agent.run("pregunta")

    kinds = [e.kind for e in eventos]
    assert "tools" in kinds
    # El evento "tools" va antes de "critique".
    assert kinds.index("tools") < kinds.index("critique")
    tools_ev = next(e for e in eventos if e.kind == "tools")
    assert tools_ev.tool_runs and len(tools_ev.tool_runs) == 3


def test_el_critico_usa_json_mode():
    client = FakeClient(["Borrador.", _verdict(True, 100)])
    agent = SelfCorrectingAgent(client=client, max_iters=1)
    agent.run("pregunta")

    # La 1ra llamada es del generador (json_mode False); la 2da, del crítico (True).
    assert client.calls[0]["json_mode"] is False
    assert client.calls[1]["json_mode"] is True


def test_una_sola_iteracion_devuelve_el_borrador_aunque_no_apruebe():
    client = FakeClient(["Único borrador.", _verdict(False, 30, ["algo"])])
    agent = SelfCorrectingAgent(client=client, max_iters=1)
    result = agent.run("pregunta")

    assert result.approved is False
    assert result.iterations == 1
    assert result.answer == "Único borrador."
