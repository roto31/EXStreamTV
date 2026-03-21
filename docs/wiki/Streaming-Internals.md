# Streaming Internals

See [Platform Guide](PLATFORM_GUIDE.md#2-how-streaming-works) for full streaming lifecycle, ProcessPoolManager, CircuitBreaker, and restart guards.

Key: ProcessPoolManager is sole FFmpeg gatekeeper. Restarts are bounded by throttle, cooldown, and circuit breaker.

## 2026-03 Remediation Fixes

The following bugs in the streaming layer were confirmed and fixed during the 2026-03 full codebase audit. See [`docs/LESSONS_LEARNED.md`](../LESSONS_LEARNED.md) for full root-cause detail.

| LL ID | File | Fix |
|---|---|---|
| LL-003 | `channel_manager.py` | DB position saves now use `run_in_executor` — no longer blocks the asyncio event loop |
| LL-013 | `process_watchdog.py` | Watchdog kills processes **outside** the async lock — eliminates 5–10s deadlock on channel failure |
| LL-014 | `throttler.py` | Buffer overflow trim aligned to `0x47` MPEG-TS sync byte — prevents corrupted packet framing |
| LL-026 | `channel_manager.py` | `async for` body indentation corrected — `is_running` break now fires on every chunk |
| LL-021 | `process_pool.py` | Semaphore acquire uses `try/except asyncio.QueueFull` instead of `locked()` check |

See [Architecture Diagram 17](../architecture/DIAGRAMS.md#17-async-lock-collect-then-act-pattern-2026-03-remediation--ll-013) for the collect-then-act lock pattern.

**Last Revised:** 2026-03-21
