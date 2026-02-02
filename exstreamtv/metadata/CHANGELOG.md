# Metadata Component Changelog

All notable changes to the Metadata component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to metadata module in this release

## [1.0.6] - 2026-01-14
### Added
- **Clients**
  - `clients/tmdb_client_v2.py` - TMDB API client
  - `clients/tvdb_client.py`, `clients/tvdb_client_v2.py` - TVDB API clients

- **Extractors**
  - `extractors/archive_org_v2.py` - Archive.org metadata extraction
  - `extractors/plex_v2.py` - Plex metadata extraction
  - `extractors/youtube_v2.py` - YouTube metadata extraction

- **Engine**
  - `engine_v2.py` - Metadata engine coordination
  - `enricher.py` - Metadata enrichment
  - `extractor.py` - Metadata extraction utilities
  - `refresh_task.py` - Scheduled metadata refresh

- **AI Enhancement**
  - `ai_enhancer_v2.py` - AI-powered metadata enhancement
  - `api_key_manager_v2.py` - API key management
