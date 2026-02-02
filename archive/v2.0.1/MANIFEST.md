# EXStreamTV v2.0.1 Archive Manifest

**Release Date**: 2026-01-17  
**Status**: Media Filtering & UI Improvements

## Summary

Media library filtering system and UI bug fixes.

## Changes

### Media Library Filters
- `exstreamtv/api/media.py` - Comprehensive filtering system
- Filter parameters: `media_type`, `year`, `year_min`, `year_max`, `duration_min`, `duration_max`, `content_rating`, `genre`, `search`
- Sorting support with NULL-safe ordering
- `GET /api/media/filters` endpoint for dynamic filter options

### Server Management Scripts
- `start.sh` - Start the server
- `restart.sh` - Stop existing server and start fresh
- `stop.sh` - Stop the running server
- Color-coded output, auto-creates config.yaml

### UI Filter Panel
- `exstreamtv/templates/media.html` - Collapsible advanced filters
- Filter dropdowns, genre text input, sort controls
- Active filter count badge

### Bug Fixes
- Missing `</div>` tag in filters panel
- Grid class not reset when switching libraries
- View mode rendering wrong variable
- Missing loading element
- Slide-out panel episode fetching
- Poster cropping in detail panel

### Other Fixes
- Added EPG constants to `constants.py`
- Fixed `MultiCollectionLink.collection_id` foreign key

## Previous Version

← v2.0.0: ErsatzTV-Compatible API

## Next Version

→ v2.1.0: AI Channel Creator Personas
