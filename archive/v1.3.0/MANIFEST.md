# EXStreamTV v1.3.0 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: WebUI Extensions (Phase 6)

## Summary

Enhanced dashboard and new WebUI pages for EPG, media browsing, and schedule building.

## New Templates

- `templates/guide.html` - EPG/Program Guide with timeline view
- `templates/media_browser.html` - Media browser with filters
- `templates/schedule_builder.html` - Visual schedule builder
- `templates/system_monitor.html` - System resource monitoring
- `templates/channel_editor.html` - Channel configuration editor
- `templates/libraries.html` - Library management UI

## Enhanced Templates

- `templates/dashboard.html` - Live stats integration

## API Additions

- `exstreamtv/api/dashboard.py` - Dashboard statistics API
- System resource monitoring (CPU, memory, disk)
- Active stream tracking

## Route Integration

- Added routes for all new pages in `main.py`
- Navigation links updated in base template

## Previous Version

← v1.2.0: Local Media Libraries

## Next Version

→ v1.4.0: macOS App Enhancement
