"""
EXStreamTV Database Models

SQLAlchemy models for all entities, including:
- Channels and streaming configuration
- Playlists and media items
- Playouts and scheduling
- Filler, deco, and templates (ErsatzTV-compatible)
- Local media libraries
- FFmpeg profiles
- Smart collections and rerun tracking
"""

from exstreamtv.database.models.base import Base
from exstreamtv.database.models.channel import (
    Channel,
    ChannelFFmpegProfile,
    ChannelPlaybackPosition,
    ChannelWatermark,
    PlayoutMode,
    StreamingMode,
    StreamSource,
)
from exstreamtv.database.models.deco import (
    Deco,
    DecoBreakContent,
    DecoGroup,
    DecoTemplate,
)
from exstreamtv.database.models.filler import (
    FillerPreset,
    FillerPresetItem,
)
from exstreamtv.database.models.library import (
    EmbyLibrary,
    JellyfinLibrary,
    LocalLibrary,
    PlexLibrary,
)
from exstreamtv.database.models.media import (
    CollectionTypeEnum,
    MediaFile,
    MediaItem,
    MediaVersion,
    MultiCollection,
    MultiCollectionLink,
)
from exstreamtv.database.models.playlist import (
    Playlist,
    PlaylistGroup,
    PlaylistItem,
)
from exstreamtv.database.models.playout import (
    Playout,
    PlayoutAnchor,
    PlayoutBuildSession,
    PlayoutHistory,
    PlayoutItem,
    PlayoutTemplate,
)
from exstreamtv.database.models.profile import (
    FFmpegProfile,
    Resolution,
)
from exstreamtv.database.models.schedule import (
    Block,
    BlockGroup,
    BlockItem,
    ProgramSchedule,
    ProgramScheduleItem,
)
from exstreamtv.database.models.smart_collection import (
    RerunCollection,
    RerunHistoryItem,
    SmartCollection,
    SmartCollectionItem,
)
from exstreamtv.database.models.template import (
    Template,
    TemplateGroup,
    TemplateItem,
)

# Aliases for backward compatibility
Watermark = ChannelWatermark
Schedule = ProgramSchedule
Collection = Playlist  # Collections are similar to playlists
CollectionItem = PlaylistItem
FillerItem = FillerPresetItem  # Alias for legacy code referencing FillerItem

__all__ = [
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
    "CollectionTypeEnum",
    "MediaItem",
    "MediaFile",
    "MediaVersion",
    "MultiCollection",
    "MultiCollectionLink",
    # Playout
    "Playout",
    "PlayoutItem",
    "PlayoutAnchor",
    "PlayoutBuildSession",
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
    "DecoBreakContent",
    "DecoGroup",
    "DecoTemplate",
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
    # Smart Collections
    "SmartCollection",
    "SmartCollectionItem",
    "RerunCollection",
    "RerunHistoryItem",
    # Aliases
    "Watermark",
    "Schedule",
    "Collection",
    "CollectionItem",
    "FillerItem",
]
