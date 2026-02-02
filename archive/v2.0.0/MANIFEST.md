# EXStreamTV v2.0.0 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Major Release - ErsatzTV-Compatible API (Phase 11)

## Summary

**Major milestone**: All 11 development phases complete with full ErsatzTV feature parity.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Integration | 2.0.0 | Created |
| All existing | 2.0.0 | Updated |

## New APIs

### Blocks API (`exstreamtv/api/blocks.py`)
- Time-based programming blocks
- Block groups for organizing related blocks
- Day-of-week scheduling with bitmask support
- Block items with collection references

### Filler Presets API (`exstreamtv/api/filler_presets.py`)
- Gap-filling content management
- Three filler modes: duration, count, pad-to-boundary
- Weighted item selection

### Templates API (`exstreamtv/api/templates.py`)
- Reusable schedule patterns
- Template groups for organization
- Apply templates to channels

### Deco API (`exstreamtv/api/deco.py`)
- Decorative content (bumpers, station IDs)
- Five deco types: bumper, commercial, station_id, promo, credits

### Scripted Schedule API (`exstreamtv/api/scripted.py`)
- 27 endpoints for complete schedule control
- Programmatic playout building

## Integration Module (`exstreamtv/integration/`)

- **IPTV Sources**: M3U/M3U8 parsing, Xtream Codes API
- **HDHomeRun Tuner**: SSDP device discovery
- **Notifications**: Discord, Telegram, Pushover, Slack
- **Home Assistant**: Media player entity, sensors
- **Plugin System**: Extensibility framework
- **Cloud Storage**: Google Drive, Dropbox, S3/B2

## New Database Models

- `MultiCollection` and `MultiCollectionLink`
- `PlayoutBuildSession`

## WebUI Additions

- Blocks management page
- Filler presets page
- Templates page
- Deco page

## Milestone

- Full feature parity with ErsatzTV
- Enhanced with StreamTV's AI agent and Apple Design UI

## Previous Version

← v1.8.0: Performance Optimization

## Next Version

→ v2.0.1: Media Filtering & UI Improvements
