# Media Management Component Changelog

All notable changes to the Media Management component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to media module in this release

## [2.0.1] - 2026-01-17
### Enhanced
- Extended `media_to_response()` with additional fields
- Added: `media_type`, `year`, `content_rating`, `genres`, `studio`
- Added: `show_title`, `season_number`, `episode_number`
- Added: `poster_path`, `art_url`, `added_date`, `originally_available`, `rating`

## [1.2.0] - 2026-01-14
### Added
- **Library Abstractions**
  - `libraries/base.py` - BaseLibrary ABC with LibraryManager
  - `libraries/local.py` - Local folder library implementation
  - `libraries/plex.py` - Plex Media Server integration
  - `libraries/jellyfin.py` - Jellyfin & Emby integration

- **Media Scanning**
  - `scanner/base.py` - Scanner base class and data types
  - `scanner/ffprobe.py` - FFprobe media analysis
  - `scanner/file_scanner.py` - Concurrent file discovery

- **Metadata Providers**
  - `providers/base.py` - Provider interface
  - `providers/tmdb.py` - TMDB movies and TV
  - `providers/tvdb.py` - TVDB TV series
  - `providers/nfo.py` - NFO file parser

- **Collections**
  - `collections.py` - Show/season/movie collection organizer
