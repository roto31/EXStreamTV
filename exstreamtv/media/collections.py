"""
Media collection organizer.

Organizes media items into hierarchical collections:
- Shows → Seasons → Episodes
- Movie Collections
- Smart collections based on metadata
"""

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Set

from exstreamtv.media.libraries.base import LibraryItem, MediaType

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    """Episode within a season."""

    item: LibraryItem
    episode_number: int
    title: str

    @property
    def id(self) -> str:
        return self.item.id

    @property
    def duration(self) -> timedelta:
        return self.item.duration


@dataclass
class Season:
    """Season within a show."""

    season_number: int
    episodes: List[Episode] = field(default_factory=list)

    @property
    def episode_count(self) -> int:
        return len(self.episodes)

    @property
    def total_duration(self) -> timedelta:
        return sum((ep.duration for ep in self.episodes), timedelta(0))

    def get_episode(self, episode_number: int) -> Optional[Episode]:
        """Get episode by number."""
        for ep in self.episodes:
            if ep.episode_number == episode_number:
                return ep
        return None

    def get_sorted_episodes(self) -> List[Episode]:
        """Get episodes sorted by episode number."""
        return sorted(self.episodes, key=lambda e: e.episode_number)


@dataclass
class Show:
    """TV show with seasons and episodes."""

    title: str
    seasons: Dict[int, Season] = field(default_factory=dict)

    # Optional metadata
    year: Optional[int] = None
    poster_path: Optional[str] = None
    fanart_path: Optional[str] = None
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None
    imdb_id: Optional[str] = None
    genres: List[str] = field(default_factory=list)

    @property
    def season_count(self) -> int:
        return len(self.seasons)

    @property
    def episode_count(self) -> int:
        return sum(s.episode_count for s in self.seasons.values())

    @property
    def total_duration(self) -> timedelta:
        return sum((s.total_duration for s in self.seasons.values()), timedelta(0))

    def get_season(self, season_number: int) -> Optional[Season]:
        """Get season by number."""
        return self.seasons.get(season_number)

    def get_sorted_seasons(self) -> List[Season]:
        """Get seasons sorted by number."""
        return [self.seasons[num] for num in sorted(self.seasons.keys())]

    def get_all_episodes(self) -> List[Episode]:
        """Get all episodes sorted by season and episode number."""
        episodes = []
        for season in self.get_sorted_seasons():
            episodes.extend(season.get_sorted_episodes())
        return episodes

    def get_episode(self, season_number: int, episode_number: int) -> Optional[Episode]:
        """Get specific episode."""
        season = self.get_season(season_number)
        if season:
            return season.get_episode(episode_number)
        return None


@dataclass
class MovieCollection:
    """Collection of related movies."""

    name: str
    movies: List[LibraryItem] = field(default_factory=list)

    # Optional metadata
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    tmdb_id: Optional[str] = None

    @property
    def movie_count(self) -> int:
        return len(self.movies)

    @property
    def total_duration(self) -> timedelta:
        return sum((m.duration for m in self.movies), timedelta(0))

    def get_sorted_movies(self) -> List[LibraryItem]:
        """Get movies sorted by year then title."""
        return sorted(self.movies, key=lambda m: (m.year or 0, m.title))


@dataclass
class SmartCollection:
    """Dynamic collection based on filter criteria."""

    name: str
    filter_func: Callable[[LibraryItem], bool]
    items: List[LibraryItem] = field(default_factory=list)
    description: str = ""

    @property
    def item_count(self) -> int:
        return len(self.items)

    def refresh(self, all_items: List[LibraryItem]) -> None:
        """Refresh collection based on filter."""
        self.items = [item for item in all_items if self.filter_func(item)]


