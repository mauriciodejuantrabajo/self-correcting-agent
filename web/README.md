# Frontend — Agente auto-corrector

Interfaz web del agente: **React + Vite + TypeScript + shadcn/ui + Tailwind**.
Consume el stream SSE del backend (FastAPI) y muestra **en vivo** la línea de
tiempo de iteraciones —cada borrador, su crítica y el puntaje— hasta la respuesta
final.

## Desarrollo

```bash
npm install        # solo la primera vez
npm run dev        # arranca Vite en http://localhost:5173
```

Vite redirige `/api` al backend en `http://localhost:8000`, así que primero levanta
el backend (`uvicorn server:app --reload --port 8000` desde la raíz del repo).

## Build

```bash
npm run build      # genera web/dist (estáticos listos para producción)
```

## Estructura

- `src/App.tsx` — UI principal: formulario, línea de tiempo, respuesta final.
- `src/components/IterationCard.tsx` — tarjeta de una iteración (borrador + crítica
  + anillo de puntaje).
- `src/lib/agent.ts` — cliente SSE y tipos del stream.
- `src/components/ui/` — primitivas de shadcn/ui.
