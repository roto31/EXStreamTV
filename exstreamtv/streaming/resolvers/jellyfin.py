"""
Jellyfin/Emby URL Resolver.

Resolves Jellyfin and Emby media items to streamable URLs.
Both use similar APIs since Emby is the fork origin of Jellyfin.
"""

import logging
from typing import Any, Optional

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    ResolvedURL,
    ResolverError,
    SourceType,
)

logger = logging.getLogger(__name__)


class JellyfinResolver(BaseResolver):
    """
    Jellyfin/Emby URL resolver.
    
    Uses the Jellyfin/Emby API to resolve item IDs to stream URLs.
    Works for both Jellyfin and Emby servers.
    
    Features:
    - Direct stream URL generation
    - API key authentication
    - Container-specific stream selection
    """
    
    source_type = SourceType.JELLYFIN
    
    def __init__(self, is_emby: bool = False):
        """
        Initialize Jellyfin resolver.
        
        Args:
            is_emby: Set to True for Emby servers (uses slightly different headers)
        """
        super().__init__()
        self.is_emby = is_emby
        self._libraries: dict[str, Any] = {}
    
    def register_library(self, name: str, library: Any) -> None:
        """Register a Jellyfin/Emby library."""
        self._libraries[name] = library
    
    async def can_handle(self, media_item: Any) -> bool:
        """Check if this resolver can handle the media item."""
        source = getattr(media_item, "source", None) or getattr(media_item, "source_type", None)
        if source:
            source_lower = str(source).lower()
            if "jellyfin" in source_lower or "emby" in source_lower:
                return True
        
        url = self._get_url(media_item)
        if url:
            url_lower = url.lower()
            if ":8096" in url_lower or "/Items/" in url_lower:
                return True
        
        return False
    
    def _get_url(self, media_item: Any) -> Optional[str]:
        """Extract URL from media item."""
        if isinstance(media_item, str):
            return media_item
        if hasattr(media_item, "url"):
            return media_item.url
        if hasattr(media_item, "path"):
            return media_item.path
        if isinstance(media_item, dict):
            return media_item.get("url") or media_item.get("path")
        return None
    
    def _extract_jellyfin_info(self, media_item: Any) -> dict[str, Any]:
        """Extract Jellyfin-specific info from media item."""
        info = {}
        
        if hasattr(media_item, "raw_metadata"):
            raw = media_item.raw_metadata
            if isinstance(raw, dict):
                info["item_id"] = raw.get("Id") or raw.get("item_id")
                info["server_url"] = raw.get("server_url")
                info["api_key"] = raw.get("api_key")
                info["user_id"] = raw.get("user_id")
        
        if hasattr(media_item, "source_id"):
            info["source_id"] = media_item.source_id
        
        # Try to extract from URL
        url = self._get_url(media_item)
        if url:
            import re
            # Match /Items/{item_id}
            match = re.search(r"/Items/([a-f0-9-]+)", url, re.IGNORECASE)
            if match:
                info["item_id"] = match.group(1)
            
            # Extract server URL
            match = re.search(r"(https?://[^/]+)", url)
            if match:
                info["server_url"] = match.group(1)
            
            # Extract API key
            match = re.search(r"api_key=([^&]+)", url)
            if match:
                info["api_key"] = match.group(1)
        
        return info
    
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
    ) -> ResolvedURL:
        """
        Resolve Jellyfin/Emby media item to stream URL.
        
        Args:
            media_item: Media item with Jellyfin/Emby source
            force_refresh: Skip cache and force fresh resolution
            
        Returns:
            ResolvedURL with Jellyfin stream URL
            
        Raises:
            ResolverError: If resolution fails
        """
        # Check cache first
        if not force_refresh:
            cached = self.get_cached(media_item)
            if cached and cached.is_valid:
                return cached.resolved_url
        
        jellyfin_info = self._extract_jellyfin_info(media_item)
        
        item_id = jellyfin_info.get("item_id")
        server_url = jellyfin_info.get("server_url")
        api_key = jellyfin_info.get("api_key")
        
        # Try registered library first
        source_id = jellyfin_info.get("source_id")
        if source_id and source_id in self._libraries:
            library = self._libraries[source_id]
            try:
                if hasattr(library, "get_stream_url"):
                    stream_url = await library.get_stream_url(item_id)
                    if stream_url:
                        source_type = SourceType.EMBY if self.is_emby else SourceType.JELLYFIN
                        resolved = ResolvedURL(
                            url=stream_url,
                            source_type=source_type,
                            expires_at=None,
                            media_id=getattr(media_item, "id", None),
                            metadata={
                                "item_id": item_id,
                                "source_id": source_id,
                            },
                        )
                        self.cache_url(media_item, resolved)
                        return resolved
            except Exception as e:
                logger.warning(f"Failed to get stream URL from Jellyfin library: {e}")
        
        # Build URL directly if we have the components
        if server_url and api_key and item_id:
            # Direct stream URL
            stream_url = (
                f"{server_url}/Items/{item_id}/Download"
                f"?api_key={api_key}"
            )
            
            headers = {
                "X-Emby-Token": api_key,
            } if self.is_emby else {
                "Authorization": f'MediaBrowser Token="{api_key}"',
            }
            
            source_type = SourceType.EMBY if self.is_emby else SourceType.JELLYFIN
            resolved = ResolvedURL(
                url=stream_url,
                source_type=source_type,
                expires_at=None,  # API key based, doesn't expire
                media_id=getattr(media_item, "id", None),
                headers=headers,
                metadata={
                    "item_id": item_id,
                    "server_url": server_url,
                },
            )
            
            self.cache_url(media_item, resolved)
            
            server_type = "Emby" if self.is_emby else "Jellyfin"
            logger.info(f"Resolved {server_type} item {item_id}")
            return resolved
        
        # Fallback: use URL directly
        url = self._get_url(media_item)
        if url:
            source_type = SourceType.EMBY if self.is_emby else SourceType.JELLYFIN
            resolved = ResolvedURL(
                url=url,
                source_type=source_type,
                expires_at=None,
                media_id=getattr(media_item, "id", None),
            )
            self.cache_url(media_item, resolved)
            return resolved
        
        raise ResolverError(
            "Missing Jellyfin connection info (server_url, api_key, or item_id)",
            source_type=SourceType.JELLYFIN,
            is_retryable=False,
        )
    
    def get_cache_key(self, media_item: Any) -> str:
        """Generate cache key using item ID."""
        jellyfin_info = self._extract_jellyfin_info(media_item)
        item_id = jellyfin_info.get("item_id")
        source_id = jellyfin_info.get("source_id", "default")
        
        prefix = "emby" if self.is_emby else "jellyfin"
        if item_id:
            return f"{prefix}:{source_id}:{item_id}"
        
        return super().get_cache_key(media_item)


class EmbyResolver(JellyfinResolver):
    """
    Emby-specific resolver.
    
    Inherits from JellyfinResolver with Emby-specific settings.
    """
    
    source_type = SourceType.EMBY
    
    def __init__(self):
        super().__init__(is_emby=True)
