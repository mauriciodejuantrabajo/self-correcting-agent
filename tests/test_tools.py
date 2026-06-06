"""Tests de las tools de inspección objetiva (sin red: son funciones puras)."""

from __future__ import annotations

import pytest

from src.tools import (
    CalcCheckTool,
    ReadabilityTool,
    WordCountTool,
    get_tools,
    run_tools,
    safe_eval,
)


# --- safe_eval (parser aritmético seguro) ---------------------------------- #

def test_safe_eval_operaciones_basicas():
    assert safe_eval("12 + 30 + 8") == 50
    assert safe_eval("(12 + 30) * 25") == 1050
    assert safe_eval("2 ** 10") == 1024


def test_safe_eval_rechaza_codigo():
    # No debe ejecutar nada que no sea aritmética pura.
    for malicioso in ["__import__('os')", "x + 1", "abs(-3)", "1; 2"]:
        with pytest.raises((ValueError, SyntaxError)):
            safe_eval(malicioso)


# --- WordCountTool --------------------------------------------------------- #

def test_word_count_detecta_exceso_de_palabras():
    draft = " ".join(["palabra"] * 200)
    r = WordCountTool().run(draft, "Resume esto en 50 palabras.")
    assert not r.ok
    assert "50 palabras" in r.findings[0]


def test_word_count_respeta_margen():
    # 55 palabras con límite de 50: dentro del margen del 15%, no es problema.
    draft = " ".join(["palabra"] * 55)
    r = WordCountTool().run(draft, "Resume esto en 50 palabras.")
    assert r.ok


def test_word_count_una_sola_oracion():
    draft = "Primera oración. Segunda oración."
    r = WordCountTool().run(draft, "Responde en una sola oración.")
    assert not r.ok
    assert "una sola oración" in r.findings[0]


def test_word_count_sin_restriccion_no_marca_nada():
    r = WordCountTool().run("Un texto cualquiera sin más.", "Explica algo.")
    assert r.ok


# --- ReadabilityTool ------------------------------------------------------- #

def test_readability_detecta_oracion_larga():
    larga = " ".join(["palabra"] * 60) + "."
    r = ReadabilityTool().run(larga, "Explica algo.")
    assert not r.ok
    assert "demasiado larga" in r.findings[0]


def test_readability_ok_con_oraciones_cortas():
    r = ReadabilityTool().run("Frase corta. Otra frase corta.", "Explica algo.")
    assert r.ok


# --- CalcCheckTool --------------------------------------------------------- #

def test_calc_check_detecta_cuenta_incorrecta():
    r = CalcCheckTool().run("La suma es 12 + 30 = 50.", "Suma 12 y 30.")
    assert not r.ok
    assert "incorrecta" in r.findings[0].lower()
    assert "42" in r.findings[0]


def test_calc_check_acepta_cuenta_correcta():
    r = CalcCheckTool().run("El total es 12 + 30 = 42.", "Suma 12 y 30.")
    assert r.ok


def test_calc_check_sin_cuentas():
    r = CalcCheckTool().run("Un texto sin operaciones.", "Explica algo.")
    assert r.ok
    assert "No se encontraron" in r.summary


# --- registro -------------------------------------------------------------- #

def test_get_tools_por_defecto():
    assert len(get_tools()) == 3


def test_get_tools_seleccion():
    tools = get_tools(["calc_check"])
    assert len(tools) == 1
    assert tools[0].name == "calc_check"


def test_run_tools_devuelve_un_resultado_por_tool():
    results = run_tools(get_tools(), "Texto de prueba.", "Pregunta.")
    assert len(results) == 3
    assert all(hasattr(r, "ok") for r in results)
