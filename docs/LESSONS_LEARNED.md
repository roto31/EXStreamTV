# EXStreamTV — Lessons Learned

Formal record of bugs found and fixed during the 2026-03 codebase remediation.
Each entry includes root cause, symptom, fix, and prevention rule.

---

## LL-01: Infinite Loop on Empty Collection (scheduler.py)
- **Category:** Logic  
- **Severity:** Critical  
- **Root Cause:** `_schedule_item()` returns empty list → `current_time` never advances → `while` loop spins at 100% CPU.  
- **Symptom:** Server pegs one CPU core; channel never streams.  
- **Fix:** Added `else` branch that advances `schedule_index` when no items produced; full-wrap guard aborts if all items empty.  
- **Prevention:** Every `while` loop that depends on external input must have a monotonic progress guarantee or a bounded iteration count.

## LL-02: Naive/Aware Datetime Mismatch (channel_manager.py)
- **Category:** Data  
- **Severity:** High  
- **Root Cause:** `datetime.utcnow()` returns naive datetime; SQLite may return naive or tz-aware depending on ORM path.  
- **Symptom:** `TypeError` on subtraction, or silently wrong elapsed time → channel resumes at wrong position.  
- **Fix:** Introduced `_utcnow()` (tz-aware) and `_ensure_utc()` normaliser. Replaced all `datetime.utcnow()` calls.  
- **Prevention:** Never use `datetime.utcnow()`. Always use `datetime.now(tz=timezone.utc)`. Normalise all DB-sourced datetimes before arithmetic.

## LL-03: Synchronous DB in Async Context (channel_manager.py)
- **Category:** Concurrency  
- **Severity:** High  
- **Root Cause:** `_save_position` called synchronous SQLAlchemy `.execute()` / `.commit()` inside `async def`.  
- **Symptom:** Blocks asyncio event loop → all channels freeze → Plex buffer spinners.  
- **Fix:** Split into `_save_position` (async, delegates) and `_save_position_sync` (called via `run_in_executor`).  
- **Prevention:** Never call synchronous I/O inside an `async def`. Always use `run_in_executor` for sync DB, file, or network calls.

## LL-04: `-flags +low_delay` on Pre-Recorded Content (ffmpeg_builder.py)
- **Category:** FFmpeg  
- **Severity:** High  
- **Root Cause:** `+low_delay` forces single-reference P-frames, dropping B-frames on pre-recorded content.  
- **Symptom:** A/V desync on virtually all modern content.  
- **Fix:** Removed `-flags +low_delay` from input flags.  
- **Prevention:** Do not use low-latency decode flags for pre-recorded VOD content. Reserve for live ingest only.

## LL-05: `+fastseek` Masking Missing `+igndts` (ffmpeg_builder.py)
- **Category:** FFmpeg  
- **Severity:** Medium  
- **Root Cause:** `+fastseek` has zero benefit for pipe output and masked the missing `+igndts` flag.  
- **Symptom:** DTS discontinuities drop packets at GOP boundaries.  
- **Fix:** Replaced `+genpts+discardcorrupt+fastseek` with constants `FFLAGS_STREAMING` (`+genpts+discardcorrupt+igndts`).  
- **Prevention:** Use shared constants for FFmpeg flags; never hardcode flag strings in multiple files.

## LL-06: Missing h264_mp4toannexb BSF on COPY Path (ffmpeg_builder.py)
- **Category:** FFmpeg  
- **Severity:** High  
- **Root Cause:** H.264 from Plex/MP4 uses AVCC NAL units; MPEG-TS requires Annex B start codes.  
- **Symptom:** First GOP is corrupted or black on most decoders.  
- **Fix:** Added `-bsf:v h264_mp4toannexb` to video COPY path.  
- **Prevention:** Always add `h264_mp4toannexb` when remuxing H.264 into MPEG-TS.

## LL-07: Muxrate Type Error (ffmpeg_builder.py)
- **Category:** Type Safety  
- **Severity:** Medium  
- **Root Cause:** `profile.video_bitrate + profile.audio_bitrate` — if either is a string, Python concatenates or raises TypeError.  
- **Symptom:** Wrong muxrate ("4000128k") or crash.  
- **Fix:** Explicit `int()` cast before addition.  
- **Prevention:** Always cast user-supplied numeric fields to int/float at point of use.

