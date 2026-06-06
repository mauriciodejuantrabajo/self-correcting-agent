"""
Backend HTTP del agente auto-corrector (FastAPI).

Expone el loop Reflexion a un frontend web (React + shadcn/Tailwind):

    GET  /api/health           → ping simple.
    POST /api/run              → ejecuta y devuelve el resultado final (sin streaming).
    GET  /api/stream?q=...&n=3  → ejecuta y transmite el progreso EN VIVO por SSE:
                                  cada borrador, cada crítica, cada reescritura, y al
                                  final la respuesta aprobada (o el mejor intento).

El agente (src/) no cambia: emite eventos por un callback `on_event` que aquí
empujamos a una cola y un generador los reenvía al navegador como eventos SSE.

Ejecutar:
    uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import json
import queue
import threading
from dataclasses import asdict
from typing import Iterator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agent import Event, SelfCorrectingAgent
from src.llm import LLMError

load_dotenv()

app = FastAPI(title="Self-Correcting Agent API")

# El frontend de Vite corre en otro puerto (5173) durante el desarrollo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    question: str
    max_iters: int = 3


def _sse(event: str, data: dict) -> str:
    """Formatea un mensaje en el protocolo SSE."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _result_payload(result) -> dict:
    return {
        "answer": result.answer,
        "approved": result.approved,
        "iterations": result.iterations,
        "attempts": [
            {
                "iteration": a.iteration,
                "draft": a.draft,
                "verdict": a.verdict.to_dict(),
            }
            for a in result.attempts
        ],
    }


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/run")
def run(req: RunRequest) -> dict:
    """Ejecuta sin streaming: devuelve el resultado final en un solo JSON."""
    try:
        agent = SelfCorrectingAgent(max_iters=req.max_iters)
        result = agent.run(req.question)
    except LLMError as exc:
        return {"error": str(exc)}
    return _result_payload(result)


@app.get("/api/stream")
def stream(q: str, n: int = 3) -> StreamingResponse:
    """Ejecuta y transmite el progreso en vivo como SSE."""

    def generate() -> Iterator[str]:
        events: queue.Queue = queue.Queue()
        SENTINEL = object()

        def on_event(ev: Event) -> None:
            events.put(asdict(ev))

        def worker() -> None:
            try:
                agent = SelfCorrectingAgent(max_iters=n, on_event=on_event)
                result = agent.run(q)
                payload = _result_payload(result)
                payload["_final"] = True
                events.put(payload)
            except LLMError as exc:
                events.put({"_error": True, "message": str(exc)})
            except Exception as exc:  # noqa: BLE001 — reportamos cualquier fallo al cliente
                events.put({"_error": True, "message": f"Error inesperado: {exc}"})
            finally:
                events.put(SENTINEL)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            item = events.get()
            if item is SENTINEL:
                break
            if isinstance(item, dict) and item.get("_final"):
                yield _sse("final", item)
            elif isinstance(item, dict) and item.get("_error"):
                yield _sse("error", item)
            else:
                yield _sse("progress", item)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
