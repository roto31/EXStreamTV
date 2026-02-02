"""
Base Media Source Interface

Abstract base class for all media source integrations.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MediaSourceStatus(Enum):
    """Status of a media source connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SCANNING = "scanning"
    ERROR = "error"


@dataclass
class MediaLibrary:
    """Represents a library from a media source."""
    id: str
    name: str
    type: str  # "movie", "show", "music", "other"
    item_count: int = 0
    is_enabled: bool = True
    last_scan: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MediaSourceItem:
    """Represents a media item from a source."""
    id: str
    title: str
    type: str  # "movie", "episode", "track", etc.
    duration_ms: int = 0
    year: int | None = None
    
    # For episodes
    show_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    
    # Media info
    file_path: str | None = None
    stream_url: str | None = None
    thumbnail_url: str | None = None
    art_url: str | None = None
    
    # Metadata
    summary: str | None = None
    genres: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    directors: list[str] = field(default_factory=list)
    studio: str | None = None
    content_rating: str | None = None
    rating: float | None = None
    
    # Source-specific
    source_type: str = ""  # "plex", "jellyfin", "emby", "local"
    source_id: str = ""
    library_id: str = ""
    
    # Raw metadata for additional processing
    raw_metadata: dict[str, Any] = field(default_factory=dict)


class MediaSource(ABC):
    """Abstract base class for media source integrations."""
    
    source_type: str = "unknown"
    
    def __init__(self, name: str, server_url: str):
        self.name = name
        self.server_url = server_url.rstrip("/")
        self.status = MediaSourceStatus.DISCONNECTED
        self._libraries: list[MediaLibrary] = []
        self._error_message: str | None = None
    
    @property
    def is_connected(self) -> bool:
        """Check if source is connected."""
        return self.status == MediaSourceStatus.CONNECTED
    
    @property
    def error_message(self) -> str | None:
        """Get the last error message."""
        return self._error_message
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the media source.
        
        Returns:
            bool: True if connection successful
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the media source."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test the connection to the media source.
        
        Returns:
            tuple[bool, str]: (success, message)
        """
        pass
    
    @abstractmethod
    async def get_libraries(self) -> list[MediaLibrary]:
        """Get available libraries from the source.
        
        Returns:
            list[MediaLibrary]: Available libraries
        """
        pass
    
    @abstractmethod
    async def scan_library(self, library_id: str) -> list[MediaSourceItem]:
        """Scan a library and return its items.
        
        Args:
            library_id: ID of the library to scan
            
        Returns:
            list[MediaSourceItem]: Items in the library
        """
        pass
    
    @abstractmethod
    async def get_item(self, item_id: str) -> MediaSourceItem | None:
        """Get a specific item by ID.
        
        Args:
            item_id: ID of the item
            
        Returns:
            MediaSourceItem | None: The item or None if not found
        """
        pass
    
    @abstractmethod
    async def get_stream_url(self, item_id: str) -> str | None:
        """Get the streaming URL for an item.
        
        Args:
            item_id: ID of the item
            
        Returns:
            str | None: Stream URL or None
        """
        pass
    
    def to_dict(self) -> dict[str, Any]:
        """Convert source to dictionary representation."""
        return {
            "name": self.name,
            "server_url": self.server_url,
            "source_type": self.source_type,
            "status": self.status.value,
            "is_connected": self.is_connected,
            "error_message": self._error_message,
            "library_count": len(self._libraries),
        }
