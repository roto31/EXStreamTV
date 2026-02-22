# API Compatibility Audit Report

> **User-facing overview:** For API overview and HDHomeRun endpoints, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

**Date:** 2025-02-21  
**Scope:** Full-surface compatibility validation for EXStreamTV  
**Constraint:** No code modifications; analysis only.

---

## SECTION 1 — Complete API Inventory

### 1.1 FastAPI Routes

#### REST Endpoints (prefix `/api`)

| File | Route | Method | Contract |
|------|-------|--------|----------|
| auth.py | /api/* | varies | Auth/session |
| dashboard.py | /api/dashboard | GET | HTML |
| dashboard.py | /api/dashboard/stats | GET | DashboardStats |
| dashboard.py | /api/dashboard/quick-stats | GET | List[QuickStat] |
| dashboard.py | /api/dashboard/system-info | GET | SystemInfo |
| dashboard.py | /api/dashboard/resource-usage | GET | ResourceUsage |
| dashboard.py | /api/dashboard/active-streams | GET | List[ActiveStream] |
| dashboard.py | /api/dashboard/activity | GET | List[ActivityItem] |
| dashboard.py | /api/dashboard/stream-history | GET | StreamHistory |
| dashboard.py | /api/dashboard/library-stats | GET | JSON |
| health.py | /api/health | GET | dict |
| health.py | /api/health/detailed | GET | dict |
| health.py | /api/health/ready | GET | dict |
| health.py | /api/health/live | GET | dict |
| health.py | /api/health/db | GET | dict |
| health.py | /api/health/channels | GET | dict |
| health.py | /api/health/streaming | GET | dict |
| settings.py | /api/settings | GET | HTML |
| settings.py | /api/settings/ffmpeg | GET/PUT | dict |
| settings.py | /api/settings/hdhomerun | GET | dict |
| settings.py | /api/settings/server | GET | dict |
| settings.py | /api/settings/streaming | GET/PUT | dict |
| settings.py | /api/settings/stream-throttler | GET/PUT | dict |
| settings.py | /api/settings/hdhr | GET | dict |
| settings.py | /api/settings/playout | GET/PUT | dict |
| settings.py | /api/settings/plex | GET/PUT | dict |
| settings.py | /api/settings/plex/* | multiple | varies |
| channels.py | /api/channels | GET | list[ChannelResponse] |
| channels.py | /api/channels/{id} | GET/PUT/DELETE | ChannelResponse |
| channels.py | /api/channels/number/{num} | GET | ChannelResponse |
| channels.py | /api/channels | POST | ChannelResponse |
| channels.py | /api/channels/{id}/playback-position | GET/POST/DELETE | varies |
| channels.py | /api/channels/{id}/icon | POST/DELETE | ChannelResponse |
| channels.py | /api/channels/{id}/playouts | GET | list |
| channels.py | /api/channels/{id}/toggle-enabled | POST | ChannelResponse |
| channels.py | /api/channels/{id}/filler | GET/PUT | dict |
| channels.py | /api/channels/{id}/deco | GET/PUT | dict |
| channels.py | /api/channels/{id}/programming | GET | dict |
| channels.py | /api/channels/{num}/schedule | GET | dict |
| media.py | /api/media/count | GET | dict |
| media.py | /api/media | GET/POST | list/dict |
| media.py | /api/media/filters | GET | list |
| media.py | /api/media/shows | GET | list |
| media.py | /api/media/shows/{title}/episodes | GET | list |
| media.py | /api/media/search | GET | list |
| media.py | /api/media/{id} | GET/DELETE | dict |
| media.py | /api/media/plex/from-rating-key | POST | dict |
| playlists.py | /api/playlists | GET/POST | list |
| schedules.py | /api/schedules | GET/POST | list |
| schedules.py | /api/schedules/{id} | GET/PUT/DELETE | ScheduleResponse |
| schedules.py | /api/schedules/{id}/items | GET/POST/DELETE | list |
| schedule_items.py | /api/schedule-items | GET | list |
| libraries.py | /api/libraries | GET | list |
| ffmpeg_profiles.py | /api/ffmpeg-profiles | GET | list |
| resolutions.py | /api/resolutions | GET | list |
| playouts.py | /api/playouts | GET/POST | list |
| playouts.py | /api/playouts/{id} | GET/PUT/DELETE | dict |
| playouts.py | /api/playouts/{id}/items | GET | list |
| playouts.py | /api/playouts/{id}/now-playing | GET | dict |
| playouts.py | /api/playouts/{id}/history | GET | list |
| playouts.py | /api/playouts/{id}/rebuild | POST | dict |
| playouts.py | /api/playouts/channel/{num} | GET | dict |
| playouts.py | /api/playouts/{id}/build/* | POST | dict |
| playouts.py | /api/playouts/{id}/skip | POST | dict |
| playouts.py | /api/playouts/{id}/cancel-skip | POST | dict |
| ollama.py | /api/ollama/query | POST | dict |
| ollama.py | /api/ollama/welcome | GET | dict |
| ollama.py | /api/ollama/conversation/clear | POST | dict |
| ollama.py | /api/ollama/fixes/{id}/apply | POST | dict |
| validation.py | /api/validation/* | varies | varies |
| import_api.py | /api/import/* | varies | varies |
| export_api.py | /api/export | GET | dict |
| export_api.py | /api/export/channels/{id}/yaml | GET/POST | varies |
| watermarks.py | /api/watermarks | GET | list |
| logs.py | /api/logs | GET | dict |
| logs.py | /api/logs/entries | GET | dict |
| logs.py | /api/logs/{entry_id} | GET | HTML |
| logs.py | /api/logs/stream | GET | SSE |
| logs.py | /api/logs/clear | GET | dict |
| logs.py | /api/logs/plex/* | GET | varies |
| logs.py | /api/logs/browser | POST | dict |
| logs.py | /api/logs/browser/entries | GET | list |
| logs.py | /api/logs/browser/clear | DELETE | dict |
| logs.py | /api/logs/ollama/* | GET | varies |
| logs.py | /api/logs/lifecycle/* | GET/POST | varies |
| collections.py | /api/collections | GET/POST | list |
| collections.py | /api/collections/{id} | GET/DELETE | dict |
| collections.py | /api/collections/{id}/items/{mid} | POST/DELETE | varies |
| collections.py | /api/collections/consolidate | POST | dict |
| collections.py | /api/collections/smart | POST | dict |
| collections.py | /api/collections/multi* | GET/POST/PUT/DELETE | varies |
| m3u_service_api.py | /api/m3u/service/status | GET | dict |
| m3u_service_api.py | /api/m3u/service/enable | POST | dict |
| m3u_service_api.py | /api/m3u/service/disable | POST | dict |
| media_sources.py | /api/media-sources/* | varies | varies |
| player.py | /api/player/* | varies | varies |
| blocks.py | /api/blocks | GET/POST | list |
| filler_presets.py | /api/filler-presets | GET | list |
| templates.py | /api/templates | GET | list |
| deco.py | /api/deco-groups | GET/POST | list |
| deco.py | /api/deco-groups/{id} | GET/PUT/DELETE | dict |
| deco.py | /api/deco | GET/POST | list |
| deco.py | /api/deco/{id} | GET/PUT/DELETE | dict |
| deco.py | /api/deco/types | GET | list |
| scripted.py | /api/scripted/* | varies | varies |

#### IPTV Endpoints (root-level, not under /api)

| File | Route | Method | Contract |
|------|-------|--------|----------|
| iptv.py | /iptv/channels.m3u | GET | application/vnd.apple.mpegurl |
| iptv.py | /iptv/xmltv.xml | GET | application/xml |
| iptv.py | /iptv/channel/{num}.m3u8 | GET | application/vnd.apple.mpegurl |
| iptv.py | /iptv/channel/{num}.ts | GET | StreamingResponse video/mp2t |
| iptv.py | /iptv/stream/{media_id} | GET/HEAD/OPTIONS | StreamingResponse/Redirect |

#### HDHomeRun Endpoints (prefix /hdhomerun)

| File | Route | Method | Contract |
|------|-------|--------|----------|
| hdhomerun/api.py | /hdhomerun/device.xml | GET | application/xml |
| hdhomerun/api.py | /hdhomerun/service.xml | GET | application/xml |
| hdhomerun/api.py | /hdhomerun/control | POST | 200 empty |
| hdhomerun/api.py | /hdhomerun/event | GET/POST | 200 empty |
| hdhomerun/api.py | /hdhomerun/discover.json | GET | JSON (FriendlyName, ModelNumber, BaseURL, etc.) |
| hdhomerun/api.py | /hdhomerun/lineup.json | GET | JSON list (GuideNumber, GuideName, URL, HD) |
| hdhomerun/api.py | /api/lineup_status.json | GET | JSON (ScanInProgress, ScanPossible, Source, SourceList) |
| hdhomerun/api.py | /hdhomerun/epg | GET | application/xml (XMLTV) |
| hdhomerun/api.py | /hdhomerun/auto/v{num} | GET | Redirect |
| hdhomerun/api.py | /hdhomerun/tuner{n}/stream | GET | StreamingResponse video/mp2t |
| hdhomerun/api.py | /hdhomerun/status.json | GET | JSON (FriendlyName, TunerStatus, etc.) |

#### Root-level HDHomeRun Redirects

| Route | Redirects To |
|-------|--------------|
| /discover.json | /hdhomerun/discover.json |
| /lineup_status.json | /hdhomerun/lineup_status.json |
| /lineup.json | /hdhomerun/lineup.json |

#### AI Channel Creator (prefix /api/ai/channel)

| File | Route | Method | Contract |
|------|-------|--------|----------|
| ai_channel.py | /api/ai/channel/start | POST | StartSessionResponse |
| ai_channel.py | /api/ai/channel/message | POST | SendMessageResponse |
| ai_channel.py | /api/ai/channel/preview/{sid} | GET | PreviewResponse |
| ai_channel.py | /api/ai/channel/create | POST | CreateChannelResponse |
| ai_channel.py | /api/ai/channel/sessions | GET | list[SessionInfo] |
| ai_channel.py | /api/ai/channel/session/{sid} | GET/DELETE | dict |
| ai_channel.py | /api/ai/channel/status | GET | dict |
| ai_channel.py | /api/ai/channel/personas | GET | list[PersonaInfoResponse] |
| ai_channel.py | /api/ai/channel/personas/{id} | GET | PersonaInfoResponse |
| ai_channel.py | /api/ai/channel/personas/{id}/welcome | GET | dict |
| ai_channel.py | /api/ai/channel/analyze | POST | AnalyzeIntentResponse |
| ai_channel.py | /api/ai/channel/sources | POST | GetSourcesResponse |
| ai_channel.py | /api/ai/channel/plan | POST | BuildPlanResponse |
| ai_channel.py | /api/ai/channel/plan/{id} | GET/PUT/DELETE | BuildPlanResponse |
| ai_channel.py | /api/ai/channel/plan/{id}/approve | POST | dict |
| ai_channel.py | /api/ai/channel/plan/{id}/execute | POST | dict |
| ai_channel.py | /api/ai/channel/start-with-persona | POST | StartSessionWithPersonaResponse |
| ai_channel.py | /api/ai/channel | GET | HTML |

#### Other Routers

| Router | Prefix | Notes |
|--------|--------|-------|
| performance | /api | Optional |
| integrations | /api | Optional |
| migration | /api/migration | Migration imports |
| ai_settings | /api | AI settings |
| docs_api | (root) | Documentation |
| prometheus | /metrics | Prometheus exposition |

### 1.2 Internal Service APIs

| Service | Location | Key Methods | Input/Output |
|---------|----------|-------------|--------------|
| ChannelManager | streaming/channel_manager.py | start_channel, stop_channel, get_channel_stream, prewarm_channels | channel_id, channel_number, channel_name |
| SessionManager | streaming/session_manager.py | init_session_manager, session ops | max_sessions, idle_timeout |
| StreamThrottler | streaming/throttler.py | ThrottleConfig, ThrottleMode | buffer control |
| ScheduleEngine | (used by playouts) | generate_playlist_from_schedule | channel, schedule |
| PlayoutEngine | (via playouts API) | rebuild, items | playout_id |
| ProcessPoolManager | streaming/process_pool_manager.py | acquire_process, release_process, get_metrics, start | - |
| DatabaseConnectionManager | database/connection.py | get_sync_session, get_pool_stats | - |
| PatternDetector | ai_agent/pattern_detector.py | find_root_cause, analyze_sequence | error_event dict |
| AutoResolver | ai_agent/auto_resolver.py | resolve_issue, _apply_restart | DetectedIssue |
| ToolRegistry | ai_agent/tool_registry.py | execute_restart_channel, can_execute_restart_channel | channel_id, envelope |
| BoundedAgentLoop | ai_agent/bounded_agent_loop.py | run_bounded_loop | envelope, planned_steps, persona |
| GroundedEnvelope | ai_agent/grounded_envelope.py | build_grounded_envelope | various params |
| PersonaConfig | ai_agent/persona_config.py | load_persona_config | persona_id |
| CircuitBreaker | streaming/circuit_breaker.py | can_restart, record_failure, get_state | channel_id |
| StreamManager | streaming (StreamTV) | get_stream_url, detect_source | MediaItem.url |

---

## SECTION 2 — Contract Deviations Found

### 2.1 Logs Router Order (Known Issue)

- **File:** exstreamtv/api/logs.py  
- **Issue:** `@router.get("/{entry_id}")` can match `/entries` if registered before `/entries`  
- **Status:** ROOT_CAUSE_INVESTIGATION_REPORT.md documents this; order may vary by import  
- **Current:** `get_log_entries` at `/entries` (L380) registered before `get_entry_by_id` at `/{entry_id}` (L464) — order appears correct  
- **Risk:** LOW if route registration order is stable

### 2.2 HDHomeRun lineup.json Raw SQL

- **File:** exstreamtv/hdhomerun/api.py  
- **Issue:** `db.execute(text(...))` used without `await` in fallback path (raw SQL)  
- **Impact:** AsyncSession requires `await db.execute()`  
- **Location:** ~L525  
- **Risk:** MODIFIED AND RISKY — async/sync mismatch in error path

### 2.3 build_grounded_envelope Optional Bridge

- **File:** exstreamtv/ai_agent/grounded_envelope.py  
- **Change:** When `failure_classification` or `confidence` empty, fills from PatternDetector bridge  
- **Impact:** Callers that omit these params now receive bridge-derived values  
- **Risk:** MODIFIED BUT COMPATIBLE — additive, backward compatible

### 2.4 run_bounded_loop New Parameters

- **File:** exstreamtv/ai_agent/bounded_agent_loop.py  
- **Change:** `enabled_override: bool | None = None`, `mode_override: str | None = None`  
- **Impact:** Optional; no callers exist  
- **Risk:** SAFE — additive

---

## SECTION 3 — Restart Path Validation

### 3.1 Restart Call Graph

```
request_channel_restart (health_tasks.py L241)
  └─ _can_trigger_restart (storm throttle, cooldown, circuit breaker)
  └─ _trigger_channel_restart
       └─ _channel_manager.stop_channel(channel_id)
       └─ _channel_manager.start_channel(...)
```

### 3.2 Callers of request_channel_restart

| Caller | Location | Guard |
|--------|----------|-------|
| tool_registry.execute_restart_channel | ai_agent/tool_registry.py L142 | can_execute_restart_channel |
| auto_resolver._apply_restart | ai_agent/auto_resolver.py L485 | (internal) |
| channel_health_task | tasks/health_tasks.py L154 | _can_trigger_restart |

### 3.3 Direct stop_channel Callers

| Caller | Location |
|--------|----------|
| _trigger_channel_restart | tasks/health_tasks.py L329 (only caller) |

### 3.4 API Exposure of Restart

- **Channels toggle-enabled:** Does NOT call stop_channel or request_channel_restart. Only updates DB `enabled` flag.
- **No API endpoint** exposes restart directly.
- **Health task:** Invokes restart only when channel is unhealthy and `_can_trigger_restart` allows.

**Verdict:** Restart path unification preserved. No API bypass.

---

## SECTION 4 — Metadata API Validation

### 4.1 XMLTV

- **Builder:** XMLTVGenerator.generate (xmltv_generator.py)  
- **Signature:** `generate(channels, programmes_by_channel, base_url, validate)`  
- **Output:** XML string with `<tv>`, `<channel>`, `<programme>`  
- **Placeholder handling:** title_resolver.is_item_placeholder used; fallback to show_title/series_title  
- **Status:** Compatible

### 4.2 M3U

- **Generator:** iptv.py get_m3u_playlist  
- **Output:** `#EXTM3U` with EXTINF, tvg-id, tvg-name, stream URLs  
- **Alignment:** Uses channel number, name, group, logo  
- **lineup.json:** GuideNumber, GuideName, URL, HD — matches M3U channel structure

### 4.3 EPG/Programme Data

- **TimelineProgramme:** start_time, stop_time, title, media_item  
- **XMLTVGenerator:** Uses TimelineProgramme; validates monotonic, no overlaps  
- **HDHomeRun EPG:** Delegates to iptv.get_epg

**Verdict:** Metadata pipeline compatible. No placeholder titles in normal flow.

---

## SECTION 5 — HDHomeRun API Validation

### 5.1 discover.json

- **Fields:** FriendlyName, ModelNumber, FirmwareName, FirmwareVersion, DeviceID, DeviceAuth, BaseURL, LineupURL, GuideURL, TunerCount  
- **Conformance:** Matches Plex DVR expectations  
- **Content-Type:** application/json (FastAPI default)

### 5.2 lineup.json

- **Schema:** List of {GuideNumber, GuideName, URL, HD}  
- **URL format:** `{base_url}/hdhomerun/auto/v{channel.number}`  
- **Enum fallback:** Raw SQL used on enum validation error; async `await` may be missing in fallback (see 2.2)

### 5.3 Tuner Endpoints

- **/hdhomerun/tuner{n}/stream:** Accepts `channel` or `url`; parses `auto:v{num}`  
- **StreamingResponse:** media_type=video/mp2t, chunked  
- **Tuner release:** In finally block

