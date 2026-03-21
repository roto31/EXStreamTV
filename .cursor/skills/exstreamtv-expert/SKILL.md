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

## Safety Patterns (Audit-Derived — 2026-03-20)

These patterns are mandatory. They prevent recurrence of 30 confirmed bugs.
Full rules:   .cursor/rules/exstreamtv-safety.mdc
Full lessons: docs/LESSONS_LEARNED.md

### Datetime — always tz-aware

    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)   # always this

    def _ensure_utc(dt):
        if dt is None: return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    elapsed = (datetime.now(tz=timezone.utc) - _ensure_utc(db_val)).total_seconds()

### FFmpeg — always from constants.py

    from exstreamtv.ffmpeg.constants import (
        FFLAGS_STREAMING,   # "+genpts+discardcorrupt+igndts"
        BSF_H264_ANNEXB,    # "h264_mp4toannexb"
        LOUDNORM_FILTER,    # "loudnorm=I=-16:TP=-1.5:LRA=11"
        PIX_FMT,            # "yuv420p"
        MPEGTS_FLAGS,       # "resend_headers"
        PCR_PERIOD_MS,      # "40"
        AUDIO_SAMPLE_RATE,  # "48000"
        AUDIO_CHANNELS,     # "2"
    )

Never hardcode. Never use -flags +low_delay. Never use +fastseek. Never use I=-24.

### H.264 COPY to MPEG-TS: bsf is mandatory

    if video_format == VideoFormat.COPY:
        cmd.extend(["-c:v", "copy"])
        cmd.extend(["-bsf:v", BSF_H264_ANNEXB])   # always — no exceptions

### Hardware decode: hwdownload before CPU filters

    if is_hw:
        filters.insert(0, "hwdownload")
    filters.append(f"format={PIX_FMT}")

### Scheduler loops: empty-output guard

    _start = idx
    while current_time < end:
        items = get_items(...)
        if items:
            current_time = items[-1].finish
        else:
            idx = (idx + 1) % total
            if idx == _start: break
            continue

### Async: never block the event loop

    async def save(self):
        await asyncio.get_event_loop().run_in_executor(None, self._save_sync)

    def _save_sync(self):
        db = factory()
        try:
            db.execute(...); db.commit()
        finally:
            db.close()

### Async locks: collect then act

    to_act = []
    async with self._lock:
        for item in list(self._items):
            if item.needs_action:
                to_act.append(item)
    for item in to_act:         # outside the lock
        await item.long_action()

### XMLTV timestamps: one format only

    ts = dt.strftime("%Y%m%d%H%M%S +0000")
    # NEVER: "%Y-%m-%d %H:%M:%S UTC"  or  "%Y-%m-%dT%H:%M:%SZ"

### EPG: guard None before strftime

    if start_time is None:
        start_time = datetime.now(tz=timezone.utc)
    start_str = start_time.strftime("%Y%m%d%H%M%S +0000")

### Channel number: int cast with error handling

    try:
        ch = int(channel_number)
    except (ValueError, TypeError):
        raise HTTPException(400, detail=f"Invalid: {channel_number!r}")
    stmt = select(Channel).where(Channel.number == ch)

### MPEG-TS buffer trim: sync byte alignment

    trimmed = buf[-max_size:]
    pos = trimmed.find(0x47)
    trimmed = trimmed[pos:] if pos > 0 else (b"" if pos == -1 else trimmed)

### Muxrate: always int()

    rate = int(profile.video_bitrate) + int(profile.audio_bitrate)
    cmd.extend(["-muxrate", f"{rate}k"])

### YAML: always safe_load

    data = yaml.safe_load(f)

### Caches: TTL required

    import time as _t
    _at = 0.0; _TTL = 300
    def _load(force=False):
        global _at
        if not force and (_t.monotonic() - _at) < _TTL: return
        # load...
        _at = _t.monotonic()

### ErsatzTV port checklist

    [ ] datetime.now(tz=timezone.utc) — not utcnow()
    [ ] FFmpeg flags from constants.py — not hardcoded
    [ ] No +low_delay, no +fastseek
    [ ] COPY path has h264_mp4toannexb
    [ ] hwdownload before format= when HW decode active
    [ ] Scheduler while-loop has empty-output guard
    [ ] XMLTV uses %Y%m%d%H%M%S +0000
    [ ] No sync DB in async def
    [ ] No await inside async lock
    [ ] MPEG-TS trim aligned to 0x47
    [ ] Muxrate uses int() cast
    [ ] yaml.safe_load()
