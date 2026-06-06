"""
Capa de acceso al LLM con dos backends intercambiables: **DeepSeek** y **Ollama**.

El resto del código (agente, crítico) no sabe cuál se usa: solo llama a
`client.complete(messages, temperature, json_mode)`. Se elige por variable de
entorno `LLM_BACKEND` (ver .env.example):

    LLM_BACKEND=ollama   (por defecto)
        OLLAMA_MODEL       modelo (por defecto: minimax-m3:cloud)
        OLLAMA_HOST        host de Ollama (opcional; usa el del paquete por defecto)

    LLM_BACKEND=deepseek
        DEEPSEEK_API_KEY   tu API key (https://platform.deepseek.com)
        DEEPSEEK_MODEL     modelo (por defecto: deepseek-v4-flash)
        DEEPSEEK_BASE_URL  endpoint (por defecto: https://api.deepseek.com)

Ambos exponen la misma interfaz `LLMClient`, así que son intercambiables.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

import requests


class LLMError(RuntimeError):
    """Error al comunicarse con el backend del LLM."""


class LLMClient(Protocol):
    """Interfaz mínima que el agente espera de cualquier backend."""

    def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> str: ...


class DeepSeekClient:
    """Cliente para la API de DeepSeek (compatible OpenAI)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: int = 180,
    ) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.base_url = (
            base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        ).rstrip("/")
        self.timeout = timeout

    def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> str:
        """Envía la conversación y devuelve el texto del asistente.

        Con `json_mode=True` se le pide al modelo que responda únicamente con un
        objeto JSON válido (útil para parsear el veredicto del crítico).
        """
        if not self.api_key:
            raise LLMError(
                "Falta DEEPSEEK_API_KEY. Copia .env.example a .env y coloca tu clave "
                "(https://platform.deepseek.com)."
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise LLMError(
                f"No se pudo conectar a DeepSeek en {self.base_url}. "
                "¿Hay conexión a internet?"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            detail = ""
            try:
                detail = f" — {resp.json()}"
            except Exception:  # noqa: BLE001 — solo enriquecemos el mensaje de error
                pass
            raise LLMError(f"DeepSeek respondió con error: {exc}{detail}") from exc

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Respuesta inesperada de DeepSeek: {data}") from exc


class OllamaClient:
    """Cliente para Ollama (local o cloud). Usa el paquete oficial `ollama`."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
    ) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", "minimax-m3:cloud")
        self.host = host or os.getenv("OLLAMA_HOST") or None

    def complete(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> str:
        try:
            from ollama import Client
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise LLMError(
                "El backend Ollama necesita el paquete `ollama`. "
                "Instálalo con: pip install ollama"
            ) from exc

        # `format="json"` hace que Ollama fuerce salida JSON (equivalente al
        # response_format de DeepSeek), útil para el veredicto del crítico.
        client = Client(host=self.host) if self.host else Client()
        try:
            response = client.chat(
                model=self.model,
                messages=messages,
                options={"temperature": temperature},
                format="json" if json_mode else None,
            )
        except Exception as exc:  # noqa: BLE001 — el cliente lanza errores variados
            raise LLMError(
                f"Ollama respondió con error usando el modelo '{self.model}': {exc}"
            ) from exc

        return _extract_ollama_content(response)


def _extract_ollama_content(response: Any) -> str:
    """Saca el texto del asistente de una respuesta de Ollama.

    Según la versión del paquete, `chat()` puede devolver un objeto `ChatResponse`
    (con `.message.content`) o un dict (`response["message"]["content"]`). Soportamos
    ambos para no romper entre versiones.
    """
    message = None
    if isinstance(response, dict):
        message = response.get("message")
    else:
        message = getattr(response, "message", None)

    content = None
    if isinstance(message, dict):
        content = message.get("content")
    elif message is not None:
        content = getattr(message, "content", None)

    if content is None:
        raise LLMError(f"Respuesta inesperada de Ollama: {response!r}")
    return str(content).strip()


def get_client() -> LLMClient:
    """Devuelve el cliente LLM según `LLM_BACKEND` (ollama | deepseek)."""
    backend = os.getenv("LLM_BACKEND", "ollama").strip().lower()
    if backend == "ollama":
        return OllamaClient()
    if backend == "deepseek":
        return DeepSeekClient()
    raise LLMError(
        f"LLM_BACKEND desconocido: '{backend}'. Usa 'deepseek' u 'ollama'."
    )
