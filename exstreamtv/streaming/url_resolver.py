"""
Central Media URL Resolver.

Routes media items to the appropriate source-specific resolver and manages
URL caching with expiration tracking.
"""

import logging
from typing import Any, Optional

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    CachedURL,
    ResolvedURL,
    ResolverError,
    SourceType,
)
from exstreamtv.streaming.source_type_detector import build_source_type_detection_chain

logger = logging.getLogger(__name__)


class MediaURLResolver:
    """
    Central URL resolution hub.
    
    Routes media items to source-specific resolvers based on the item's
    source type. Manages a unified cache for all resolved URLs.
    
    Usage:
        resolver = MediaURLResolver()
        resolved = await resolver.resolve(media_item)
        print(f"Stream URL: {resolved.url}")
        if resolved.expires_at:
            print(f"Expires in: {resolved.expires_in}")
    """
    
    def __init__(self):
        self._resolvers: dict[SourceType, BaseResolver] = {}
        # Issue 5.2: Bounded cache prevents unbounded growth from millions
        # of unique URLs. TTL=7200s (2h) matches typical URL expiry windows.
        from cachetools import TTLCache
        self._global_cache: TTLCache = TTLCache(maxsize=5000, ttl=7200)
        self._initialized = False
        self._detection_chain = build_source_type_detection_chain()
    
    def _lazy_init(self) -> None:
        """Lazily initialize resolvers on first use."""
        if self._initialized:
            return
        
        try:
            from exstreamtv.streaming.resolvers.youtube import YouTubeResolver
            self._resolvers[SourceType.YOUTUBE] = YouTubeResolver()
        except ImportError as e:
            logger.warning(f"YouTubeResolver not available: {e}")
        
        try:
            from exstreamtv.streaming.resolvers.plex import PlexResolver
            self._resolvers[SourceType.PLEX] = PlexResolver()
        except ImportError as e:
            logger.warning(f"PlexResolver not available: {e}")
        
        try:
            from exstreamtv.streaming.resolvers.jellyfin import JellyfinResolver
            self._resolvers[SourceType.JELLYFIN] = JellyfinResolver()
            self._resolvers[SourceType.EMBY] = JellyfinResolver()  # Same API
        except ImportError as e:
            logger.warning(f"JellyfinResolver not available: {e}")
        
        try:
            from exstreamtv.streaming.resolvers.archive_org import ArchiveOrgResolver
            self._resolvers[SourceType.ARCHIVE_ORG] = ArchiveOrgResolver()
        except ImportError as e:
            logger.warning(f"ArchiveOrgResolver not available: {e}")
        
        try:
            from exstreamtv.streaming.resolvers.local import LocalFileResolver
            self._resolvers[SourceType.LOCAL] = LocalFileResolver()
        except ImportError as e:
            logger.warning(f"LocalFileResolver not available: {e}")
        
        self._initialized = True
        logger.info(f"MediaURLResolver initialized with {len(self._resolvers)} resolvers")
    
    def register_resolver(self, source_type: SourceType, resolver: BaseResolver) -> None:
        """
        Register a custom resolver for a source type.
        
        Args:
            source_type: The source type to handle
            resolver: The resolver instance
        """
        self._resolvers[source_type] = resolver
        logger.info(f"Registered resolver for {source_type.value}")
    
    def _detect_source_type(self, media_item: Any) -> SourceType:
        """
        Detect the source type from a media item.

        Delegates to a Chain of Responsibility (see source_type_detector.py)
        that checks in priority order:
            1. Explicit Plex rating key
            2. Explicit source/source_type attribute keyword match
            3. Archive.org-specific metadata fields
            4. raw_metadata JSON content
            5. URL pattern matching

        Args:
            media_item: Media item (dict, model, or object)

        Returns:
            Detected SourceType
        """
        return self._detection_chain.detect(media_item)
    
    def _get_resolver(self, source_type: SourceType) -> Optional[BaseResolver]:
        """Get resolver for a source type."""
        self._lazy_init()
        return self._resolvers.get(source_type)
    
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
        preferred_source: Optional[SourceType] = None,
    ) -> ResolvedURL:
        """
        Resolve a media item to a streamable URL.
        
        Args:
            media_item: The media item to resolve
            force_refresh: Skip cache and force fresh resolution
            preferred_source: Override auto-detection with specific source
            
        Returns:
            ResolvedURL with streamable URL and metadata
            
        Raises:
            ResolverError: If resolution fails
        """
        source_type = preferred_source or self._detect_source_type(media_item)
        
        resolver = self._get_resolver(source_type)
        if resolver is None:
            # Fallback: try to use the URL directly
            url = self._extract_url(media_item)
            if url:
                logger.warning(
                    f"No resolver for {source_type.value}, using URL directly: {url[:50]}..."
                )
                return ResolvedURL(
                    url=url,
                    source_type=source_type,
                    media_id=getattr(media_item, "id", None),
                )
            
            raise ResolverError(
                f"No resolver available for source type: {source_type.value}",
                source_type=source_type,
                is_retryable=False,
            )
        
        try:
            resolved = await resolver.resolve(media_item, force_refresh=force_refresh)
            
            # Cache in global cache
            cache_key = f"{source_type.value}:{getattr(media_item, 'id', hash(str(media_item)))}"
            self._global_cache[cache_key] = CachedURL(
                cache_key=cache_key,
                resolved_url=resolved,
            )
            
            logger.debug(
                f"Resolved {source_type.value} URL: {resolved.url[:50]}... "
                f"(expires: {resolved.expires_at})"
            )
            
            return resolved
            
        except ResolverError:
            raise
        except Exception as e:
            logger.error(f"Resolution failed for {source_type.value}: {e}")
            raise ResolverError(
                f"Failed to resolve URL: {e}",
                source_type=source_type,
                is_retryable=True,
                original_error=e,
            )
    
    def _extract_url(self, media_item: Any) -> Optional[str]:
        """Extract URL from media item."""
        if hasattr(media_item, "url") and media_item.url:
            return media_item.url
        if hasattr(media_item, "path") and media_item.path:
            return media_item.path
        if isinstance(media_item, dict):
            return media_item.get("url") or media_item.get("path")
        if isinstance(media_item, str):
            return media_item
        return None
    
    async def refresh_if_expired(
        self,
        media_item: Any,
        threshold_minutes: int = 60,
    ) -> Optional[ResolvedURL]:
        """
        Refresh URL if it's expired or about to expire.
        
        Args:
            media_item: The media item
            threshold_minutes: Refresh if expiring within this many minutes
            
        Returns:
            New ResolvedURL if refreshed, None if not needed
        """
        source_type = self._detect_source_type(media_item)
        cache_key = f"{source_type.value}:{getattr(media_item, 'id', hash(str(media_item)))}"
        
        cached = self._global_cache.get(cache_key)
        if cached is None:
            # Not cached, resolve fresh
            return await self.resolve(media_item)
        
        if cached.resolved_url.is_expired:
            logger.info(f"URL expired, refreshing: {cache_key}")
            return await self.resolve(media_item, force_refresh=True)
        
        if cached.needs_refresh(threshold_minutes):
            logger.info(f"URL expiring soon, proactively refreshing: {cache_key}")
            return await self.resolve(media_item, force_refresh=True)
        
        return None
    
    def get_expiring_urls(self, threshold_minutes: int = 60) -> list[CachedURL]:
        """
        Get all URLs that will expire within the threshold.
        
        Args:
            threshold_minutes: Expiration threshold in minutes
            
        Returns:
            List of CachedURL entries that need refresh
        """
        return [
            cached for cached in self._global_cache.values()
            if cached.needs_refresh(threshold_minutes)
        ]
    
    def get_cached(self, media_item: Any) -> Optional[ResolvedURL]:
        """Get cached URL if still valid."""
        source_type = self._detect_source_type(media_item)
        cache_key = f"{source_type.value}:{getattr(media_item, 'id', hash(str(media_item)))}"
        
        cached = self._global_cache.get(cache_key)
        if cached and cached.is_valid:
            return cached.resolved_url
        
        return None
    
    def clear_cache(self) -> dict[str, int]:
        """Clear all caches. Returns stats."""
        global_cleared = len(self._global_cache)
        self._global_cache.clear()
        
        resolver_cleared = {}
        for source_type, resolver in self._resolvers.items():
            count = resolver.clear_cache()
            resolver_cleared[source_type.value] = count
        
        return {
            "global_cache": global_cleared,
            **resolver_cleared,
        }
    
    def get_stats(self) -> dict[str, Any]:
        """Get resolver statistics."""
        stats = {
            "global_cache_size": len(self._global_cache),
            "registered_resolvers": list(self._resolvers.keys()),
            "resolver_stats": {},
        }
        
        for source_type, resolver in self._resolvers.items():
            stats["resolver_stats"][source_type.value] = resolver.get_cache_stats()
        
        # Count by source type
        source_counts: dict[str, int] = {}
        for cached in self._global_cache.values():
            source = cached.resolved_url.source_type.value
            source_counts[source] = source_counts.get(source, 0) + 1
        stats["cache_by_source"] = source_counts
        
        return stats


# Global resolver instance
_resolver_instance: Optional[MediaURLResolver] = None


def get_url_resolver() -> MediaURLResolver:
    """Get the global MediaURLResolver instance."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = MediaURLResolver()
    return _resolver_instance
