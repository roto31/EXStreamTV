# Pattern refactor — canonical sources

Agents and implementers should treat these documents as the **requirements baseline** for the design-pattern refactor and UI roadmap.

| Source | Location | Role |
|--------|----------|------|
| **Agent safety / audit rules** | [AGENTS.md](../../AGENTS.md) at repo root | Non-negotiable: datetime, FFmpeg `constants.py`, XMLTV format, async DB, scheduler loops, etc. All pattern code must stay compatible. |
| **Pattern task order & constraints** | `EXStreamTV-Cursor-Pattern-Prompt.md` (maintain a local copy; e.g. under `~/Downloads/` or commit a snapshot under `docs/architecture/`) | Tasks 1–20, Section 1 absolute constraints, file tree, verification greps, `patterns-implemented.mdc` content. |
| **UI / React roadmap** | `EXStreamTV-UI-Architecture.md` (same as above) | Separate from backend pattern tasks: React shell, v1 API shape, ErsatzTV removal. Do not block backend Tasks 1–20 on UI work unless explicitly combined. |

## Repo-local enforcement

- Cursor rule: [.cursor/rules/patterns-implemented.mdc](../../.cursor/rules/patterns-implemented.mdc)
- Implemented modules: `exstreamtv/patterns/`
- Stream facade: `exstreamtv/services/stream_service.py`

If the Downloads copies drift, **diff against this repo’s** `docs/LESSONS_LEARNED.md` and `AGENTS.md` before large merges.

## Tasks 1–20 (external checklist — in-repo verification)

The numbered **Tasks 1–20** live in **`EXStreamTV-Cursor-Pattern-Prompt.md`** (local/Downloads; optionally commit beside this doc). This repo does **not** reproduce that file verbatim; use the table below to verify **intent** against code.

| Bucket | In-repo evidence |
|--------|------------------|
| Patterns / DI / lifespan | [`exstreamtv/patterns/`](../../exstreamtv/patterns/) · [`exstreamtv/services/stream_service.py`](../../exstreamtv/services/stream_service.py) · [`.cursor/rules/patterns-implemented.mdc`](../../.cursor/rules/patterns-implemented.mdc) |
| Schedule memento | migration **`006`** · [`exstreamtv/api/schedule_history.py`](../../exstreamtv/api/schedule_history.py) · [`exstreamtv/services/schedule_snapshot_service.py`](../../exstreamtv/services/schedule_snapshot_service.py) |
| Async subprocess | [`exstreamtv/utils/async_subprocess.py`](../../exstreamtv/utils/async_subprocess.py) |
| Track B UI | [`docs/EXStreamTV-UI-Architecture.md`](EXStreamTV-UI-Architecture) · [`frontend/`](../../frontend/) |

**Gap:** For byte-for-byte “Task *N* = …” parity, add **`docs/architecture/EXStreamTV-Cursor-Pattern-Prompt-SNAPSHOT.md`** (copy of your local prompt) and check off items there.

## Alembic / existing SQLite databases

If `exstreamtv.db` already has tables but `alembic_version` is empty, a blind `alembic upgrade head` will fail (e.g. “table already exists”). **Stamp** the revision that matches the current schema, then upgrade: e.g. `alembic stamp 005` then `alembic upgrade head` (adds `schedule_history` / `006`). See migration `exstreamtv/database/migrations/versions/006_add_schedule_history.py`.
