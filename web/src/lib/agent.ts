// Tipos y cliente del stream SSE del agente auto-corrector.
// El backend (FastAPI) emite tres tipos de eventos en /api/stream:
//   - "progress": un Event del loop (draft, critique, revise, accepted, exhausted)
//   - "final":    la respuesta definitiva + todos los intentos
//   - "error":    un mensaje de error

export type ToolRun = {
  tool: string
  label: string
  findings: string[]
  summary: string
  ok: boolean
}

export type Verdict = {
  approved: boolean
  score: number
  issues: string[]
  summary: string
  tool_runs: ToolRun[]
}

export type Phase = "generating" | "inspecting" | "critiquing" | "revising"

export type ProgressEvent = {
  kind:
    | "start"
    | "phase"
    | "draft"
    | "tools"
    | "critique"
    | "revise"
    | "accepted"
    | "exhausted"
    | "info"
  iteration: number
  message: string
  text: string | null
  verdict: Verdict | null
  tool_runs: ToolRun[] | null
  phase: Phase | null
}

export type Attempt = {
  iteration: number
  draft: string
  verdict: Verdict
}

export type FinalResult = {
  answer: string
  approved: boolean
  iterations: number
  attempts: Attempt[]
}

export type StreamHandlers = {
  onProgress: (ev: ProgressEvent) => void
  onFinal: (result: FinalResult) => void
  onError: (message: string) => void
  onDone: () => void
}

// Abre el stream SSE y delega cada evento a los handlers.
// Devuelve una función para cerrar la conexión.
export function runAgent(
  question: string,
  maxIters: number,
  handlers: StreamHandlers,
): () => void {
  const url = `/api/stream?q=${encodeURIComponent(question)}&n=${maxIters}`
  const source = new EventSource(url)

  source.addEventListener("progress", (e) => {
    handlers.onProgress(JSON.parse((e as MessageEvent).data))
  })
  source.addEventListener("final", (e) => {
    handlers.onFinal(JSON.parse((e as MessageEvent).data))
    source.close()
    handlers.onDone()
  })
  source.addEventListener("error", (e) => {
    // Puede ser un error de la app (con data) o un corte de conexión (sin data).
    const data = (e as MessageEvent).data
    if (data) {
      try {
        handlers.onError(JSON.parse(data).message ?? "Error desconocido.")
      } catch {
        handlers.onError("Error en el stream.")
      }
    } else {
      handlers.onError("Se perdió la conexión con el servidor.")
    }
    source.close()
    handlers.onDone()
  })

  return () => source.close()
}
