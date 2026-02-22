# Root-Cause Investigation Report
## EXStreamTV Streaming Instability and System Errors

> **User-facing overview:** For streaming architecture and restart safety, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

**Document type:** Executive technical summary  
**Date:** Investigation based on codebase analysis (logs not provided)  
**Scope:** Scheduling and streaming failures, API errors, recursion, health restarts

---

## SECTION 1 — Failure Categories (with Timestamps)

> **Note:** Actual terminal logs were not provided. Categories and evidence are derived from code inspection. Timestamps cannot be inferred without log data.

| # | Category | Approx Occurrences | Earliest/Peak | Evidence |
|---|----------|--------------------|---------------|----------|
| 1 | Base64 "Incorrect padding" | Recurring | N/A | `exstreamtv/api/logs.py` L443-444: `logger.exception(f"Error decoding log entry: {e}")` |
| 2 | GET /api/logs/entries → 400 Bad Request | Recurring | N/A | Same handler returns 400 on decode failure |
| 3 | ProcessPoolManager acquire failed: maximum recursion depth exceeded | Sporadic | N/A | `exstreamtv/streaming/mpegts_streamer.py` L761: `logger.error(f"ProcessPoolManager acquire failed: {e}")` |
| 4 | Channel \<id\> no output for \<seconds\> - unhealthy | Every 30s when stale | N/A | `exstreamtv/tasks/health_tasks.py` L108-111 |
| 5 | Repeated playout rebuild loops | Every 5 min | N/A | `exstreamtv/tasks/playout_tasks.py` L85-87, `main.py` L70 |

**Categorized failure list:**

1. **Log decoding / API 400** — Base64 decode failure when decoding `entry_id`; returns 400  
2. **ProcessPoolManager recursion** — `RecursionError` during `acquire_process`  
3. **Channel unhealthy** — Health task marks channel unhealthy when no output for 180s  
4. **Playout rebuild** — Task logs "needs more content" every 5 min for channels with &lt;30 min content  

---

## SECTION 2 — Code Correlation

### A) Base64 "Incorrect padding"

| Item | Location | Details |
|------|----------|---------|
| Decoding implementation | `exstreamtv/api/logs.py` L394-398 | `base64.b64decode(entry_id).decode("utf-8")` |
| Input source | HTTP path param `entry_id` | Request path `/api/logs/{entry_id}` |
| Error handling | L443-444 | `logger.exception(...)` then `raise HTTPException(status_code=400, ...)` |
| Validation gap | None | No pre-check that `entry_id` is valid base64 before decode |

**Cause:** `entry_id` is treated as base64-encoded. Non-base64 values (e.g. `"entries"`) raise `binascii.Error: Incorrect padding`.

### B) GET /api/logs/entries → 400 Bad Request

| Item | Location | Details |
|------|----------|---------|
| Router | `exstreamtv/api/logs.py` | `router = APIRouter(prefix="/logs")` |
| Route registration order | L380, L449 | `@router.get("/{entry_id}")` **before** `@router.get("/entries")` |
| Why 400 | Route collision | `GET /api/logs/entries` matches `/{entry_id}` with `entry_id="entries"` |
| Flow | log_entry_detail("entries") | `base64.b64decode("entries")` → `binascii.Error` → 400 |

**Cause:** Catch-all route `/{entry_id}` is registered before `/entries`, so `/entries` is matched as `entry_id="entries"`. Decoding that string triggers the base64 error and 400.

### C) ProcessPoolManager recursion depth exceeded

| Item | Location | Details |
|------|----------|---------|
| acquire_process | `exstreamtv/streaming/process_pool_manager.py` L203-217 | Calls `await self._startup_rate_limiter.acquire()` at L217 |
| Rate limiter | L104-118 | `TokenBucket.acquire()` |
| Recursion | L117-118 | After `await asyncio.sleep(wait_time)`, calls `await self.acquire()` |
| Call stack | mpegts_streamer.stream_via_pool L757 | `acquire_process(channel_id, cmd)` |

