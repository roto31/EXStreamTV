# Restart Safety Model

See [Platform Guide](Platform-Guide#2-how-streaming-works) for restart guards, decision flow, and [Invariants](Invariants) for formal invariants.

Three mechanisms: global throttle (10/60s), per-channel cooldown (30s), circuit breaker (5 failures → 120s block).

## 2026-03 Remediation: Watchdog Deadlock Fix (LL-013)

The process watchdog previously called `_kill_process()` while holding `self._lock`. A kill waits up to 5 seconds for the process to respond. During that wait, every other coroutine trying to acquire the lock (e.g., `register_process`, `report_output`) was blocked — causing cascade kills across all channels.

**Fix:** processes to kill are collected inside the lock (instantaneous), then killed outside it (slow). See [Architecture Diagram 17](Architecture-Diagrams#17-async-lock-collect-then-act-pattern-2026-03-remediation--ll-013).

**Last Revised:** 2026-03-21
