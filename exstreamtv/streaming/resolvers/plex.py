"""
Plex URL Resolver.

Resolves Plex media items to streamable URLs using the Plex API.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    ResolvedURL,
    ResolverError,
    SourceType,
)

logger = logging.getLogger(__name__)

# Plex URL expiration time - set conservatively to refresh before actual expiration
PLEX_URL_EXPIRY_HOURS = 2  # Refresh every 2 hours to be safe (Plex typically expires at 4 hours)

# Module-level cache for Plex library info to avoid repeated DB queries
_plex_library_cache: dict[int, dict] = {}
_plex_first_library_cache: Optional[dict] = None
_plex_cache_loaded: bool = False


def _load_plex_library_cache() -> None:
    """Load Plex library info into memory cache."""
    global _plex_library_cache, _plex_first_library_cache, _plex_cache_loaded
    
    if _plex_cache_loaded:
        return
    
    try:
        from exstreamtv.database.session import get_sync_session
        from exstreamtv.database.models import PlexLibrary
        
        with get_sync_session() as session:
            libraries = session.query(PlexLibrary).all()
            for lib in libraries:
                _plex_library_cache[lib.id] = {
                    "id": lib.id,
                    "name": lib.name,
                    "server_url": lib.server_url,
                    "token": lib.token,
                }
                if _plex_first_library_cache is None:
                    _plex_first_library_cache = _plex_library_cache[lib.id]
            
            _plex_cache_loaded = True
            logger.info(f"Loaded {len(_plex_library_cache)} Plex libraries into cache")
    except Exception as e:
        logger.warning(f"Failed to load Plex library cache: {e}")
        _plex_cache_loaded = True  # Don't retry on every call


class PlexResolver(BaseResolver):
    """
    Plex URL resolver.
    
    Uses the Plex API to resolve rating keys to stream URLs.
    Note: Plex transcode URLs expire after ~4 hours, so we refresh proactively.
    
    Features:
    - Direct play URL generation
    - Transcode URL generation (optional)
    - Token-based authentication
    - Library-aware resolution
    - Automatic URL refresh before expiration
    """
    
    source_type = SourceType.PLEX
    
    def __init__(self):
        """Initialize Plex resolver."""
        super().__init__()
        self._sources: dict[str, Any] = {}
    
    def register_source(self, name: str, source: Any) -> None:
        """Register a Plex media source."""
        self._sources[name] = source
    
    async def can_handle(self, media_item: Any) -> bool:
        """Check if this resolver can handle the media item."""
        # Check source attribute
        source = getattr(media_item, "source", None) or getattr(media_item, "source_type", None)
        if source and "plex" in str(source).lower():
            return True
        
        # Check URL patterns
        url = self._get_url(media_item)
        if url:
            url_lower = url.lower()
            if ":32400" in url_lower or "/library/metadata/" in url_lower:
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
    
    def _extract_plex_info(self, media_item: Any) -> dict[str, Any]:
        """Extract Plex-specific info from media item, with fallback to global config."""
        info = {}
        
        if hasattr(media_item, "raw_metadata"):
            raw = media_item.raw_metadata
            if isinstance(raw, dict):
                info["rating_key"] = raw.get("ratingKey")
                info["server_url"] = raw.get("server_url")
                info["token"] = raw.get("token")
        
        if hasattr(media_item, "source_id"):
            info["source_id"] = media_item.source_id
        
        # Try plex_rating_key attribute
        if hasattr(media_item, "plex_rating_key") and media_item.plex_rating_key:
            info["rating_key"] = str(media_item.plex_rating_key)
        
        # Try source_id or external_id (may contain /library/metadata/{rating_key})
        if not info.get("rating_key"):
            import re
            for attr in ["source_id", "external_id"]:
                val = getattr(media_item, attr, None)
                if val:
                    match = re.search(r"/library/metadata/(\d+)", str(val))
                    if match:
                        info["rating_key"] = match.group(1)
                        break
        
        # Try to extract from URL
        url = self._get_url(media_item)
        if url:
            import re
            # Match /library/metadata/{rating_key}
            match = re.search(r"/library/metadata/(\d+)", url)
            if match:
                info["rating_key"] = match.group(1)
            
            # Extract server URL
            match = re.search(r"(https?://[^/]+)", url)
            if match:
                info["server_url"] = match.group(1)
            
            # Extract token
            match = re.search(r"X-Plex-Token=([^&]+)", url)
            if match:
                info["token"] = match.group(1)
        
        # FALLBACK 1: Try library_id to look up Plex library connection info from cache
        if not info.get("server_url") or not info.get("token"):
            # Ensure cache is loaded
            _load_plex_library_cache()
            
            library_id = getattr(media_item, "library_id", None)
            if library_id and library_id in _plex_library_cache:
                lib_info = _plex_library_cache[library_id]
                if not info.get("server_url"):
                    info["server_url"] = lib_info["server_url"]
                if not info.get("token"):
                    info["token"] = lib_info["token"]
                logger.debug(f"Using Plex credentials from cached library {library_id}: {lib_info['name']}")
        
        # FALLBACK 2: Try first available Plex library from cache
        if not info.get("server_url") or not info.get("token"):
            if _plex_first_library_cache:
                lib_info = _plex_first_library_cache
                if not info.get("server_url"):
                    info["server_url"] = lib_info["server_url"]
                if not info.get("token"):
                    info["token"] = lib_info["token"]
                logger.debug(f"Using Plex credentials from first cached library: {lib_info['name']}")
        
        # FALLBACK 3: If still missing, try global config
        if not info.get("server_url") or not info.get("token"):
            try:
                from exstreamtv.config import get_config
                config = get_config()
                
                # Try plex section first
                plex_config = getattr(config, 'plex', None)
                if plex_config:
                    if not info.get("server_url"):
                        info["server_url"] = getattr(plex_config, 'url', '') or getattr(plex_config, 'base_url', '')
                    if not info.get("token"):
                        info["token"] = getattr(plex_config, 'token', '')
                
                # Also try libraries.plex
                libraries_plex = getattr(getattr(config, 'libraries', None), 'plex', None)
                if libraries_plex:
                    if not info.get("server_url"):
                        info["server_url"] = getattr(libraries_plex, 'url', '')
                    if not info.get("token"):
                        info["token"] = getattr(libraries_plex, 'token', '')
                
                if info.get("server_url") or info.get("token"):
                    logger.debug(f"Using Plex credentials from global config")
            except Exception as e:
                logger.warning(f"Failed to load Plex config: {e}")
        
        return info
    
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
    ) -> ResolvedURL:
        """
        Resolve Plex media item to stream URL.
        
        Args:
            media_item: Media item with Plex source
            force_refresh: Skip cache and force fresh resolution
            
        Returns:
            ResolvedURL with Plex stream URL
            
        Raises:
            ResolverError: If resolution fails
        """
        # Check cache first
        if not force_refresh:
            cached = self.get_cached(media_item)
            if cached and cached.is_valid:
                return cached.resolved_url
        
        plex_info = self._extract_plex_info(media_item)
        
        rating_key = plex_info.get("rating_key")
        server_url = plex_info.get("server_url")
        token = plex_info.get("token")
        
        # Try to get from registered source
        source_id = plex_info.get("source_id")
        if source_id and source_id in self._sources:
            source = self._sources[source_id]
            try:
                stream_url = await source.get_stream_url(rating_key)
                if stream_url:
                    resolved = ResolvedURL(
                        url=stream_url,
                        source_type=SourceType.PLEX,
                        expires_at=datetime.utcnow() + timedelta(hours=PLEX_URL_EXPIRY_HOURS),
                        media_id=getattr(media_item, "id", None),
                        metadata={
                            "rating_key": rating_key,
                            "source_id": source_id,
                        },
                    )
                    self.cache_url(media_item, resolved)
                    return resolved
            except Exception as e:
                logger.warning(f"Failed to get stream URL from Plex source: {e}")
        
        # Build URL directly if we have the components
        if server_url and token and rating_key:
            # Need to query Plex API to get the actual file path (part key)
            try:
                import aiohttp
                
                metadata_url = f"{server_url}/library/metadata/{rating_key}?X-Plex-Token={token}"
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        metadata_url,
                        headers={"Accept": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            # Extract the part key from the response
                            # Structure: MediaContainer -> Metadata[0] -> Media[0] -> Part[0] -> key
                            metadata_list = data.get("MediaContainer", {}).get("Metadata", [])
                            if metadata_list:
                                media_list = metadata_list[0].get("Media", [])
                                if media_list:
                                    part_list = media_list[0].get("Part", [])
                                    if part_list:
                                        part_key = part_list[0].get("key")
                                        if part_key:
                                            stream_url = f"{server_url}{part_key}?X-Plex-Token={token}"
                                            
                                            resolved = ResolvedURL(
                                                url=stream_url,
                                                source_type=SourceType.PLEX,
                                                expires_at=datetime.utcnow() + timedelta(hours=PLEX_URL_EXPIRY_HOURS),
                                                media_id=getattr(media_item, "id", None),
                                                headers={"X-Plex-Token": token},
                                                metadata={
                                                    "rating_key": rating_key,
                                                    "server_url": server_url,
                                                    "part_key": part_key,
                                                },
                                            )
                                            
                                            self.cache_url(media_item, resolved)
                                            logger.info(f"Resolved Plex item {rating_key}")
                                            return resolved
                            
                            logger.warning(f"No part key found in Plex metadata for {rating_key}")
                        else:
                            logger.warning(f"Plex metadata request failed: {resp.status}")
                            
            except Exception as e:
                logger.warning(f"Failed to query Plex metadata for {rating_key}: {e}")
            
            # Fallback: try the old URL format (might work for some setups)
            stream_url = f"{server_url}/library/metadata/{rating_key}/file?X-Plex-Token={token}"
            logger.warning(f"Using fallback Plex URL format for {rating_key}")
            
            resolved = ResolvedURL(
                url=stream_url,
                source_type=SourceType.PLEX,
                expires_at=datetime.utcnow() + timedelta(hours=PLEX_URL_EXPIRY_HOURS),
                media_id=getattr(media_item, "id", None),
                headers={"X-Plex-Token": token},
                metadata={
                    "rating_key": rating_key,
                    "server_url": server_url,
                },
            )
            
            self.cache_url(media_item, resolved)
            return resolved
        
        # Fallback: try to use URL directly
        url = self._get_url(media_item)
        if url:
            resolved = ResolvedURL(
                url=url,
                source_type=SourceType.PLEX,
                expires_at=datetime.utcnow() + timedelta(hours=PLEX_URL_EXPIRY_HOURS),
                media_id=getattr(media_item, "id", None),
            )
            self.cache_url(media_item, resolved)
            return resolved
        
        raise ResolverError(
            "Missing Plex connection info (server_url, token, or rating_key)",
            source_type=SourceType.PLEX,
            is_retryable=False,
        )
    
    def get_cache_key(self, media_item: Any) -> str:
        """Generate cache key using rating key."""
        plex_info = self._extract_plex_info(media_item)
        rating_key = plex_info.get("rating_key")
        source_id = plex_info.get("source_id", "default")
        
        if rating_key:
            return f"plex:{source_id}:{rating_key}"
        
        return super().get_cache_key(media_item)
