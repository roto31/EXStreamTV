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

## Safety Patterns (Derived from 2026-03 Audit — 30 Confirmed Bugs)

The following patterns are **mandatory** when working on EXStreamTV. They are derived
from bugs found in a full codebase audit. The corresponding Cursor rules are in
`.cursor/rules/exstreamtv-safety.mdc` and are auto-applied to all Python files.

---

### Datetime — Always Tz-Aware

```python
# ✅ Correct
from datetime import datetime, timezone
now = datetime.now(tz=timezone.utc)

# ❌ Never use
now = datetime.utcnow()   # naive — causes TypeError on subtraction with DB values
now = datetime.now()      # local time — wrong for UTC-anchored schedules
```

SQLite does not store timezone info. Any datetime loaded from the DB via the sync
engine is naive. Normalise before arithmetic:
```python
def _ensure_utc(dt):
    if dt is None: return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
```

---

### FFmpeg Flags — Always From constants.py

```python
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
```

**Never hardcode these values.** The constants file is the single source of truth.

**Specifically banned flags:**
- `-flags +low_delay` — drops B-frames on pre-recorded content
- `+fastseek` in `-fflags` — wrong context, masks missing `+igndts`
- `loudnorm=I=-24` — wrong target; use `-16 LUFS` (EBU R128)

---

### H.264 COPY → MPEG-TS Always Needs bsf

```python
if video_format == VideoFormat.COPY:
    cmd.extend(["-c:v", "copy"])
    cmd.extend(["-bsf:v", BSF_H264_ANNEXB])   # Non-optional. Always required.
```

---

### Hardware Decode → CPU Filter Chain Needs hwdownload

```python
if is_hardware_decode_active:
    filters.insert(0, "hwdownload")
filters.append(f"format={PIX_FMT}")
```

---

### Scheduler While Loops Need Empty-Output Guard

```python
while current_time < end:
    items = get_items(...)
    if items:
        current_time = items[-1].finish
    else:
        index = (index + 1) % total
        if index == start_index:
            break   # full wrap with no output — abort
        continue
```

---

### Async Functions: Never Call Sync DB Directly

```python
# ✅ Correct pattern
async def save(self):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, self._save_sync)

def _save_sync(self):
    db = self.db_session_factory()
    try:
        db.execute(...)
        db.commit()
    finally:
        db.close()
```

---

### Async Locks: Collect Then Act

```python
to_process = []
async with self._lock:
    for item in list(self._items):
        if item.needs_action:
            to_process.append(item)
# ← lock released here
for item in to_process:
    await item.action()   # long-running outside lock
```

---

### XMLTV Timestamps: One Format Only

```python
# ✅ Correct
ts = dt.strftime("%Y%m%d%H%M%S +0000")

# ❌ Wrong
ts = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
```

---

### EPG Values: Guard None Before strftime

```python
if start_time is None:
    start_time = datetime.now(tz=timezone.utc)
if end_time is None or end_time <= start_time:
    end_time = start_time + timedelta(seconds=1800)
start_str = start_time.strftime("%Y%m%d%H%M%S +0000")
```

---

### Channel Number: Cast to int

```python
try:
    ch = int(channel_number)
except (ValueError, TypeError):
    raise HTTPException(400, detail=f"Invalid channel number: {channel_number!r}")
stmt = select(Channel).where(Channel.number == ch)
```

---

### MPEG-TS Buffer Trim: Align to 0x47

```python
trimmed = buffer[-max_size:]
pos = trimmed.find(0x47)
trimmed = trimmed[pos:] if pos > 0 else (b"" if pos == -1 else trimmed)
```

---

### Muxrate: Always int()

```python
rate = int(profile.video_bitrate) + int(profile.audio_bitrate)
cmd.extend(["-muxrate", f"{rate}k"])
```

---

### YAML: Always safe_load

```python
data = yaml.safe_load(f)   # never yaml.load(f, Loader=yaml.FullLoader)
```

---

### Caches: TTL Required

```python
import time as _time
_loaded_at = 0.0
_TTL = 300

def _load(force=False):
    global _loaded_at
    if not force and (_time.monotonic() - _loaded_at) < _TTL:
        return
    # ... load ...
    _loaded_at = _time.monotonic()
```

---

### ErsatzTV Port Checklist

Before committing any code ported from ErsatzTV (C#):

- [ ] All datetime values are tz-aware (`datetime.now(tz=timezone.utc)`)
- [ ] No FFmpeg flags hardcoded — imported from constants.py
- [ ] No `+low_delay`, no `+fastseek`
- [ ] H.264 COPY path includes `h264_mp4toannexb`
- [ ] Scheduler while-loops have empty-output guard
- [ ] XMLTV timestamps use `%Y%m%d%H%M%S +0000`
- [ ] No sync DB calls inside async functions
- [ ] No long-running awaits inside async locks
- [ ] MPEG-TS buffer trims aligned to `0x47`
- [ ] Muxrate uses explicit `int()` cast
