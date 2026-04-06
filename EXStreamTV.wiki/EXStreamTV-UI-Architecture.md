# EXStreamTV UI Architecture (Track B)

**Status:** Implemented in `frontend/` (Vite + React + TypeScript).  
**Backend:** FastAPI remains source of truth; UI uses **`/api`** JSON routes only (no ErsatzTV-era importer UI in this tree).

---

## 1. Goals

- **Parity with server:** Channel list, schedules entry points, settings shell, and **schedule-history (memento)** flows aligned with `exstreamtv/api/` and `docs/api/README.md`.
- **Personas:** Explicit **persona id** for APIs that accept `persona_id` (e.g. schedule snapshot capture).
- **Styling:** **Tailwind CSS** for layout and responsive shell.
- **Routing:** **React Router** — deep-linkable sections.

---

## 2. Stack

| Layer | Choice |
|--------|--------|
| Build | Vite 5 |
| UI | React 18, TypeScript |
| CSS | Tailwind 3 |
| Routing | React Router 6 |
| Data | Native `fetch` + clients under `src/api/` |

---

## 2a. Frontend hooks

| Hook | File | Purpose |
|------|------|---------|
| `useAsync` | `hooks/useAsync.ts` | Simple async-fetch with cancellation; returns `{ data, error, loading }` |
| `useAsyncResource` | `hooks/useAsyncResource.ts` | Template Method variant — adds `enabled` guard and `errorData` fallback; preferred for page-level data loading |

**Pattern justification (per `.cursor/rules/exstreamtv-design-pattern-selection.mdc` §C Behavioral):**  
Pain point: repeated `useEffect + cancelled + try/catch` copied into every page → Template Method extracts the fixed skeleton (mount → load → success/error) and lets callers vary only the `loader` function.

---

## 3. Dev proxy & ports

- Default EXStreamTV HTTP port: **8411** (`exstreamtv.config`).
- Vite dev server: **5173**.
- `vite.config.ts` proxies **`/api`** and **`/iptv`** → `http://127.0.0.1:8411`.

Production: same host as API or set `VITE_API_BASE` (see `src/api/client.ts`).

---

## 4. Personas

| Persona | `persona_id` |
|---------|----------------|
| Operator | `operator` |
| Curator | `curator` |
| Viewer | `viewer` |

**Viewer:** **Schedule history** is hidden in the nav; direct URL shows a read-only message (no capture/revert). Use **operator** or **curator** for memento APIs.

Stored in **`sessionStorage`** (`exstreamtv.persona_id`) and **React context**.

---

## 5. Route map

| Path | Purpose |
|------|---------|
| `/` | Dashboard — health, quick links |
| `/channels` | `GET /api/channels` |
| `/channels/:id` | Channel detail: playouts table, now-playing, upcoming items (collapsible raw JSON) |
| `/schedules` | `GET /api/schedules` |
| `/schedules/:id` | Schedule detail (`GET /api/schedules/{id}`) |
| `/schedule-history` | `POST /api/schedule-history/capture` |
| `/settings` | Persona + API hints |

---

## 6. `frontend/src/` layout

```
api/client.ts
api/channels.ts
api/playouts.ts
api/schedules.ts
api/scheduleHistory.ts
context/PersonaContext.tsx
layout/AppShell.tsx
pages/Dashboard.tsx
pages/ChannelsPage.tsx
pages/ChannelDetailPage.tsx
pages/SchedulesPage.tsx
pages/ScheduleDetailPage.tsx
pages/ScheduleHistoryPage.tsx
pages/SettingsPage.tsx
App.tsx
main.tsx
index.css
```

---

## 7. API conventions

- **`/api/...`** JSON; **`persona_id`** on schedule-history per `docs/api/README.md`.

---

## 8. Verification

- `npm run build`; with server on **8411**, `npm run dev` — smoke Dashboard, Channels, **channel detail** (now-playing when a playout exists), Schedules detail, Schedule history.

See `docs/architecture/PATTERN_REFACTOR_SOURCES.md`, `AGENTS.md`.
