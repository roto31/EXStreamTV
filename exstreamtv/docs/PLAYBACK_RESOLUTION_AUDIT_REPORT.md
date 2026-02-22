# Complete End-to-End Playback Resolution Audit Report

> **User-facing overview:** For HDHomeRun emulation and Plex integration, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

**Date:** 2026-02-21  
**Scope:** Plex "Could not Tune Channel" fix verification and channel playback validation  
**Data Sources:** EXStreamTV logs (2000 lines), Plex logs (1000 lines via EXStreamTV API), live endpoint tests

---

## SECTION 1 — EXStreamTV Log Findings

### Log Source
- **Endpoint:** `http://192.168.1.120:8411/api/logs/entries?lines=2000`
- **Total entries:** 2000
- **Timestamp range:** 2026-02-21 17:53–18:00

### Failure Signature Search Results

| Signature | Found | Count | Notes |
|-----------|-------|-------|-------|
| HTTP 4xx/5xx on stream | No | 0 | No stream endpoint errors |
| Broken pipe | No | 0 | — |
| FFmpeg non-zero exit | No | 0 | — |
| "no output" (unhealthy) | Yes | 16 | Channels 104, 119, 120 |
| Restart velocity spike | No | — | 3 restarts in ~30s, contained |
| Tuner conflicts | No | 0 | — |
| HDHomeRun endpoint errors | No | 0 | — |
| MPEG-TS write errors | No | 0 | — |
| Entries marked `is_error` | No | 0 | — |

### Channel Unhealthy Events (Evidence)

```
2026-02-21 17:55:06 - Channel 104 no output for 186s - unhealthy
2026-02-21 17:55:06 - Triggering restart for channel 5
2026-02-21 17:55:06 - Stopping channel 104 (The X-Files and Califormication) for restart
2026-02-21 17:55:13 - Successfully restarted channel 104 (restart #1)

2026-02-21 17:55:13 - Channel 119 no output for 208s - unhealthy
2026-02-21 17:55:13 - Triggering restart for channel 20
2026-02-21 17:55:13 - Stopping channel 119 (Coen Brothers) for restart
2026-02-21 17:55:20 - Successfully restarted channel 119 (restart #2)

2026-02-21 17:55:27 - Successfully restarted channel 120 (restart #1)
```

### HDHomeRun Stream Request (Evidence)

```
2026-02-21 17:54:58 - exstreamtv.hdhomerun.api - INFO - HDHomeRun stream request for channel 100 from 192.168.1.120
```

One successful HDHomeRun stream request logged; no subsequent error.

### WARNING Breakdown
- **FFmpeg stderr (version banner):** 55 — informational, not failures
- **Channel unhealthy → restart:** 3 — health-task driven, expected recovery

---

## SECTION 2 — Plex Log Findings

### Log Source
- **Endpoint:** `http://192.168.1.120:8411/api/logs/plex/logs/entries?lines=1000`
- **Method:** EXStreamTV reads Plex logs from local filesystem (`~/Library/Logs/Plex Media Server`)
- **Total entries:** 1000

### DVR/Tune Error Search Results

| Signature | Found |
|-----------|-------|
| "Could not tune channel" | No |
| "Device not responding" | No |
| "Timed out" | No |
| "Invalid media" | No |
| Transcoder errors (live TV) | No |
| "No response from tuner" | No |
| HTTP status from EXStreamTV | No |
| Repeated tune attempts | No |
| Stream ended unexpectedly (live TV) | No |

**Note:** Plex log entries in the sample are predominantly library metadata and direct-play streaming. No recent live TV/DVR tune attempts with errors were found. This may mean:
1. No live TV tune was attempted in the log window, or
2. Tune attempts succeeded and did not generate errors.

---

## SECTION 3 — Correlation Analysis

| Plex Event | EXStreamTV Event | Correlation |
|------------|------------------|-------------|
| — | HDHomeRun stream request ch 100 @ 17:54:58 | No Plex error in same window |
| — | Channel 104 restart @ 17:55:06–17:55:13 | Health-task only |
| — | Channel 119 restart @ 17:55:13–17:55:20 | Health-task only |
| — | Channel 120 restart @ 17:55:27 | Health-task only |

**Conclusion:** No Plex tune failures could be matched to EXStreamTV errors in the correlated time window.

---

## SECTION 4 — Channel Unhealthy Root Cause

### Channels Affected
- **104** (The X-Files and Califormication)
- **119** (Coen Brothers)
- **120** (Superman and Batman)

### Root Cause Analysis

1. **Mechanism:** Health task in `health_tasks.py` marks a channel unhealthy when `last_output_time` is stale beyond `UNHEALTHY_THRESHOLD` (180s).

2. **last_output_time** is set when `ChannelStream._stream_loop` yields chunks from FFmpeg. No chunks → no updates → health task marks unhealthy.

