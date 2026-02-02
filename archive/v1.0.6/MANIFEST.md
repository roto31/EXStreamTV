# EXStreamTV v1.0.6 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Complete Module Port

## Summary

Major release: Complete module port from StreamTV bringing the codebase to 115+ Python modules.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| API | 1.0.6 | Created |
| HDHomeRun | 1.0.6 | Created |
| Importers | 1.0.6 | Created |
| Metadata | 1.0.6 | Created |
| Utils | 1.0.6 | Created |
| Validation | 1.0.6 | Created |
| Services | 1.0.6 | Created |
| Scheduling | 1.0.6 | Created |
| Media Sources | 1.0.6 | Created |
| Transcoding | 1.0.6 | Created |

## New Modules

### HDHomeRun
- SSDP server for device discovery
- HDHomeRun API emulation for Plex/Jellyfin/Emby

### API Routes (30+)
- Channels, Playlists, Schedules, Auth, IPTV endpoints

### Importers
- M3U, Plex, YouTube importers

### Supporting Modules
- `integration/` - External service integrations
- `metadata/` - Media metadata providers
- `middleware/` - Request middleware
- `scheduling/` - Schedule management
- `services/` - Background services
- `utils/` - Utility functions
- `validation/` - Input validation

## Metrics

- 115+ Python modules
- 36 HTML templates
- Complete WebUI with Apple Design System

## Previous Version

← v1.0.5: WebUI Templates

## Next Version

→ v1.0.7: Import Path Updates
