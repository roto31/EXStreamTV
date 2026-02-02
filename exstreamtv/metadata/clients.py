"""
Metadata Clients Compatibility Module

This module provides backward compatibility for modules that import
from metadata.clients. It provides metadata provider client interfaces.
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
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for metadata."""
        raise NotImplementedError
    
    async def get_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed metadata for an item."""
        raise NotImplementedError


class TMDBClient(MetadataClient):
    """TMDB metadata client."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search TMDB."""
        logger.debug(f"TMDB search: {query}")
        return []
    
    async def get_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get TMDB details."""
        logger.debug(f"TMDB get details: {item_id}")
        return None


class TVDBClient(MetadataClient):
    """TVDB metadata client."""
    
    BASE_URL = "https://api4.thetvdb.com/v4"
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search TVDB."""
        logger.debug(f"TVDB search: {query}")
        return []
    
    async def get_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get TVDB details."""
        logger.debug(f"TVDB get details: {item_id}")
        return None


class OMDBClient(MetadataClient):
    """OMDB metadata client."""
    
    BASE_URL = "https://www.omdbapi.com"
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """Search OMDB."""
        logger.debug(f"OMDB search: {query}")
        return []
    
    async def get_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get OMDB details."""
        logger.debug(f"OMDB get details: {item_id}")
        return None


__all__ = [
    "MetadataClient",
    "TMDBClient",
    "TVDBClient",
    "OMDBClient",
]
