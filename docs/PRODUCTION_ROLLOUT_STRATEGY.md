# Production Rollout Strategy (Section I)

1. **Phase 1 (pre-rollout):** Run 24h soak test; verify no restart invocation, no memory growth. Fix any failures.
2. **Phase 2:** Enable `metadata_self_resolution_enabled` on single-channel pilot; monitor 48h.
3. **Phase 3:** Enable globally; keep `metadata_self_resolution_cooldown_sec = 300`; monitor Prometheus alerts.
4. **Rollback:** Set `metadata_self_resolution_enabled = False`; restart or config reload. No DB migration required.
