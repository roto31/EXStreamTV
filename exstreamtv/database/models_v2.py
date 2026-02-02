"""
EXStreamTV Database Models v2

This module provides backward compatibility for v2 modules that import
from models_v2. It re-exports all models from the main models package.

Note: This is an alias module. All models are defined in exstreamtv.database.models.
"""

# Re-export everything from the main models package
from exstreamtv.database.models import *

# Additional imports that v2 modules might need
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
    CollectionTypeEnum,
    MediaItem,
    MediaFile,
    MediaVersion,
    MultiCollection,
    MultiCollectionLink,
    # Playout
    Playout,
    PlayoutItem,
    PlayoutAnchor,
    PlayoutBuildSession,
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
    DecoBreakContent,
    DecoGroup,
    DecoTemplate,
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
    # Smart Collections
    SmartCollection,
    SmartCollectionItem,
    RerunCollection,
    RerunHistoryItem,
    # Aliases
    Watermark,
    Schedule,
    Collection,
    CollectionItem,
    FillerItem,
)

# v2 modules may also need APIKeyToken - check if it exists
try:
    from exstreamtv.database.models.api_key import APIKeyToken
except ImportError:
    # Create a placeholder if not defined
    class APIKeyToken:
        """Placeholder for APIKeyToken model."""
        pass
