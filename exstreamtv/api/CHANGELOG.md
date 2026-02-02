# API Component Changelog

All notable changes to the API component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- Enhanced `/api/ai/channel/plan/{id}/execute` endpoint with BlockScheduleExecutor and CollectionExecutor
- New response fields: `block_group_id`, `blocks_created`, `collections_created`, `schedule_items_created`

## [2.4.0] - 2026-01-17
### Added
- 12 new AI Channel Creator API endpoints
- **Persona Management**: `GET /api/ai/channel/personas`, `GET /api/ai/channel/personas/{id}`, `GET /api/ai/channel/personas/{id}/welcome`
- **Intent Analysis**: `POST /api/ai/channel/analyze`
- **Source Selection**: `POST /api/ai/channel/sources`
- **Build Plan Management**: `POST /api/ai/channel/plan`, `GET /api/ai/channel/plan/{id}`, `PUT /api/ai/channel/plan/{id}`, `POST /api/ai/channel/plan/{id}/approve`, `POST /api/ai/channel/plan/{id}/execute`, `DELETE /api/ai/channel/plan/{id}`
- **Sessions**: `POST /api/ai/channel/start-with-persona`
- 10 new Pydantic models for request/response handling

## [2.0.1] - 2026-01-17
### Added
- `exstreamtv/api/media.py` - Comprehensive media filtering system
- Filter parameters: `media_type`, `year`, `year_min`, `year_max`, `duration_min`, `duration_max`, `content_rating`, `genre`, `search`
- Sorting support: `sort_by` and `sort_order`
- `GET /api/media/filters` endpoint for dynamic filter options

## [2.0.0] - 2026-01-14
### Added
- Blocks API (`exstreamtv/api/blocks.py`) - Time-based programming blocks
- Filler Presets API (`exstreamtv/api/filler_presets.py`) - Gap-filling content
- Templates API (`exstreamtv/api/templates.py`) - Reusable schedule patterns
- Deco API (`exstreamtv/api/deco.py`) - Decorative content (bumpers, station IDs)
- Scripted Schedule API (`exstreamtv/api/scripted.py`) - 27 endpoints for schedule control
- Integration API (`exstreamtv/api/integrations.py`) - External service endpoints

## [1.8.0] - 2026-01-14
### Added
- Performance Monitoring API (`exstreamtv/api/performance.py`)
- Comprehensive statistics endpoint
- Cache, database, FFmpeg, and task stats

## [1.3.0] - 2026-01-14
### Added
- Dashboard statistics API (`exstreamtv/api/dashboard.py`)
- System resource monitoring endpoints

## [1.2.0] - 2026-01-14
### Added
- Library CRUD and scan endpoints (`exstreamtv/api/libraries.py`)
- Media item management (`exstreamtv/api/media.py`)

## [1.0.6] - 2026-01-14
### Added
- Initial port of 30+ FastAPI routers from StreamTV
- Channels, playlists, schedules, auth, IPTV endpoints
