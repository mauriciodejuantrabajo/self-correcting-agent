import { Plus, Trash2, MessageSquare, RefreshCw, Check, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { HistoryEntry } from "@/lib/useHistory"

// Sidebar de memoria/historial, estilo ChatGPT. Persiste en localStorage.
export function Sidebar({
  entries,
  activeId,
  onOpen,
  onNew,
  onRemove,
  onClear,
}: {
  entries: HistoryEntry[]
  activeId: string | null
  onOpen: (entry: HistoryEntry) => void
  onNew: () => void
  onRemove: (id: string) => void
  onClear: () => void
}) {
  return (
    <aside className="flex h-screen w-72 shrink-0 flex-col border-r border-violet-400/10 bg-card/30 backdrop-blur-xl">
      {/* Marca */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="inline-flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-cyan-500 shadow-md shadow-violet-500/30 ring-1 ring-white/20">
          <RefreshCw className="size-5 text-white" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-gradient">Auto-corrector</div>
          <div className="text-[11px] text-muted-foreground">Reflexion · memoria local</div>
        </div>
      </div>

      <div className="px-3">
        <Button
          onClick={onNew}
          className="w-full justify-start gap-2 bg-gradient-to-br from-violet-500 to-cyan-500 text-white shadow-md shadow-violet-500/25 transition-all hover:from-violet-400 hover:to-cyan-400"
        >
          <Plus className="size-4" /> Nueva consulta
        </Button>
      </div>

      {/* Lista de historial */}
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto px-2">
        {entries.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            Tus consultas aparecerán aquí. Se guardan en este navegador.
          </p>
        ) : (
          <ul className="space-y-1">
            {entries.map((e) => {
              const approved = e.result.approved
              return (
                <li key={e.id}>
                  <button
                    onClick={() => onOpen(e)}
                    className={cn(
                      "group flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-sm transition-all",
                      e.id === activeId
                        ? "border-l-2 border-violet-400 bg-violet-500/15 text-foreground"
                        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
                    )}
                  >
                    <MessageSquare className="mt-0.5 size-4 shrink-0 opacity-70" />
                    <span className="min-w-0 flex-1 truncate">{e.question}</span>
                    <span className="mt-0.5 shrink-0" title={approved ? "Aprobada" : "Mejor intento"}>
                      {approved ? (
                        <Check className="size-3.5 text-emerald-400" />
                      ) : (
                        <AlertTriangle className="size-3.5 text-amber-400" />
                      )}
                    </span>
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(ev) => {
                        ev.stopPropagation()
                        onRemove(e.id)
                      }}
                      className="shrink-0 rounded p-0.5 opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                    >
                      <Trash2 className="size-3.5" />
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {/* Pie */}
      {entries.length > 0 && (
        <div className="border-t border-border p-3">
          <button
            onClick={onClear}
            className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-destructive"
          >
            <Trash2 className="size-3.5" /> Borrar historial
          </button>
        </div>
      )}
    </aside>
  )
}
