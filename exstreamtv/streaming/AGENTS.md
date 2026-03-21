# Streaming Module — Safety Rules

Full rules: .cursor/rules/exstreamtv-safety.mdc

## Async event loop — most critical rules in this module

- NEVER call sync SQLAlchemy .execute() or .commit() inside async def
- Pattern for saves: await loop.run_in_executor(None, self._method_sync)
- _save_position and equivalents must be split: async wrapper + sync worker

## Async locks (process_watchdog.py and any code using locks)

- Never await self._kill_process() inside async with self._lock
- Collect timed-out processes into a list under the lock, kill them after release
- _kill_process calls asyncio.wait_for(..., timeout=5.0) — 5 seconds inside a lock deadlocks all channels

## MPEG-TS buffer operations (throttler.py)

- Any buffer trim: find 0x47 sync byte, trim ONLY from that byte boundary onward
- Log all overflow trim events at logger.warning level (not debug)

## channel_manager.py

- _stream_loop inner async for body: correct indent is 4 spaces relative to the for statement
- Replace all datetime.utcnow() with _utcnow() returning datetime.now(tz=timezone.utc)
- Apply _ensure_utc() to all position.playout_start_time values before subtraction

## process_pool.py

- Use try/except for acquire_nowait:
    try: sem.acquire_nowait()
    except asyncio.QueueFull: return None
- Never: if not semaphore.locked(): semaphore.acquire_nowait()

## resolvers/plex.py

- Module-level cache _plex_cache_loaded must have TTL tracking:
    _plex_cache_loaded_at: float = 0.0
    _PLEX_CACHE_TTL_SECONDS: int = 300
