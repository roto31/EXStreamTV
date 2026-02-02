"""
Base library classes.

Ported from ErsatzTV library concepts.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LibraryType(Enum):
    """Type of media library."""

    LOCAL = "local"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"


class MediaType(Enum):
    """Type of media content."""

    MOVIE = "movie"
    SHOW = "show"
    SEASON = "season"
    EPISODE = "episode"
    MUSIC = "music"
    MUSIC_VIDEO = "music_video"
    OTHER = "other"


@dataclass
class LibraryItem:
    """A media item in a library."""

    id: str
    library_id: int
    media_type: MediaType
    title: str
    path: Optional[str] = None
    sort_title: Optional[str] = None
    duration: timedelta = timedelta(0)

    # Metadata
    year: Optional[int] = None
    studio: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    actors: List[str] = field(default_factory=list)

    # Show/Episode specifics
    show_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None

    # Artwork
    poster_path: Optional[str] = None
    fanart_path: Optional[str] = None
    thumb_path: Optional[str] = None

    # External IDs
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None
    imdb_id: Optional[str] = None

    # Timestamps
    added_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def display_title(self) -> str:
        """Get formatted display title."""
        if self.media_type == MediaType.EPISODE:
            return f"{self.show_title} S{self.season_number:02d}E{self.episode_number:02d} - {self.title}"
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


@dataclass
class LibraryStats:
    """Statistics for a library."""

    total_items: int = 0
    movies: int = 0
    shows: int = 0
    episodes: int = 0
    total_duration: timedelta = timedelta(0)
    total_size: int = 0
    last_scanned: Optional[datetime] = None


class BaseLibrary(ABC):
    """
    Abstract base class for media libraries.

    Ported from ErsatzTV library interfaces.
    """

    def __init__(
        self,
        library_id: int,
        name: str,
        library_type: LibraryType,
    ):
        self.library_id = library_id
        self.name = name
        self.library_type = library_type
        self._items: Dict[str, LibraryItem] = {}
        self._last_sync: Optional[datetime] = None

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to the library source.

        Returns:
            True if connection successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the library source."""
        pass

    @abstractmethod
    async def sync(self) -> List[LibraryItem]:
        """
        Synchronize with the library source.

        Returns:
            List of all library items.
        """
        pass

    @abstractmethod
    async def get_item(self, item_id: str) -> Optional[LibraryItem]:
        """
        Get a specific item by ID.

        Args:
            item_id: Item identifier.

        Returns:
            LibraryItem or None.
        """
        pass

    @abstractmethod
    async def get_stream_url(self, item_id: str) -> Optional[str]:
        """
        Get streaming URL for an item.

        Args:
            item_id: Item identifier.

        Returns:
            Stream URL or None.
        """
        pass

    async def get_items(
        self,
        media_type: Optional[MediaType] = None,
        limit: Optional[int] = None,
    ) -> List[LibraryItem]:
        """
        Get items from the library.

        Args:
            media_type: Filter by media type.
            limit: Maximum items to return.

        Returns:
            List of LibraryItem.
        """
        items = list(self._items.values())

        if media_type:
            items = [i for i in items if i.media_type == media_type]

        if limit:
            items = items[:limit]

        return items

    def get_stats(self) -> LibraryStats:
        """Get library statistics."""
        items = list(self._items.values())

        return LibraryStats(
            total_items=len(items),
            movies=sum(1 for i in items if i.media_type == MediaType.MOVIE),
            shows=sum(1 for i in items if i.media_type == MediaType.SHOW),
            episodes=sum(1 for i in items if i.media_type == MediaType.EPISODE),
            total_duration=sum((i.duration for i in items), timedelta(0)),
            last_scanned=self._last_sync,
        )


class LibraryManager:
    """
    Manages multiple media libraries.

    Ported from ErsatzTV library management.
    """

    def __init__(self):
        self._libraries: Dict[int, BaseLibrary] = {}

    def add_library(self, library: BaseLibrary) -> None:
        """Add a library to the manager."""
        self._libraries[library.library_id] = library
        logger.info(f"Added library: {library.name} ({library.library_type.value})")

    def remove_library(self, library_id: int) -> None:
        """Remove a library from the manager."""
        if library_id in self._libraries:
            del self._libraries[library_id]
            logger.info(f"Removed library: {library_id}")

    def get_library(self, library_id: int) -> Optional[BaseLibrary]:
        """Get a library by ID."""
        return self._libraries.get(library_id)

    def get_all_libraries(self) -> List[BaseLibrary]:
        """Get all libraries."""
        return list(self._libraries.values())

    async def sync_all(self) -> Dict[int, List[LibraryItem]]:
        """
        Synchronize all libraries.

        Returns:
            Dict mapping library ID to items.
        """
        results = {}

        for library_id, library in self._libraries.items():
            try:
                logger.info(f"Syncing library: {library.name}")
                await library.connect()
                items = await library.sync()
                results[library_id] = items
                logger.info(f"Synced {len(items)} items from {library.name}")
            except Exception as e:
                logger.error(f"Error syncing {library.name}: {e}")
                results[library_id] = []
            finally:
                await library.disconnect()

        return results

    async def get_all_items(
        self,
        media_type: Optional[MediaType] = None,
    ) -> List[LibraryItem]:
        """Get items from all libraries."""
        all_items = []

        for library in self._libraries.values():
            items = await library.get_items(media_type)
            all_items.extend(items)

        return all_items