3. **Likely causes of no output for 180s+**
   - FFmpeg slow to connect (e.g. Archive.org, Plex)
   - Source URL temporarily unreachable
   - Seek to a large offset delaying first output
   - Process pool contention under load

4. **Recovery path:** Health task triggers restart via `channel_manager.stop_channel()` + `start_channel()`. Restarts succeeded (restart #1, #2); no storm (3 restarts in ~30s).

5. **Relationship to Plex:** Channels 104, 119, 120 may or may not be tuned by Plex. Unhealthy events come from the health task, not from Plex tune attempts.

---

## SECTION 5 — Fixes Applied (if any)

### Previously Applied Fix (DeviceID)

| Fix | Status | Evidence |
|-----|--------|----------|
| DeviceID changed from "EXSTREAMTV" to "E5E17001" | **Deployed** | `discover.json` returns `"DeviceID":"E5E17001"` |
| Config validator for invalid DeviceID | **Active** | `config.py` normalizes invalid IDs |

### No Additional Fixes Applied

- No code changes for channel unhealthy (operating as designed)
- No stream pipeline changes
- No restart logic changes

---

## SECTION 6 — Stream Validation Results

### Manual Stream Tests

| Channel | HTTP | Content-Type | Bytes (15s) | MPEG-TS Packets |
|---------|------|--------------|-------------|-----------------|
| 100 | 200 | video/mp2t | 1128 | 6 (keepalive only) |

**Observation:** Channel 100 returned only the keepalive chunk (1128 bytes) in 15 seconds. No real MPEG-TS data flowed in that window.

**Interpretation:** Cold start can exceed 15s before first real chunk (FFmpeg spawn, source connect, seek). The keepalive prevents Plex from timing out during startup. Earlier validation (different run) saw ~9.5 MB in 8s when the channel was warm.

### HDHomeRun Contract Validation

| Check | Result |
|-------|--------|
| discover.json DeviceID = 8 hex | Yes — `E5E17001` |
| lineup.json valid JSON | Yes |
| GuideNumber unique | Yes — 36 channels, no duplicates |
| Channel URLs non-empty | Yes |
| TunerCount | 4 |
| Lineup entries | 36 |

---

## SECTION 7 — Regression Tests Added

| Test | Location | Purpose |
|------|----------|---------|
| `test_default_device_id_is_valid_8_hex` | `tests/unit/test_config.py` | DeviceID format |
| `test_invalid_device_id_normalized_to_default` | `tests/unit/test_config.py` | Invalid DeviceID handling |
| `test_valid_device_id_preserved` | `tests/unit/test_config.py` | Valid DeviceID preserved |
| `test_lineup_json` (enhanced) | `tests/reliability/test_platform_pytest.py` | GuideNumber unique, URL present |
| `test_discover_json` (DeviceID assert) | `tests/reliability/test_platform_pytest.py` | DeviceID 8 hex |
| `test_hdhomerun_stream_endpoint_returns_200_video_mp2t` | `tests/reliability/test_platform_pytest.py` | Stream 200 + video/mp2t |

All tests pass (excluding network test when server not running).

---

## SECTION 8 — Invariant Verification

| Invariant | Status |
|-----------|--------|
| Restart path uses health_tasks only | Verified |
| No restart storm | Verified (< 10 restarts in 60s window) |
| CircuitBreaker semantics | Unchanged |
| No new blocking calls | N/A |
| No direct stop_channel misuse | Verified (grep) |
| Pool exhaustion | None observed |

---

## SECTION 9 — Final Playback Confirmation

### Status: **PARTIALLY CONFIRMED**

| Criterion | Status |
|-----------|--------|
| DeviceID fix deployed | Confirmed |
| HDHomeRun stream request received | Confirmed (ch 100) |
| EXStreamTV stream endpoint 200 + video/mp2t | Confirmed |
| No "Could not tune channel" in Plex logs | Confirmed (in 1000-line sample) |
| Plex successful tune in logs | Not confirmed (no explicit success entries in sample) |
| Stream sustained > 5s of real data | Not confirmed (1128 bytes in 15s for cold ch 100) |
| User playback on macOS/iOS/tvOS | Not verified (requires manual test) |

### Required User Verification

1. **Remove and re-add DVR in Plex** (DeviceID changed; Plex caches the old device).
2. **Rescan channels** after re-adding.
3. **Test playback** on:
   - macOS browser
   - Plex iOS app
   - Plex tvOS app
4. **If issues persist:** Export latest 1000 lines from Plex Server Console and correlate timestamps with EXStreamTV logs.

---

## Appendix — Log Extraction Commands

```bash
# EXStreamTV logs
curl -s "http://192.168.1.120:8411/api/logs/entries?lines=2000" | python3 -m json.tool > exstreamtv_logs.json

# Plex logs (via EXStreamTV)
curl -s "http://192.168.1.120:8411/api/logs/plex/logs/entries?lines=1000" | python3 -m json.tool > plex_logs.json
```
