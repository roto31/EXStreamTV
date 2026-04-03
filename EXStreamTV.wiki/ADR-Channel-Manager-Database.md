# ADR: ChannelManager and database sessions (sync vs async)

## Status

Accepted — 2026-04-01

## Context

- `ChannelManager` and the MPEG-TS / playout pipeline were ported from a synchronous StreamTV/ErsatzTV-style stack. They use a **sync** SQLAlchemy `Session` from `get_sync_session_factory()` and run long-lived asyncio tasks that call into that stack.
- FastAPI routes and newer code use **async** `AsyncSession` via `Depends(get_db)`.
- The pattern prompt (EXStreamTV-Cursor-Pattern-Prompt.md) calls for async-only DB access in services; the codebase audit (see `AGENTS.md`, `docs/LESSONS_LEARNED.md`) also warns against calling sync SQLAlchemy directly from `async def` without `run_in_executor`.

## Decision

1. **Keep sync sessions inside the channel/stream worker path** for now: `ChannelManager`, playout resolution, and FFmpeg-adjacent code that already run in a dedicated concurrency model (async generators + sync DB callbacks). Migrating this surface to `AsyncSession` would require a wide refactor (every `db.query` / `session.execute` in the hot path) and retest of streaming stability.
2. **Do not call sync session methods from inside `async def` without offloading** to a thread (`asyncio.to_thread` or `run_in_executor`). New code should prefer **repositories + AsyncSession** at the API boundary (`exstreamtv/patterns/repository/`, `ChannelRepository`, etc.).
3. **ID types**: channel primary keys are **integers** in the ORM; public string IDs (e.g. command queue) remain at the API/FSM boundary but DB repositories use `int` for `Channel.id` consistently.

## Consequences

- **Pros:** Stable streaming path; incremental migration possible.
- **Cons:** Two session styles coexist; reviewers must ensure sync DB is not invoked directly from async handlers without a thread boundary.
- **Follow-up:** Optional future ADR for a full async ChannelManager once playout and pool managers share a single async session factory.

## References

- `exstreamtv/streaming/channel_manager.py`
- `exstreamtv/main.py` (lifespan wiring)
- `AGENTS.md` (async lock + sync DB rules)
- `EXStreamTV-UI-Architecture.md` (backend remains FastAPI; UI is separate `frontend/`)
