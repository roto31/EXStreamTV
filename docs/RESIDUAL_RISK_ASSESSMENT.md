# Residual Risk Assessment (Section J)

| Risk                                   | Mitigation                                                                                  |
| -------------------------------------- | ------------------------------------------------------------------------------------------- |
| LLM API outage during resolution       | Cooldown and failure memory limit retries; resolution aborts safely.                        |
| XMLTV validation false positive        | Config `validate=False` escape hatch for diagnostics only; production always validate=True. |
| Restart storm from undiscovered caller | Formal verification CI; grep enforcement.                                                   |
| Memory growth in anomaly clustering   | Cap 1000 buckets; evict oldest.                                                             |
| Type/strict mypy breaks builds         | Incremental adoption; exclude non-core modules initially.                                   |

**Out of scope (per constraints):** No streaming pipeline changes; no restart path logic changes; no new unbounded loops; no DB schema changes.
