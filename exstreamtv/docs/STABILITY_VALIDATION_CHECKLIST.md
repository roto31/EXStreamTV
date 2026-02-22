# Stability Validation Checklist

> **User-facing overview:** For streaming lifecycle, restart guards, and ProcessPoolManager, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

## SECTION 1 — Current Weak Points (with file references)


| Weak Point                         | File                    | Function/Lines                    |
| ---------------------------------- | ----------------------- | --------------------------------- |
| TokenBucket unbounded wait         | process_pool_manager.py | TokenBucket.acquire L104-118      |
| acquire_process no timeout         | process_pool_manager.py | acquire_process L203-252          |
| No circuit breaker on restarts     | health_tasks.py         | _trigger_channel_restart L165-239 |
| No restart storm throttle          | health_tasks.py         | channel_health_task L42-161       |
| No pool acquisition latency metric | mpegts_streamer.py      | stream_via_pool L728-781          |


## SECTION 2 — Circuit Breaker Implementation

**File:** `exstreamtv/streaming/circuit_breaker.py`

- States: CLOSED, OPEN, HALF_OPEN
- Failure threshold: 5 in 300s window
- Cooldown: 120s before HALF_OPEN
- `can_restart()`: fail-fast when OPEN
- Integration: `health_tasks._can_trigger_restart()` before `_trigger_channel_restart()`
- `record_failure()`: on restart exception, on acquire_process exception
- Async-safe via asyncio.Lock

## SECTION 3 — ProcessPoolManager v2 Hardening

**File:** `exstreamtv/streaming/process_pool_manager.py`

- TokenBucket: loop-based acquire (no recursion) — already fixed
- acquire_process: `timeout_seconds=90`, `max_attempts=5`
- Exponential backoff: `min(2**attempt, 60)`
- Fail-fast: memory/fd rejection raised immediately
- Retry only: timeout, capacity
- New metric: `exstreamtv_ffmpeg_spawn_timeout_total`

## SECTION 4 — Observability Additions

**File:** `exstreamtv/monitoring/metrics.py`


| Metric                                       | Where Incremented                            |
| -------------------------------------------- | -------------------------------------------- |
| exstreamtv_pool_acquisition_latency_seconds  | mpegts_streamer.stream_via_pool              |
| exstreamtv_restart_rate_per_minute           | health_tasks._record_restart_triggered       |
| exstreamtv_health_timeouts_total             | health_tasks.channel_health_task (unhealthy) |
| exstreamtv_playout_rebuild_total             | playout_tasks.rebuild_playouts_task          |
| exstreamtv_circuit_breaker_state{channel_id} | health_tasks._can_trigger_restart            |


## SECTION 5 — Soak Test Harness

**File:** `scripts/soak_test.py`

- Run: `python scripts/soak_test.py --duration 86400 --url http://127.0.0.1:8000`
- Metrics: requests, restarts, pool_active_max, memory_rss_mb_max, recursion_errors, restart_storms
- Failure thresholds: recursion_errors>0, restart_storms>=3
- Exit non-zero on instability

## SECTION 6 — Restart Storm Containment

**File:** `exstreamtv/tasks/health_tasks.py`

- Global throttle: max 10 restarts in 60s
- Per-channel cooldown: 30s between restarts
- Circuit breaker: block restart when OPEN
- Guard location: `_can_trigger_restart()` before `_trigger_channel_restart()`
- Storm detection: `len(_RESTART_TIMESTAMPS) >= RESTART_STORM_THRESHOLD`

## SECTION 7 — Stability Validation Checklist

System considered stabilized when:

- No RecursionError in logs
- No infinite restart loops (restart_count bounded per channel)
- Pool acquisition bounded (timeout 90s, max_attempts 5)
- Circuit breaker blocks unhealthy channels (OPEN state)
- Restart storm throttle prevents >10 restarts/60s
- 24h soak test: `python scripts/soak_test.py --duration 86400` exits 0

