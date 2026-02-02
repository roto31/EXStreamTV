"""
Base Metadata Client

Provides base class for metadata provider clients.
"""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MetadataClient:
    """
    Base class for metadata provider clients.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._cache: Dict[str, Any] = {}
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for metadata."""
        raise NotImplementedError
    
    async def get_details(self, item_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get detailed metadata for an item."""
        raise NotImplementedError
    
    async def get_images(self, item_id: str, **kwargs) -> List[str]:
        """Get images for an item."""
        return []
    
    def clear_cache(self) -> None:
        """Clear the client cache."""
        self._cache.clear()


__all__ = ["MetadataClient"]
