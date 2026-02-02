# Database Component Changelog

All notable changes to the Database component will be documented in this file.

## [2.6.0] - 2026-01-31
### Added - Tunarr/dizqueTV Integration
- **DatabaseConnectionManager** (`connection.py`) - Dynamic pool sizing from Tunarr
  - Dynamic pool calculation: `(channel_count * 2.5) + 10 base connections`
  - Pool event monitoring (connections created, checked in/out, invalidated, recycled)
  - Health checks with latency measurement
  - Automatic pool resizing based on channel count
  - `ConnectionMetrics` dataclass for pool statistics
- **DatabaseBackupManager** (`backup.py`) - Scheduled backup system from Tunarr
  - `BackupConfig` for backup settings
  - `BackupInfo` dataclass for backup metadata
  - Scheduled automatic backups with configurable interval
  - Backup rotation (keep N most recent)
  - Gzip compression support
  - Pre-restore safety backup
  - Manual backup/restore API
- Updated `__init__.py` with new exports

## [2.5.0] - 2026-01-17
### Added
- **CollectionTypeEnum** (`models/media.py`) - STATIC, SMART, MANUAL collection types
- `collection_type` field on Playlist model
- `search_query` field for smart collection queries
- Migration `002_add_collection_smart_fields.py`

## [2.0.1] - 2026-01-17
### Fixed
- `MultiCollectionLink.collection_id` foreign key corrected from `collections.id` to `playlists.id`

## [2.0.0] - 2026-01-14
### Added
- `MultiCollection` and `MultiCollectionLink` models for combining collections
- `PlayoutBuildSession` for persistent build state

## [1.8.0] - 2026-01-14
### Added
- `optimization.py` - Query optimization utilities
- Performance indexes for frequently queried columns
- SQLite WAL mode for better concurrency
- Batch operations for bulk inserts/updates

## [1.2.0] - 2026-01-14
### Added
- `models/library.py` - Library source models
- `models/media.py` - MediaItem, MediaVersion, MediaFile

## [1.0.2] - 2026-01-14
### Added
- Complete database model suite (ErsatzTV-compatible)
- Channel, ChannelWatermark, ChannelFFmpegProfile
- Playlist, PlaylistGroup, PlaylistItem
- MediaItem, MediaFile, MediaVersion
- Playout, PlayoutItem, PlayoutAnchor, PlayoutHistory, PlayoutTemplate
- ProgramSchedule, ProgramScheduleItem, Block, BlockGroup, BlockItem
- FillerPreset, FillerPresetItem
- Deco, DecoGroup
- Template, TemplateGroup, TemplateItem
- PlexLibrary, JellyfinLibrary, EmbyLibrary, LocalLibrary
- FFmpegProfile, Resolution

## [1.0.1] - 2026-01-14
### Added
- Database connection management (`connection.py`)
- Database models package structure
