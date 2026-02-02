"""
Archive.org URL Resolver.

Resolves Archive.org item URLs to direct file stream URLs.
"""

import logging
import re
from typing import Any, Optional
from urllib.parse import quote, unquote

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    ResolvedURL,
    ResolverError,
    SourceType,
)

logger = logging.getLogger(__name__)


class ArchiveOrgResolver(BaseResolver):
    """
    Archive.org URL resolver.
    
    Parses Archive.org URLs to extract identifiers and construct
    direct download/stream URLs.
    
    Archive.org URLs are permanent and don't expire.
    
    Features:
    - Identifier extraction from various URL formats
    - Direct file URL construction
    - Metadata file support
    - Rate limit awareness (HTTP 464)
    """
    
    source_type = SourceType.ARCHIVE_ORG
    
    BASE_URL = "https://archive.org"
    DOWNLOAD_URL = "https://archive.org/download"
    
    # Patterns for extracting Archive.org identifiers
    IDENTIFIER_PATTERNS = [
        r"archive\.org/details/([^/?\s]+)",
        r"archive\.org/download/([^/?\s]+)",
        r"archive\.org/embed/([^/?\s]+)",
    ]
    
    def __init__(self):
        """Initialize Archive.org resolver."""
        super().__init__()
    
    async def can_handle(self, media_item: Any) -> bool:
        """Check if this resolver can handle the media item."""
        source = getattr(media_item, "source", None) or getattr(media_item, "source_type", None)
        if source:
            source_lower = str(source).lower()
            if "archive" in source_lower:
                return True
        
        url = self._get_url(media_item)
        if url and "archive.org" in url.lower():
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
    
    def _extract_identifier(self, url: str) -> Optional[str]:
        """
        Extract Archive.org identifier from URL.
        
        Examples:
        - https://archive.org/details/identifier -> identifier
        - https://archive.org/download/identifier/file.mp4 -> identifier
        """
        for pattern in self.IDENTIFIER_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def _extract_filename(self, url: str) -> Optional[str]:
        """
        Extract filename from Archive.org download URL.
        
        Example:
        - https://archive.org/download/identifier/file.mp4 -> file.mp4
        """
        match = re.search(r"archive\.org/download/[^/]+/(.+?)(?:\?|$)", url)
        if match:
            return match.group(1)
        return None
    
    def _is_direct_url(self, url: str) -> bool:
        """Check if URL is already a direct download URL."""
        return "/download/" in url and re.search(r"\.\w{2,4}(?:\?|$)", url)
    
    def _encode_archive_url(self, url: str) -> str:
        """
        Properly URL-encode an Archive.org URL.
        
        Archive.org URLs often have spaces and special characters in filenames.
        FFmpeg requires these to be percent-encoded.
        
        Args:
            url: Raw Archive.org URL (may have spaces)
            
        Returns:
            Properly encoded URL
        """
        if "/download/" not in url:
            return url
        
        # Split into base and filename parts
        # Example: https://archive.org/download/identifier/filename with spaces.mp4
        parts = url.split("/download/", 1)
        if len(parts) != 2:
            return url
        
        base = parts[0] + "/download/"
        remainder = parts[1]  # "identifier/filename with spaces.mp4"
        
        # Split into identifier and filename
        slash_idx = remainder.find("/")
        if slash_idx == -1:
            return url  # No filename, just identifier
        
        identifier = remainder[:slash_idx]
        filename = remainder[slash_idx + 1:]
        
        # Check if already encoded (contains %20 or other encodings)
        if "%" in filename:
            # Already encoded, decode first to avoid double-encoding
            filename = unquote(filename)
        
        # Encode the filename (safe='/' preserves any subdirectory slashes)
        encoded_filename = quote(filename, safe='')
        
        return f"{base}{identifier}/{encoded_filename}"
    
    def _get_identifier_from_item(self, media_item: Any) -> Optional[str]:
        """
        Extract Archive.org identifier from media item fields.
        
        Checks: archive_org_identifier, raw_metadata, meta_data
        """
        # Check archive_org_identifier field
        if hasattr(media_item, "archive_org_identifier"):
            identifier = media_item.archive_org_identifier
            if identifier:
                return identifier
        if isinstance(media_item, dict):
            identifier = media_item.get("archive_org_identifier")
            if identifier:
                return identifier
        
        # Check raw_metadata JSON
        raw_metadata = None
        if hasattr(media_item, "raw_metadata"):
            raw_metadata = media_item.raw_metadata
        elif hasattr(media_item, "meta_data"):
            raw_metadata = media_item.meta_data
        elif isinstance(media_item, dict):
            raw_metadata = media_item.get("raw_metadata") or media_item.get("meta_data")
        
        if raw_metadata:
            try:
                import json
                if isinstance(raw_metadata, str):
                    meta_dict = json.loads(raw_metadata)
                else:
                    meta_dict = raw_metadata
                return meta_dict.get("identifier")
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        return None
    
    def _get_filename_from_item(self, media_item: Any) -> Optional[str]:
        """
        Extract Archive.org filename from media item fields.
        
        Checks: archive_org_filename, raw_metadata, meta_data
        """
        # Check archive_org_filename field
        if hasattr(media_item, "archive_org_filename"):
            filename = media_item.archive_org_filename
            if filename:
                return filename
        if isinstance(media_item, dict):
            filename = media_item.get("archive_org_filename")
            if filename:
                return filename
        
        # Check raw_metadata JSON
        raw_metadata = None
        if hasattr(media_item, "raw_metadata"):
            raw_metadata = media_item.raw_metadata
        elif hasattr(media_item, "meta_data"):
            raw_metadata = media_item.meta_data
        elif isinstance(media_item, dict):
            raw_metadata = media_item.get("raw_metadata") or media_item.get("meta_data")
        
        if raw_metadata:
            try:
                import json
                if isinstance(raw_metadata, str):
                    meta_dict = json.loads(raw_metadata)
                else:
                    meta_dict = raw_metadata
                
                # Check for filename or video_files
                if meta_dict.get("filename"):
                    return meta_dict.get("filename")
                video_files = meta_dict.get("video_files", [])
                if video_files and isinstance(video_files, list):
                    return video_files[0].get("name")
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        return None
    
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
    ) -> ResolvedURL:
        """
        Resolve Archive.org media item to stream URL.
        
        Args:
            media_item: Media item with Archive.org source
            force_refresh: Skip cache and force fresh resolution
            
        Returns:
            ResolvedURL with Archive.org stream URL
            
        Raises:
            ResolverError: If resolution fails
        """
        # Check cache first
        if not force_refresh:
            cached = self.get_cached(media_item)
            if cached and cached.is_valid:
                return cached.resolved_url
        
        url = self._get_url(media_item)
        if not url:
            raise ResolverError(
                "No URL found in media item",
                source_type=SourceType.ARCHIVE_ORG,
                is_retryable=False,
            )
        
        # If already a direct download URL, use it (but ensure it's properly encoded)
        if self._is_direct_url(url):
            encoded_url = self._encode_archive_url(url)
            resolved = ResolvedURL(
                url=encoded_url,
                source_type=SourceType.ARCHIVE_ORG,
                expires_at=None,  # Archive.org URLs don't expire
                media_id=getattr(media_item, "id", None),
                headers={
                    "Referer": "https://archive.org/",
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                metadata={
                    "identifier": self._extract_identifier(url),
                    "filename": self._extract_filename(url),
                },
            )
            self.cache_url(media_item, resolved)
            return resolved
        
        identifier = self._extract_identifier(url)
        
        # Also check media_item fields for identifier if not in URL
        if not identifier:
            identifier = self._get_identifier_from_item(media_item)
        
        if not identifier:
            raise ResolverError(
                f"Could not extract Archive.org identifier from URL: {url}",
                source_type=SourceType.ARCHIVE_ORG,
                is_retryable=False,
            )
        
        # Extract filename from URL first, then from media_item fields
        filename = self._extract_filename(url)
        if not filename:
            filename = self._get_filename_from_item(media_item)
        
        if filename:
            # Construct direct download URL with URL-encoded filename
            encoded_filename = quote(filename, safe='')
            stream_url = f"{self.DOWNLOAD_URL}/{identifier}/{encoded_filename}"
            logger.debug(f"Constructed Archive.org URL: {stream_url}")
        else:
            # CRITICAL: Cannot use details page URL - FFmpeg can't stream HTML!
            # Fall back to metadata API to find video file
            logger.warning(
                f"No filename found for Archive.org item {identifier}. "
                f"Attempting to construct default URL pattern."
            )
            # Try common patterns: identifier.mp4, identifier_edit.mp4
            stream_url = f"{self.DOWNLOAD_URL}/{identifier}/{identifier}.mp4"
        
        resolved = ResolvedURL(
            url=stream_url,
            source_type=SourceType.ARCHIVE_ORG,
            expires_at=None,  # Archive.org URLs are permanent
            media_id=getattr(media_item, "id", None),
            headers={
                "Referer": "https://archive.org/",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
            metadata={
                "identifier": identifier,
                "filename": filename,
            },
        )
        
        self.cache_url(media_item, resolved)
        
        logger.info(f"Resolved Archive.org item: {identifier}")
        return resolved
    
    def get_cache_key(self, media_item: Any) -> str:
        """Generate cache key using identifier and filename."""
        url = self._get_url(media_item)
        if url:
            identifier = self._extract_identifier(url)
            filename = self._extract_filename(url)
            if identifier:
                if filename:
                    return f"archive_org:{identifier}:{filename}"
                return f"archive_org:{identifier}"
        
        return super().get_cache_key(media_item)