```python
# process_pool_manager.py L104-118
async def acquire(self) -> None:
    async with self._lock:
        ...
        if self.tokens >= 1:
            self.tokens -= 1
            return
        wait_time = (1 - self.tokens) / self.rate
        self.tokens = 0
    await asyncio.sleep(wait_time)
    await self.acquire()  # Tail recursion — stack grows each wait cycle
```

**Cause:** Tail recursion. Each wait cycle adds one frame. Under sustained contention (e.g. many restarts), depth can exceed Python’s recursion limit (~1000).

### D) Channel unhealthy → restart

| Item | Location | Details |
|------|----------|---------|
| Health monitor | `exstreamtv/tasks/health_tasks.py` L42-62 | `channel_health_task()` |
| Schedule | `main.py` L76 | Every 30 seconds |
| Timeout | health_tasks.py L99 | `UNHEALTHY_THRESHOLD = 180` (3 minutes) |
| Restart trigger | L106-117 | If `time_since_output > 180` and `auto_restart_enabled` |
| Restart logic | L165-239 | `_trigger_channel_restart()` → `stop_channel()` → `start_channel()` |
| Pool acquisition | channel_manager L804-809 | `stream_via_pool()` → `acquire_process()` |

**Flow:** No output for 180s → health task restarts channel → `start_channel` → `_stream_loop` → `stream_via_pool` → `acquire_process` → `TokenBucket.acquire()`.

---

## SECTION 3 — Failure Cascade Map

```
[No content / slow source / FFmpeg stall]
         │
         ▼
   No chunks streamed
   last_output_time not updated
         │
         ▼
   Health task (every 30s): time_since_output > 180s
         │
         ▼
   "Channel X no output for Ys - unhealthy"
         │
         ▼
   _trigger_channel_restart(channel_id)
         │
         ▼
   stop_channel() → start_channel()
         │
         ▼
   stream_via_pool() → acquire_process()
         │
         ▼
   TokenBucket.acquire()
         │
         ├── [Tokens available] → spawn FFmpeg → OK
         │
         └── [No tokens] → sleep → acquire() [recursion]
                              │
                              └── Repeated under load → RecursionError
                                    │
                                    ▼
                              "ProcessPoolManager acquire failed: maximum recursion depth exceeded"
```

**Relationship summary:**

- **Independent:** Logs API 400 (route ordering), Base64 decode failure (same root cause)
- **Causally linked:** Health timeout → restart → acquire → recursion
- **Restart storm:** Several unhealthy channels restarting every 30s can overload `acquire_process`
- **Recursive retry:** `TokenBucket.acquire()` uses recursion instead of a loop

---

## SECTION 4 — Root Cause Ranking

### 1. Primary root cause — Route collision causing 400 and Base64 errors

- **Evidence:** `/{entry_id}` registered before `/entries`; `entries` decoded as base64
- **Impact:** `/api/logs/entries` returns 400 and log UI breaks
- **Interaction:** Separate from streaming; does not trigger restarts or recursion

### 2. Secondary root cause — TokenBucket recursion under restart load

- **Evidence:** `TokenBucket.acquire()` uses tail recursion (L117-118)
- **Impact:** Under many restarts, recursion depth can exceed limit
- **Interaction:** Triggered by health restarts; does not cause health timeout itself

### 3. Cascade amplifier — Health restarts under no-output conditions

- **Evidence:** `UNHEALTHY_THRESHOLD = 180`; restart on no output
- **Impact:** Multiple restarts contend on `acquire_process` and worsen recursion risk
- **Interaction:** Amplifies recursion when many channels are unhealthy

### 4. Contributing factor — Playout rebuild “needs more content” loops

- **Evidence:** `rebuild_playouts_task` logs but does not add content (L90-93)
- **Impact:** Log noise; channels may stay in “no content” state → no output → health timeout
- **Interaction:** Indirect: no content → no chunks → health timeout → restart cascade

