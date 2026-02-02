# EXStreamTV v1.2.0 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Local Media Libraries (Phase 4)

## Summary

Local media library support with library abstractions, media scanning, and metadata providers.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Media Management | 1.2.0 | Created |

## Media Module Structure

### Library Abstractions
- `libraries/base.py` - BaseLibrary ABC with LibraryManager
- `libraries/local.py` - Local folder library implementation
- `libraries/plex.py` - Plex Media Server integration
- `libraries/jellyfin.py` - Jellyfin & Emby integration

### Media Scanning
- `scanner/base.py` - Scanner base class and data types
- `scanner/ffprobe.py` - FFprobe media analysis
- `scanner/file_scanner.py` - Concurrent file discovery

### Metadata Providers
- `providers/base.py` - Provider interface
- `providers/tmdb.py` - TMDB movies and TV
- `providers/tvdb.py` - TVDB TV series
- `providers/nfo.py` - NFO file parser

### Collections
- `collections.py` - Show/season/movie collection organizer

### API Routes
- `exstreamtv/api/libraries.py` - Library CRUD and scan endpoints
- `exstreamtv/api/media.py` - Media item management

### Database Models
- `exstreamtv/database/models/library.py` - Library source models
- `exstreamtv/database/models/media.py` - MediaItem, MediaVersion, MediaFile

## Previous Version

← v1.0.9: ErsatzTV Playout Engine

## Next Version

→ v1.3.0: WebUI Extensions
