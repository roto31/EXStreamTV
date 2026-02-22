# Observability

**Version:** 2.6.0  
**Last Updated:** 2026-02-21

This document lists all Prometheus metrics and alert thresholds. For architecture and monitoring philosophy, see [Platform Guide §6](../PLATFORM_GUIDE.md#6-observability--monitoring).

---

## Prometheus Endpoint

```
GET http://localhost:8411/metrics
```

Returns Prometheus text exposition format. Compatible with Prometheus scrape configs and Alertmanager.

---

## Metrics Reference

### FFmpeg Process Pool

| Metric | Type | Labels | Description |
|--------|------|--------|--------------|
| `exstreamtv_ffmpeg_processes_active` | gauge | — | Active FFmpeg processes |
| `exstreamtv_ffmpeg_spawn_pending` | gauge | — | Pending spawns |
| `exstreamtv_ffmpeg_spawn_rejected_total` | counter | `reason` (memory, fd, capacity) | Rejected spawns |
| `exstreamtv_ffmpeg_spawn_timeout_total` | counter | — | Spawn timeouts |
| `exstreamtv_ffmpeg_pool_pressure_events_total` | counter | — | Pool pressure events |

### Per-Channel

| Metric | Type | Labels | Description |
|--------|------|--------|--------------|
| `exstreamtv_channel_restart_total` | counter | `channel_id` | Restarts per channel |
| `exstreamtv_stream_success_total` | counter | `channel_id` | Successful streams |
| `exstreamtv_stream_failure_total` | counter | `channel_id` | Failed streams |
| `exstreamtv_channel_memory_bytes` | gauge | `channel_id` | Memory per channel |
| `exstreamtv_circuit_breaker_state` | gauge | `channel_id` | 0=closed, 1=half_open, 2=open |

### Stability

| Metric | Type | Description |
|--------|------|-------------|
| `exstreamtv_pool_acquisition_latency_seconds` | gauge | Pool acquisition time |
| `exstreamtv_restart_rate_per_minute` | gauge | Restart rate |
| `exstreamtv_health_timeouts_total` | counter | Health check timeouts |
| `exstreamtv_playout_rebuild_total` | counter | Playout rebuilds |

### System

| Metric | Type | Description |
|--------|------|-------------|
| `exstreamtv_system_rss_bytes` | gauge | Resident set size |
| `exstreamtv_fd_usage` | gauge | Open file descriptors |
| `exstreamtv_event_loop_lag_seconds` | gauge | Event loop lag |
| `exstreamtv_db_pool_checked_out` | gauge | DB connections in use |
| `exstreamtv_db_pool_size` | gauge | DB pool size |

### Metadata

| Metric | Type | Description |
|--------|------|-------------|
| `exstreamtv_metadata_lookup_success_total` | counter | Successful metadata lookups |
| `exstreamtv_metadata_lookup_failure_total` | counter | Failed metadata lookups |
| `exstreamtv_episode_metadata_missing_total` | counter | Missing episode metadata |
| `exstreamtv_movie_metadata_missing_total` | counter | Missing movie metadata |
| `exstreamtv_placeholder_title_generated_total` | counter | Placeholder titles used |
| `exstreamtv_xmltv_programme_missing_episode_num_total` | counter | Missing episode numbers |
| `exstreamtv_xmltv_programme_missing_desc_total` | counter | Missing descriptions |
| `exstreamtv_xmltv_programme_missing_year_total` | counter | Missing years |
| `exstreamtv_xmltv_validation_error_total` | counter | XMLTV validation errors |
| `exstreamtv_xmltv_lineup_mismatch_total` | counter | Lineup vs XMLTV mismatches |
| `exstreamtv_ai_metadata_resolution_attempt_total` | counter | AI resolution attempts |
| `exstreamtv_ai_metadata_resolution_success_total` | counter | AI resolution successes |
| `exstreamtv_ai_metadata_resolution_abort_total` | counter | AI resolution aborts |

---

## Alert Thresholds

These thresholds are defined in code for external alerting (e.g., Prometheus Alertmanager). EXStreamTV does not enforce them in-process.

| Metric / Condition | Warning | Critical |
|--------------------|---------|----------|
| metadata_failure_ratio | > 0.3 | > 0.5 |
| placeholder_ratio | > 0.2 | — |
| restart_velocity (per minute) | > 0.5 | > 2.0 |
| pool_pressure | — | > 0.9 |

---

## Early Warning Signals

The metadata pipeline emits a single structured log per EPG cycle when:

- > 5% programmes missing episode_num
- > 5% programmes missing year
- > 10 programmes with placeholder titles
- metadata_failure_ratio > 0.3
- Drift: metadata_failure_ratio increased by > 0.1 since last check

---

## Related Documentation

- [Platform Guide](../PLATFORM_GUIDE.md) — Monitoring philosophy
- [Operational Guide](OPERATIONAL_GUIDE.md) — Diagnosis and verification
