"""
EXStreamTV Database Module

Provides SQLAlchemy models, migrations, and database utilities.
"""

from exstreamtv.database.connection import (
    close_db,
    get_db,
    get_pool_stats,
    get_session,
    get_sync_session,
    get_sync_session_factory,
    init_db,
    init_sync_db,
    # New Tunarr-style connection management
    DatabaseConnectionManager,
    ConnectionMetrics,
    get_connection_manager,
    init_connection_manager,
)

# Backup management (Tunarr-style)
from exstreamtv.database.backup import (
    DatabaseBackupManager,
    BackupConfig,
    BackupInfo,
    get_backup_manager,
    init_backup_manager,
)

from exstreamtv.database.models import (
    # Base
    Base,
    # Channel
    Channel,
    ChannelFFmpegProfile,
    ChannelPlaybackPosition,
    ChannelWatermark,
    PlayoutMode,
    StreamingMode,
    StreamSource,
    # Playlist
    Playlist,
    PlaylistGroup,
    PlaylistItem,
    # Media
    MediaItem,
    MediaFile,
    MediaVersion,
    # Playout
    Playout,
    PlayoutItem,
    PlayoutAnchor,
    PlayoutHistory,
    PlayoutTemplate,
    # Schedule
    ProgramSchedule,
    ProgramScheduleItem,
    Block,
    BlockGroup,
    BlockItem,
    # Filler
    FillerPreset,
    FillerPresetItem,
    # Deco
    Deco,
    DecoGroup,
    # Template
    Template,
    TemplateGroup,
    TemplateItem,
    # Library
    PlexLibrary,
    JellyfinLibrary,
    EmbyLibrary,
    LocalLibrary,
    # Profile
    FFmpegProfile,
    Resolution,
)

# Aliases for backward compatibility
Watermark = ChannelWatermark
Schedule = ProgramSchedule
ScheduleItem = ProgramScheduleItem  # Alias for schedule_items.py
Collection = Playlist  # Collections are similar to playlists
CollectionItem = PlaylistItem

__all__ = [
    # Connection
    "close_db",
    "get_db",
    "get_pool_stats",
    "get_session",
    "get_sync_session",
    "get_sync_session_factory",
    "init_db",
    "init_sync_db",
    # Connection management (Tunarr)
    "DatabaseConnectionManager",
    "ConnectionMetrics",
    "get_connection_manager",
    "init_connection_manager",
    # Backup management (Tunarr)
    "DatabaseBackupManager",
    "BackupConfig",
    "BackupInfo",
    "get_backup_manager",
    "init_backup_manager",
    # Base
    "Base",
    # Channel
    "Channel",
    "ChannelFFmpegProfile",
    "ChannelPlaybackPosition",
    "ChannelWatermark",
    "PlayoutMode",
    "StreamingMode",
    "StreamSource",
    # Playlist
    "Playlist",
    "PlaylistGroup",
    "PlaylistItem",
    # Media
    "MediaItem",
    "MediaFile",
    "MediaVersion",
    # Playout
    "Playout",
    "PlayoutItem",
    "PlayoutAnchor",
    "PlayoutHistory",
    "PlayoutTemplate",
    # Schedule
    "ProgramSchedule",
    "ProgramScheduleItem",
    "Block",
    "BlockGroup",
    "BlockItem",
    # Filler
    "FillerPreset",
    "FillerPresetItem",
    # Deco
    "Deco",
    "DecoGroup",
    # Template
    "Template",
    "TemplateGroup",
    "TemplateItem",
    # Library
    "PlexLibrary",
    "JellyfinLibrary",
    "EmbyLibrary",
    "LocalLibrary",
    # Profile
    "FFmpegProfile",
    "Resolution",
    # Aliases for backward compatibility
    "Watermark",
    "Schedule",
    "ScheduleItem",
    "Collection",
    "CollectionItem",
]
