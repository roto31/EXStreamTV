"""
Metadata providers for media enrichment.

Supports:
- TMDB (The Movie Database)
- TVDB (TheTVDB)
- NFO file parsing (Kodi/Plex format)
"""

from exstreamtv.media.providers.base import MetadataProvider, MediaMetadata
from exstreamtv.media.providers.tmdb import TMDBProvider
from exstreamtv.media.providers.tvdb import TVDBProvider
from exstreamtv.media.providers.nfo import NFOParser

__all__ = [
    "MetadataProvider",
    "MediaMetadata",
    "TMDBProvider",
    "TVDBProvider",
    "NFOParser",
]
