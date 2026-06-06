// Memoria local del historial de consultas (persistida en localStorage).
// Permite reabrir consultas anteriores sin volver a ejecutarlas, estilo ChatGPT.

import { useCallback, useState } from "react"
import type { FinalResult } from "./agent"

const STORAGE_KEY = "sca.history.v1"
const MAX_ENTRIES = 50

export type HistoryEntry = {
  id: string
  question: string
  result: FinalResult
  createdAt: number
}

function load(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function save(entries: HistoryEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {
    // localStorage lleno o no disponible: el historial es best-effort.
  }
}

export function useHistory() {
  // Carga inicial perezosa desde localStorage (una sola vez, sin efecto).
  const [entries, setEntries] = useState<HistoryEntry[]>(load)

  const add = useCallback((question: string, result: FinalResult): string => {
    const entry: HistoryEntry = {
      id: crypto.randomUUID(),
      question,
      result,
      createdAt: Date.now(),
    }
    setEntries((prev) => {
      const next = [entry, ...prev].slice(0, MAX_ENTRIES)
      save(next)
      return next
    })
    return entry.id
  }, [])

  const remove = useCallback((id: string) => {
    setEntries((prev) => {
      const next = prev.filter((e) => e.id !== id)
      save(next)
      return next
    })
  }, [])

  const clear = useCallback(() => {
    setEntries([])
    save([])
  }, [])

  return { entries, add, remove, clear }
}
