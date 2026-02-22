# EXStreamTV

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)]()
[![Version](https://img.shields.io/badge/Version-2.6.0-blue.svg)](https://github.com/roto31/EXStreamTV)

EXStreamTV creates custom live TV channels from online sources (YouTube, Archive.org) and local media (Plex, Jellyfin, Emby, local folders). Plex DVR treats it as an HDHomeRun tuner — discover, add, and tune your channels like a physical device.

## What It Does

- Streams YouTube and Archive.org without downloading
- Pulls content from Plex, Jellyfin, Emby, and local folders
- Schedules channels with block scheduling, templates, and filler
- Emulates HDHomeRun so Plex DVR can discover and tune channels
- Provides M3U/EPG for IPTV players and a web interface

## Plex Integration

Plex discovers EXStreamTV as an HDHomeRun device on your network. After adding the DVR, you see your custom channels in the lineup. Tuning a channel starts live streaming; multiple clients can share the same stream.

See [Platform Guide](docs/PLATFORM_GUIDE.md#3-hdhomrun-emulation) for how discovery, lineup, and tuning work.

## Architecture Overview

```
Clients (Plex, IPTV, Web) → REST / M3U / HDHomeRun API → SessionManager → ChannelManager
    → ProcessPoolManager (FFmpeg) → StreamThrottler → Live MPEG-TS
```

Restarts are bounded by a global throttle (10 per 60s), per-channel cooldown (30s), and a per-channel circuit breaker. The ProcessPoolManager is the sole gatekeeper for FFmpeg process spawning.

See [Platform Guide](docs/PLATFORM_GUIDE.md) for full architecture and diagrams.

## Key Features

- **HDHomeRun Emulation** — Plex, Emby, Jellyfin DVR support
- **Hardware Transcoding** — NVENC, QSV, VAAPI, VideoToolbox, AMF
- **Advanced Scheduling** — Time slots, balance scheduling, filler
- **AI Agent** — Bounded diagnostic and remediation loop (optional)
- **macOS Menu Bar App** — Native app with onboarding wizard
- **Session Management & Throttling** — Tunarr/dizqueTV-style delivery

## Feature Flags (Summary)

| Area | Key Flags | Default |
|------|-----------|---------|
| AI Agent | `ai_agent.bounded_agent_enabled` | false |
| Metadata Self-Resolution | `ai_agent.metadata_self_resolution_enabled` | false |
| HDHomeRun | `hdhomerun.enabled` | true |
| Stream Throttler | `stream_throttler.enabled` | true |

See [Feature Flags](docs/FEATURE_FLAGS.md) for full reference.

## Safety Guarantees

- **Bounded restarts** — Throttle, cooldown, and circuit breaker prevent restart storms
- **Containment mode** — AI agent stops when restart velocity or pool pressure is high
- **Confidence gating** — Metadata tools require minimum confidence before running
- **No unbounded loops** — Agent loop capped at 3 steps; no tool-from-tool
- **Automatic shutdown** — Stops after 3 consecutive metadata tool failures

See [Platform Guide](docs/PLATFORM_GUIDE.md#10-production-readiness--safety-model) for details.

## Quick Start

### macOS
```bash
cd EXStreamTV
./scripts/install_macos.sh
./start.sh
```

### macOS App (Recommended)
```bash
cd EXStreamTVApp
swift build -c release
cp -r .build/release/EXStreamTVApp.app /Applications/
```
Launch the app and follow the onboarding wizard.

### Docker
```bash
cd containers/docker
docker-compose up -d
```

### AI Setup (Optional)
Get a free Groq API key at [console.groq.com](https://console.groq.com) for AI-assisted channel creation.

Access the web interface at `http://localhost:8411`

## Requirements

- **Python**: 3.10 or higher
- **FFmpeg**: With hardware acceleration support
- **Network**: Internet for online streaming sources

## Documentation

| Document | Description |
|----------|-------------|
| [Platform Guide](docs/PLATFORM_GUIDE.md) | Full architecture, streaming, HDHomeRun, AI, observability |
| [Installation](docs/guides/INSTALLATION.md) | Installation steps |
| [Quick Start](docs/guides/QUICK_START.md) | First channel in 10 minutes |
| [AI Setup](docs/guides/AI_SETUP.md) | AI configuration and bounded agent |
| [Streaming Stability](docs/guides/STREAMING_STABILITY.md) | Session management, throttling, error screens |
| [API Reference](docs/api/README.md) | REST and IPTV endpoints |
| [Observability](docs/OBSERVABILITY.md) | Prometheus metrics and alerting |
| [Operational Guide](docs/OPERATIONAL_GUIDE.md) | Diagnosis and verification |

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Plex "Could not Tune Channel" | DeviceID must be 8 hex chars. See `config.yaml` → `hdhomerun.device_id`. Re-add DVR in Plex after fixing. |
| Restarts blocked | Circuit breaker or storm throttle. Check `/metrics` for `exstreamtv_circuit_breaker_state` and restart rate. |
| No stream output | Channel health: last output > 180s. Check logs for `ProcessPoolManager` or FFmpeg errors. |
| High memory / FDs | Pool pressure. Reduce channels or increase `ffmpeg.max_processes` if system allows. |
| AI not acting | `bounded_agent_enabled` and `metadata_self_resolution_enabled` default to false. Check containment mode. |

See [Operational Guide](docs/OPERATIONAL_GUIDE.md) for detailed diagnosis.

## Project Structure

```
EXStreamTV/
├── exstreamtv/           # Python backend
│   ├── api/              # REST, IPTV, HDHomeRun
│   ├── ai_agent/         # Bounded agent, tools, metadata resolution
│   ├── streaming/        # ChannelManager, ProcessPoolManager, CircuitBreaker
│   ├── scheduling/       # Playout engine
│   ├── ffmpeg/           # Transcoding pipeline
│   └── monitoring/       # Metrics, Prometheus
├── EXStreamTVApp/        # macOS menu bar app
├── containers/           # Docker
├── tests/                # pytest suite
└── docs/                 # Documentation
```

## Migration

### From StreamTV
```bash
python scripts/migrate_from_streamtv.py --source /path/to/streamtv
```

### From ErsatzTV
```bash
python scripts/migrate_from_ersatztv.py --source /path/to/ersatztv
```

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License — see [LICENSE](LICENSE).

## Acknowledgments

- [StreamTV](https://github.com/roto31/StreamTV) — Original Python streaming platform
- [ErsatzTV](https://github.com/ErsatzTV/ErsatzTV) — Scheduling and transcoding
- [pseudotv-plex](https://github.com/DEFENDORe/pseudotv) — Original inspiration
- [dizquetv](https://github.com/vexorian/dizquetv) — Community fork inspiration
