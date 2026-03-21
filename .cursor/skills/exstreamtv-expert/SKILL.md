---
name: exstreamtv-expert
description: Expert in the EXStreamTV platform. Knows the codebase structure, Python backend (exstreamtv/), Swift app (EXStreamTVApp/), tests, and APIs. Ensures all changes do not break existing code by analyzing impact, finding callers and tests, and running verification. Use when editing EXStreamTV code, adding features, fixing bugs, refactoring, or when the user asks to avoid breaking changes or analyze impact.
---

# EXStreamTV Codebase Expert

## When to Apply

- Editing any file under `exstreamtv/`, `EXStreamTVApp/`, or `tests/`
- Adding or changing APIs, database models, streaming, playout, or config
- Refactoring, renaming, or changing function signatures
- User asks to "not break anything," "analyze impact," or "ensure changes are safe"

## Core Rule

**Before and after every change:** Identify what could break, find affected code and tests, then verify. Never assume a change is isolated.

---

## Before Making Changes

1. **Identify scope**
   - Which module(s) are you touching? (e.g. `exstreamtv/api/`, `exstreamtv/streaming/`, `exstreamtv/database/`)
   - Is this a public API, a shared model, or an internal helper?

2. **Find dependents**
   - Search for imports and usages of the symbol you are changing (function, class, constant, route).
   - Check: `exstreamtv/`, `EXStreamTVApp/` (if API or config), and `tests/`.

3. **Find tests**
   - Tests live under `tests/`; layout mirrors `exstreamtv/` (e.g. `exstreamtv/streaming/` → `tests/streaming/`, `tests/unit/`, `tests/integration/`, `tests/e2e/`).
   - Run tests for the area you changed (see "Verification" below).

4. **Check interfaces**
   - Changing a function signature? Update all call sites and any tests that mock or assert on it.
   - Changing an API route or response shape? Check API clients and frontend (EXStreamTVApp or web UI).

---

## Change Safety Checklist

- [ ] All call sites of changed functions/classes are updated (or intentionally unchanged and still valid).
- [ ] No orphaned imports or references; no broken type hints or docstrings.
- [ ] Database/models: migrations considered if schema or ORM usage changes; existing data paths still work.
- [ ] Config/constants: consumers of the config key or constant are updated or backward-compatible.
- [ ] API routes: request/response contracts unchanged unless versioned or documented; clients updated if needed.
- [ ] Tests exist for the changed behavior; existing tests still pass.

---

## Verification

1. **Lint**
   ```bash
   ruff check exstreamtv/ tests/ --output-format=concise
   ```

2. **Type check** (if mypy/pyright is used in project)
   - Run the project’s type checker on `exstreamtv/` and affected `tests/`.

3. **Tests**
   - Full suite: `pytest tests/ -v`
   - Focused (after editing one area): `pytest tests/unit/ tests/integration/ -v` or `pytest tests/ -k "streaming" -v`
   - Markers (see `pytest.ini`): `unit`, `integration`, `e2e`, `slow`, `ffmpeg`, `network`. Run what’s appropriate; e.g. `pytest -m "not e2e and not slow"` for fast feedback.

4. **Smoke**
   - If you changed startup or config: run the app or main entrypoint briefly to confirm it starts (e.g. `python -m exstreamtv --help` or project’s run script).

---

## Codebase Map (Quick Reference)

| Area | Purpose |
|------|---------|
| `exstreamtv/` | Python backend: API, DB, streaming, playout, scheduling, metadata, FFmpeg, etc. |
| `exstreamtv/api/` | HTTP/IPTV API routes and handlers. |
| `exstreamtv/database/` | Models, migrations, DB access. |
| `exstreamtv/streaming/` | Channel/stream management, MPEG-TS, resolvers (Plex, Jellyfin, local, etc.). |
| `exstreamtv/playout/` | Program scheduling, filler, builder. |
| `exstreamtv/scheduling/` | Schedule rules and logic. |
| `exstreamtv/ffmpeg/`, `exstreamtv/transcoding/` | Encoding, transcoding, hardware. |
| `exstreamtv/metadata/` | Metadata providers, enrichment, extractors. |
| `EXStreamTVApp/` | macOS Swift/SwiftUI app (status bar, settings, dashboard). |
| `tests/` | pytest: `conftest.py`, `unit/`, `integration/`, `e2e/`, `reliability/`, fixtures. |

For a detailed map and dependency notes, see [reference.md](reference.md).

---

## Summary

- **Before:** Scope → dependents → tests → interfaces.
- **Checklist:** Call sites, types, DB/config, API, tests.
- **After:** Lint → type check → pytest (full or focused) → smoke if needed.

Apply this workflow on every EXStreamTV change so that existing code and tests remain intact.

---

## Known Bug Patterns (2026-03 Remediation)

The following patterns were confirmed as bugs across the codebase. When editing these files,
verify these fixes remain intact:

| File | Bug | Fix |
|------|-----|-----|
| `playout/scheduler.py` | Infinite loop on empty collection | `else` branch advances index; full-wrap abort |
| `streaming/channel_manager.py` | `datetime.utcnow()` naive/aware mismatch | `_utcnow()` + `_ensure_utc()` helpers |
| `streaming/channel_manager.py` | Sync DB in async context | `_save_position_sync` via `run_in_executor` |
| `transcoding/ffmpeg_builder.py` | `-flags +low_delay` drops B-frames | Removed; uses `FFLAGS_STREAMING` constant |
| `transcoding/ffmpeg_builder.py` | Missing `h264_mp4toannexb` on COPY | Added `-bsf:v` on copy path |
| `transcoding/ffmpeg_builder.py` | Muxrate string concatenation | `int()` cast before addition |
| `ffmpeg/pipeline.py` | Missing `hwdownload` before format= | Prepend when HW accel active |
| `ffmpeg/pipeline.py` | Loudnorm -24 vs -16 mismatch | Uses `LOUDNORM_FILTER` constant |
| `api/iptv.py` | `None.strftime()` in EPG emission | None guard with fallback |
| `api/iptv.py` | `idx` loop variable shadow | Renamed to `_ci` |
| `hdhomerun/api.py` | String/int channel number mismatch | `int(channel_number)` cast |
| `streaming/resolvers/plex.py` | Cache never expires | 5-minute TTL via `monotonic()` |
| `streaming/process_watchdog.py` | Kill inside lock → deadlock | Kill collected outside lock |
| `streaming/throttler.py` | Buffer trim breaks MPEG-TS framing | Align to 0x47 sync byte |
| `ffmpeg/process_pool.py` | `locked()` before `acquire_nowait()` | try/except pattern |
| `scheduling/parser.py` | Bare integer duration returns None | `isdigit()` check added |
| `scheduling/engine.py` | `datetime.utcnow()` deprecated | `_utcnow()` helper |

**Constants file:** `exstreamtv/ffmpeg/constants.py` — single source of truth for FFmpeg flags.
Import from here; never hardcode flag values in individual builders.
