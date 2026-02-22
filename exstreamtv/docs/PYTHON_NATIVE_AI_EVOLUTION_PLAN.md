# Python-Native AI Evolution Plan

> **User-facing overview:** For AI agent safety model and containment, see [PLATFORM_GUIDE.md](../../docs/PLATFORM_GUIDE.md).

**Constraint:** Stability > intelligence; Containment > automation; Determinism > autonomy  
**Scope:** Bounded multi-step reasoning, safe tool-calling, structured grounding, persona safety

---

## SECTION 1 — Current AI Stability Profile

### AI Call Flow

| Component | Entry | Flow | LLM |
|-----------|-------|------|-----|
| TroubleshootingService | `analyze_and_suggest()` | LogAnalyzer → build_prompt → Ollama/provider → _extract_fixes_from_response | Single shot |
| FixSuggester | `suggest_fixes()` | Sync POST `/api/generate` | Single shot |
| ChannelCreatorAgent | `create_from_spec()` | OllamaClient.chat / provider.generate | Single shot |

No agent loop, no tool-calling.

### PersonaManager

- `PersonaType` enum (7), `PersonaInfo`, `PersonaContext`
- Static prompt templates; no risk tolerance, tool policy, operational mode

### PatternDetector

- Rule-based `KNOWN_PATTERNS`, `_classify_error()`, `find_root_cause()` — no LLM
- Output: PatternAnalysis, FailurePrediction, RootCauseAnalysis
- **Not wired:** instantiated in main.py, no event callers

### AutoResolver

- `STRATEGY_MAP` (IssueType → ResolutionStrategy)
- `_apply_restart()`: `stop_channel()` only, no `start_channel()`; **bypasses** health_tasks, circuit breaker, storm throttle
- **Not wired:** `resolve()` never invoked

### Restart Triggers

| Source | Guard |
|--------|-------|
| health_tasks._trigger_channel_restart | _can_trigger_restart (storm, cooldown, circuit breaker) |
| ChannelStream._auto_restart | max_restarts=5, exponential backoff |
| AutoResolver._apply_restart | None (bypasses all) |

### Retries / Loops

| Location | Bound |
|----------|-------|
| health_tasks | Every 30s |
| acquire_process | max_attempts=5 |
| TokenBucket | while+sleep (no recursion) |
| ChannelStream._stream_loop | Task lifecycle |
| playout_tasks | Every 5 min |

### Async Boundaries

- TroubleshootingService, health_tasks, AutoResolver, CircuitBreaker: async
- FixSuggester: sync

### Classification

**Reactive / Heuristic / Deterministic / Semi-structured**

### Weaknesses

- Multi-step: none
- Tool orchestration: none; AutoResolver would bypass guards if wired
- Deterministic containment: AutoResolver divergent
- Hallucination: free-form LLM; brittle fix extraction
- Restart governance: health_tasks correct; AutoResolver unsafe

---

## SECTION 2 — Bounded Agent Loop Architecture

### State Machine

```
State → Evidence → Plan → Tool → Observe → Score → Continue | Stop
```

### Hard Requirements

- Iteration cap: `max_steps=3`
- Cooldown: 5s between tools
- No recursive self-invocation
- No tool-from-tool
- Restart only via `_can_trigger_restart`
- Circuit-breaker aware
- Async-safe; no DB mutation from agent

### Option Comparison

| Criterion | A) Instructor | B) LangChain | C) Custom |
|-----------|---------------|--------------|-----------|
| Stability | Good | Medium | Full control |
| Storm risk | Low | Medium | Low |
| Debug | Medium | High | Low |
| Deps | +instructor | +langchain | None |

### Recommendation: **Option C — Custom In-House**

- Zero deps; explicit containment; minimal surface
- Single module `bounded_agent_loop.py`

```
async def run_bounded_loop(envelope, persona, max_steps=3):
    for step in range(max_steps):
        if envelope.containment_mode: return escalate()
        plan = await plan_next_step(state, persona)
        if plan.action == "STOP": return finalize()
        await enforce_cooldown(step)
        result = await execute_tool(plan.tool_id, plan.params)
        state = observe_and_update(state, result)
        if not should_continue(state, result): return finalize()
    return finalize()
```

---

