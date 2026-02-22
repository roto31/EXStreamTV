# Metadata Self-Resolution Activation Status

> **User-facing overview:** For AI agent safety and metadata pipeline, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

## SECTION 1 — Config Flags Added

**File:** `exstreamtv/config.py` (AIAgentConfig)

- `metadata_self_resolution_enabled: bool = False`
- `metadata_self_resolution_cooldown_sec: int = 300`

If `metadata_self_resolution_enabled` is False, self-resolution does not run.

---

## SECTION 2 — Trigger Points Integrated

1. **After EPG cycle** (`api/iptv.py` ~L1944): When `check_early_warning()` returns True, `asyncio.create_task(run_metadata_self_resolution(None))` is fired. Does not block EPG response.

2. **TroubleshootingService** (`services/troubleshooting_service.py` ~L146): Triggers resolution when:
   - Query includes metadata/EPG/xmltv/placeholder/guide, or
   - PatternDetector classification indicates metadata-related issues  
   AND `metadata_self_resolution_enabled` is True. Uses recursion guard before invocation.

3. **5-minute scheduled cadence** (`tasks/metadata_resolution_task.py`, `main.py`): Task runs every 300s; if `metadata_failure_ratio > 0.2`, triggers resolution. All safety checks are inside `run_metadata_self_resolution`.

---

## SECTION 3 — Duplicate Prevention Mechanism

**File:** `exstreamtv/ai_agent/metadata_self_resolution.py`

- `_active_resolution: set[int | str]` — keys: channel_id or `"global"`
- `asyncio.Lock` (`_resolution_lock`) for access
- `_acquire_resolution(channel_id)` — returns False if already active
- `_release_resolution(channel_id)` — called in `finally` after each run

No threading; uses asyncio.Lock only.

---

## SECTION 4 — Cooldown Enforcement

- `_last_run: dict[int | str, float]` — monotonic timestamps per channel/global
- `_can_run_after_cooldown(channel_id, cooldown_sec)` — skips if elapsed time < cooldown
- `_record_run(channel_id)` — called after completion
- Cooldown source: `metadata_self_resolution_cooldown_sec` (default 300)

---

## SECTION 5 — Failure Memory Logic

- `_channel_attempts: dict[int, int]` — attempt count per channel
- `_channel_last_ratio: dict[int, float]` — last metadata_failure_ratio
- `_channel_suspended_until: dict[int, float]` — suspend until timestamp

Logic: If `attempt_count >= 3` AND ratio did not improve → suspend 1 hour.  
Log: `"Metadata self-resolution temporarily suspended for channel {id}"`

---

## SECTION 6 — Invocation Guardrails

**`_can_invoke_safely(channel_id)`** checks:

- `bounded_agent_enabled == True`
- `metadata_self_resolution_enabled == True`
- `containment_mode == False` (restart_velocity, pool_pressure)
- `pool_pressure < 0.9`
- Circuit breaker CLOSED for `channel_id` when channel-scoped

On failure → returns `(False, reason)` and aborts.

---

## SECTION 7 — Recursion Protection

- `_metadata_resolution_context: bool` — True while inside `run_metadata_self_resolution`
- `in_metadata_resolution_context()` — public check for callers
- Set at start of `_run_single`, cleared in `finally`
- EPG trigger and TroubleshootingService call `in_metadata_resolution_context()` before invoking
- `run_metadata_self_resolution` does not call TroubleshootingService

---

## SECTION 8 — Production Safety Verification

| Check | Status |
|-------|--------|
| No streaming modifications | ✓ |
| No restart path changes | ✓ |
| No DB schema changes | ✓ |
| No new background loops (beyond 5-min scheduler task) | ✓ |
| No memory growth (bounded dicts/sets) | ✓ |
| No blocking calls (asyncio.Lock, async) | ✓ |
| No recursion | ✓ |
| No restart storms | ✓ |
| Max 1 resolution per channel per cooldown | ✓ |

---

## SECTION 9 — Final Metadata Self-Resolution Status

**Status:** Production-hardened and ready for activation.

**Activation:** Set `ai_agent.metadata_self_resolution_enabled: true` in config to enable.

**Behavior:**
- Runs only when enabled and all guardrails pass
- Triggers: EPG early warning, Troubleshooting metadata queries, or 5-min schedule when ratio > 0.2
- Duplicate prevention, cooldown, and failure memory limit run frequency and avoid ineffective loops
