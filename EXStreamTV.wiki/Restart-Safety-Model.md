# Restart Safety Model

See [Platform Guide](Platform-Guide#2-how-streaming-works) for restart guards, decision flow, and [Invariants](Invariants) for formal invariants.

Three mechanisms: global throttle (10/60s), per-channel cooldown (30s), circuit breaker (5 failures → 120s block).

**Last Revised:** 2026-03-20
