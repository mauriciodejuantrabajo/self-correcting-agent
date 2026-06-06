"""
CLI del agente auto-corrector (rich): muestra en vivo cómo el agente genera un
borrador, lo critica y lo reescribe hasta aprobarlo, y al final imprime la
respuesta definitiva.

Uso:
    python -m src.main "Explica qué es la inyección SQL y cómo prevenirla."
    python -m src.main                          # modo interactivo
    python -m src.main "tu pregunta" -n 4       # hasta 4 iteraciones
    python -m src.main "tu pregunta" -o out.md  # guarda la respuesta final
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .agent import Event, SelfCorrectingAgent
from .llm import LLMError

# En Windows, la consola por defecto usa cp1252 y rompe al imprimir emojis/acentos.
# Forzamos UTF-8 en stdout/stderr para que la traza con emojis se vea bien.
for _stream in (sys.stdout, sys.stderr):
    reconfig = getattr(_stream, "reconfigure", None)
    if reconfig:
        reconfig(encoding="utf-8")

console = Console()


def _print_event(ev: Event) -> None:
    if ev.kind == "start":
        return
    if ev.kind == "draft":
        title = "✍️  Borrador" if ev.iteration == 1 else f"✍️  Reescritura (iter. {ev.iteration})"
        console.print(Panel(Markdown(ev.text or ""), title=title, border_style="cyan"))
    elif ev.kind == "tools":
        lines = []
        for t in ev.tool_runs or []:
            icon = "✓" if t.get("ok") else "✗"
            color = "green" if t.get("ok") else "red"
            lines.append(f"[{color}]{icon}[/] [bold]{t.get('label')}[/]: {t.get('summary')}")
            for f in t.get("findings", []):
                lines.append(f"    [red]›[/] {f}")
        if lines:
            console.print(
                Panel("\n".join(lines), title=f"🔧 Herramientas (iter. {ev.iteration})",
                      border_style="blue")
            )
    elif ev.kind == "critique":
        v = ev.verdict or {}
        approved = v.get("approved")
        color = "green" if approved else "yellow"
        mark = "✓ aprobado" if approved else "↻ a revisar"
        lines = [f"[{color}]{mark}[/]  puntaje: [bold]{v.get('score', 0)}/100[/]"]
        if v.get("summary"):
            lines.append(f"[dim]{v['summary']}[/]")
        for issue in v.get("issues", []):
            lines.append(f"  • {issue}")
        console.print(
            Panel("\n".join(lines), title=f"🔍 Crítica (iter. {ev.iteration})", border_style=color)
        )
    elif ev.kind == "revise":
        console.print(f"[dim]↻ {ev.message}[/]")
    elif ev.kind == "exhausted":
        console.print(f"[yellow]⚠ {ev.message}[/]")
    elif ev.kind == "info":
        console.print(f"[dim]ℹ {ev.message}[/]")


def answer_once(agent: SelfCorrectingAgent, question: str) -> str:
    console.print(f"\n[bold]?[/]  {question}\n")
    result = agent.run(question)
    console.print()
    badge = (
        "[green]aprobada[/]" if result.approved else "[yellow]mejor intento[/]"
    )
    console.print(
        Panel(
            Markdown(result.answer),
            title=f"Respuesta final ({badge}, {result.iterations} iteración/es)",
            border_style="green" if result.approved else "yellow",
        )
    )
    return result.answer


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Agente auto-corrector (Reflexion). Backend: DeepSeek u Ollama."
    )
    parser.add_argument("question", nargs="?", help="La petición a resolver.")
    parser.add_argument(
        "-n", "--max-iters", type=int, default=3,
        help="Máximo de iteraciones de crítica/reescritura (por defecto: 3).",
    )
    parser.add_argument("-o", "--output", help="Guardar la respuesta final en un .md.")
    args = parser.parse_args(argv)

    try:
        agent = SelfCorrectingAgent(max_iters=args.max_iters, on_event=_print_event)
    except LLMError as exc:
        console.print(f"[red]{exc}[/]")
        return 1

    try:
        if args.question:
            text = answer_once(agent, args.question)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as fh:
                    fh.write(text)
                console.print(f"[dim]Guardado en {args.output}[/]")
            return 0

        console.print(
            "[bold]Agente auto-corrector[/] — escribe tu petición ('salir' para terminar)."
        )
        while True:
            try:
                question = console.input("\n[bold cyan]?[/] ").strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\nHasta luego.")
                return 0
            if question.lower() in {"salir", "exit", "quit"}:
                console.print("Hasta luego.")
                return 0
            if not question:
                continue
            try:
                answer_once(agent, question)
            except LLMError as exc:
                console.print(f"[red]{exc}[/]")
    except LLMError as exc:
        console.print(f"[red]{exc}[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