---

## SECTION 5 — Minimal Patch Plan

### Patch 1: Fix logs route collision

**File:** `exstreamtv/api/logs.py`  
**Change:** Register `/entries` before `/{entry_id}`.

**Action:** Move `@router.get("/entries")` and its handler above `@router.get("/{entry_id}")`.

**Rationale:** Ensures `GET /api/logs/entries` hits the entries handler instead of being treated as `entry_id="entries"`, eliminating 400 and Base64 decode errors for that path.

### Patch 2: Replace TokenBucket recursion with a loop

**File:** `exstreamtv/streaming/process_pool_manager.py`  
**Function:** `TokenBucket.acquire`

**Current (L104-118):**
```python
async def acquire(self) -> None:
    async with self._lock:
        now = time.monotonic()
        elapsed = now - self._last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self._last_update = now
        if self.tokens >= 1:
            self.tokens -= 1
            return
        wait_time = (1 - self.tokens) / self.rate
        self.tokens = 0
    await asyncio.sleep(wait_time)
    await self.acquire()
```

**Replace with:**
```python
async def acquire(self) -> None:
    while True:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self._last_update = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            wait_time = (1 - self.tokens) / self.rate
            self.tokens = 0
        await asyncio.sleep(wait_time)
```

**Rationale:** Same behavior, no recursion, so recursion limit cannot be hit. No change to API or semantics.

### Patch 3 (optional): Add Base64 padding handling

**File:** `exstreamtv/api/logs.py`  
**Function:** `log_entry_detail`  
**Change:** Add padding before decode (e.g. append `"=" * (4 - len(entry_id) % 4)` when needed) or validate base64 before decode and return 404 for invalid IDs instead of 400 for decode errors.  
**Rationale:** Makes the log detail endpoint more tolerant of malformed IDs; lower priority than Patch 1.

---

## SECTION 6 — Stability Validation Plan

### Target metrics to monitor

| Metric | Source | Target |
|--------|--------|--------|
| `GET /api/logs/entries` 200 rate | Access logs / APM | 100% for valid requests |
| ProcessPoolManager acquire exceptions | Logs / metrics | 0 RecursionError |
| Channels unhealthy count | `channel_health_task` stats | Decrease over time |
| Restarts triggered per health run | `channel_health_task` stats | &lt; N restarts per 30s |

### Log patterns that should disappear

- `Error decoding log entry: Incorrect padding` for path `/api/logs/entries`
- `ProcessPoolManager acquire failed: maximum recursion depth exceeded`

### What should decrease in frequency

- `Channel X no output for Ys - unhealthy` (after fixing upstream causes like no content)
- `Triggering restart for channel X`

### What must never appear again

- `RecursionError` or `maximum recursion depth exceeded` in `TokenBucket.acquire` / `acquire_process`
- 400 from `GET /api/logs/entries` when requesting the entries list (not a specific entry)

---

## Appendix: Key Code References

| Component | File | Lines |
|-----------|------|-------|
| Log entry detail (base64 decode) | `exstreamtv/api/logs.py` | 379-446 |
| Log entries endpoint | `exstreamtv/api/logs.py` | 448-465 |
| TokenBucket | `exstreamtv/streaming/process_pool_manager.py` | 95-118 |
| acquire_process | `exstreamtv/streaming/process_pool_manager.py` | 203-252 |
| stream_via_pool | `exstreamtv/streaming/mpegts_streamer.py` | 728-781 |
| channel_health_task | `exstreamtv/tasks/health_tasks.py` | 42-161 |
| _trigger_channel_restart | `exstreamtv/tasks/health_tasks.py` | 165-239 |
| _stream_loop | `exstreamtv/streaming/channel_manager.py` | 732-843 |
| rebuild_playouts_task | `exstreamtv/tasks/playout_tasks.py` | 14-112 |
