"""Tests del parseo del veredicto del crítico (sin red: parseamos strings)."""

from __future__ import annotations

from src.critic import parse_verdict
from src.tools import ToolResult


def test_parsea_json_limpio():
    raw = '{"approved": true, "score": 90, "issues": [], "summary": "Bien."}'
    v = parse_verdict(raw)
    assert v.approved is True
    assert v.score == 90
    assert v.issues == []
    assert v.summary == "Bien."


def test_quita_code_fence():
    raw = '```json\n{"approved": false, "score": 50, "issues": ["falta X"], "summary": "x"}\n```'
    v = parse_verdict(raw)
    assert v.approved is False
    assert v.issues == ["falta X"]


def test_aprobado_pero_con_issues_se_corrige_a_no_aprobado():
    # Coherencia: si hay problemas, no puede estar aprobado.
    raw = '{"approved": true, "score": 80, "issues": ["queda un error"], "summary": "x"}'
    v = parse_verdict(raw)
    assert v.approved is False


def test_score_se_acota_entre_0_y_100():
    assert parse_verdict('{"approved": false, "score": 250}').score == 100
    assert parse_verdict('{"approved": false, "score": -10}').score == 0


def test_json_invalido_devuelve_veredicto_conservador():
    v = parse_verdict("esto no es json")
    assert v.approved is False
    assert v.score == 0
    assert v.issues  # tiene al menos un mensaje explicativo


# --- integración con tools ------------------------------------------------- #

def _tool_con_problema():
    return ToolResult(
        tool="calc_check",
        label="Verificación aritmética",
        findings=["Cuenta incorrecta: «2 + 2 = 5», pero el resultado correcto es 4."],
        summary="1 cuenta verificada; 1 con error.",
    )


def test_tool_con_problema_fuerza_no_aprobado():
    # El LLM dice "aprobado", pero una tool detectó un error objetivo: manda la tool.
    raw = '{"approved": true, "score": 95, "issues": [], "summary": "Perfecto."}'
    v = parse_verdict(raw, tool_runs=[_tool_con_problema()])
    assert v.approved is False
    assert v.score <= 70
    assert any("Cuenta incorrecta" in i for i in v.issues)
    assert len(v.tool_runs) == 1


def test_findings_de_tool_se_agregan_a_issues_sin_duplicar():
    finding = "Cuenta incorrecta: «2 + 2 = 5», pero el resultado correcto es 4."
    raw = f'{{"approved": false, "score": 50, "issues": ["{finding}"], "summary": "x"}}'
    v = parse_verdict(raw, tool_runs=[_tool_con_problema()])
    # El finding ya estaba en issues del LLM: no debe duplicarse.
    assert v.issues.count(finding) == 1


def test_tools_ok_no_alteran_el_veredicto():
    ok_tool = ToolResult(tool="word_count", label="Conteo", findings=[], summary="10 palabras.")
    raw = '{"approved": true, "score": 90, "issues": [], "summary": "Bien."}'
    v = parse_verdict(raw, tool_runs=[ok_tool])
    assert v.approved is True
    assert v.score == 90
