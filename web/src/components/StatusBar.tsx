import { PenLine, Wrench, Search, RefreshCw, Loader2, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { Phase } from "@/lib/agent"

// Metadatos de cada fase del trabajo del agente, para mostrar qué está haciendo.
const PHASES: { key: Phase; label: string; icon: LucideIcon }[] = [
  { key: "generating", label: "Generar", icon: PenLine },
  { key: "inspecting", label: "Inspeccionar", icon: Wrench },
  { key: "critiquing", label: "Criticar", icon: Search },
  { key: "revising", label: "Reescribir", icon: RefreshCw },
]

const PHASE_TEXT: Record<Phase, string> = {
  generating: "Generando el borrador…",
  inspecting: "Inspeccionando con herramientas…",
  critiquing: "El crítico está evaluando…",
  revising: "Reescribiendo con la crítica…",
}

// Barra de estado: muestra EN VIVO qué fase está ejecutando el agente y en qué
// iteración va, con un stepper de las 4 fases.
export function StatusBar({
  phase,
  iteration,
  maxIters,
  running,
}: {
  phase: Phase | null
  iteration: number
  maxIters: number
  running: boolean
}) {
  if (!running) return null
  const activeIdx = phase ? PHASES.findIndex((p) => p.key === phase) : -1

  return (
    <div className="sticky top-0 z-10 mb-5 animate-in fade-in slide-in-from-top-2">
      <div className="ring-gradient overflow-hidden rounded-2xl bg-card/70 p-4 shadow-lg shadow-violet-500/10 backdrop-blur-xl">
        {/* Texto de la fase actual */}
        <div className="mb-3 flex items-center gap-2.5">
          <span className="relative flex size-2.5">
            <span className="absolute inline-flex size-full animate-ping rounded-full bg-violet-400 opacity-75" />
            <span className="relative inline-flex size-2.5 rounded-full bg-violet-500" />
          </span>
          <span className="text-sm font-medium text-foreground">
            {phase ? PHASE_TEXT[phase] : "Trabajando…"}
          </span>
          {iteration > 0 && (
            <span className="ml-auto rounded-full bg-violet-500/15 px-2.5 py-0.5 text-xs font-semibold text-violet-200">
              Iteración {iteration} / {maxIters}
            </span>
          )}
        </div>

        {/* Stepper de las 4 fases */}
        <div className="flex items-center gap-1.5">
          {PHASES.map((p, i) => {
            const Icon = p.icon
            const isActive = i === activeIdx
            const isDone = activeIdx >= 0 && i < activeIdx
            return (
              <div key={p.key} className="flex flex-1 items-center gap-1.5">
                <div
                  className={cn(
                    "flex flex-1 items-center gap-1.5 rounded-lg border px-2 py-1.5 transition-all",
                    isActive &&
                      "border-violet-400/50 bg-gradient-to-br from-violet-500/20 to-cyan-500/10 text-foreground",
                    isDone && "border-emerald-500/30 bg-emerald-500/5 text-emerald-300",
                    !isActive && !isDone && "border-border/60 text-muted-foreground",
                  )}
                >
                  {isActive ? (
                    <Loader2 className="size-3.5 shrink-0 animate-spin text-violet-300" />
                  ) : (
                    <Icon className="size-3.5 shrink-0" />
                  )}
                  <span className="truncate text-[11px] font-medium">{p.label}</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
