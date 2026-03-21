# IPTV Streaming Hardening — Strengthened Plan

## Phase 0 — Gap Analysis (Completed)

| Gap | Finding |
|-----|---------|
| **Architectural** | `last_item_index` still used in iptv.py EPG (legacy path); clock authority used in StreamPositionResolver but EPG has dual path |
| **Validation** | No probe_required flag; no guard against probing empty/HTML/slate URLs |
| **Regressions** | Timeline exclusion could reduce channel content if many items fail resolution |
| **Race conditions** | `_timeline_lock` in ChannelStream; multiple clients share `_broadcast_queue`; no explicit backpressure |
| **Performance** | ProcessPoolManager token bucket; no rate limit per-client |
| **Bandwidth** | No adaptive muxrate; no upstream-aware tuning |
| **Concurrency** | Plex + IPTV + HDHomeRun share ChannelManager; single _stream_loop per channel |
| **ORM** | canonical_timeline converts to DTO before session close; runtime may receive dict |
| **Restart reintroduction** | ResolverError re-raised in resolve() propagates to caller; health task does not check _sleeping_for_clock_advance |

## Phase 1 — Plan Strengthening

### 1. Resolver Isolation Guarantees
- Explicit SourceType enforcement in _detect_source_type
- ResolverRegistry: reject SourceType.UNKNOWN for Plex fallback; require explicit plex_rating_key or source="plex"
- No implicit resolver fallback to Plex from URL pattern ("plex" substring)
- Plex routing: only when source="plex" OR plex_rating_key present OR /library/metadata/ in URL (exact path)
- Add test: resolver_routing_per_source_type

### 2. Restart Loop Kill Switch
- If restart_count >= 3 AND last_failure_classification == RESOLVER_FAILURE: disable auto_restart for channel, log
- Add _resolver_failure_restart_disabled flag
- Health task: do NOT restart when metrics contain "sleeping_for_clock_advance" == True

### 3. Probe Safety Enforcement
- validate_duration: never probe when resolved_url is None/empty (already done)
- validate_precache: add guard at caller; never call with empty URL
- _stream_loop: never precache when media_url is falsy

### 4. XMLTV/EPG Integrity
- EPG in iptv.py uses last_item_index; schedule_authority uses clock. Both paths must align.
- Assertion: for same timestamp, clock.resolve_item_and_seek should match EPG item when using clock-derived position.

### 5. ORM Safety Barrier
- canonical_timeline: _media_item_to_dto, _playout_item_to_dto — ensure all timeline items are DTO-only
- StreamPositionResolver receives CanonicalTimelineItem with media_item as dict

### 6. Rollback Strategy
- All changes behind feature guards or incremental
- Git: each stage is a separate commit; revert by commit hash
- Config: add `iptv_hardening.resolver_strict_routing: true` (default True) to allow disable
- If regression: set to false, restart

### 7. Validation Gates
- Gate 1: After resolver changes — Plex channel with rating_key still resolves
- Gate 2: After timeline exclusion — Channel with mixed sources still has content
- Gate 3: After resolution handling — No restart on resolver failure
- Gate 4: After health changes — Channel in sleep does not get restarted

## Stage Execution Order

- **Stage A**: Resolver strict routing (url_resolver.py)
- **Stage B**: Timeline exclusion (canonical_timeline.py) + IPTV fallback fix
- **Stage C**: StreamPositionResult + channel_manager resolution handling + restart kill switch
- **Stage D**: Health task sleep guard + probe safety guards
- **Stage E**: Tests and validation

---

## Execution Summary (Completed)

### Safeguards Added

| Safeguard | Location |
|-----------|----------|
| Resolver strict routing | url_resolver._detect_source_type: Plex only via explicit source, plex_rating_key, or /library/metadata/ path |
| Timeline exclusion | canonical_timeline: skip items where _resolve_url returns None |
| IPTV fallback fix | iptv.py: return 503 when channel_manager unavailable (was broken create_continuous_stream) |
| No-programming health ping | channel_manager: use _sleep_with_health_pings(5) instead of sleep(5) |
| Sleep guard for health | channel_manager: _sleeping_for_clock_advance flag; health_tasks: skip restart when True |
| Probe safety | precache.validate_precache: reject empty URL; duration_validator.get_duration_from_url: reject empty |

### Rollback

- Revert commits in reverse order of application
- Config: (future) `iptv_hardening.resolver_strict_routing: false` to re-enable loose Plex URL matching

### Regression Test Results

- test_resolver_source_type: 5 passed
- test_stream_continuity: 26 passed
- test_section_e_restart_path: 3 failed (pre-existing: tool_registry, request_channel_restart)

**Last Revised:** 2026-03-20