class CollectionOrganizer:
    """
    Organizes media items into collections.

    Features:
    - Automatic show/season/episode grouping
    - Movie collection detection
    - Smart collection support
    - Multi-library aggregation
    """

    def __init__(self):
        self._shows: Dict[str, Show] = {}
        self._movie_collections: Dict[str, MovieCollection] = {}
        self._smart_collections: Dict[str, SmartCollection] = {}
        self._movies: List[LibraryItem] = []
        self._all_items: List[LibraryItem] = []

    @property
    def shows(self) -> Dict[str, Show]:
        """Get all shows."""
        return self._shows

    @property
    def movies(self) -> List[LibraryItem]:
        """Get all standalone movies."""
        return self._movies

    @property
    def movie_collections(self) -> Dict[str, MovieCollection]:
        """Get movie collections."""
        return self._movie_collections

    @property
    def smart_collections(self) -> Dict[str, SmartCollection]:
        """Get smart collections."""
        return self._smart_collections

    def add_items(self, items: List[LibraryItem]) -> None:
        """
        Add items to the organizer.

        Items are automatically organized into shows, movies, etc.
        """
        for item in items:
            self._all_items.append(item)

            if item.media_type == MediaType.EPISODE:
                self._add_episode(item)
            elif item.media_type == MediaType.MOVIE:
                self._add_movie(item)
            elif item.media_type == MediaType.SHOW:
                self._add_show_metadata(item)

        # Refresh smart collections
        self._refresh_smart_collections()

    def clear(self) -> None:
        """Clear all collections."""
        self._shows.clear()
        self._movie_collections.clear()
        self._movies.clear()
        self._all_items.clear()

    def _add_episode(self, item: LibraryItem) -> None:
        """Add an episode item."""
        show_title = item.show_title or "Unknown Show"

        # Get or create show
        if show_title not in self._shows:
            self._shows[show_title] = Show(
                title=show_title,
                year=item.year,
                genres=item.genres,
            )

        show = self._shows[show_title]

        # Get or create season
        season_number = item.season_number or 0
        if season_number not in show.seasons:
            show.seasons[season_number] = Season(season_number=season_number)

        season = show.seasons[season_number]

        # Add episode
        episode = Episode(
            item=item,
            episode_number=item.episode_number or 0,
            title=item.title,
        )
        season.episodes.append(episode)

    def _add_movie(self, item: LibraryItem) -> None:
        """Add a movie item."""
        self._movies.append(item)

    def _add_show_metadata(self, item: LibraryItem) -> None:
        """Add show-level metadata."""
        show_title = item.title

        if show_title not in self._shows:
            self._shows[show_title] = Show(title=show_title)

        show = self._shows[show_title]

        # Update metadata if not set
        if item.year and not show.year:
            show.year = item.year
        if item.poster_path and not show.poster_path:
            show.poster_path = item.poster_path
        if item.fanart_path and not show.fanart_path:
            show.fanart_path = item.fanart_path
        if item.tmdb_id and not show.tmdb_id:
            show.tmdb_id = item.tmdb_id
        if item.tvdb_id and not show.tvdb_id:
            show.tvdb_id = item.tvdb_id
        if item.imdb_id and not show.imdb_id:
            show.imdb_id = item.imdb_id
        if item.genres and not show.genres:
            show.genres = item.genres

    def add_smart_collection(
        self,
        name: str,
        filter_func: Callable[[LibraryItem], bool],
        description: str = "",
    ) -> SmartCollection:
        """
        Add a smart collection.

        Args:
            name: Collection name.
            filter_func: Function to filter items.
            description: Collection description.

        Returns:
            The created SmartCollection.
        """
        collection = SmartCollection(
            name=name,
            filter_func=filter_func,
            description=description,
        )
        collection.refresh(self._all_items)
        self._smart_collections[name] = collection
        return collection

    def _refresh_smart_collections(self) -> None:
        """Refresh all smart collections."""
        for collection in self._smart_collections.values():
            collection.refresh(self._all_items)

    def get_show(self, title: str) -> Optional[Show]:
        """Get a show by title."""
        return self._shows.get(title)

    def get_show_titles(self) -> List[str]:
        """Get all show titles sorted."""
        return sorted(self._shows.keys())

    def get_movies_by_genre(self, genre: str) -> List[LibraryItem]:
        """Get movies by genre."""
        genre_lower = genre.lower()
        return [
            m for m in self._movies
            if any(g.lower() == genre_lower for g in m.genres)
        ]

    def get_movies_by_year(self, year: int) -> List[LibraryItem]:
        """Get movies by year."""
        return [m for m in self._movies if m.year == year]

    def get_recent_movies(self, limit: int = 20) -> List[LibraryItem]:
        """Get recently added movies."""
        sorted_movies = sorted(
            self._movies,
            key=lambda m: m.added_at or m.updated_at or m.year or 0,
            reverse=True,
        )
        return sorted_movies[:limit]

    def get_recent_episodes(self, limit: int = 20) -> List[Episode]:
        """Get recently added episodes."""
        all_episodes = []
        for show in self._shows.values():
            all_episodes.extend(show.get_all_episodes())

        sorted_episodes = sorted(
            all_episodes,
            key=lambda e: e.item.added_at or e.item.updated_at or 0,
            reverse=True,
        )
        return sorted_episodes[:limit]

    def get_all_genres(self) -> Set[str]:
        """Get all unique genres."""
        genres = set()
        for item in self._all_items:
            genres.update(item.genres)
        return genres

    def get_statistics(self) -> Dict[str, Any]:
        """Get collection statistics."""
        total_duration = timedelta(0)
        for item in self._all_items:
            total_duration += item.duration

        return {
            "total_items": len(self._all_items),
            "shows": len(self._shows),
            "total_episodes": sum(s.episode_count for s in self._shows.values()),
            "movies": len(self._movies),
            "movie_collections": len(self._movie_collections),
            "smart_collections": len(self._smart_collections),
            "total_duration_hours": total_duration.total_seconds() / 3600,
            "genres": len(self.get_all_genres()),
        }

    def search(
        self,
        query: str,
        media_type: Optional[MediaType] = None,
        limit: int = 50,
    ) -> List[LibraryItem]:
        """
        Search items by title.

        Args:
            query: Search query.
            media_type: Optional media type filter.
            limit: Maximum results.

        Returns:
            Matching items.
        """
        query_lower = query.lower()
        results = []

        for item in self._all_items:
            # Filter by type if specified
            if media_type and item.media_type != media_type:
                continue

            # Match title
            if query_lower in item.title.lower():
                results.append(item)
                continue

            # Match show title for episodes
            if item.show_title and query_lower in item.show_title.lower():
                results.append(item)

        return results[:limit]


