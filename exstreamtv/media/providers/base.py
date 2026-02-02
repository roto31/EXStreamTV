"""
Base metadata provider classes.

Abstract interfaces for metadata providers.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PersonInfo:
    """Information about a person (actor, director, etc.)."""

    name: str
    role: str = ""  # Character name for actors
    job: str = ""  # Job title for crew
    image_url: Optional[str] = None
    tmdb_id: Optional[str] = None


@dataclass
class MediaMetadata:
    """
    Unified metadata structure for media items.

    Supports movies, TV shows, and episodes.
    """

    # Identifiers
    title: str
    original_title: Optional[str] = None
    tmdb_id: Optional[str] = None
    tvdb_id: Optional[str] = None
    imdb_id: Optional[str] = None

    # Type and categorization
    media_type: str = "movie"  # "movie", "show", "episode"
    genres: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Show-specific (for episodes)
    show_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None

    # Descriptions
    overview: Optional[str] = None
    tagline: Optional[str] = None

    # Dates
    release_date: Optional[date] = None
    year: Optional[int] = None

    # Ratings
    rating: Optional[float] = None  # 0-10 scale
    vote_count: Optional[int] = None
    content_rating: Optional[str] = None  # "TV-MA", "PG-13", etc.

    # Runtime
    runtime_minutes: Optional[int] = None

    # Artwork
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    thumb_url: Optional[str] = None
    logo_url: Optional[str] = None

    # People
    cast: List[PersonInfo] = field(default_factory=list)
    crew: List[PersonInfo] = field(default_factory=list)

    # Production
    studios: List[str] = field(default_factory=list)
    networks: List[str] = field(default_factory=list)  # For TV
    countries: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)

    # Extra data
    popularity: Optional[float] = None
    budget: Optional[int] = None
    revenue: Optional[int] = None
    status: Optional[str] = None  # "Released", "Ended", etc.
    homepage: Optional[str] = None

    @property
    def display_title(self) -> str:
        """Get formatted display title."""
        if self.media_type == "episode" and self.show_title:
            prefix = f"{self.show_title} "
            if self.season_number is not None and self.episode_number is not None:
                prefix += f"S{self.season_number:02d}E{self.episode_number:02d} - "
            return prefix + self.title
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title

    @property
    def director(self) -> Optional[str]:
        """Get director name."""
        for person in self.crew:
            if person.job.lower() == "director":
                return person.name
        return None

    @property
    def lead_actors(self) -> List[str]:
        """Get top 5 actor names."""
        return [p.name for p in self.cast[:5]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "original_title": self.original_title,
            "tmdb_id": self.tmdb_id,
            "tvdb_id": self.tvdb_id,
            "imdb_id": self.imdb_id,
            "media_type": self.media_type,
            "genres": self.genres,
            "tags": self.tags,
            "show_title": self.show_title,
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "overview": self.overview,
            "tagline": self.tagline,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "year": self.year,
            "rating": self.rating,
            "vote_count": self.vote_count,
            "content_rating": self.content_rating,
            "runtime_minutes": self.runtime_minutes,
            "poster_url": self.poster_url,
            "backdrop_url": self.backdrop_url,
            "thumb_url": self.thumb_url,
            "studios": self.studios,
            "networks": self.networks,
            "cast": [{"name": p.name, "role": p.role} for p in self.cast],
            "director": self.director,
        }


class MetadataProvider(ABC):
    """
    Abstract base class for metadata providers.

    Providers fetch metadata from external sources like TMDB or TVDB.
    """

    def __init__(self, api_key: str, language: str = "en-US"):
        """
        Initialize the metadata provider.

        Args:
            api_key: API key for the service.
            language: Preferred language for metadata.
        """
        self.api_key = api_key
        self.language = language

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def search_movie(
        self, query: str, year: Optional[int] = None
    ) -> List[MediaMetadata]:
        """
        Search for movies.

        Args:
            query: Search query.
            year: Optional release year.

        Returns:
            List of matching MediaMetadata.
        """
        pass

    @abstractmethod
    async def search_tv(
        self, query: str, year: Optional[int] = None
    ) -> List[MediaMetadata]:
        """
        Search for TV shows.

        Args:
            query: Search query.
            year: Optional first air year.

        Returns:
            List of matching MediaMetadata.
        """
        pass

    @abstractmethod
    async def get_movie(self, movie_id: str) -> Optional[MediaMetadata]:
        """
        Get movie details by ID.

        Args:
            movie_id: Provider-specific movie ID.

        Returns:
            MediaMetadata or None.
        """
        pass

    @abstractmethod
    async def get_tv_show(self, show_id: str) -> Optional[MediaMetadata]:
        """
        Get TV show details by ID.

        Args:
            show_id: Provider-specific show ID.

        Returns:
            MediaMetadata or None.
        """
        pass

    @abstractmethod
    async def get_episode(
        self, show_id: str, season: int, episode: int
    ) -> Optional[MediaMetadata]:
        """
        Get episode details.

        Args:
            show_id: Provider-specific show ID.
            season: Season number.
            episode: Episode number.

        Returns:
            MediaMetadata or None.
        """
        pass

    async def search(
        self,
        query: str,
        media_type: str = "movie",
        year: Optional[int] = None,
    ) -> List[MediaMetadata]:
        """
        Generic search method.

        Args:
            query: Search query.
            media_type: "movie" or "tv".
            year: Optional year.

        Returns:
            List of matching MediaMetadata.
        """
        if media_type == "tv":
            return await self.search_tv(query, year)
        return await self.search_movie(query, year)

    async def get_best_match(
        self,
        title: str,
        media_type: str = "movie",
        year: Optional[int] = None,
    ) -> Optional[MediaMetadata]:
        """
        Get the best matching result for a title.

        Args:
            title: Media title.
            media_type: "movie" or "tv".
            year: Optional year for better matching.

        Returns:
            Best matching MediaMetadata or None.
        """
        results = await self.search(title, media_type, year)

        if not results:
            return None

        # If year provided, prefer exact match
        if year:
            for result in results:
                if result.year == year:
                    return result

        # Return first result as best match
        return results[0] if results else None