## LL-08: Inconsistent fflags Between Builders (pipeline.py)
- **Category:** Consistency  
- **Severity:** Medium  
- **Root Cause:** `pipeline.py` hardcoded its own fflags string independently of `ffmpeg_builder.py`.  
- **Symptom:** Different error tolerance behaviour depending on code path.  
- **Fix:** Both files now import `FFLAGS_STREAMING` from `constants.py`.  
- **Prevention:** Single source of truth for shared configuration via `constants.py`.

## LL-09: Wrong Loudnorm Target (pipeline.py)
- **Category:** Audio  
- **Severity:** Medium  
- **Root Cause:** `pipeline.py` used `I=-24` (ATSC A/85); `ffmpeg_builder.py` used `I=-16` (EBU R128).  
- **Symptom:** Volume jumps between items depending on which code path was used.  
- **Fix:** Both now use `LOUDNORM_FILTER` constant (`I=-16`).  
- **Prevention:** Audio normalization parameters must be defined once in constants.

## LL-10: Missing hwdownload Before format= (pipeline.py)
- **Category:** FFmpeg / HW Accel  
- **Severity:** High  
- **Root Cause:** Hardware-decoded frames live on GPU surface. `format=yuv420p` can't convert from hardware surfaces.  
- **Symptom:** "Impossible to convert between the formats" crash on VAAPI/NVENC/QSV.  
- **Fix:** Prepend `hwdownload` filter when hardware acceleration is active.  
- **Prevention:** Always download frames from GPU before applying CPU-side filters.

## LL-11: EPG Timestamp Format (iptv.py)
- **Category:** Standards  
- **Severity:** Low  
- **Root Cause:** HTTP header used `%Y-%m-%d %H:%M:%S UTC` instead of ISO 8601.  
- **Symptom:** Log parsers confused by non-standard format.  
- **Fix:** Changed to `%Y-%m-%dT%H:%M:%SZ`.  
- **Prevention:** Use ISO 8601 for all machine-readable timestamps.

## LL-12: None start_time in EPG Emission (iptv.py)
- **Category:** Null Safety  
- **Severity:** High  
- **Root Cause:** `start_time` / `end_time_prog` may be `None` when all position-tracking paths fall through.  
- **Symptom:** `None.strftime()` → `AttributeError` → EPG generation silently fails for affected channel.  
- **Fix:** Added None guards with fallback to `now` / +30min.  
- **Prevention:** Always guard nullable values before calling methods on them, especially in long conditional chains.

## LL-13: Loop Variable `idx` Shadow (iptv.py)
- **Category:** Scoping  
- **Severity:** Medium  
- **Root Cause:** Two `for idx in range(current_item_index)` loops shadow the outer scope.  
- **Symptom:** Downstream code using `idx` gets last loop value → wrong cycle offset → Plex shows wrong "Now Playing".  
- **Fix:** Renamed loop variables to `_ci`.  
- **Prevention:** Never reuse outer-scope variable names in inner loops. Use throwaway names (`_ci`, `_i`) for loop-local counters.

## LL-14: Channel Number Type Mismatch (hdhomerun/api.py)
- **Category:** Type Safety  
- **Severity:** High  
- **Root Cause:** `Channel.number == channel_number` compares integer DB column to string path parameter.  
- **Symptom:** Zero rows returned → Plex gets error screen.  
- **Fix:** `int(channel_number)` cast with ValueError guard.  
- **Prevention:** Always cast path parameters to the DB column type before comparison.

## LL-15: Plex Cache Never Expires (plex.py)
- **Category:** Caching  
- **Severity:** Medium  
- **Root Cause:** `_plex_cache_loaded = True` set once, never reset. Credential/library changes invisible for process lifetime.  
- **Symptom:** Stale server URLs, missing new libraries.  
- **Fix:** Added TTL (5 minutes) via `_plex_cache_loaded_at` + `monotonic()`.  
- **Prevention:** All caches must have a TTL or explicit invalidation path.

