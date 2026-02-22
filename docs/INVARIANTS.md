# Formal Invariants

**Version:** 2.6.0  
**Last Updated:** 2026-02-21

This document states the invariants the system enforces. For context and diagrams, see [Platform Guide §7](../PLATFORM_GUIDE.md#7-formal-invariants).

---

## Restart Invariants

| ID | Invariant |
|----|-----------|
| R1 | At most 10 restarts in any 60-second window (global throttle) |
| R2 | No channel restarts within 30 seconds of its previous restart (per-channel cooldown) |
| R3 | When circuit breaker is OPEN for a channel, no restart for that channel until 120s cooldown elapses |
| R4 | All restarts go through `request_channel_restart`; no direct `stop_channel`/`start_channel` from external callers |

---

## Streaming Invariants

| ID | Invariant |
|----|-----------|
| S1 | All FFmpeg processes are acquired and released via ProcessPoolManager |
| S2 | Process count never exceeds `min(config.max_processes, memory-based, FD-based)` |
| S3 | Spawn rate is limited by token bucket (default 5 per second) |
| S4 | Memory and FD guards are checked before each spawn |

---

## Agent Invariants

| ID | Invariant |
|----|-----------|
| A1 | No database writes by the agent loop |
| A2 | No tool-from-tool calls; tools execute sequentially |
| A3 | At most one HIGH-risk tool per loop |
| A4 | Containment mode blocks all tool execution |
| A5 | Restart tools route through `health_tasks.request_channel_restart` |

---

## Async Invariants

| ID | Invariant |
|----|-----------|
| U1 | No blocking I/O in agent loop or envelope builder |
| U2 | ProcessPoolManager uses asyncio.Lock for registry access |
| U3 | Circuit breaker uses asyncio.Lock for state updates |

---

## Metadata Invariants

| ID | Invariant |
|----|-----------|
| M1 | XMLTV validation runs before emit; invalid programmes raise XMLTVValidationError |
| M2 | Placeholder titles (Item \d+) are never emitted; fallbacks used |
| M3 | Drift detection does not block EPG generation or streaming |

---

## Related Documentation

- [Platform Guide](../PLATFORM_GUIDE.md) — Invariant context