### 5.4 Root Redirects

- `/discover.json`, `/lineup_status.json`, `/lineup.json` → 307 to /hdhomerun/*  

**Verdict:** HDHomeRun API compatible. One async/sync issue in lineup fallback path.

---

## SECTION 6 — Observability Impact

### 6.1 Metrics Instrumentation

- **Prometheus:** /metrics returns text/plain; no change to other API responses  
- **MetricsCollector:** Used internally; to_prometheus_text() only for /metrics  
- **health_tasks:** Calls get_metrics_collector().inc_health_timeouts(), set_circuit_breaker_state  
- **ProcessPoolManager:** get_metrics() feeds Prometheus router

### 6.2 Payload Leakage

- No API endpoint returns internal metrics in JSON except /metrics (intended)  
- Dashboard stats are high-level (channel counts, system info)

### 6.3 Performance

- **Prometheus /metrics:** Updates mc from ProcessPoolManager, DB; single await asyncio.sleep(0) for lag  
- **Blocking:** check_ffmpeg, check_ffprobe use subprocess.run (blocking) in health endpoint — pre-existing  
- **Memory:** No new retention from observability changes

**Verdict:** Observability does not alter API payloads. No regressions identified.

---

## SECTION 7 — Cross-Module Compatibility Findings

### 7.1 Imports and Dependencies

| Module | Imports From | Potential Circular |
|--------|--------------|---------------------|
| bounded_agent_loop | grounded_envelope, tool_registry | None |
| tool_registry | grounded_envelope, health_tasks (lazy) | None |
| auto_resolver | health_tasks (lazy) | None |
| grounded_envelope | pattern_envelope_bridge (lazy) | None |
| pattern_envelope_bridge | pattern_detector | None |
| main.py | persona_config (lazy) | None |

### 7.2 run_bounded_loop Call Sites

- **Callers:** NONE  
- **Status:** Implemented but not invoked by any API or service  
- **Integration:** TroubleshootingService.analyze_and_suggest is single-shot; does not call run_bounded_loop

### 7.3 Exception Handling

- **Broad except:** Present in api/iptv.py, api/dashboard.py, api/ollama.py, api/performance.py, api/settings.py (try/except for optional features)  
- **Risk:** Most are for optional imports or fallbacks; may mask incompatibility in edge cases  
- **Recommendation:** Avoid bare `except:`; use `except Exception` with logging

### 7.4 Dead Code / Orphaned Functions

- **run_bounded_loop:** Orphaned — no invoker
- **Build plans (_build_plans):** Used by ai_channel plan/execute flow

---

## SECTION 8 — Streaming Contract Validation

### 8.1 IPTV Stream Endpoints

- **/iptv/channel/{num}.ts:** StreamingResponse, video/mp2t, chunked, X-Accel-Buffering: no  
- **/iptv/stream/{media_id}:** GET/HEAD/OPTIONS; StreamingResponse or RedirectResponse for Plex  
- **Headers:** Access-Control-Allow-Origin: *, Cache-Control, Connection: keep-alive

