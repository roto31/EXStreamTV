"""
Base URL Resolver and common types.

Provides the abstract base class for all URL resolvers and shared data models.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SourceType(str, Enum):
    """Media source types for URL resolution."""
    
    YOUTUBE = "youtube"
    ARCHIVE_ORG = "archive_org"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"
    LOCAL = "local"
    M3U = "m3u"
    UNKNOWN = "unknown"


class ResolverError(Exception):
    """Error during URL resolution."""
    
    def __init__(
        self,
        message: str,
        source_type: SourceType = SourceType.UNKNOWN,
        is_retryable: bool = True,
        original_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.source_type = source_type
        self.is_retryable = is_retryable
        self.original_error = original_error


@dataclass
class ResolvedURL:
    """
    A resolved, streamable URL with metadata.
    
    Attributes:
        url: The streamable URL
        source_type: Type of media source
        expires_at: When this URL expires (None = never)
        media_id: Original media item ID
        codec_info: Pre-probed codec information
        headers: Required HTTP headers for streaming
        cookies: Required cookies for streaming
        is_transcoded: Whether this is a transcoded stream
        metadata: Additional source-specific metadata
    """
    
    url: str
    source_type: SourceType
    expires_at: Optional[datetime] = None
    media_id: Optional[int] = None
    codec_info: Optional[dict[str, Any]] = None
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    is_transcoded: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if this URL has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at
    
    @property
    def expires_in(self) -> Optional[timedelta]:
        """Get time until expiration."""
        if self.expires_at is None:
            return None
        return self.expires_at - datetime.utcnow()
    
    def is_expiring_soon(self, threshold_minutes: int = 60) -> bool:
        """Check if URL will expire within threshold."""
        if self.expires_at is None:
            return False
        threshold = datetime.utcnow() + timedelta(minutes=threshold_minutes)
        return self.expires_at <= threshold


@dataclass
class CachedURL:
    """
    Cached URL entry with resolution metadata.
    
    Used for caching resolved URLs to avoid repeated lookups.
    """
    
    cache_key: str
    resolved_url: ResolvedURL
    resolved_at: datetime = field(default_factory=datetime.utcnow)
    refresh_count: int = 0
    last_error: Optional[str] = None
    
    @property
    def is_valid(self) -> bool:
        """Check if cached URL is still valid."""
        return not self.resolved_url.is_expired
    
    def needs_refresh(self, threshold_minutes: int = 30) -> bool:
        """Check if URL needs proactive refresh."""
        return self.resolved_url.is_expiring_soon(threshold_minutes)


class BaseResolver(ABC):
    """
    Abstract base class for URL resolvers.
    
    Each resolver handles a specific media source type and knows how to
    convert MediaItem references to streamable URLs.
    """
    
    source_type: SourceType = SourceType.UNKNOWN
    
    def __init__(self):
        self._cache: dict[str, CachedURL] = {}
    
    @abstractmethod
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
    ) -> ResolvedURL:
        """
        Resolve a media item to a streamable URL.
        
        Args:
            media_item: The media item to resolve (source-specific)
            force_refresh: Skip cache and force fresh resolution
            
        Returns:
            ResolvedURL with streamable URL and metadata
            
        Raises:
            ResolverError: If resolution fails
        """
        pass
    
    @abstractmethod
    async def can_handle(self, media_item: Any) -> bool:
        """
        Check if this resolver can handle the given media item.
        
        Args:
            media_item: The media item to check
            
        Returns:
            True if this resolver can handle the item
        """
        pass
    
    def get_cache_key(self, media_item: Any) -> str:
        """
        Generate a cache key for a media item.
        
        Override for source-specific key generation.
        """
        if hasattr(media_item, "id"):
            return f"{self.source_type.value}:{media_item.id}"
        return f"{self.source_type.value}:{hash(str(media_item))}"
    
    def get_cached(self, media_item: Any) -> Optional[CachedURL]:
        """Get cached URL if valid."""
        cache_key = self.get_cache_key(media_item)
        cached = self._cache.get(cache_key)
        
        if cached and cached.is_valid:
            return cached
        
        # Remove expired entries
        if cached:
            del self._cache[cache_key]
        
        return None
    
    def cache_url(self, media_item: Any, resolved_url: ResolvedURL) -> CachedURL:
        """Cache a resolved URL."""
        cache_key = self.get_cache_key(media_item)
        
        existing = self._cache.get(cache_key)
        refresh_count = existing.refresh_count + 1 if existing else 0
        
        cached = CachedURL(
            cache_key=cache_key,
            resolved_url=resolved_url,
            refresh_count=refresh_count,
        )
        
        self._cache[cache_key] = cached
        return cached
    
    def clear_cache(self) -> int:
        """Clear all cached URLs. Returns count of cleared entries."""
        count = len(self._cache)
        self._cache.clear()
        return count
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        valid_count = sum(1 for c in self._cache.values() if c.is_valid)
        expiring_soon = sum(1 for c in self._cache.values() if c.needs_refresh())
        
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "expiring_soon": expiring_soon,
            "expired_entries": len(self._cache) - valid_count,
        }
