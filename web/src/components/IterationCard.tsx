import { useState } from "react"
import { ChevronDown, ChevronRight, Check, AlertTriangle, Loader2 } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { ToolPanel } from "@/components/ToolPanel"
import type { ToolRun, Verdict } from "@/lib/agent"

// Una iteración del loop: el borrador, la inspección de tools y (si ya llegó) su crítica.
export type IterationView = {
  iteration: number
  draft?: string
  toolRuns?: ToolRun[]
  verdict?: Verdict
  // "drafting" = generando texto; "critiquing" = esperando veredicto.
  state: "drafting" | "critiquing" | "done"
}

function scoreColor(score: number): string {
  if (score >= 85) return "text-emerald-400"
  if (score >= 60) return "text-amber-400"
  return "text-rose-400"
}

function ScoreRing({ score }: { score: number }) {
  return (
    <div className="relative size-11 shrink-0">
      <svg viewBox="0 0 36 36" className="size-11 -rotate-90">
        <circle cx="18" cy="18" r="16" fill="none" strokeWidth="3" className="stroke-muted" />
        <circle
          cx="18"
          cy="18"
          r="16"
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 100.5} 100.5`}
          className={cn("transition-all", scoreColor(score))}
          stroke="currentColor"
        />
      </svg>
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center text-[11px] font-bold",
          scoreColor(score),
        )}
      >
        {score}
      </span>
    </div>
  )
}

export function IterationCard({ it, isLatest }: { it: IterationView; isLatest: boolean }) {
  const approved = it.verdict?.approved
  // El borrador final aprobado o vigente arranca expandido; los anteriores, colapsados.
  const [open, setOpen] = useState(isLatest)

  return (
    <Card
      className={cn(
        "gap-0 overflow-hidden bg-card/60 p-0 ring-1 backdrop-blur transition-all",
        approved === true && "ring-emerald-500/40 shadow-lg shadow-emerald-500/5",
        approved === false && "ring-amber-500/30",
        approved === undefined && "ring-violet-400/20",
      )}
    >
      {/* Cabecera: número de iteración + veredicto */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-accent/40"
      >
        {open ? (
          <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        )}

        <span className="inline-flex size-6 items-center justify-center rounded-md bg-gradient-to-br from-violet-500/30 to-cyan-500/20 text-xs font-bold text-violet-200 ring-1 ring-violet-400/20">
          {it.iteration}
        </span>
        <span className="text-sm font-semibold">Iteración</span>

        <div className="ml-auto flex items-center gap-3">
          {it.state === "drafting" && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> redactando…
            </span>
          )}
          {it.state === "critiquing" && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" /> evaluando…
            </span>
          )}
          {it.verdict && (
            <>
              <Badge
                variant="secondary"
                className={cn(
                  "gap-1",
                  approved ? "text-emerald-400" : "text-amber-400",
                )}
              >
                {approved ? <Check className="size-3" /> : <AlertTriangle className="size-3" />}
                {approved ? "Aprobado" : `${it.verdict.issues.length} problema(s)`}
              </Badge>
              <ScoreRing score={it.verdict.score} />
            </>
          )}
        </div>
      </button>

      {open && (
        <div className="border-t border-border">
          {/* Borrador */}
          {it.draft ? (
            <div className="px-5 py-4">
              <div className="prose prose-sm prose-invert max-w-none prose-headings:font-semibold prose-a:text-cyan-400">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{it.draft}</ReactMarkdown>
              </div>
            </div>
          ) : (
            <div className="px-5 py-4 text-sm text-muted-foreground">Generando borrador…</div>
          )}

          {/* Inspección de herramientas */}
          {it.toolRuns && it.toolRuns.length > 0 && (
            <div className="border-t border-border px-5 py-4">
              <ToolPanel runs={it.toolRuns} />
            </div>
          )}

          {/* Crítica */}
          {it.verdict && (
            <div className="border-t border-border bg-muted/30 px-5 py-4">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Crítica del revisor
              </div>
              {it.verdict.summary && (
                <p className="mb-2 text-sm text-foreground/90">{it.verdict.summary}</p>
              )}
              {it.verdict.issues.length > 0 ? (
                <ul className="space-y-1">
                  {it.verdict.issues.map((issue, i) => (
                    <li key={i} className="flex gap-2 text-sm text-muted-foreground">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber-500" />
                      {issue}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-emerald-400">
                  Sin problemas: la respuesta cumple la rúbrica.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
