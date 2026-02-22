# Operational Guide

**Version:** 2.6.0  
**Last Updated:** 2026-02-21

This guide describes how to diagnose issues, read logs, and verify system health. For architecture, see [Platform Guide](../PLATFORM_GUIDE.md).

---

## Diagnosing Issues

### 1. Check Prometheus Metrics

```bash
curl http://localhost:8411/metrics
```

Key metrics:

| Metric | Healthy | Investigate |
|--------|---------|-------------|
| `exstreamtv_restart_rate_per_minute` | < 0.5 | High restart rate |
| `exstreamtv_circuit_breaker_state{channel_id="X"}` | 0 (closed) | 2 = open, restarts blocked |
| `exstreamtv_ffmpeg_processes_active` | < max_processes | Near capacity |
| `exstreamtv_stream_failure_total` | Low relative to success | Per-channel failures |
| `exstreamtv_health_timeouts_total` | 0 | Channels timing out |

### 2. Review Logs

- **Channel health** — `Channel X no output for Ys` indicates stale stream
- **Restart storm** — `Restart storm throttle` means global limit hit
- **Circuit breaker** — `Circuit breaker OPEN for channel X` means restarts blocked
- **ProcessPoolManager** — `Spawn rejected`, `pool pressure`, `zombie process`
- **Metadata** — `EPG metadata early warning`, `Metadata drift`, `Metadata enrichment degraded`

### 3. Verify HDHomeRun

```bash
curl http://localhost:8411/hdhomerun/discover.json
curl http://localhost:8411/hdhomerun/lineup.json
```

- `DeviceID` must be 8 hex characters (e.g., `E5E17001`)
- `lineup.json` must return non-empty array, unique GuideNumbers, non-empty URLs
- If Plex reports "Could not Tune Channel," re-add DVR after fixing DeviceID

---

## Verifying Stream Health

- Web UI channel status
- `exstreamtv_stream_success_total` and `exstreamtv_stream_failure_total` per channel
- `last_output_time` recent for active channels (health task checks every 30s)

---

## Verifying XMLTV Integrity

- `exstreamtv_xmltv_validation_error_total` — should be 0 in normal operation
- `exstreamtv_xmltv_lineup_mismatch_total` — indicates lineup vs XMLTV inconsistency
- Fetch EPG URL and validate structure if needed

---

## Safely Disabling AI

Set in `config.yaml`:

```yaml
ai_agent:
  enabled: false                    # All AI off
  # Or granular:
  bounded_agent_enabled: false       # Bounded loop off (default)
  metadata_self_resolution_enabled: false  # Metadata self-res off (default)
```

---

## Common Issues

| Symptom | Check | Resolution |
|---------|-------|------------|
| Plex "Could not Tune Channel" | DeviceID format | Use 8 hex chars; re-add DVR |
| Restarts blocked | Circuit breaker, storm throttle | Wait for cooldown; reduce channel load |
| No stream output | Health, FFmpeg | Check logs; verify source availability |
| High memory / FDs | Pool pressure | Reduce channels or tune `max_processes` |
| AI not acting | Flags, containment | Enable flags; check containment mode |

---

## Log Interpretation

| Log Message | Meaning |
|-------------|---------|
| `Restart storm throttle: N restarts in 60s` | Global limit hit; all restarts blocked |
| `Restart cooldown: channel X last restart Ys ago` | Per-channel cooldown active |
| `Circuit breaker OPEN for channel X` | Restarts blocked for 120s |
| `ProcessPoolManager: pool pressure` | FFmpeg capacity near limit |
| `ProcessPoolManager: zombie process` | Exited FFmpeg not yet cleaned |
| `Long-run leak detection: RSS increased` | Containment mode; agent disabled |
| `EPG metadata early warning` | Metadata thresholds crossed |
| `Metadata drift: failure_ratio increased` | Enrichment degraded |

---

## Related Documentation

- [Platform Guide](../PLATFORM_GUIDE.md) — Full operational context
- [Observability](OBSERVABILITY.md) — Metrics reference
- [Feature Flags](FEATURE_FLAGS.md) — Config toggles
