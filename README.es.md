> **Idioma / Language:** [English](README.md) · **Español**

# 🔁 Agente auto-corrector (Reflexion)

Un agente que **no se queda con su primera respuesta**. Genera un borrador, luego
un **crítico** lo evalúa contra una rúbrica y devuelve un veredicto estructurado
(puntaje + problemas concretos), y si hace falta el agente **reescribe** el
borrador resolviendo esos problemas. El ciclo se repite hasta **aprobar** o agotar
un presupuesto de iteraciones.

Es la técnica **Reflexion**: usar al propio modelo como su revisor para subir la
calidad sin intervención humana. Funciona con **Ollama** (local o cloud — por
defecto `minimax-m3:cloud`) o con **DeepSeek** (API en la nube) — se elige por una
variable de entorno.

Tiene una **interfaz web moderna** (React + shadcn/ui + Tailwind sobre un backend
FastAPI, que transmite cada iteración **en vivo** por Server-Sent Events) y
también **CLI** y una alternativa **Streamlit** sin npm.

```
?  Explica qué es la inyección SQL y cómo prevenirla.

  ✍️  Borrador (iter. 1)
  La inyección SQL es cuando un atacante mete código SQL en un input…

  🔍 Crítica (iter. 1)   ↻ a revisar   puntaje: 60/100
     • Falta un ejemplo de código concreto.
     • No menciona consultas parametrizadas como defensa principal.

  ↻ Reescribiendo para resolver 2 problema(s).

  ✍️  Reescritura (iter. 2)
  La **inyección SQL** ocurre cuando datos no confiables se concatenan…
  ```sql
  -- Vulnerable:  "SELECT * FROM users WHERE name = '" + nombre + "'"
  -- Seguro (parametrizado):
  cursor.execute("SELECT * FROM users WHERE name = ?", (nombre,))
  ```

  🔍 Crítica (iter. 2)   ✓ aprobado   puntaje: 92/100

  Respuesta final (aprobada, 2 iteraciones)
```

## El problema

La primera respuesta de un LLM suele ser "suficiente", pero no la mejor: omite
partes de la pregunta, le falta un ejemplo, mezcla cosas o se va por las ramas.
Pedirle "esfuérzate más" de entrada no alcanza, porque el modelo no sabe **qué**
está mal con lo que todavía no escribió.

## La solución

Separar **escribir** de **evaluar**, y cerrar el ciclo:

1. **Generar.** El agente produce un primer borrador para la petición.
2. **Criticar.** Un segundo rol —el crítico, con su propio prompt y temperatura 0—
   juzga el borrador contra una **rúbrica** (correctitud, completitud, claridad,
   formato) y devuelve **JSON**: `approved`, `score` y una lista de `issues`
   accionables.
3. **Reescribir.** Si no está aprobado, el agente reescribe el borrador con los
   problemas como contexto, y vuelve al paso 2.
4. **Cortar.** Termina al aprobar, o al llegar al tope de iteraciones; en ese caso
   devuelve el **mejor intento** (el de mayor puntaje), no el último sin más.

El truco es que **criticar es más fácil que generar**: el modelo detecta fallos en
un texto concreto que tiene delante mucho mejor que si intentara escribir perfecto
de una. Cada reescritura ataca problemas específicos, no un "hazlo mejor" difuso.

## Lo que lo hace robusto

- 🎯 **Veredicto estructurado**: el crítico responde en JSON (modo JSON nativo del
  backend). Se parsea de forma **defensiva**: si el JSON viene en un bloque
  ```` ```json ```` se limpia, y si es ilegible se asume "no aprobado" para seguir
  iterando en vez de romper.
- 🧮 **Coherencia forzada**: si el crítico marca problemas pero dice "aprobado",
  se corrige a no aprobado (los problemas mandan).
- 💰 **Presupuesto de iteraciones**: tope configurable (`max_iters`) para acotar el
  costo y evitar loops; el costo es la preocupación #1 en producción.
- 🏆 **Mejor intento**: si se agota el presupuesto, se devuelve el borrador con
  mayor puntaje, no necesariamente el último.
- 🔌 **Dos backends**: DeepSeek u Ollama, intercambiables sin tocar el agente.

## Arquitectura

```
server.py             Backend HTTP (FastAPI): expone el agente y transmite cada
                      iteración EN VIVO por SSE (/api/stream).
