# EXStreamTV v1.0.2 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Database & FFmpeg Foundation

## Summary

Complete database model suite and FFmpeg pipeline with hardware detection.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Backend Core | 1.0.2 | Enhanced |
| Database | 1.0.2 | Complete models |
| FFmpeg Pipeline | 1.0.2 | Created |
| Scripts | 1.0.2 | Created |

## Database Models Added

### Channel Models
- Channel, ChannelWatermark, ChannelFFmpegProfile

### Playlist Models
- Playlist, PlaylistGroup, PlaylistItem

### Media Models
- MediaItem, MediaFile, MediaVersion

### Playout Models
- Playout, PlayoutItem, PlayoutAnchor, PlayoutHistory, PlayoutTemplate

### Schedule Models
- ProgramSchedule, ProgramScheduleItem, Block, BlockGroup, BlockItem

### Other Models
- FillerPreset, FillerPresetItem
- Deco, DecoGroup
- Template, TemplateGroup, TemplateItem
- PlexLibrary, JellyfinLibrary, EmbyLibrary, LocalLibrary
- FFmpegProfile, Resolution

## FFmpeg Module

- Hardware capability detection (VideoToolbox, NVENC, QSV, VAAPI, AMF)
- Pipeline builder with StreamTV bug fixes preserved
- Encoder auto-selection based on platform

## Files Created

- `exstreamtv/main.py` - Main FastAPI application
- `exstreamtv/database/models/*.py` - All model files
- `exstreamtv/ffmpeg/` - FFmpeg module
- `alembic.ini` - Alembic migration configuration
- `scripts/migrate_from_streamtv.py`
- `scripts/migrate_from_ersatztv.py`

## Previous Version

← v1.0.1: Project Infrastructure

## Next Version

→ v1.0.3: Streaming Module
