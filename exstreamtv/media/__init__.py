"""
EXStreamTV Media Library Module

Local and remote media library management with scanning and metadata.

Features:
- Local file system scanning
- Plex, Jellyfin, Emby integration
- TMDB/TVDB metadata providers
- NFO file parsing
- FFprobe-based media analysis
- Collection organization
"""

from exstreamtv.media.scanner import MediaScanner, ScanResult, ScanProgress
from exstreamtv.media.providers import (
    MetadataProvider,
    MediaMetadata,
    TMDBProvider,
    TVDBProvider,
    NFOParser,
)
from exstreamtv.media.libraries import (
    LibraryManager,
    LibraryType,
    LocalLibrary,
    PlexLibrary,
    JellyfinLibrary,
    EmbyLibrary,
)
from exstreamtv.media.collections import (
    CollectionOrganizer,
    Show,
    Season,
    Episode,
    MovieCollection,
    SmartCollection,
)

__all__ = [
    # Scanner
    "MediaScanner",
    "ScanResult",
    "ScanProgress",
    # Providers
    "MetadataProvider",
    "MediaMetadata",
    "TMDBProvider",
    "TVDBProvider",
    "NFOParser",
    # Libraries
    "LibraryManager",
    "LibraryType",
    "LocalLibrary",
    "PlexLibrary",
    "JellyfinLibrary",
    "EmbyLibrary",
    # Collections
    "CollectionOrganizer",
    "Show",
    "Season",
    "Episode",
    "MovieCollection",
    "SmartCollection",
]
