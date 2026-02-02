"""
URL Resolvers for different media sources.

Resolves MediaItem objects to streamable URLs with expiration tracking.
"""

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    CachedURL,
    ResolvedURL,
    ResolverError,
    SourceType,
)
from exstreamtv.streaming.resolvers.youtube import YouTubeResolver
from exstreamtv.streaming.resolvers.plex import PlexResolver
from exstreamtv.streaming.resolvers.jellyfin import JellyfinResolver, EmbyResolver
from exstreamtv.streaming.resolvers.archive_org import ArchiveOrgResolver
from exstreamtv.streaming.resolvers.local import LocalFileResolver

__all__ = [
    # Base
    "BaseResolver",
    "CachedURL",
    "ResolvedURL",
    "ResolverError",
    "SourceType",
    # Resolvers
    "YouTubeResolver",
    "PlexResolver",
    "JellyfinResolver",
    "EmbyResolver",
    "ArchiveOrgResolver",
    "LocalFileResolver",
]
