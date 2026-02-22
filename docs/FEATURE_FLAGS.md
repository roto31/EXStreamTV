# Feature Flags

**Version:** 2.6.0  
**Last Updated:** 2026-02-21

This document lists config toggles that control features. All keys are under `config.yaml` (or environment variables with `EXSTREAMTV_` prefix where applicable).

---

## AI Agent

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ai_agent.enabled` | bool | true | Master AI switch |
| `ai_agent.bounded_agent_enabled` | bool | false | Bounded agent loop |
| `ai_agent.bounded_agent_mode` | str | "diagnostic" | diagnostic, remediation, metadata, full |
| `ai_agent.metadata_self_resolution_enabled` | bool | false | Metadata self-resolution |
| `ai_agent.metadata_self_resolution_cooldown_sec` | int | 300 | Cooldown between resolutions |
| `ai_agent.metadata_self_resolution_disable_hours` | float | 1.0 | Suspend duration after failures |
| `ai_agent.force_metadata_resolution` | bool | false | Bypass confidence gate |

---

## Auto Healer

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ai_auto_heal.enabled` | bool | true | Master auto-healer switch |
| `ai_auto_heal.self_healing_toggle` | bool | true | Self-healing |
| `ai_auto_heal.channel_creator_toggle` | bool | true | Channel creator |
| `ai_auto_heal.troubleshooting_toggle` | bool | true | Troubleshooting |
| `ai_auto_heal.pattern_detection_enabled` | bool | true | Pattern detection |
| `ai_auto_heal.auto_resolve_enabled` | bool | true | Auto resolution |
| `ai_auto_heal.ffmpeg_monitor_enabled` | bool | true | FFmpeg monitoring |

---

## HDHomeRun

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `hdhomerun.enabled` | bool | true | HDHomeRun emulation |
| `hdhomerun.device_id` | str | "E5E17001" | Must be 8 hex chars |
| `hdhomerun.tuner_count` | int | 4 | Virtual tuners |
| `hdhomerun.friendly_name` | str | "EXStreamTV" | Display name |

---

## Stream Throttler

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `stream_throttler.enabled` | bool | true | Rate limiting |
| `stream_throttler.target_bitrate_bps` | int | 4000000 | Target bitrate |
| `stream_throttler.mode` | str | "realtime" | realtime, burst, adaptive, disabled |

---

## Session Manager

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `session_manager.max_sessions_per_channel` | int | 50 | Max viewers per channel |
| `session_manager.idle_timeout_seconds` | int | 300 | Disconnect idle |
| `session_manager.cleanup_interval_seconds` | int | 60 | Cleanup cadence |

---

## FFmpeg / ProcessPoolManager

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ffmpeg.max_processes` | int | 150 | Max FFmpeg processes |
| `ffmpeg.spawns_per_second` | float | 5 | Token bucket rate |
| `ffmpeg.memory_guard_threshold` | float | 0.85 | Reject spawn if memory > 85% |
| `ffmpeg.fd_guard_reserve` | int | 100 | Reserve FDs |
| `ffmpeg.pool_pressure_threshold` | float | 0.80 | Early warning at 80% |
| `ffmpeg.long_run_hours` | float | 24.0 | Kill processes after N hours |

---

## EPG

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `epg.episode_num_required` | bool | false | Require episode numbers |
| `epg.plex_xmltv_mismatch_ratio_threshold` | float | 0.15 | Mismatch threshold |

---

## Related Documentation

- [Platform Guide](../PLATFORM_GUIDE.md) — Architecture
- [Observability](OBSERVABILITY.md) — Metrics