## SECTION 3 — Hardened Tool Exposure Model

| Tool | Input | Output | Risk | Cooldown | Retry | Idempotent | CB |
|------|-------|--------|------|----------|-------|------------|-----|
| restart_channel | channel_id | success | HIGH | 30s | 1 | No | MUST use _can_trigger_restart |
| refresh_plex_token | — | success | LOW | 60s | 2 | Yes | — |
| fetch_recent_logs | channel_id? | LogEvent[] | LOW | 5s | 3 | Yes | — |
| inspect_pool_status | — | active, max, pressure | LOW | 10s | 3 | Yes | — |
| get_channel_health | channel_id | metrics | LOW | 5s | 3 | Yes | — |
| rebuild_playout | channel_id | success | MEDIUM | 120s | 1 | No | — |
| invalidate_cache | channel_id? | success | LOW | 30s | 2 | Yes | — |

**restart_channel:** Route through `_trigger_channel_restart`; reject if containment_mode or restart_count >= cap.

**Prevention:** No HIGH-risk clustering (max 1/loop, 60s cooldown); check pool_pressure before HIGH.

---

## SECTION 4 — Structured Grounding 2.0

### GroundedContextEnvelope

```
channel_id, failure_classification, restart_count, restart_velocity,
pool_pressure, last_error_type, error_frequency, last_action,
cooldown_remaining, confidence, timestamp, containment_mode
```

**Sources:** PatternDetector, health_tasks metrics, ProcessPoolManager, LogCollector.

**Hallucination:** Envelope injected into prompt; tools constrained by envelope.

**Blind remediation:** restart requires non-empty failure_classification.

**Restart storms:** containment_mode → no HIGH-risk tools.

**Determinism:** Envelope fully observable; preconditions checked.

---

## SECTION 5 — Persona Safety Model

### Persona YAML

```yaml
id: system_admin
risk_tolerance: medium
aggressiveness: moderate
tool_access_policy:
  restart_channel: require_evidence
  rebuild_playout: require_approval
escalation_policy:
  on_containment: immediate
containment_bias: true
operational_mode: remediation  # diagnostic | remediation | containment | passive
restart_cap: 3
planning_depth_max: 2
retry_threshold: 0.6
```

**Effects:** planning_depth_max caps steps; tool_access_policy filters; retry_threshold gates continue; escalation on containment; operational_mode restricts tool set.

---

## SECTION 6 — Restart Storm Protection Model

### Trigger

```
containment_mode = (
  restart_velocity >= 10/60
  OR circuit_breaker OPEN
  OR pool_pressure >= 0.9
)
```

### Agent in Containment

- Disable HIGH-risk tools
- Cooldown 60s
- Return "Escalate to operator"

---

## SECTION 7 — Phased Migration Plan

| Phase | Scope | Metric |
|-------|-------|--------|
| 0 | Envelope builder, observability | exstreamtv_grounded_envelope_events_total |
| 1 | Read-only tools only | Diagnostic latency |
| 2 | LOW-risk tools | Fix application rate |
| 3 | restart_channel via guard, rebuild_playout | MTTR, storm frequency |
| 4 | Full loop, max_steps=3 | MTBF, hallucination (audit) |

**Targets:** MTBF neutral; MTTR improved; no storm increase; false positive <5%; latency variance <50ms p99.

---

## SECTION 8 — Production Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Async deadlock | LOW | Single Lock per run |
| Event loop block | LOW | No sync LLM in loop |
| ProcessPool | MODERATE | Restart via health_tasks only |
| ChannelManager | MODERATE | No direct calls from agent |
| Memory | LOW | Bounded envelope |
| Debug | LOW | Linear flow |
| Ops overhead | LOW | Config-driven |

---

## SECTION 9 — Final Recommendation

1. **Custom loop (Option C)** — zero deps, full containment control.
2. **Unify restart path** — Route all restarts through `_can_trigger_restart`.
3. **Wire PatternDetector/AutoResolver** — Event bridge: LogCollector → PatternDetector → envelope; AutoResolver invoked only from agent with guarded restart.
4. **Implement envelope first** — Phase 0 yields value without agent risk.
5. **Persona YAML** — Load at startup; extend PersonaManager.
6. **No OpenClaw** — Fully Python-native.
