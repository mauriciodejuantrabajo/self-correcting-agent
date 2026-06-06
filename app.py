"""
Interfaz Streamlit del agente auto-corrector (alternativa sin npm al frontend React).

Muestra cada iteración del loop —borrador, crítica con su puntaje, y reescritura—
a medida que ocurren, y al final la respuesta definitiva.

Ejecutar:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.agent import Event, SelfCorrectingAgent
from src.llm import LLMError

load_dotenv()

st.set_page_config(page_title="Agente auto-corrector", page_icon="🔁", layout="centered")
st.title("🔁 Agente auto-corrector")
st.caption(
    "Genera un borrador, lo critica contra una rúbrica y lo reescribe hasta aprobarlo "
    "(técnica *Reflexion*)."
)

with st.sidebar:
    st.header("Ajustes")
    max_iters = st.slider("Máximo de iteraciones", 1, 5, 3)
    st.markdown(
        "Cada iteración = una crítica + (si hace falta) una reescritura. "
        "Más iteraciones = mejor calidad pero más llamadas al modelo."
    )

question = st.text_area(
    "Tu petición",
    placeholder="Ej.: Explica qué es la inyección SQL y cómo prevenirla, con un ejemplo.",
    height=100,
)

if st.button("Generar y auto-corregir", type="primary", disabled=not question.strip()):
    container = st.container()

    def on_event(ev: Event) -> None:
        if ev.kind == "draft":
            label = "Borrador inicial" if ev.iteration == 1 else f"Reescritura (iter. {ev.iteration})"
            with container.expander(f"✍️ {label}", expanded=False):
                st.markdown(ev.text or "")
        elif ev.kind == "critique":
            v = ev.verdict or {}
            ok = v.get("approved")
            icon = "✅" if ok else "🔧"
            with container.expander(
                f"{icon} Crítica (iter. {ev.iteration}) — puntaje {v.get('score', 0)}/100",
                expanded=not ok,
            ):
                if v.get("summary"):
                    st.write(v["summary"])
                for issue in v.get("issues", []):
                    st.markdown(f"- {issue}")
        elif ev.kind == "revise":
            container.info(f"↻ {ev.message}")
        elif ev.kind == "exhausted":
            container.warning(ev.message)

    try:
        agent = SelfCorrectingAgent(max_iters=max_iters, on_event=on_event)
        with st.spinner("Pensando, criticando y reescribiendo…"):
            result = agent.run(question)
    except LLMError as exc:
        st.error(str(exc))
    else:
        st.divider()
        if result.approved:
            st.success(f"Respuesta aprobada en {result.iterations} iteración/es.")
        else:
            st.warning(
                f"Se alcanzó el máximo de iteraciones. Se muestra el mejor intento "
                f"({result.iterations} iteración/es)."
            )
        st.markdown("### Respuesta final")
        st.markdown(result.answer)