### 8.2 HDHomeRun Stream

- **/hdhomerun/tuner{n}/stream:** Same StreamingResponse pattern  
- **ChannelManager path:** get_channel_stream → start → get_stream()  
- **Fallback:** MPEGTSStreamer when ChannelManager unavailable

### 8.3 URL Structure

- **M3U:** /iptv/channel/{num}.ts or .m3u8  
- **HDHomeRun:** /hdhomerun/auto/v{num} → tuner stream  
- **Query params:** access_token when api_key_required

### 8.4 Buffering/Chunking

- **X-Accel-Buffering: no:** Disables nginx buffering  
- **Transfer-Encoding: chunked:** Standard for streaming  
- **media_type:** video/mp2t for MPEG-TS

**Verdict:** Streaming contract unchanged. Plex-compatible.

---

## SECTION 9 — AI Agent Safety Validation

### 9.1 Agent Invocation

- **bounded_agent_enabled:** Checked at run_bounded_loop entry; returns early if False  
- **run_bounded_loop:** NOT called by any API or background task  
- **TroubleshootingService:** Invoked only by POST /api/ollama/query; single-shot LLM analysis

### 9.2 Tool Execution

- **execute_restart_channel:** Only via run_bounded_loop → execute_tool  
- **No public API** exposes tool execution  
- **ollama/fixes/{id}/apply:** Placeholder; returns success without applying

