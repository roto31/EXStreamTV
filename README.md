# EXStreamTV

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)]()
[![Version](https://img.shields.io/badge/Version-2.6.0-blue.svg)](https://github.com/roto31/EXStreamTV)

**EXStreamTV** is a unified IPTV streaming platform combining the best of [StreamTV](https://github.com/roto31/StreamTV) and [ErsatzTV](https://github.com/ErsatzTV/ErsatzTV). Stream from online sources (YouTube, Archive.org) and local media libraries to create custom TV channels with advanced scheduling, hardware transcoding, and EPG support.

## Key Features

### From StreamTV (Preserved)
- **Direct Online Streaming**: YouTube and Archive.org without downloads
- **Apple Design WebUI**: Modern, responsive interface with sidebar navigation
- **AI Agent**: Intelligent log analysis and error detection
- **HDHomeRun Emulation**: Native Plex, Emby, Jellyfin integration
- **macOS Menu Bar App**: Native menu bar application with onboarding wizard

### From ErsatzTV (Ported)
- **Hardware Transcoding**: NVENC, QSV, VAAPI, VideoToolbox, AMF
- **Local Media Libraries**: Plex, Jellyfin, Emby, local folders
- **Advanced Playouts**: Block scheduling, templates, filler content
- **Sophisticated EPG**: Rich metadata, multi-episode grouping

### New in v2.6
- **Tunarr/dizqueTV Integration**: Session management, stream throttling, error screens, time-slot and balance scheduling
- **AI Self-Healing**: Unified log collector, FFmpeg monitor, pattern detection, auto-resolver
- **Database Backup**: Scheduled backups with rotation and compression
- **AI-Powered Channel Creation**: Use AI to design and schedule channels (Groq, SambaNova, OpenRouter, Ollama)
- **Native Video Player**: Watch channels directly in the macOS app
- **6-Step Onboarding Wizard**: Guided first-run setup experience

## Quick Start

### macOS
```bash
cd EXStreamTV
./scripts/install_macos.sh
./start.sh
```

### macOS App (Recommended)
```bash
# Build and install the menu bar app
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

### Getting Started
- [Installation Guide](docs/guides/INSTALLATION.md)
- [Quick Start](docs/guides/QUICK_START.md)
- [Onboarding Guide](docs/guides/ONBOARDING.md) - First-run setup wizard

### Features
- [AI Setup Guide](docs/guides/AI_SETUP.md) - Configure cloud or local AI
- [macOS App Guide](docs/guides/MACOS_APP_GUIDE.md) - Menu bar app features
- [Hardware Transcoding](docs/guides/HW_TRANSCODING.md)
- [Local Media Setup](docs/guides/LOCAL_MEDIA.md)

### Reference
- [API Reference](docs/api/README.md)
- [Architecture](docs/architecture/SYSTEM_DESIGN.md)
- [Distribution Guide](docs/development/DISTRIBUTION.md) - Building installers
- [MCP Server](docs/mcp/README.md) - Model Context Protocol server for Cursor / Claude Desktop

## Project Structure

```
EXStreamTV/
├── exstreamtv/           # Main Python package
│   ├── api/              # REST API endpoints
│   ├── ai_agent/         # AI log analysis & channel creation
│   │   └── providers/    # Cloud AI providers (Groq, SambaNova, OpenRouter)
│   ├── database/         # SQLAlchemy models & migrations
│   ├── ffmpeg/           # Hardware transcoding pipeline
│   ├── media/            # Local media management
│   ├── scheduling/       # Advanced playout engine
│   ├── streaming/        # Channel streaming
│   └── templates/        # WebUI templates
├── EXStreamTVApp/        # macOS Menu Bar Application
│   └── Sources/
│       ├── Views/        # SwiftUI views including Onboarding/
│       └── Services/     # AI, Dependency, Login managers
├── containers/           # Docker deployment
├── distributions/        # macOS PKG/DMG installers
├── scripts/              # Installation scripts
├── mcp_server/           # MCP server (docs, config, API context for AI tools)
├── mcp/                  # MCP descriptors (tools, SERVER_METADATA)
├── tests/                # Test suite
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

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [StreamTV](https://github.com/roto31/StreamTV) - Original Python streaming platform
- [ErsatzTV](https://github.com/ErsatzTV/ErsatzTV) - Advanced scheduling and transcoding features
- [pseudotv-plex](https://github.com/DEFENDORe/pseudotv) - Original inspiration
- [dizquetv](https://github.com/vexorian/dizquetv) - Community fork inspiration

---

**Made with care for the IPTV community**
