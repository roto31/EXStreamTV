# Architectural Fix: Session Boundaries & DetachedInstanceError

## Root Cause

`DetachedInstanceError: Parent instance <MediaItem> is not bound to a Session; lazy load operation of attribute 'files' cannot proceed` occurred because:

1. `build_from_playout` / `build_from_yaml` loaded ORM `MediaItem` and `PlayoutItem` from the database
2. Session closed after the query, detaching the objects
3. `validate_duration()` → `_get_path()` accessed `media_item.files` (lazy relationship)
4. Lazy load failed outside session scope
5. Clock EPG failed for channels 2–28, triggering infinite restart loop

## Fix Implemented

### 1. ORM → DTO Conversion (canonical_timeline.py)

- **`_media_item_to_dto(mi)`**: Converts `MediaItem` ORM to plain dict while session is open. Extracts `files` list as `[{"path": ..., "url": ...}]`. Never stores ORM in timeline.
- **`_playout_item_to_dto(pi)`**: Converts `PlayoutItem` to dict with `id`, `title`, `custom_title`, `source_url`.
- **`build_from_playout`**: Uses `selectinload(MediaItem.files)` for eager load, then converts each row to DTOs before session closes.
- **`build_from_yaml`**: In `_sync_build`, after `ScheduleEngine.generate_playlist_from_schedule`, converts each `media_item` to DTO before return.

### 2. Duration Validator (duration_validator.py)

- **`_get_path()`**: Only reads plain dicts. Never accesses ORM `.files`. Supports `media_item.get("path")`, `media_item.get("files")[0]["path"]`, and nested `media_item["media_item"]` as dict.
- **`_get_metadata_duration()`**: Prefers dict access; no ORM lazy loads.

### 3. Title Resolver (api/title_resolver.py)

- Handles `media_item` as dict: `media_item.get("title")`, `media_item.get("path")`, `media_item.get("files")`.
- Never accesses ORM `.files` to avoid DetachedInstanceError.

### 4. Timeline Lock & Circuit Breaker (authority.py, xmltv_from_clock.py)

- **Per-channel lock**: `_get_timeline_lock(channel_id)` prevents concurrent `ensure_clock` for same channel.
- **Circuit breaker**: `_epg_failure_logged` set — on Clock EPG failure, log once per channel, skip until next rebuild. No repeated retries on every EPG request.

### 5. YouTube Resolver (streaming/resolvers/youtube.py)

- Added detection for: `"vpn"`, `"proxy"`, `"not a bot"`, `"confirm you're not a bot"`
- Classified as `is_retryable=False` → skip item, do not retry indefinitely
- Existing: `"private video"`, `"video unavailable"`, `"sign in"`, `"rate limit"`

## Verification

- **No ORM in canonical timeline**: `CanonicalTimelineItem.media_item` and `.playout_item` are plain dicts or None.
- **Clock EPG**: Build path uses only DTOs; no lazy load outside session.
- **Stream resolver**: `item.media_item` is dict; `url_resolver.resolve()` handles dict (already supported).
- **EPG XML**: `ClockProgramme.media_item` flows from timeline; now dict throughout.

## Files Changed

| File | Change |
|------|--------|
| `scheduling/canonical_timeline.py` | DTO conversion, selectinload, no ORM in result |
| `scheduling/duration_validator.py` | Dict-only `_get_path`, `_get_metadata_duration` |
| `api/title_resolver.py` | Dict handling for `media_item` |
| `scheduling/authority.py` | Per-channel lock, `_epg_failure_logged` |
| `scheduling/xmltv_from_clock.py` | Circuit breaker on EPG failure |
| `streaming/resolvers/youtube.py` | VPN/bot/private error classification |

**Last Revised:** 2026-03-20
