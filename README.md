> **Idioma / Language:** **English** · [Español](README.es.md)

# 🔁 Self-Correcting Agent (Reflexion)

An agent that **doesn't settle for its first answer**. It generates a draft, then
a **critic** evaluates it against a rubric and returns a structured verdict (score
+ concrete issues), and if needed the agent **rewrites** the draft fixing those
issues. The cycle repeats until it's **approved** or a budget of iterations runs
out.

It's the **Reflexion** technique: using the model itself as its reviewer to raise
quality without human intervention. It works with **Ollama** (local or cloud — by
default `minimax-m3:cloud`) or with **DeepSeek** (cloud API) — chosen by an
environment variable.

It has a **modern web interface** (React + shadcn/ui + Tailwind over a FastAPI
backend, which streams each iteration **live** via Server-Sent Events) and also a
**CLI** and a **Streamlit** alternative without npm.

```
?  Explain what SQL injection is and how to prevent it.

  ✍️  Draft (iter. 1)
  SQL injection is when an attacker inserts SQL code into an input…

  🔍 Critique (iter. 1)   ↻ needs review   score: 60/100
     • Missing a concrete code example.
     • Doesn't mention parameterized queries as the main defense.

  ↻ Rewriting to fix 2 issue(s).

  ✍️  Rewrite (iter. 2)
  **SQL injection** happens when untrusted data is concatenated…
  ```sql
  -- Vulnerable:  "SELECT * FROM users WHERE name = '" + name + "'"
  -- Safe (parameterized):
  cursor.execute("SELECT * FROM users WHERE name = ?", (name,))
  ```

  🔍 Critique (iter. 2)   ✓ approved   score: 92/100

  Final answer (approved, 2 iterations)
```

## The problem

An LLM's first answer is usually "good enough", but not the best: it omits parts
of the question, lacks an example, mixes things up or rambles. Telling it "try
harder" up front isn't enough, because the model doesn't know **what's** wrong
with what it hasn't written yet.

## The solution

Separate **writing** from **evaluating**, and close the loop:

1. **Generate.** The agent produces a first draft for the request.
2. **Critique.** A second role —the critic, with its own prompt and temperature 0—
   judges the draft against a **rubric** (correctness, completeness, clarity,
   format) and returns **JSON**: `approved`, `score` and a list of actionable
   `issues`.
3. **Rewrite.** If not approved, the agent rewrites the draft with the issues as
   context, and goes back to step 2.
4. **Stop.** It ends on approval, or when reaching the iteration cap; in that case
   it returns the **best attempt** (the highest-scoring one), not just the last.

The trick is that **criticizing is easier than generating**: the model detects
flaws in a concrete text in front of it far better than if it tried to write
perfectly in one shot. Each rewrite attacks specific issues, not a vague "make it
better".

## What makes it robust

- 🎯 **Structured verdict**: the critic answers in JSON (the backend's native JSON
  mode). It's parsed **defensively**: if the JSON comes in a ```` ```json ````
  block it's cleaned, and if it's unreadable it's assumed "not approved" to keep
  iterating instead of breaking.
- 🧮 **Forced consistency**: if the critic flags issues but says "approved", it's
  corrected to not approved (the issues win).
- 💰 **Iteration budget**: a configurable cap (`max_iters`) to bound cost and avoid
  loops; cost is the #1 concern in production.
- 🏆 **Best attempt**: if the budget runs out, the highest-scoring draft is
  returned, not necessarily the last.
- 🔌 **Two backends**: DeepSeek or Ollama, interchangeable without touching the
  agent.

## Architecture

```
server.py             HTTP backend (FastAPI): exposes the agent and streams each
                      iteration LIVE via SSE (/api/stream).
app.py                Alternative web interface (Streamlit), no npm.
web/                  React + Vite + shadcn/ui + Tailwind frontend.
├── src/App.tsx        Main UI: input, iteration timeline, answer.
├── src/components/    IterationCard (draft + critique + score ring) and shadcn/ui.
└── src/lib/agent.ts   SSE client and stream types.
src/
├── llm.py            LLM backends: DeepSeek (HTTP) and Ollama, interchangeable.
├── prompts.py        The prompts of the three roles (generator, critic, rewriter).
├── critic.py         Evaluates a draft → Verdict (robustly parsed JSON).
├── agent.py          The Reflexion loop: generate → critique → rewrite, with events.
└── main.py           CLI (rich) with a live trace of each iteration.
tests/                Tests with a fake LLM (no real network, no API calls).
```