# Preset smart collection filters
def filter_hd(item: LibraryItem) -> bool:
    """Filter for HD content (720p+)."""
    # Would need resolution info from media files
    return True  # Placeholder


def filter_unwatched(item: LibraryItem) -> bool:
    """Filter for unwatched content."""
    # Would need watch history integration
    return True  # Placeholder


def filter_short_movies(item: LibraryItem) -> bool:
    """Filter for movies under 90 minutes."""
    if item.media_type != MediaType.MOVIE:
        return False
    return item.duration.total_seconds() < 5400  # 90 minutes


def filter_long_movies(item: LibraryItem) -> bool:
    """Filter for movies over 2 hours."""
    if item.media_type != MediaType.MOVIE:
        return False
    return item.duration.total_seconds() > 7200  # 2 hours


def create_genre_filter(genre: str) -> Callable[[LibraryItem], bool]:
    """Create a genre filter function."""
    genre_lower = genre.lower()
    return lambda item: any(g.lower() == genre_lower for g in item.genres)


def create_year_filter(start_year: int, end_year: int) -> Callable[[LibraryItem], bool]:
    """Create a year range filter function."""
    return lambda item: item.year is not None and start_year <= item.year <= end_year


def create_decade_filter(decade: int) -> Callable[[LibraryItem], bool]:
    """Create a decade filter (e.g., 1990 for 90s)."""
    return create_year_filter(decade, decade + 9)
