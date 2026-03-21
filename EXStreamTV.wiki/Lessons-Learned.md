# EXStreamTV — Lessons Learned

> **Wiki mirror:** Matches [`docs/LESSONS_LEARNED.md`](https://github.com/roto31/EXStreamTV/blob/main/docs/LESSONS_LEARNED.md) on `main`. Edit the repository file first, then refresh this page.

**Document version:** 1.3  
**Audit date:** 2026-03-20 (codebase); **LL-031–035** Confluence / publishing (2026-03-21 – 2026-03-22)  
**Scope:** Full codebase audit — 30 confirmed issues across 18 files; plus 5 documentation/tooling lessons (LL-031–035)  
**Status:** Active — rules and skills derived from this document are enforced via `.cursor/rules/exstreamtv-safety.mdc` (runtime) and `.cursor/rules/exstreamtv-confluence.mdc` (docs/Confluence paths)

---

## How to Use This Document

Each entry follows the format:

| Field | Meaning |
|---|---|
| **ID** | Unique identifier, referenced by Cursor rules |
| **Category** | Functional area |
| **Severity** | 🔴 Critical / 🟡 High / 🟡 Medium |
| **File(s)** | Files containing the bug |
| **Root Cause** | Why it happened |
| **Symptom** | What the user/system experiences |
| **Fix Applied** | What was changed |
| **Prevention Rule** | Which Cursor rule prevents recurrence |

---

## LL-001 — Infinite Loop on Empty Collection

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/playout/scheduler.py` |
| **Root Cause** | `while current_time < end` loop only advanced `current_time` inside `if items_result.items:`. If `_schedule_item()` returned an empty list (broken collection, empty library, FFprobe timeout), `current_time` never advanced. The loop condition remained permanently `True`. |
| **Symptom** | Service process spins at 100% CPU until killed. All channels freeze. No error logged. |
| **Fix Applied** | Added `else` branch that advances `schedule_index` unconditionally and breaks if all schedule items have been exhausted without producing output. |
| **Prevention Rule** | RULE 05 — Scheduler Loops: Always Guard Against Empty Output |

---

## LL-002 — Naive/Aware Datetime Collision in Channel Position Tracking

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/streaming/channel_manager.py` |
| **Root Cause** | `datetime.utcnow()` returns a naive datetime. `position.playout_start_time` loaded from SQLite (no `PARSE_DECLTYPES` configured) may be naive or tz-aware depending on the ORM path. Subtracting them raises `TypeError` or silently produces a wrong `elapsed` value. |
| **Symptom** | On service restart, channel jumps to wrong position in schedule. EPG and actual playback diverge. Occasional `TypeError` in logs. |
| **Fix Applied** | Added `_utcnow()` helper returning `datetime.now(tz=timezone.utc)`. Added `_ensure_utc()` normaliser applied to all DB-sourced datetimes before arithmetic. Replaced all `datetime.utcnow()` calls. |
| **Prevention Rule** | RULE 01 — Datetime: Always Timezone-Aware |

---

## LL-003 — Synchronous Database Call Blocking Asyncio Event Loop

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/streaming/channel_manager.py` (`_save_position`) |
| **Root Cause** | `_save_position` is `async def` but calls synchronous SQLAlchemy `.execute()` and `.commit()` directly. The blocking call freezes the event loop for the duration of the DB write. |
| **Symptom** | Periodic Plex buffering spinners during position saves. All channels and HTTP requests stall simultaneously. Duration scales with disk I/O latency (worse on spinning disks or network storage). |
| **Fix Applied** | Refactored `_save_position` to dispatch synchronous work via `asyncio.get_event_loop().run_in_executor(None, self._save_position_sync)`. |
| **Prevention Rule** | RULE 06 — Database Sessions: Never Block the Event Loop |

---

## LL-004 — `-flags +low_delay` Drops B-Frames → A/V Desync

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/transcoding/ffmpeg_builder.py` |
| **Root Cause** | `-flags +low_delay` was ported from ErsatzTV without verifying its semantics in a pre-recorded content context. This flag forces single-reference P-frames at the decoder, dropping B-frames. Virtually all modern H.264/HEVC content uses B-frames. |
| **Symptom** | Audio runs ahead of video progressively. Dropped frames. Visual stuttering. Gets worse over long sessions. |
| **Fix Applied** | Removed `-flags +low_delay` entirely from the input flags block. |
| **Prevention Rule** | RULE 02 — FFmpeg Flags: Use constants.py; RULE 16 — ErsatzTV Ports: Verify Flag Semantics |

---

## LL-005 — `+fastseek` Instead of `+igndts` — DTS Discontinuities

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/transcoding/ffmpeg_builder.py` |
| **Root Cause** | `+fastseek` (a seek optimisation flag, irrelevant for pipe output) was present instead of `+igndts`. Without `+igndts`, streams where DTS > PTS (common with B-frame content, YouTube, Archive.org, Plex transcodes) cause FFmpeg to emit DTS discontinuity warnings and drop packets at GOP boundaries. |
| **Symptom** | Brief freezes every few minutes. `DTS discontinuity` in FFmpeg logs. |
| **Fix Applied** | Replaced `+fastseek` with `+igndts` in the fflags string. Moved to `FFLAGS_STREAMING` constant. |
| **Prevention Rule** | RULE 02 — FFmpeg Flags: Use constants.py |

---

## LL-006 — Missing `h264_mp4toannexb` on COPY Path

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/transcoding/ffmpeg_builder.py` |
| **Root Cause** | When `VideoFormat.COPY` is selected, `-c:v copy` was written without the `h264_mp4toannexb` bitstream filter. Plex sends H.264 in MP4/AVCC format (length-prefixed NAL units). MPEG-TS requires Annex B start codes. |
| **Symptom** | Black screen or heavily corrupted video for the first GOP (typically 2–5 seconds) when a Plex channel starts or resumes. |
| **Fix Applied** | Added `-bsf:v h264_mp4toannexb` unconditionally after `-c:v copy`. Added `BSF_H264_ANNEXB` constant. |
| **Prevention Rule** | RULE 03 — H.264 COPY Path: Always Add Bitstream Filter |

---

## LL-007 — Wrong XMLTV Timestamp Format

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/api/iptv.py` |
| **Root Cause** | HTTP response header used `%Y-%m-%d %H:%M:%S UTC` — an ISO 8601 format, not valid XMLTV. The XMLTV spec requires `YYYYMMDDHHMMSS +HHMM` with no dashes or colons. Two different format strings existed in the same file. |
| **Symptom** | Programme entries using the wrong format are silently rejected by Plex. Guide shows gaps or missing programmes. |
| **Fix Applied** | Standardised all XMLTV timestamps to `%Y%m%d%H%M%S +0000`. Fixed header to ISO 8601 (`%Y-%m-%dT%H:%M:%SZ`). |
| **Prevention Rule** | RULE 07 — XMLTV Timestamps: Exactly One Format |

---

## LL-008 — `start_time = None` Not Guarded Before `strftime()`

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/api/iptv.py` |
| **Root Cause** | Multiple conditional assignment branches could leave `start_time` as `None`. The downstream `start_time.strftime(...)` call had no guard, raising `AttributeError` silently (caught by a broad `except Exception`), killing EPG generation for the affected channel with no visible error. |
| **Symptom** | Specific channels show no guide data in Plex. No error in the UI. `AttributeError` buried in logs. |
| **Fix Applied** | Added explicit `if start_time is None:` guard with `now` fallback immediately before all `strftime()` calls in the EPG emission block. |
| **Prevention Rule** | RULE 08 — EPG Variables: Guard None Before strftime |

---

## LL-009 — Loop Variable `idx` Shadows Outer Counter

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/api/iptv.py` |
| **Root Cause** | Two inner `for idx in range(current_item_index):` loops shadowed the outer `current_item_index` variable. After the loops, downstream code referencing `idx` received the last loop iteration value instead of the outer counter, corrupting the cycle offset arithmetic used to calculate EPG start times. |
| **Symptom** | EPG shows the wrong programme in the "Now Playing" slot. Guide is shifted by a variable number of items. |
| **Fix Applied** | Renamed both inner loop variables to `_ci` throughout their bodies. |
| **Prevention Rule** | RULE 09 — Loop Variables: Never Shadow Outer Counters |

---

## LL-010 — Channel Number String vs Integer in DB Query

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/hdhomerun/api.py` |
| **Root Cause** | FastAPI path parameters arrive as `str`. `Channel.number` is stored as `int`. The query `Channel.number == channel_number` compared int column to string value. SQLite coerces this in most cases but strict ORM type checking returns zero rows. |
| **Symptom** | Plex "Could not tune channel" error. Channel lookup returns None. Error screen displayed instead of stream. |
| **Fix Applied** | Added explicit `int(channel_number)` cast with `HTTPException(400)` on `ValueError`. Applied to all channel number lookups in the HDHomeRun API. |
| **Prevention Rule** | RULE 10 — Channel Number: Always Cast to int |

---

## LL-011 — Two Conflicting FFmpeg Command Builders

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/ffmpeg/pipeline.py`, `exstreamtv/transcoding/ffmpeg_builder.py` |
| **Root Cause** | Two independent FFmpeg command builders coexist with different flag sets, different loudnorm targets, different error handling, and different output format configurations. Channels may use either builder depending on code path, producing inconsistent behaviour. |
| **Symptom** | Channels behave differently from each other with no visible reason. Volume jumps between channels. Some channels have correct MPEG-TS headers; others don't. |
| **Fix Applied** | Created `exstreamtv/ffmpeg/constants.py` as single source of truth. Both builders import shared constants. Long-term resolution: merge into a single canonical factory. |
| **Prevention Rule** | RULE 02 — FFmpeg Flags: Use constants.py |

---

## LL-012 — `format=yuv420p` Without `hwdownload` Crashes HW Accel

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/ffmpeg/pipeline.py` (`_build_filter_chain`) |
| **Root Cause** | `format=yuv420p` was appended unconditionally, even when hardware decoding was active. Hardware-decoded frames live on a GPU surface (CUDA/QSV/VAAPI). Applying a CPU-side filter directly to a GPU surface raises "Impossible to convert between the formats" and FFmpeg exits. |
| **Symptom** | Hardware-accelerated channels fail immediately with FFmpeg error. Software fallback activates silently (or channel never starts). |
| **Fix Applied** | Added `is_hw` detection. Prepend `hwdownload` to the filter chain when hardware decode is active. |
| **Prevention Rule** | RULE 04 — Hardware Accel Filter Chain: hwdownload Before format= |

---

## LL-013 — Process Watchdog Holds Lock During 5-Second Kill Operation

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/streaming/process_watchdog.py` |
| **Root Cause** | `_kill_process` was called inside `async with self._lock`. The kill operation calls `asyncio.wait_for(..., timeout=5.0)` and potentially `process.wait()`. All of this blocked the lock for up to 10 seconds per killed channel, deadlocking `register_process`, `report_output`, and all other lock acquirers. |
| **Symptom** | During a channel failure/restart, all other channels stop reporting output. Watchdog triggers cascade kills. Entire service becomes unresponsive for 5–10 seconds. |
| **Fix Applied** | Collected timed-out processes inside the lock, executed kills outside it. |
| **Prevention Rule** | RULE 11 — Async Locks: Never Await Blocking I/O Inside Lock |

---

## LL-014 — MPEG-TS Buffer Trim Not Aligned to Sync Byte

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/streaming/throttler.py` |
| **Root Cause** | When the throttler buffer overflowed, it trimmed by simple byte slice: `self._buffer[-max_size:]`. This could cut mid-packet, delivering a stream with broken MPEG-TS framing (sync byte not at offset 0). |
| **Symptom** | Brief freeze or corruption artefact in Plex during high-load periods or at stream start. Plex shows a spinning wheel, then recovers. |
| **Fix Applied** | After trimming, find the first `0x47` sync byte and align the buffer to it. Log overflow events as warnings. |
| **Prevention Rule** | RULE 12 — MPEG-TS Buffer Operations: Align to Sync Byte |

---

## LL-015 — `datetime.utcnow` as dataclass default_factory (Deprecated)

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/streaming/process_watchdog.py` |
| **Root Cause** | `field(default_factory=datetime.utcnow)` used deprecated API. Deprecated in Python 3.12, removed in 3.14. Also produces naive datetimes inconsistent with tz-aware datetimes used elsewhere. |
| **Symptom** | `DeprecationWarning` in Python 3.12+. Will raise `AttributeError` in Python 3.14+. Mixed naive/aware datetimes in watchdog code. |
| **Fix Applied** | Replaced with `_now()` helper returning `datetime.now(tz=timezone.utc)`. |
| **Prevention Rule** | RULE 01 — Datetime: Always Timezone-Aware |

---

## LL-016 — Muxrate Type Error — String Concatenation Instead of Addition

| Field | Detail |
|---|---|
| **Severity** | 🟡 High |
| **File** | `exstreamtv/transcoding/ffmpeg_builder.py` |
| **Root Cause** | `f"{profile.video_bitrate + profile.audio_bitrate}k"` — if either field is stored as `str` in the DB, Python concatenates strings instead of adding integers. `"4000" + "128"` = `"4000128"` → muxrate of 4 Gbps. No exception raised. |
| **Symptom** | MPEG-TS mux buffer massively over-provisioned. Plex may fail to buffer stream, show excessive memory usage, or reject the stream entirely. |
| **Fix Applied** | Added explicit `int()` cast: `int(profile.video_bitrate) + int(profile.audio_bitrate)`. |
| **Prevention Rule** | RULE 13 — Muxrate: Always Explicit int Cast |

---

## LL-017 — HD Flag Derived From Channel Name String

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/hdhomerun/api.py` |
| **Root Cause** | `"HD": 1 if "HD" in channel.name.upper() else 0` — channels named "HDTV Classics" get HD=1 regardless of actual resolution; 1080p channels without "HD" in the name get HD=0. Plex uses the HD flag to sort and prioritise the channel guide. |
| **Symptom** | Channels sorted incorrectly in Plex guide. HD channels shown below SD. |
| **Fix Applied** | Check `is_hd` DB field first, then `resolution` field, then name heuristic as last resort. |
| **Prevention Rule** | RULE 10 (general type safety) |

---

## LL-018 — `parse_duration` Returns None on Bare Integer Input

| Field | Detail |
|---|---|
| **Severity** | 🟡 High |
| **File** | `exstreamtv/scheduling/parser.py` |
| **Root Cause** | `parse_duration("30")` — bare integer with no unit — returned `None` because `total_seconds` stayed 0 after all regex patterns failed to match. Callers passing `None` to `timedelta(seconds=None)` raised `TypeError`. Item silently dropped from schedule. |
| **Symptom** | Schedule items with bare integer durations are silently skipped. Gaps appear in the channel schedule. Guide shows dead air. |
| **Fix Applied** | Added early `if duration_str.isdigit(): return int(duration_str) or None` branch. |
| **Prevention Rule** | RULE 17 — duration: parse_duration Handles Bare Integers |

---

## LL-019 — Module-Level Cache Without TTL

| Field | Detail |
|---|---|
| **Severity** | 🟡 High |
| **File** | `exstreamtv/streaming/resolvers/plex.py` |
| **Root Cause** | `_plex_cache_loaded = True` set on first load, never reset. Credential changes, server URL changes, and library additions are invisible for the entire process lifetime. |
| **Symptom** | After changing Plex server credentials or adding a library, channels continue using old credentials until service restart. |
| **Fix Applied** | Added `_plex_cache_loaded_at` timestamp and `_PLEX_CACHE_TTL_SECONDS = 300` TTL. Cache is invalidated and reloaded when age exceeds TTL. |
| **Prevention Rule** | RULE 15 — Caches: Always Include TTL |

---

## LL-020 — `_generate_sequence_playlist` Uses `datetime.utcnow()` for Anchor

| Field | Detail |
|---|---|
| **Severity** | 🟡 High |
| **File** | `exstreamtv/scheduling/engine.py` |
| **Root Cause** | `current_time = datetime.utcnow()` at the start of playlist generation. Produces a naive datetime used as the anchor for all subsequent `timedelta` additions and EPG start time calculations. |
| **Symptom** | EPG anchor drifts over time if mixed with tz-aware datetimes. Guide shows programmes at wrong times after service restart or DST transition. |
| **Fix Applied** | Replaced with `_utcnow()` helper returning `datetime.now(tz=timezone.utc)`. |
| **Prevention Rule** | RULE 01 — Datetime: Always Timezone-Aware |

---

## LL-021 — Wrong asyncio.Semaphore API Usage

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/ffmpeg/process_pool.py` |
| **Root Cause** | `asyncio.Semaphore.locked()` returns `True` only when count == 0 (fully exhausted). The pattern `if not semaphore.locked(): semaphore.acquire_nowait()` is semantically wrong — the correct non-blocking try-acquire uses `try: semaphore.acquire_nowait() except asyncio.QueueFull:`. |
| **Symptom** | Non-critical — logic happens to work in most cases. Confusing to future maintainers. Risk of subtle race condition if semaphore internal state model changes. |
| **Fix Applied** | Replaced with `try/except asyncio.QueueFull` pattern. |
| **Prevention Rule** | RULE 18 — Semaphore: Use try/except for acquire_nowait |

---

## LL-022 — yaml.FullLoader on User Config Files

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/config.py` |
| **Root Cause** | `yaml.load(f, Loader=yaml.FullLoader)` used instead of `yaml.safe_load()`. `FullLoader` allows `!!python/object`, `!!python/tuple`, and other Python-specific YAML constructs. Inconsistent with `scheduling/parser.py` which correctly uses `safe_load`. |
| **Symptom** | Security risk on user-supplied config files. Inconsistent parsing behaviour between config and schedule YAML. |
| **Fix Applied** | Replaced with `yaml.safe_load(f)`. |
| **Prevention Rule** | RULE 14 — YAML: Always Use safe_load |

---

## LL-023 — `mn-olympics-` Hardcoded Path Prefix in Schedule Parser

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/scheduling/parser.py` |
| **Root Cause** | `find_schedule_file()` included `f"mn-olympics-{channel_number}.yml"` as the first candidate path. This was a project-specific artifact from Channel 1980 (MN 1980 Winter Olympics / WCCO) development work left in the general-purpose parser. |
| **Symptom** | No functional impact for non-olympics channels (falls through to generic names). Confuses future contributors. Dead code. |
| **Fix Applied** | Removed `mn-olympics-` prefix entries from the candidate list. |
| **Prevention Rule** | Do not hardcode project-specific path prefixes in general-purpose utilities. |

---

## LL-024 — `scheduling/engine_v2.py` Not Wired Into Router

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/scheduling/engine_v2.py` |
| **Root Cause** | `engine_v2.py` imports from `database.models_v2` (not `database.models`) and implements a superior `generate_timeline` method with correct zero-duration guards. However it is never imported in `main.py` or anywhere in the active code path. Any fixes in v2 are dead code. |
| **Symptom** | Improvements to the scheduling engine do not take effect. Developers may patch v2 believing they fixed a bug, but the fix never runs. |
| **Fix Applied** | Document as dead code. Wire into active path or delete in next refactor. |
| **Prevention Rule** | Never maintain a `_v2` file that is not wired into the active code path without explicit documentation. |

---

## LL-025 — `api/epg_generator_v2.py` Dead Code

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/api/epg_generator_v2.py` |
| **Root Cause** | `epg_generator_v2.py` (8702 chars) is a partial reimplementation of the EPG generator not referenced by any router or active code path. The 119KB `iptv.py` remains the active path. |
| **Symptom** | Any EPG fixes applied to v2 are invisible. `iptv.py` continues to run with its bugs. |
| **Fix Applied** | Document as dead code. Wire in or delete. |
| **Prevention Rule** | Same as LL-024. |

---

## LL-026 — `async for` Double-Indent Leaves Zombie FFmpeg on Channel Stop

| Field | Detail |
|---|---|
| **Severity** | 🟡 High |
| **File** | `exstreamtv/streaming/channel_manager.py` |
| **Root Cause** | The body of `async for chunk in streamer.stream(...)` had 8 spaces of indent instead of 4. Python accepted the syntax but the `if not self._is_running: break` check at the wrong indent level did not cleanly release the streamer coroutine on channel stop. |
| **Symptom** | After stopping a channel, FFmpeg process may continue running for up to one segment duration before being killed by the watchdog. Memory and CPU leak during channel cycling. |
| **Fix Applied** | Corrected indentation of the `async for` body. |
| **Prevention Rule** | Use a linter (`flake8`, `ruff`) in CI to catch indent anomalies. |

---

## LL-027 — SQLite DB Backup Committed to Repository

| Field | Detail |
|---|---|
| **Severity** | 🔴 Security |
| **File** | `exstreamtv.db.backup.20260126_224008` (repo root) |
| **Root Cause** | A SQLite backup file was committed directly to the repository. The file may contain Plex tokens, server URLs, channel configs, API keys, and user data. |
| **Symptom** | Any person with read access to the repository can extract credentials and access the Plex server. |
| **Fix Applied** | `git rm --cached` + `.gitignore` entries for `*.db.backup.*` and `*.db`. Credentials should be rotated. |
| **Prevention Rule** | Add `*.db`, `*.db-*`, `*.sqlite`, `*.db.backup.*` to `.gitignore` on project creation. Never commit database files. |

---

## LL-028 — `_get_next_playout_item` Missing `finally: db.close()`

| Field | Detail |
|---|---|
| **Severity** | 🔴 Critical |
| **File** | `exstreamtv/streaming/channel_manager.py` |
| **Root Cause** | `_get_next_playout_item` opened a DB session but the confirmed code showed a `finally: db.close()` was present. Re-evaluated as correctly handled. |
| **Status** | Retracted — `finally: db.close()` confirmed present. |

---

## LL-029 — `_build_filter_chain` Always Appends format=yuv420p (No-Op Path)

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **File** | `exstreamtv/ffmpeg/pipeline.py` |
| **Root Cause** | `format=yuv420p` was appended even when `scaling_mode` is `None` and no other filters are active, creating a single-element filter chain with no purpose in the software path. |
| **Symptom** | Unnecessary FFmpeg filter overhead. For hardware paths, crash (see LL-012). |
| **Fix Applied** | Gated on actual filter content. Returns `""` when no filters are needed. |
| **Prevention Rule** | RULE 04 |

---

## LL-030 — `iptv_router` Has No URL Prefix

| Field | Detail |
|---|---|
| **Severity** | 🟡 Low |
| **File** | `exstreamtv/main.py` |
| **Root Cause** | `include_router(iptv_router, tags=["IPTV"])` — no `prefix`. Routes mount at `/xmltv`, `/m3u`, etc. (root level). Intentional for Plex compatibility but not documented. |
| **Symptom** | No functional issue. Future developers may accidentally create routes that collide with the IPTV router's root-level paths. |
| **Fix Applied** | Added inline comment explaining intentional no-prefix for Plex DVR compatibility. |
| **Prevention Rule** | Document intentional deviations from conventions inline. |

---

## LL-031 — Atlassian MCP Confluence Create Page Uses ADF (Not Storage)

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **Area** | Documentation tooling / Confluence |
| **Root Cause** | Cursor **Atlassian MCP** `createConfluencePage` accepts **ADF** JSON in `body`. Passing HTML/storage or expecting automatic Mermaid from raw Markdown does not apply. Workflows that embed the whole wiki in a single **Markdown code block** in ADF do not execute Mermaid or render Markdown as on GitHub. |
| **Symptom** | Confluence pages show a giant Markdown code fence; diagrams are not interactive. Expectation mismatch vs GitHub wiki rendering. |
| **Fix Applied** | Added `scripts/publish_confluence_wiki_tree.py` (and existing `publish_confluence_mirror.py`) using **Confluence REST API** with `body.storage` and `{code:language=mermaid}` macros via shared `confluence_markdown_storage.py`. |
| **Prevention Rule** | RULE DOC-01 — Confluence: Choose Storage REST vs ADF MCP |

---

## LL-032 — PEP 723 Script Dependencies Require `uv run scripts/…`, Not `uv run python scripts/…`

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **Area** | Tooling / uv |
| **Root Cause** | Inline `# /// script` dependencies in `scripts/publish_confluence_*.py` are honored when **uv** executes the **script path** as the entrypoint. Running `uv run python scripts/foo.py` uses the project interpreter without necessarily attaching the script’s declared dependencies (e.g. `markdown`), causing `ModuleNotFoundError`. |
| **Symptom** | Local or CI publish commands fail on `import markdown` despite the script header listing it. |
| **Fix Applied** | Documented correct invocation: `uv run scripts/publish_confluence_wiki_tree.py` (and same pattern for `publish_confluence_mirror.py`). |
| **Prevention Rule** | RULE DOC-02 — uv: Invoke PEP 723 Scripts by Path |

---

## LL-033 — Confluence Duplicate Page Titles in One Space (Landing vs Wiki File)

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **Area** | Documentation / Confluence |
| **Root Cause** | Confluence requires **unique page titles per space**. A root landing page titled `EXStreamTV` cannot coexist with a child from `EXStreamTV.wiki/EXStreamTV.md` if both use the same title. |
| **Symptom** | API create/update fails with title conflict, or accidental overwrite/confusion in navigation. |
| **Fix Applied** | `wiki_sidebar_order.confluence_wiki_child_title()` maps stem `EXStreamTV` → **`EXStreamTV Wiki`** for the wiki-backed child only; root stays **`EXStreamTV`**. |
| **Prevention Rule** | RULE DOC-03 — Confluence: Avoid Title Collisions |

---

## LL-034 — httpx Default `Content-Type: application/json` Breaks Confluence Attachment Uploads (HTTP 415)

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **Area** | Documentation tooling / Confluence REST |
| **File(s)** | `scripts/publish_confluence_wiki_tree.py`, `scripts/publish_confluence_mirror.py` (`httpx.Client` default headers) |
| **Root Cause** | A shared **`httpx.Client`** was constructed with default headers **`Content-Type: application/json`**. Confluence’s **`POST …/content/{id}/child/attachment`** expects **`multipart/form-data`** (file field). The client-wide JSON content type is applied to multipart requests as well, so the server responds **415 Unsupported Media Type**. This is **not** specific to SVG — the same bug breaks **all** attachment uploads (Kroki **mermaid-*.svg**, wiki **screenshots** `.png`/`.gif`, etc.). |
| **Symptom** | Publish run completes page body updates but logs many lines: `Attachment failed <name>: 415`. Mermaid diagrams referenced via `ri:attachment` are missing; screenshot images in wiki pages do not attach. |
| **Fix Applied** | Removed **`Content-Type`** from the Confluence client’s default headers; keep **`Accept: application/json`**. Requests using **`json=…`** still get the correct JSON content type from httpx; **`files=…`** uploads receive proper **`multipart/form-data`** with a boundary. |
| **Prevention Rule** | RULE DOC-05 — Confluence REST: Never Default `Content-Type: application/json` on Clients Used for Multipart |

**Reference log (2026-03-21):** First full tree publish after introducing the JSON default — dozens of `Attachment failed mermaid-….svg: 415` and screenshot `415` lines; landing and page bodies still “Published … Done.”

---

## LL-035 — Wiki Tree Publisher Attempts Second Root Page With Same Title (HTTP 400)

| Field | Detail |
|---|---|
| **Severity** | 🟡 Medium |
| **Area** | Documentation tooling / Confluence REST |
| **File(s)** | `scripts/publish_confluence_wiki_tree.py` |
| **Root Cause** | On a **second** publish run, if **`CONFLUENCE_ROOT_PAGE_ID`** was unset, the script always **`POST`**ed a new page with the root title (**`EXStreamTV`**). Confluence enforces **unique page titles per space**, so the create fails after the first successful run. |
| **Symptom** | `400 Bad Request` — *A page with this title already exists: A page already exists with the same TITLE in this space*. |
| **Fix Applied** | Before create, **`GET …/content?spaceKey=&title=&type=page&status=current`** (with **`expand=ancestors`**) to reuse an existing root id when **`parent_id`** matches (or a single unambiguous hit). Users may still set **`CONFLUENCE_ROOT_PAGE_ID`** to skip lookup. |
| **Prevention Rule** | RULE DOC-06 — Confluence: Reuse Root Page or Set `CONFLUENCE_ROOT_PAGE_ID` |

---

## Summary Statistics

| Severity | Count |
|---|---|
| 🔴 Critical | 14 |
| 🟡 High | 9 |
| 🟡 Medium | 11 |
| 🟡 Low | 1 |
| 🔴 Security | 1 |
| Retracted | 1 |
| **Total confirmed** | **35** |

| Category | Count |
|---|---|
| A/V sync / playback | 6 |
| EPG / Plex guide | 5 |
| Async/event loop | 3 |
| Datetime handling | 4 |
| FFmpeg flags | 4 |
| Scheduler / playout | 2 |
| Resource management | 3 |
| Dead code | 2 |
| Security | 1 |
| Documentation / Confluence / uv | 5 |
