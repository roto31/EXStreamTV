# EXStreamTV frontend (Track B)

Vite + React + TypeScript + Tailwind + React Router. See **[docs/EXStreamTV-UI-Architecture.md](../docs/EXStreamTV-UI-Architecture.md)**.

## Setup

```bash
cd frontend
npm install   # generates package-lock.json for npm ci in CI
npm run dev   # http://localhost:5173 — proxies /api and /iptv to http://127.0.0.1:8411
```

## Build

```bash
npm run build
```

Optional: `VITE_API_BASE=https://your-server:8411` for a split deployment (empty = relative URLs).
