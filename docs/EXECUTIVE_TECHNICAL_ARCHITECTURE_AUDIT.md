# Executive Technical Architecture Audit

**Document**: Post–Clock Authority Cutover Architecture Audit  
**Source**: Clock Authority Validation Report (synthesis)  
**Classification**: Internal – Engineering Leadership, Infrastructure Review, Production Readiness

---

## 1) Executive Summary

### High-Level Status of System Stability Post-Cutover

The Broadcast Clock Authority cutover introduces a single source of truth for schedule position. Automated validation confirms clock duration integrity and rebuild logic alignment. XMLTV generation has been decoupled from URL resolution and ffprobe. Concurrency and locking are structured without identified deadlock risk.

### What Was Fixed

- **Duration propagation**: Fallback chain (media_item.duration → playout_item.duration → 1800) prevents zero or None durations.
- **EPG/XML path**: Resolution removed from timeline build; `skip_resolution=True` enforces metadata-only EPG generation.
- **Rebuild logic**: Rebuild task uses `clock.total_cycle_duration` as primary authority before PlayoutItem-based fallback.
- **CancelledError handling**: Shadowed `asyncio` import removed to avoid UnboundLocalError on cancellation.

### What Was Eliminated

- Resolution and ffprobe from EPG/XMLTV generation.
- PlayoutItem `start_time >= now` as the only source for “remaining content” for clock-based channels.
- Risk of zero `total_cycle_duration` causing mass rebuilds when clocks have valid timelines.

### Current Production Posture

Automated validation (clock integrity, rebuild count) has passed. XMLTV and concurrency are validated by code and design. IPTV, Plex, and HDHomeRun streaming stability are **not yet verified**; runtime soak tests are required before production sign-off.

---

## 2) Architectural Layer-by-Layer Audit

### Broadcast Clock Authority

| Aspect | Detail |
|--------|--------|
| **What changed** | Clock is sole schedule authority; position from `(now - anchor_time) % total_cycle_duration`. |
| **Previous risk** | Confusion between PlayoutItem timestamps and clock position for continuous channels. |
| **Evidence of stability** | All channels with a timeline report `total_cycle_duration > 0`; sum of item durations matches clock total; no drift. |
| **Remaining uncertainty** | None from the validation report. |

### Canonical Timeline

| Aspect | Detail |
|--------|--------|
| **What changed** | `build_from_playout(..., skip_resolution=True)` uses metadata-only duration; no URL resolution or ffprobe for EPG path. |
| **Previous risk** | Resolution failures excluding items from the timeline; empty or sparse EPG. |
| **Evidence of stability** | Fallback chain prevents zero or None durations; guarded assertions added for `canonical_duration > 0`. |
| **Remaining uncertainty** | None from the report. |

### Duration Propagation

| Aspect | Detail |
|--------|--------|
| **What changed** | `_playout_item_to_dto` includes duration from `(finish_time - start_time).total_seconds()`; `_get_metadata_duration` follows media_item → playout_item → 1800. |
| **Previous risk** | Zero or None durations causing `total_cycle_duration = 0`, rebuild storms, clock invalidation. |
| **Evidence of stability** | Validation confirms no `canonical_duration == 0` and no None propagation; fallback 1800 used when metadata is absent or zero. |
| **Remaining uncertainty** | None from the report. |

### Rebuild Logic

| Aspect | Detail |
|--------|--------|
| **What changed** | Rebuild task checks `clock.total_cycle_duration >= 1800` first; PlayoutItem-based check only when no clock or short cycle. |
| **Previous risk** | `PlayoutItem.start_time >= now` returning nothing for clock-based channels → “0.0 min remaining” → mass rebuild. |
| **Evidence of stability** | Rebuild run: 0 channels rebuilt (0.0%); below 5% threshold. |
| **Remaining uncertainty** | None from the report. |

### Resolver Isolation (Plex)

| Aspect | Detail |
|--------|--------|
| **What changed** | EPG no longer calls resolution during timeline build; resolution happens at stream time. |
| **Previous risk** | EPG blocked or delayed by resolver failures. |
| **Evidence of stability** | Plex DTO includes `plex_rating_key`; `server_url` and `token` come from config at resolve time; contract not weakened. |
| **Remaining uncertainty** | Report states “No metadata gap”; no runtime Plex tune test. |

### XMLTV Generation

| Aspect | Detail |
|--------|--------|
| **What changed** | `build_epg_from_clock` uses clock and timeline only; no resolution or ffprobe. |
| **Previous risk** | 500 errors, CancelledError leakage, ffprobe during EPG build. |
| **Evidence of stability** | Design review: no resolution in EPG path; `skip_resolution=True` in `load_timeline_async`; no ffprobe; 500 and CancelledError addressed in prior session. |
| **Remaining uncertainty** | None from the report. |

### Concurrency / Locking Model

| Aspect | Detail |
|--------|--------|
| **What changed** | Per-channel lock via `_get_timeline_lock(channel_id)`; `AsyncCancellationGuard.safe_lock` for shutdown-safe acquisition. |
| **Previous risk** | Concurrent timeline load per channel; CancelledError during lock wait. |
| **Evidence of stability** | Per-channel isolation; no global lock; lock scope limited to timeline load and clock creation; no nested acquisition; CancelledError re-raised and lock released. |
| **Remaining uncertainty** | None from the report. |

---

## 3) Risk Assessment Matrix