The frontend (React) talks to the backend (FastAPI), which wraps the agent
(Python). The progress travels from the agent to the browser in real time via
**Server-Sent Events**:

```
  browser (React/shadcn) ──HTTP──► FastAPI (server.py) ──► SelfCorrectingAgent (src/)
        ▲                                                          │
        └────────── SSE: draft, critique, rewrite ◄───────────────┘
```

The **loop** coordinated by `agent.py`:

```
            request
               │
               ▼
        ✍️  Generate draft
               │
               ▼
        🔍 Critique ──► Verdict { approved, score, issues }
               │
        approved? ── yes ──► ✅ final answer
               │ no
               ▼
        budget left? ── no ──► 🏆 best attempt
               │ yes
               ▼
        ✍️  Rewrite (with the issues) ──┐
               ▲                        │
               └────────────────────────┘
```

## Requirements

- **Python 3.10+**
- **Node 18+** and **npm** (for the React web interface; the Streamlit version doesn't need it)
- An LLM backend, **one** of these two:
  - **Ollama** (recommended) → https://ollama.com. For `minimax-m3:cloud` and other
    `*:cloud` models, run `ollama signin`; for local models, `ollama serve`.
  - **DeepSeek** → API key at https://platform.deepseek.com

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/mauriciodejuantrabajo/self-correcting-agent.git
cd self-correcting-agent

# 2. (Optional) virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure the backend (see next section)
```

## Configuration

```bash
cp .env.example .env       # on Windows: copy .env.example .env
```

Edit `.env` and choose the backend with `LLM_BACKEND`.

**Option A — Ollama (recommended, default):**

```env
LLM_BACKEND=ollama
OLLAMA_MODEL=minimax-m3:cloud
# OLLAMA_HOST=http://localhost:11434   # optional
```

For cloud models (`minimax-m3:cloud` and other `*:cloud`) you need an Ollama
account: run `ollama signin` once. For a local model, first
`ollama pull llama3.1` (or whichever you prefer) and set `OLLAMA_MODEL=llama3.1`.

**Option B — DeepSeek (cloud API):**

```env
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=sk-your-real-key-here
DEEPSEEK_MODEL=deepseek-v4-flash
```

> 🔒 **`.env` is in `.gitignore` and is never committed.** The versioned file is
> `.env.example`, which only carries placeholders.

## Usage

### Web interface (React + shadcn — recommended)

You need **two processes**: the backend (FastAPI) and the frontend (Vite).

```bash
# Terminal 1 — backend (at the repo root)
uvicorn server:app --reload --port 8000

# Terminal 2 — frontend
cd web
npm install        # first time only
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the backend (port 8000). Type
your request and you'll see, live, the **timeline** of iterations: each draft, its
**critique** with the score (color ring) and the issues, down to the final
approved answer. You can adjust the **maximum iterations** (2–5).

### Alternative web interface (Streamlit, no npm)

```bash
streamlit run app.py
```

### CLI

```bash
python -m src.main "Explain what SQL injection is and how to prevent it."
python -m src.main                                  # interactive mode
python -m src.main "your request" -n 4              # up to 4 iterations
python -m src.main "your request" -o answer.md      # saves the final answer
```

## Tests

```bash
pytest
```

The tests replace the LLM with a fake one that returns predefined drafts and
verdicts, modeling different scenarios. They cover: the **robust parsing** of the
critic's verdict (clean JSON, with a *code fence*, invalid, score/approved
consistency), the **full loop** (approves on the first try, rewrites and approves,
exhausts iterations and returns the best attempt), the **order of the events**
that feed the UI, and the **backend selector** (DeepSeek/Ollama). **No real
network call is made**, so the CI is reproducible and doesn't consume quota.

## License

[MIT](LICENSE) © Mauricio De Juan