## LL-16: Watchdog Lock Deadlock (process_watchdog.py)
- **Category:** Concurrency  
- **Severity:** Critical  
- **Root Cause:** `_kill_process` called inside `async with self._lock`. Kill can take up to 5s. Concurrent callers block.  
- **Symptom:** Multi-second freezes across all channels when one channel times out.  
- **Fix:** Collect timed-out processes under lock; kill them outside lock.  
- **Prevention:** Never perform I/O or long operations while holding an asyncio lock.

## LL-17: Deprecated `datetime.utcnow` in Dataclass Defaults (process_watchdog.py)
- **Category:** Deprecation  
- **Severity:** Low  
- **Root Cause:** `default_factory=datetime.utcnow` deprecated in Python 3.12+.  
- **Symptom:** DeprecationWarning; naive datetime.  
- **Fix:** Replaced with `_now()` returning tz-aware UTC.  
- **Prevention:** Same as LL-02.

## LL-18: MPEG-TS Buffer Trim Mid-Packet (throttler.py)
- **Category:** Protocol  
- **Severity:** High  
- **Root Cause:** Buffer overflow trim at arbitrary byte offset breaks MPEG-TS packet framing.  
- **Symptom:** Plex shows freeze or corruption artifact.  
- **Fix:** Align trim to nearest `0x47` sync byte.  
- **Prevention:** All MPEG-TS buffer operations must respect 188-byte packet boundaries.

## LL-19: Wrong Semaphore API (process_pool.py)
- **Category:** API Misuse  
- **Severity:** Medium  
- **Root Cause:** `asyncio.Semaphore.locked()` returns True only at count==0. The `if not locked: acquire` pattern has a race.  
- **Symptom:** Pool may reject requests when slots are available, or allow over-limit.  
- **Fix:** `try: acquire_nowait() except asyncio.QueueFull`.  
- **Prevention:** Use try/except around `acquire_nowait()` — never check `locked()` before acquiring.

## LL-20: Bare Integer Duration Not Parsed (parser.py)
- **Category:** Parsing  
- **Severity:** Medium  
- **Root Cause:** `parse_duration` only handled `HH:MM:SS`, `MM:SS`, and ISO 8601. Bare `"30"` fell through to `None`.  
- **Symptom:** `timedelta(seconds=None)` → `TypeError`. Item silently dropped from schedule.  
- **Fix:** Added `isdigit()` check at top of function.  
- **Prevention:** Parse functions should handle all reasonable input formats and log warnings for unrecognized ones.

## LL-21: Dead `mn-olympics-` Prefix (parser.py)
- **Category:** Tech Debt  
- **Severity:** Low  
- **Root Cause:** Hardcoded project-specific schedule file prefix from Channel 1980 work.  
- **Symptom:** None (dead code), but confuses maintainers.  
- **Fix:** Removed; replaced with `channel-{number}` pattern.  
- **Prevention:** Remove project-specific prefixes when the originating project is retired.

## LL-22: HD Flag From Name String (hdhomerun/api.py)
- **Category:** Logic  
- **Severity:** Low  
- **Root Cause:** `"HD" in channel.name.upper()` — false positives ("HDTV Classics") and false negatives (1080p without "HD" in name).  
- **Symptom:** Plex guide sorts channels incorrectly.  
- **Fix:** Check `is_hd` DB field → `resolution` field → name heuristic (with SD exclusion).  
- **Prevention:** Prefer structured data (DB fields, resolution) over string heuristics.

## LL-23: yaml.FullLoader Allows Code Execution (config.py)
- **Category:** Security  
- **Severity:** Critical  
- **Root Cause:** `yaml.FullLoader` permits `!!python/object` constructs in user-supplied config files.  
- **Symptom:** Arbitrary code execution via crafted config.yaml.  
- **Fix:** Already using `yaml.safe_load` — confirmed correct.  
- **Prevention:** Always use `yaml.safe_load()` for user-supplied YAML. Never use `FullLoader` or `UnsafeLoader`.

## LL-24: Deprecated `datetime.utcnow` in Scheduling Engine (engine.py)
- **Category:** Deprecation  
- **Severity:** Low  
- **Root Cause:** Same as LL-02/LL-17.  
- **Fix:** Added `_utcnow()` helper, replaced call.  
- **Prevention:** Project-wide ban on `datetime.utcnow()`.

---

**Generated:** 2026-03-20  
**Patches Applied:** 16 (across 14 files)  
**Issues Documented:** 24