| Risk Area | Status | Severity | Evidence | Remaining Risk |
|-----------|--------|----------|----------|----------------|
| Duration collapse | Mitigated | High | Fallback chain; no zero/None in validation | Low |
| Mass rebuild storms | Mitigated | High | 0% rebuild; clock-first logic | Low |
| Clock invalidation | Mitigated | Medium | Clock immutable once created | Low |
| XMLTV 500 / EPG failure | Mitigated | High | Resolution removed; CancelledError fixed | Low |
| Resolver contract violation | None | High | Design review; metadata from config | Low |
| Race conditions / deadlock | Mitigated | Medium | Per-channel locks; design review | Low |
| IPTV streaming failure | Unverified | High | Manual verify required | Medium |
| Plex streaming failure | Unverified | High | Manual verify required | Medium |
| HDHomeRun failure | Unverified | Medium | Manual verify required | Medium |
| Restart loops | Unverified | High | Manual verify required | Medium |

---

## 4) Operational Verification Gaps

The report explicitly marks these as **Manual verify required**; they are **not** assumed to have passed:

| Gap | Required Runtime Test |
|-----|------------------------|
| IPTV streaming stable | Tune `/iptv/channel/{id}.ts` for multiple channels; confirm 200; observe streams for at least 5 minutes without restart or failure. |
| Plex streaming stable | Tune Plex DVR on channels with Plex content; confirm no “Stream unavailable” or “Missing Plex connection info”; observe stability. |
| HDHomeRun stable | Tune HDHomeRun clients; confirm stable playback; no timeline invalidation or stream drop. |
| No restart loops | Run server for 5+ minutes under IPTV/Plex/HDHomeRun load; inspect logs for repeated restarts, cascading errors, or channel respawn. |

---

## 5) Production Readiness Score

| Layer | Score (0–10) | Justification |
|-------|---------------|---------------|
| Broadcast Clock Authority | 9 | Automated validation passed; duration integrity confirmed. |
| Canonical Timeline | 9 | Metadata-only EPG path in place; duration fallback enforced. |
| Duration Propagation | 9 | No zero/None durations observed; fallback chain implemented. |
| Rebuild Logic | 9 | 0% rebuild rate; clock-first logic validated. |
| Resolver Isolation (Plex) | 8 | Design and metadata reviewed; no runtime Plex test yet. |
| XMLTV Generation | 9 | Resolution removed; design and prior fixes confirmed. |
| Concurrency / Locking | 9 | Per-channel locks; no deadlock identified. |
| **IPTV Streaming** | **5** | **Manual verification not yet performed.** |
| **Plex Streaming** | **5** | **Manual verification not yet performed.** |
| **HDHomeRun** | **5** | **Manual verification not yet performed.** |

**Overall Score**: 7.7

**Adjustment**: If streaming (IPTV, Plex, HDHomeRun) is manually verified and stable, overall would rise to approximately 8.5–9.0. Current score reflects unverified streaming posture.

---

## 6) Final Stability Statement

| Statement | Status |
|----------|--------|
| Architecture is internally consistent | **Yes**. Clock is sole schedule authority; timeline is metadata-only for EPG; rebuild uses clock; resolution at stream time. |
| Clock authority is sole schedule authority | **Yes**. Position from clock; no index ownership; no conflicting sources. |
| Rebuild storms eliminated | **Yes**. Validation shows 0% rebuild; clock-first logic applied. |
| Duration collapse prevented | **Yes**. Fallback chain and validation confirm no zero or None durations. |
| Resolver contract preserved | **Yes**. Design review and report state no weakening; metadata sourced from config. |
| IPTV streaming stable | **Unknown**. Manual verification required. |
| Plex streaming stable | **Unknown**. Manual verification required. |
| HDHomeRun stable | **Unknown**. Manual verification required. |
| No restart loops | **Unknown**. Manual verification required. |

---

## 7) Required Final Soak Test Plan

### Preconditions

- Server started with `EXSTREAMTV_VALIDATE_DURATIONS=1` (optional, for assertions).
- Log collection enabled.
- At least one channel with Plex content and one with non-Plex content.

### Step-by-Step Runtime Validation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Request `/iptv/xmltv.xml` | HTTP 200; non-empty XML; no 500. |
| 2 | Tune IPTV stream: `/iptv/channel/{channel_id}.ts` or equivalent M3U entry | HTTP 200; continuous stream; no restart. |
| 3 | Tune Plex DVR to an EXStreamTV channel | Playback starts; no “Stream unavailable” or “Missing Plex connection info”. |
| 4 | Tune HDHomeRun to an EXStreamTV channel | Playback starts; no drop or timeline invalidation. |
| 5 | Run 2+ IPTV streams and 1 Plex stream concurrently | All streams stable; no mutual interference. |
| 6 | Let server run for 5 minutes with active streams | No restart loops; no mass rebuild; no cascading errors. |
| 7 | Inspect logs | No repeated “needs more content”; no “0.0 min remaining” for channels with timelines; no UnboundLocalError; no unresolved CancelledError. |

### Clean Log Conditions

- No `total_cycle_duration == 0` for channels with content.
- No “Channel X needs more content (only 0.0 min remaining)” for clock-based channels with valid timelines.
- No “Missing Plex connection info” when Plex is configured and content is Plex-sourced.
- No repeated channel manager restarts or FFmpeg respawn loops.

---

*End of Executive Technical Architecture Audit*

**Last Revised:** 2026-03-20
