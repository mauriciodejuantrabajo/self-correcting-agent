"""Tests del selector de backend del LLM (sin red: solo elegimos la clase)."""

from __future__ import annotations

import pytest

from src.llm import (
    DeepSeekClient,
    LLMError,
    OllamaClient,
    _extract_ollama_content,
    get_client,
)


class _Msg:
    def __init__(self, content):
        self.content = content


class _Resp:
    def __init__(self, content):
        self.message = _Msg(content)


def test_extract_ollama_desde_objeto():
    assert _extract_ollama_content(_Resp("hola")) == "hola"


def test_extract_ollama_desde_dict():
    # Algunas versiones del paquete devuelven un dict en vez del objeto.
    resp = {"message": {"content": "  hola  "}}
    assert _extract_ollama_content(resp) == "hola"


def test_extract_ollama_respuesta_invalida_lanza_error():
    with pytest.raises(LLMError):
        _extract_ollama_content({"sin": "mensaje"})


def test_backend_por_defecto_es_ollama(monkeypatch):
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    assert isinstance(get_client(), OllamaClient)


def test_backend_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "deepseek")
    client = get_client()
    assert isinstance(client, DeepSeekClient)


def test_backend_ollama_modelo_por_defecto(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "ollama")
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    assert get_client().model == "minimax-m3:cloud"


def test_backend_es_case_insensitive(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "Ollama")
    assert isinstance(get_client(), OllamaClient)


def test_backend_desconocido_lanza_error(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "gpt-casero")
    with pytest.raises(LLMError):
        get_client()
