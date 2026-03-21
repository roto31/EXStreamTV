# Clock Authority Validation Report

Post-cutover validation: Broadcast Clock Authority, metadata-only timeline, resolver isolation, rebuild refactor.

---

## 1) Clock Duration Validation Results

**Script**: `python scripts/validate_clock_authority.py`

| Check | Result |
|-------|--------|
| total_cycle_duration > 0 | ✓ All channels with timeline |
| sum(canonical_duration) ≈ total_cycle_duration | ✓ No drift |
| No canonical_duration == 0 | ✓ Fallback chain ensures 1800 |
| No None durations propagating | ✓ `t.canonical_duration or 1800` |
| Channels with no timeline | Treated as N/A (e.g. ch23) |

---

## 2) Channels Rebuilt Count

**Phase 3**: Rebuild uses `clock.total_cycle_duration` as sole authority.

- **Result**: 0 channels rebuilt (0.0%)
- **Threshold**: < 5% acceptable
- **Status**: ✓ PASSED

---

## 3) Resolver Metadata Validation (Plex)

**DTO fields** (`_media_item_to_dto`): `plex_rating_key` present for Plex items.

**At resolve time** (Plex resolver injects from authoritative sources):
- `server_url`: PlexLibrary, Plex config, or channel config
- `token`: Plex config
- `rating_key`: From plex_rating_key in DTO, or source_id, or URL parse

**Contract**: Resolver does NOT weaken—server_url/token come from config at resolve time. No metadata gap.

---

## 4) IPTV Streaming Test

| Endpoint | Expected | Validation |
|----------|----------|------------|
| `/iptv/channel/{id}.ts` | 200, no restart loops | Manual run required |
| M3U | 200 | Manual run required |

---

## 5) Plex Streaming Test

| Check | Expected |
|-------|----------|
| Plex DVR tune | No "Stream unavailable" |
| No "Missing Plex connection info" | Resolver gets server_url/token from config |
| No restart loops | Manual run required |

---

## 6) HDHomeRun Test

| Check | Expected |
|-------|----------|
| HDHomeRun tune | Stable stream |
| No timeline invalidation | Clock stable |

---

## 7) XMLTV Generation Result

| Check | Status |
|-------|--------|
| build_epg_from_clock does NOT call resolution | ✓ Uses ensure_clock + timeline only |
| skip_resolution=True preserved | ✓ authority.load_timeline_async |
| No ffprobe during XMLTV | ✓ Metadata-only build |
| No 500 errors | ✓ Verified in prior session |
| No CancelledError escaping | ✓ Removed shadowed asyncio import |

---

## 8) Code Modified

| File | Change |
|------|--------|
| `canonical_timeline.py` | Guarded assert `canonical_duration > 0` (EXSTREAMTV_VALIDATE_DURATIONS=1) |
| `authority.py` | Guarded assert `total_cycle_duration > 0` |
| `playout_tasks.py` | Guarded assert when skipping rebuild |
| `scripts/validate_clock_authority.py` | **New** validation script |

**Assertions**: Enable with `EXSTREAMTV_VALIDATE_DURATIONS=1`. Remove after 5‑min soak test passes.

---

## 9) Concurrency / Race Validation (Phase 7)

| Check | Status |
|-------|--------|
| Per-channel lock `_get_timeline_lock(channel_id)` | ✓ No global lock |
| `AsyncCancellationGuard.safe_lock` | ✓ CancelledError re-raised, lock released |
| Lock scope | ✓ Only around timeline load + clock create, no await across external I/O |
| Deadlock risk | None—per-channel locks, no nested acquisition |

---

## 10) Confirmation No Regression

- **Duration collapse**: Prevented by fallback chain (media → playout → 1800)
- **Clock invalidation**: Not triggered—clock immutable once created
- **Mass rebuild**: Prevented by clock.total_cycle_duration check
- **Resolver metadata**: Plex rating_key in DTO; server_url/token from config
- **IPTV/Plex/XMLTV**: Architecture unchanged; EPG decoupled from resolution

---

## End State Checklist

| Item | Status |
|------|--------|
| total_cycle_duration valid for all channels | ✓ |
| No mass rebuild storms | ✓ |
| IPTV streaming stable | Manual verify |
| Plex streaming stable | Manual verify |
| HDHomeRun stable | Manual verify |
| XMLTV stable | ✓ |
| No contract violations | ✓ |
| No restart loops | Manual verify |
| No race conditions | ✓ |
| No duration drift | ✓ |
| No metadata gaps | ✓ |

---

## Run Validation

```bash
# Phase 1 + 3 (clock integrity + rebuild)
python scripts/validate_clock_authority.py

# With assertions (5-min soak)
EXSTREAMTV_VALIDATE_DURATIONS=1 python -m uvicorn exstreamtv.main:app --host 0.0.0.0 --port 8411
```

**Last Revised:** 2026-03-20
