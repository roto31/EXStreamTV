"""
Resolver Registry — Strict source-type to resolver mapping.

No default. No implicit routing. Configuration error if source_type missing.
"""

import logging
from typing import Any

from exstreamtv.streaming.contract import SourceClassification, StreamSource
from exstreamtv.streaming.resolvers.base import BaseResolver, ResolvedURL, ResolverError, SourceType

logger = logging.getLogger(__name__)


class ResolverRegistryError(Exception):
    """Raised when resolver not found for source type."""

    def __init__(self, source_type: SourceType, message: str | None = None):
        self.source_type = source_type
        super().__init__(message or f"No resolver registered for source type: {source_type.value}")


def _resolved_to_stream_source(resolved: ResolvedURL, seek_offset: float, title: str, duration: float) -> StreamSource:
    """Convert ResolvedURL to StreamSource."""
    classification_map = {
        SourceType.PLEX: SourceClassification.PLEX,
        SourceType.LOCAL: SourceClassification.FILE,
        SourceType.YOUTUBE: SourceClassification.YOUTUBE,
        SourceType.ARCHIVE_ORG: SourceClassification.ARCHIVE,
        SourceType.JELLYFIN: SourceClassification.URL,
        SourceType.EMBY: SourceClassification.URL,
        SourceType.M3U: SourceClassification.URL,
        SourceType.UNKNOWN: SourceClassification.URL,
    }
    classification = classification_map.get(resolved.source_type, SourceClassification.URL)
    return StreamSource(
        url=resolved.url,
        headers=dict(resolved.headers),
        seek_offset=seek_offset,
        probe_required=classification in (SourceClassification.YOUTUBE, SourceClassification.ARCHIVE),
        allow_retry=True,
        classification=classification,
        source_type=resolved.source_type,
        title=title,
        canonical_duration=duration,
    )


class ResolverRegistry:
    """
    Strict resolver registry. No default fallback.

    Usage:
        registry = ResolverRegistry()
        resolver = registry.get(item.source_type)
        source = await resolver.resolve(item.media_item)
    """

    def __init__(self):
        self._map: dict[SourceType, BaseResolver] = {}
        self._initialized = False

    def _lazy_init(self) -> None:
        if self._initialized:
            return
        try:
            from exstreamtv.config import get_config
            from exstreamtv.streaming.resolvers.youtube import YouTubeResolver
            cookies = get_config().sources.youtube.cookies_file or None
            self._map[SourceType.YOUTUBE] = YouTubeResolver(cookies_file=cookies)
        except ImportError as e:
            logger.warning(f"YouTubeResolver not available: {e}")
        try:
            from exstreamtv.streaming.resolvers.plex import PlexResolver
            self._map[SourceType.PLEX] = PlexResolver()
        except ImportError as e:
            logger.warning(f"PlexResolver not available: {e}")
        try:
            from exstreamtv.streaming.resolvers.jellyfin import JellyfinResolver
            self._map[SourceType.JELLYFIN] = JellyfinResolver()
            self._map[SourceType.EMBY] = JellyfinResolver()
        except ImportError as e:
            logger.warning(f"JellyfinResolver not available: {e}")
        try:
            from exstreamtv.streaming.resolvers.archive_org import ArchiveOrgResolver
            self._map[SourceType.ARCHIVE_ORG] = ArchiveOrgResolver()
        except ImportError as e:
            logger.warning(f"ArchiveOrgResolver not available: {e}")
        try:
            from exstreamtv.streaming.resolvers.local import LocalFileResolver
            self._map[SourceType.LOCAL] = LocalFileResolver()
        except ImportError as e:
            logger.warning(f"LocalFileResolver not available: {e}")
        try:
            from exstreamtv.streaming.resolvers.direct_url import DirectURLResolver
            self._map[SourceType.UNKNOWN] = DirectURLResolver()
        except ImportError as e:
            logger.warning(f"DirectURLResolver not available: {e}")
        self._initialized = True
        logger.info(f"ResolverRegistry initialized with {len(self._map)} resolvers")

    def get(self, source_type: SourceType) -> BaseResolver:
        """
        Get resolver for source type. Raises ResolverRegistryError if not found.
        """
        self._lazy_init()
        resolver = self._map.get(source_type)
        if resolver is None:
            raise ResolverRegistryError(source_type)
        return resolver

    def register(self, source_type: SourceType, resolver: BaseResolver) -> None:
        """Register a resolver for a source type."""
        self._map[source_type] = resolver
        logger.info(f"Registered resolver for {source_type.value}")

    def has(self, source_type: SourceType) -> bool:
        """Check if resolver exists for source type."""
        self._lazy_init()
        return source_type in self._map


_registry: ResolverRegistry | None = None


def get_resolver_registry() -> ResolverRegistry:
    """Get the global ResolverRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ResolverRegistry()
    return _registry
