# Metadata AI Self-Resolution Implementation

> **User-facing overview:** For architecture, confidence gating, and safety model, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

## Executive Summary

Production-safe Ollama-based self-resolution for metadata issues integrated with:
- `GroundedContextEnvelope`, `bounded_agent_loop`, `tool_registry`
- `PatternDetector`, `UnifiedLogCollector`, metadata observability counters

**Constraints enforced:**
- No DB mutation by LLM
- No unbounded loops
- No auto-restart without guard
- No blocking calls
- No streaming pipeline changes

---

## SECTION 1 — Metadata Pattern Extensions

**File:** `exstreamtv/ai_agent/pattern_detector.py`

- **`MetadataIssueType`** enum: `METADATA_LOOKUP_FAILURE`, `EPISODE_NUM_MISSING`, `MOVIE_YEAR_MISSING`, `PLACEHOLDER_TITLE_EXCESS`, `XMLTV_VALIDATION_ERROR`, `LINEUP_MISMATCH`
- **`MetadataAnalysis`** dataclass: `channel_id`, `issue_type`, `confidence`, `affected_items_count`, `last_error_type`, `metadata_failure_ratio`
- **`analyze_metadata_issues(metrics, channel_id, programme_total)`**: Deterministic analysis from `get_metadata_metrics()`. No LLM.

---

## SECTION 2 — Metadata Tool Registry Additions

**File:** `exstreamtv/ai_agent/tool_registry.py`

Five LOW-risk tools added:

| Tool                    | risk_class | cooldown_sec | retry_cap |
|-------------------------|------------|--------------|-----------|
| re_enrich_metadata      | LOW        | 30           | 1         |
| refresh_plex_metadata   | LOW        | 30           | 1         |
| rebuild_xmltv           | LOW        | 30           | 1         |
| reparse_filename_metadata | LOW     | 30           | 1         |
| fetch_metadata_logs     | LOW        | 5            | 1         |

- **`METADATA_ONLY_TOOLS`** frozenset for metadata mode
- **`get_tools_for_mode("metadata")`** returns only metadata tools

**Implementations:** `exstreamtv/ai_agent/metadata_tools_impl.py`

- All idempotent where possible
- No `restart_channel` allowed
- 30s cooldown enforced in metadata mode

---

## SECTION 3 — Envelope Extensions

**File:** `exstreamtv/ai_agent/grounded_envelope.py`

New fields on `GroundedContextEnvelope`:

- `metadata_failure_ratio: float = 0.0`
- `placeholder_ratio: float = 0.0`
- `xmltv_validation_errors: int = 0`
- `lineup_mismatch_count: int = 0`
- `plex_metadata_mismatch_flag: bool = False`
- `recent_metadata_errors: str = ""` (compact summary, O(1) memory)

`build_grounded_envelope` and `_build_updated_envelope` updated to pass these through.

---

## SECTION 4 — Bounded Agent Metadata Integration

**File:** `exstreamtv/ai_agent/metadata_self_resolution.py`

**Flow:**
1. Build envelope with metadata observability
2. Check guardrails → abort if containment/velocity/pool/circuit
3. If metadata issues + bounded_agent_enabled: optionally get tool from Ollama
4. Run `run_bounded_loop(max_steps=3, mode="metadata")`

**Ollama integration:**
- Structured prompt with evidence only
- Response schema: `{"action": "<tool_name|STOP>", "reason": "...", "confidence": 0.0-1.0}`
- Invalid schema → reject
- No free-form shell commands

**Trigger:** `run_metadata_self_resolution(channel_id, use_ollama)` — called from troubleshooting when user query mentions metadata/EPG/xmltv/placeholder/guide.

---

## SECTION 5 — Guardrails Enforcement

**Abort when:**
- `containment_mode == True`
- `restart_velocity >= 10/60`
- `pool_pressure >= 0.9`
- Circuit breaker OPEN

Returns escalation message only; no resolution attempted.

**Autonomy boundaries:**
- Agent cannot modify DB schema
- Cannot alter streaming endpoints
- Cannot edit config files
- Cannot call `restart_channel`
- Max 3 steps per loop
- Cannot call same tool twice in same loop (enforced in `run_bounded_loop`)

---

## SECTION 6 — Observability Counters

**File:** `exstreamtv/monitoring/metadata_metrics.py`

| Counter                                  |
|------------------------------------------|
| ai_metadata_resolution_attempt_total      |
| ai_metadata_resolution_success_total     |
| ai_metadata_resolution_abort_total        |
| ai_metadata_tool_selected (via dict)      |

`inc_ai_metadata_tool_selected(tool_name)` called when metadata tools execute.

---

## SECTION 7 — Safety Verification

| Constraint                 | Status |
|----------------------------|--------|
| No streaming modifications | OK     |
| No restart path changes     | OK     |
| No blocking calls          | OK (async httpx, MetadataRefreshTask async) |
| No background loops        | OK (one-shot resolution) |
| No unbounded memory        | OK (O(1) envelope, compact log summary) |
| No new high-risk tools     | OK (all LOW) |
| No recursive agent calls   | OK     |
| No async misuse            | OK     |

---

## SECTION 8 — Production Readiness Status

- **Phase 1–4:** Implemented
- **Phase 5:** Log ingestion via `get_metadata_log_summary()` in `metadata_tools_impl.py`
- **Phase 6:** Guardrails in `_check_guardrails()`
- **Phase 7:** Boundaries enforced in loop + tool allowlist
- **Phase 8:** Observability counters added
- **Phase 9:** Escalation when `metadata_failure_ratio > 0.4` after resolution
- **Phase 10:** Safety constraints verified

**Invocation:** Call `run_metadata_self_resolution(channel_id=None, use_ollama=True)` when metadata issues are suspected.

---

## SECTION 9 — Production Hardening (Activation Complete)

### Config flags (Phase 1)

- `ai_agent.metadata_self_resolution_enabled: bool` (default False)
- `ai_agent.metadata_self_resolution_cooldown_sec: int` (default 300)

If disabled, self-resolution never executes.

### Trigger points (Phase 2)

1. **After EPG cycle** (`api/iptv.py`): When `check_early_warning()` returns True, fire `asyncio.create_task(run_metadata_self_resolution(None))`
2. **TroubleshootingService**: When query or PatternDetector classification is metadata-related AND `metadata_self_resolution_enabled`, invoke resolution (with recursion guard)
3. **Scheduled cadence** (`tasks/metadata_resolution_task.py`): Every 5 minutes, if `metadata_failure_ratio > 0.2`, trigger resolution

### Duplicate prevention (Phase 3)

- `_active_resolution: set[int|str]` with `asyncio.Lock`
- Acquire before run, release in `finally`
- Skip if already active for same channel/global

### Cooldown (Phase 4)

- `_last_run: dict` per channel/global
- Skip if `now - last_run < cooldown_sec`

### Failure memory (Phase 5)

- `_channel_attempts`, `_channel_suspended_until`
- If `attempts >= 3` and ratio unchanged → suspend 1 hour
- Log: "Metadata self-resolution temporarily suspended for channel {id}"

### Invocation guardrails (Phase 7)

Before execution: bounded_agent_enabled, metadata_self_resolution_enabled, containment_mode, pool_pressure < 0.9, circuit_breaker CLOSED.

### Recursion protection (Phase 9)

- `in_metadata_resolution_context()` — True when inside `run_metadata_self_resolution`
- TroubleshootingService checks before invoking; EPG trigger checks

### Logging (Phase 8)

- One log at start: "AI metadata remediation started for channel {id}"
- One log at end: "AI metadata remediation completed — success/failure"
- No per-step logging