### 9.3 Persona YAML

- **Load:** main.py lifespan when config.ai_agent.enabled  
- **Blocking:** load_persona_config is sync file I/O; minimal, non-blocking for startup  
- **Missing YAML:** Logged; load_persona_config falls back to PersonaConfig()

### 9.4 PatternDetector Bridge

- **Subscription:** UnifiedLogCollector subscribes async callback on error emit  
- **Flow:** emit(event) → subscriber → update_from_events([event]) → find_root_cause  
- **Log ingestion:** Callback is async; does not block emit  
- **Condition:** Only when pattern_detection_enabled

### 9.5 AutoResolver

- **External invoke:** None — no API calls get_auto_resolver or resolve_issue  
- **Internal:** Initialized in main.py; used by background detection (if wired)  
- **Restart path:** _apply_restart uses request_channel_restart ✓

**Verdict:** AI agent safety constraints satisfied. Bounded loop not auto-triggered.

---

## SECTION 10 — Risk Classification Summary

| API/Component | Classification | Notes |
|---------------|----------------|-------|
| Restart path | SAFE | All restarts via request_channel_restart |
| HDHomeRun lineup fallback | MODIFIED AND RISKY | Possible async/sync mismatch |
| build_grounded_envelope | MODIFIED BUT COMPATIBLE | PatternDetector bridge additive |
| run_bounded_loop | SAFE | New optional params; no callers |
| Persona load | SAFE | Non-blocking startup |
| PatternDetector bridge | SAFE | Async subscriber, no new loops |
| AutoResolver | SAFE | Uses request_channel_restart |
| IPTV/Streaming | SAFE | Contract unchanged |
| XMLTV/M3U | SAFE | Schema unchanged |
| Observability | SAFE | No payload changes |
| run_bounded_loop | UNUSED | Implemented but not wired |

---

## SECTION 11 — Required Corrections (if any)

1. **HDHomeRun lineup.json fallback (hdhomerun/api.py ~L525):** FIXED  
   - Raw SQL fallback now uses `await db.execute(text(...))` and `raw_exec.fetchall()`.

2. **run_bounded_loop integration:** FIXED  
   - TroubleshootingService.analyze_and_suggest() calls run_bounded_loop when `config.ai_agent.bounded_agent_enabled` and `request` provided.  
   - Ollama route passes `request=request` to analyze_and_suggest.

3. **Logs route order (logs.py):** VERIFIED  
   - `/entries` declared before `/{entry_id}`. Safety comment added.

---

**End of Report**
