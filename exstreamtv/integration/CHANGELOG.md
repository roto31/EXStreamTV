# Integration Component Changelog

All notable changes to the Integration component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to integration module in this release

## [2.0.0] - 2026-01-14
### Added
- **IPTV Source System** (`iptv_sources.py`)
  - M3U/M3U8 playlist parsing with auto-refresh
  - Xtream Codes API support
  - Multi-source management with filtering

- **HDHomeRun Tuner Input** (`hdhomerun_tuner.py`)
  - SSDP-based device discovery
  - Channel lineup import
  - Tuner status monitoring

- **Notification Services** (`notifications.py`)
  - Discord webhook integration
  - Telegram bot API support
  - Pushover notifications
  - Slack webhook support
  - Multi-service routing with priority filtering

- **Home Assistant Integration** (`homeassistant.py`)
  - Media player entity
  - Server status and stream count sensors
  - Event firing for automations

- **Plugin System** (`plugins.py`)
  - Plugin discovery and lifecycle management
  - Source, Provider, and Notification plugin types
  - Hook system for events

- **Cloud Storage** (`cloud_storage.py`)
  - Google Drive with OAuth2
  - Dropbox API integration
  - S3/Backblaze B2 support
  - Presigned URL generation for streaming
