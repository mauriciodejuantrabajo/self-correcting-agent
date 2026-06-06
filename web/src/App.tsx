import { useRef, useState } from "react"
import { Send, Loader2, Sparkles, Check, AlertTriangle, Wrench } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { IterationCard, type IterationView } from "@/components/IterationCard"
import { Sidebar } from "@/components/Sidebar"
import { StatusBar } from "@/components/StatusBar"
import {
  runAgent,
  type FinalResult,
  type Phase,
  type ProgressEvent,
} from "@/lib/agent"
import { useHistory, type HistoryEntry } from "@/lib/useHistory"

const EXAMPLES = [
  "Explica qué es la inyección SQL y cómo prevenirla, con un ejemplo.",
  "Resume en máximo 40 palabras qué es Docker.",
  "Suma 128, 256 y 64 y muestra la operación con el total.",
  "Compara REST y GraphQL en una tabla de 3 filas.",
]

export default function App() {
  const [question, setQuestion] = useState("")
  const [maxIters, setMaxIters] = useState(3)
  const [running, setRunning] = useState(false)
  const [finalIteration, setFinalIteration] = useState<IterationView | null>(null)
  const [result, setResult] = useState<FinalResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState<string | null>(null)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase | null>(null)
  const [phaseIter, setPhaseIter] = useState(0)
  const closeRef = useRef<(() => void) | null>(null)
  const pendingQuestion = useRef("")

  const history = useHistory()

  function reset() {
    setFinalIteration(null)
    setResult(null)
    setError(null)
    setPhase(null)
    setPhaseIter(0)
  }

  function newQuery() {
    if (running) return
    closeRef.current?.()
    reset()
    setQuestion("")
    setSubmitted(null)
    setActiveId(null)
  }

  // Para esta tarea solo mostramos la iteración FINAL al terminar; durante la
  // ejecución basta con la barra de fases. Así que aquí solo seguimos la fase.
  function handleProgress(ev: ProgressEvent) {
    if (ev.kind === "phase") {
      setPhase(ev.phase)
      if (ev.iteration > 0) setPhaseIter(ev.iteration)
    }
  }

  // Construye la vista de la iteración final a partir del último intento del result.
  function finalIterationFrom(r: FinalResult): IterationView | null {
    const last = r.attempts[r.attempts.length - 1]
    if (!last) return null
    return {
      iteration: last.iteration,
      draft: last.draft,
      toolRuns: last.verdict.tool_runs,
      verdict: last.verdict,
      state: "done",
    }
  }

  function submit(q: string) {
    const text = q.trim()
    if (!text || running) return
    reset()
    setSubmitted(text)
    setActiveId(null)
    setRunning(true)
    pendingQuestion.current = text
    closeRef.current = runAgent(text, maxIters, {
      onProgress: handleProgress,
      onFinal: (r) => {
        setResult(r)
        setFinalIteration(finalIterationFrom(r))
        const id = history.add(pendingQuestion.current, r)
        setActiveId(id)
      },
      onError: (m) => setError(m),
      onDone: () => {
        setRunning(false)
        setPhase(null)
      },
    })
  }

  // Reabre una consulta del historial sin re-ejecutarla.
  function openFromHistory(entry: HistoryEntry) {
    if (running) return
    closeRef.current?.()
    reset()
    setQuestion("")
    setSubmitted(entry.question)
    setActiveId(entry.id)
    // Mostramos solo la iteración final guardada.
    setFinalIteration(finalIterationFrom(entry.result))
    setResult(entry.result)
  }

  function handleRemove(id: string) {
    history.remove(id)
    if (id === activeId) newQuery()
  }

  function handleClear() {
    history.clear()
    newQuery()
  }

  const showWelcome = !submitted && !running

  return (
    <div className="relative flex h-screen overflow-hidden">
      {/* Resplandor de fondo */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-32 left-1/3 size-[42rem] -translate-x-1/2 rounded-full bg-violet-500/30 blur-3xl" />
        <div className="absolute top-10 right-0 size-[32rem] rounded-full bg-cyan-500/25 blur-3xl" />
        <div className="absolute bottom-[-6rem] left-1/4 size-[28rem] rounded-full bg-fuchsia-500/20 blur-3xl" />
      </div>

      <Sidebar
        entries={history.entries}
        activeId={activeId}
        onOpen={openFromHistory}
        onNew={newQuery}
        onRemove={handleRemove}
        onClear={handleClear}
      />

      {/* Área principal */}
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-8">
            {showWelcome ? (
              <div className="flex flex-col items-center pt-12 text-center">
                <div className="mb-4 inline-flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-cyan-500 shadow-lg shadow-violet-500/30 ring-1 ring-white/20">
                  <Sparkles className="size-8 text-white" />
                </div>
                <h1 className="text-gradient text-4xl font-bold tracking-tight">
                  Agente auto-corrector
                </h1>
                <p className="mx-auto mt-3 max-w-xl text-balance text-muted-foreground">
                  Genera un borrador, lo <span className="text-foreground">inspecciona con
                  herramientas</span> (conteo, cuentas, legibilidad), se{" "}
                  <span className="text-foreground">critica</span> y se{" "}
                  <span className="text-foreground">reescribe</span> hasta aprobarlo.
                </p>
                <div className="mt-8 grid w-full gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((ex) => (
                    <button
                      key={ex}
                      onClick={() => {
                        setQuestion(ex)
                        submit(ex)
                      }}
                      className="group rounded-xl border border-violet-400/15 bg-card/60 p-3 text-left text-sm text-muted-foreground shadow-sm transition-all hover:-translate-y-0.5 hover:border-violet-400/40 hover:bg-accent hover:text-foreground hover:shadow-lg hover:shadow-violet-500/10"
                    >
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {/* Pregunta enviada */}
                {submitted && (
                  <div className="mb-6 flex justify-end">
                    <div className="max-w-[80%] animate-in fade-in slide-in-from-right-2 rounded-2xl rounded-br-sm bg-gradient-to-br from-violet-500 to-cyan-500 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-violet-500/25">
                      {submitted}
                    </div>
                  </div>
                )}

                {/* Estado en vivo: qué está haciendo el agente ahora mismo */}
                <StatusBar
                  phase={phase}
                  iteration={phaseIter}
                  maxIters={maxIters}
                  running={running}
                />

                {error && (
                  <Card className="mb-6 border-destructive/50 p-4 text-sm text-destructive">
                    {error}
                  </Card>
                )}

                {/* Iteración final: la inspección y crítica del resultado entregado */}
                {finalIteration && (
                  <div className="mb-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                      <Wrench className="size-4 text-violet-400" />
                      <span className="text-gradient">Inspección y crítica final</span>
                    </div>
                    <IterationCard it={finalIteration} isLatest />
                  </div>
                )}

                {/* Respuesta final */}
                {result && (
                  <div className="animate-in fade-in slide-in-from-bottom-2 duration-500">
                    <Separator className="mb-6" />
                    <div className="mb-3 flex items-center gap-2">
                      {result.approved ? (
                        <Badge variant="secondary" className="gap-1 text-emerald-400">
                          <Check className="size-3" /> Aprobada
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="gap-1 text-amber-400">
                          <AlertTriangle className="size-3" /> Mejor intento
                        </Badge>
                      )}
                      <span className="text-sm text-muted-foreground">
                        en {result.iterations} iteración{result.iterations === 1 ? "" : "es"}
                      </span>
                    </div>
                    <Card className="ring-gradient bg-card/70 p-6 shadow-xl shadow-violet-500/5">
                      <div className="prose prose-sm prose-invert max-w-none prose-headings:font-semibold prose-a:text-cyan-400 prose-strong:text-violet-200">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.answer}</ReactMarkdown>
                      </div>
                    </Card>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Barra de input fija abajo */}
        <div className="border-t border-border bg-background/80 backdrop-blur">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              submit(question)
            }}
            className="mx-auto max-w-3xl px-4 py-4"
          >
            <div className="flex gap-2">
              <Input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Escribe tu petición…"
                disabled={running}
                className="h-12 text-base"
              />
              <Button
                type="submit"
                disabled={running || !question.trim()}
                className="h-12 bg-gradient-to-br from-violet-500 to-cyan-500 px-5 text-white shadow-lg shadow-violet-500/25 transition-all hover:from-violet-400 hover:to-cyan-400 hover:shadow-violet-500/40"
              >
                {running ? <Loader2 className="size-5 animate-spin" /> : <Send className="size-5" />}
              </Button>
            </div>

            <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
              <span>Iteraciones máximas:</span>
              {[2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  disabled={running}
                  onClick={() => setMaxIters(n)}
                  className={
                    "size-7 rounded-md border text-xs font-medium transition-all " +
                    (maxIters === n
                      ? "border-transparent bg-gradient-to-br from-violet-500 to-cyan-500 text-white shadow-sm shadow-violet-500/30"
                      : "border-border hover:border-violet-400/40 hover:bg-accent")
                  }
                >
                  {n}
                </button>
              ))}
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}
