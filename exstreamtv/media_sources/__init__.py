"""
EXStreamTV Media Sources

Integration modules for Plex, Jellyfin, Emby, and local media libraries.
Based on ErsatzTV's library management patterns.
"""

from exstreamtv.media_sources.plex_client import PlexMediaSource
from exstreamtv.media_sources.jellyfin_client import JellyfinMediaSource
from exstreamtv.media_sources.emby_client import EmbyMediaSource
from exstreamtv.media_sources.base import MediaSource, MediaSourceStatus

__all__ = [
    "MediaSource",
    "MediaSourceStatus",
    "PlexMediaSource",
    "JellyfinMediaSource",
    "EmbyMediaSource",
]
