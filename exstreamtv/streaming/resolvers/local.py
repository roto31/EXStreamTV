"""
Local File URL Resolver.

Resolves local file paths to verified, streamable paths.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

from exstreamtv.streaming.resolvers.base import (
    BaseResolver,
    ResolvedURL,
    ResolverError,
    SourceType,
)

logger = logging.getLogger(__name__)


class LocalFileResolver(BaseResolver):
    """
    Local file URL resolver.
    
    Validates that local file paths exist and are readable,
    then returns the path for FFmpeg to use directly.
    
    Features:
    - Path existence validation
    - File accessibility check
    - Symlink resolution
    - file:// URL support
    """
    
    source_type = SourceType.LOCAL
    
    def __init__(self, allowed_paths: Optional[list[str]] = None):
        """
        Initialize local file resolver.
        
        Args:
            allowed_paths: Optional list of allowed base paths for security.
                          If None, all paths are allowed.
        """
        super().__init__()
        self.allowed_paths = allowed_paths
    
    async def can_handle(self, media_item: Any) -> bool:
        """Check if this resolver can handle the media item."""
        source = getattr(media_item, "source", None) or getattr(media_item, "source_type", None)
        if source:
            source_lower = str(source).lower()
            if "local" in source_lower or "file" in source_lower:
                return True
        
        path = self._get_path(media_item)
        if path:
            # Check if it looks like a local path
            if path.startswith("/") or path.startswith("file://"):
                return True
            # Windows paths
            if len(path) > 2 and path[1] == ":":
                return True
        
        return False
    
    def _get_path(self, media_item: Any) -> Optional[str]:
        """Extract file path from media item."""
        if isinstance(media_item, str):
            return media_item
        if hasattr(media_item, "path") and media_item.path:
            return media_item.path
        if hasattr(media_item, "url") and media_item.url:
            return media_item.url
        if isinstance(media_item, dict):
            return media_item.get("path") or media_item.get("url")
        return None
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path, handling file:// URLs.
        
        Examples:
        - file:///path/to/file.mp4 -> /path/to/file.mp4
        - /path/to/file.mp4 -> /path/to/file.mp4
        """
        if path.startswith("file://"):
            path = path[7:]  # Remove file://
        
        # Resolve any symlinks and normalize
        return os.path.normpath(path)
    
    def _is_path_allowed(self, path: str) -> bool:
        """Check if path is within allowed directories."""
        if self.allowed_paths is None:
            return True
        
        resolved_path = Path(path).resolve()
        
        for allowed in self.allowed_paths:
            allowed_path = Path(allowed).resolve()
            try:
                resolved_path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        
        return False
    
    async def resolve(
        self,
        media_item: Any,
        force_refresh: bool = False,
    ) -> ResolvedURL:
        """
        Resolve local file path to verified stream path.
        
        Args:
            media_item: Media item with local file path
            force_refresh: Ignored for local files (always validates)
            
        Returns:
            ResolvedURL with verified file path
            
        Raises:
            ResolverError: If file doesn't exist or isn't accessible
        """
        path = self._get_path(media_item)
        if not path:
            raise ResolverError(
                "No path found in media item",
                source_type=SourceType.LOCAL,
                is_retryable=False,
            )
        
        normalized_path = self._normalize_path(path)
        
        # Security check
        if not self._is_path_allowed(normalized_path):
            raise ResolverError(
                f"Path not in allowed directories: {normalized_path}",
                source_type=SourceType.LOCAL,
                is_retryable=False,
            )
        
        # Check file exists
        if not os.path.exists(normalized_path):
            raise ResolverError(
                f"File not found: {normalized_path}",
                source_type=SourceType.LOCAL,
                is_retryable=False,
            )
        
        # Check it's a file (not directory)
        if not os.path.isfile(normalized_path):
            raise ResolverError(
                f"Path is not a file: {normalized_path}",
                source_type=SourceType.LOCAL,
                is_retryable=False,
            )
        
        # Check readable
        if not os.access(normalized_path, os.R_OK):
            raise ResolverError(
                f"File not readable: {normalized_path}",
                source_type=SourceType.LOCAL,
                is_retryable=False,
            )
        
        # Get file info
        stat_info = os.stat(normalized_path)
        file_size = stat_info.st_size
        
        resolved = ResolvedURL(
            url=normalized_path,
            source_type=SourceType.LOCAL,
            expires_at=None,  # Local files don't expire
            media_id=getattr(media_item, "id", None),
            metadata={
                "file_size": file_size,
                "file_name": os.path.basename(normalized_path),
                "extension": os.path.splitext(normalized_path)[1].lower(),
            },
        )
        
        logger.debug(f"Resolved local file: {normalized_path} ({file_size} bytes)")
        return resolved
    
    def get_cache_key(self, media_item: Any) -> str:
        """Generate cache key using normalized path."""
        path = self._get_path(media_item)
        if path:
            normalized = self._normalize_path(path)
            return f"local:{normalized}"
        
        return super().get_cache_key(media_item)
