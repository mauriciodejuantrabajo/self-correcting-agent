import { Calculator, Type, BookOpen, Wrench, Check, X, type LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ToolRun } from "@/lib/agent"

// Icono por tool para que se reconozca de un vistazo.
const TOOL_ICONS: Record<string, LucideIcon> = {
  word_count: Type,
  readability: BookOpen,
  calc_check: Calculator,
}

function ToolChip({ run }: { run: ToolRun }) {
  const Icon = TOOL_ICONS[run.tool] ?? Wrench
  return (
    <div
      className={cn(
        "rounded-lg border p-3 transition-colors",
        run.ok
          ? "border-emerald-500/25 bg-emerald-500/5"
          : "border-rose-500/30 bg-rose-500/5",
      )}
    >
      <div className="flex items-center gap-2">
        <Icon className={cn("size-4", run.ok ? "text-emerald-400" : "text-rose-400")} />
        <span className="text-sm font-medium">{run.label}</span>
        <span className="ml-auto">
          {run.ok ? (
            <Check className="size-4 text-emerald-400" />
          ) : (
            <X className="size-4 text-rose-400" />
          )}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{run.summary}</p>
      {run.findings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {run.findings.map((f, i) => (
            <li key={i} className="flex gap-1.5 text-xs text-rose-300/90">
              <span className="mt-1.5 size-1 shrink-0 rounded-full bg-rose-400" />
              {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Panel de herramientas: muestra la inspección objetiva del borrador (en vivo).
export function ToolPanel({ runs }: { runs: ToolRun[] }) {
  if (runs.length === 0) return null
  const flagged = runs.filter((r) => !r.ok).length

  return (
    <div className="animate-in fade-in slide-in-from-bottom-1 duration-300">
      <div className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <Wrench className="size-3.5" /> Herramientas de inspección
        {flagged > 0 ? (
          <span className="rounded-full bg-rose-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-rose-300">
            {flagged} con hallazgos
          </span>
        ) : (
          <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
            todo OK
          </span>
        )}
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
        {runs.map((r) => (
          <ToolChip key={r.tool} run={r} />
        ))}
      </div>
    </div>
  )
}