app.py                Interfaz web alternativa (Streamlit), sin npm.
web/                  Frontend React + Vite + shadcn/ui + Tailwind.
├── src/App.tsx        UI principal: input, línea de tiempo de iteraciones, respuesta.
├── src/components/    IterationCard (borrador + crítica + anillo de puntaje) y shadcn/ui.
└── src/lib/agent.ts   Cliente SSE y tipos del stream.
src/
├── llm.py            Backends del LLM: DeepSeek (HTTP) y Ollama, intercambiables.
├── prompts.py        Los prompts de los tres roles (generador, crítico, reescritor).
├── critic.py         Evalúa un borrador → Verdict (JSON parseado de forma robusta).
├── agent.py          El loop Reflexion: generar → criticar → reescribir, con eventos.
└── main.py           CLI (rich) con la traza viva de cada iteración.
tests/                Tests con un LLM falso (sin red real ni llamadas a la API).
```

El frontend (React) habla con el backend (FastAPI), que envuelve el agente
(Python). El progreso viaja del agente al navegador en tiempo real por
**Server-Sent Events**:

```
  navegador (React/shadcn) ──HTTP──► FastAPI (server.py) ──► SelfCorrectingAgent (src/)
        ▲                                                          │
        └────────── SSE: borrador, crítica, reescritura ◄──────────┘
```

El **loop** que coordina `agent.py`:

```
            petición
               │
               ▼
        ✍️  Generar borrador
               │
               ▼
        🔍 Criticar ──► Verdict { approved, score, issues }
               │
        ¿aprobado? ── sí ──► ✅ respuesta final
               │ no
               ▼
        ¿queda presupuesto? ── no ──► 🏆 mejor intento
               │ sí
               ▼
        ✍️  Reescribir (con los issues) ──┐
               ▲                          │
               └──────────────────────────┘
```

## Requisitos

- **Python 3.10+**
- **Node 18+** y **npm** (para la interfaz web React; la versión Streamlit no lo necesita)
- Un backend de LLM, **uno** de estos dos:
  - **Ollama** (recomendado) → https://ollama.com. Para `minimax-m3:cloud` y otros
    modelos `*:cloud`, ejecuta `ollama signin`; para modelos locales, `ollama serve`.
  - **DeepSeek** → API key en https://platform.deepseek.com

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/mauriciodejuantrabajo/self-correcting-agent.git
cd self-correcting-agent

# 2. (Opcional) entorno virtual
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar el backend (ver siguiente sección)
```

## Configuración

```bash
cp .env.example .env       # en Windows: copy .env.example .env
```

Edita `.env` y elige el backend con `LLM_BACKEND`.

**Opción A — Ollama (recomendada, por defecto):**

```env
LLM_BACKEND=ollama
OLLAMA_MODEL=minimax-m3:cloud
# OLLAMA_HOST=http://localhost:11434   # opcional
```

Para los modelos cloud (`minimax-m3:cloud` y otros `*:cloud`) necesitas una cuenta
de Ollama: ejecuta `ollama signin` una vez. Para un modelo local, primero
`ollama pull llama3.1` (o el que prefieras) y pon `OLLAMA_MODEL=llama3.1`.

**Opción B — DeepSeek (API en la nube):**

```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=sk-tu-key-real-aca
DEEPSEEK_MODEL=deepseek-v4-flash
```

> 🔒 **`.env` está en `.gitignore` y nunca se sube.** El archivo versionado es
> `.env.example`, que solo trae placeholders.

## Uso

### Interfaz web (React + shadcn — recomendada)

Necesitas **dos procesos**: el backend (FastAPI) y el frontend (Vite).

```bash
# Terminal 1 — backend (en la raíz del repo)
uvicorn server:app --reload --port 8000

# Terminal 2 — frontend
cd web
npm install        # solo la primera vez
npm run dev
```

Abre `http://localhost:5173`. Vite redirige `/api` al backend (puerto 8000). Escribe
tu petición y verás, en vivo, la **línea de tiempo** de iteraciones: cada borrador,
su **crítica** con el puntaje (anillo de color) y los problemas, hasta la respuesta
final aprobada. Puedes ajustar el **máximo de iteraciones** (2–5).

### Interfaz web alternativa (Streamlit, sin npm)

```bash
streamlit run app.py
```

### CLI

```bash
python -m src.main "Explica qué es la inyección SQL y cómo prevenirla."
python -m src.main                                  # modo interactivo
python -m src.main "tu petición" -n 4               # hasta 4 iteraciones
python -m src.main "tu petición" -o respuesta.md    # guarda la respuesta final
```

## Tests

```bash
pytest
```

Los tests reemplazan el LLM por uno falso que devuelve borradores y veredictos
predefinidos, modelando distintos escenarios. Cubren: el **parseo robusto** del
veredicto del crítico (JSON limpio, con *code fence*, inválido, coherencia
puntaje/aprobado), el **loop completo** (aprueba a la primera, reescribe y aprueba,
agota iteraciones y devuelve el mejor intento), el **orden de los eventos** que
alimentan la UI, y el **selector de backend** (DeepSeek/Ollama). **No se hace
ninguna llamada de red real**, así el CI es reproducible y no consume cuota.

## Licencia

[MIT](LICENSE) © Mauricio De Juan
