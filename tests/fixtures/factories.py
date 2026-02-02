"""
Test Data Factories

Factory classes for generating test data.
"""

import random
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from exstreamtv.database.models.channel import Channel
from exstreamtv.database.models.playlist import Playlist, PlaylistItem
from exstreamtv.database.models.media import MediaItem
from exstreamtv.database.models.library import LocalLibrary, PlexLibrary


class BaseFactory:
    """Base factory class."""
    
    _counter = 0
    
    @classmethod
    def _next_id(cls) -> int:
        cls._counter += 1
        return cls._counter
    
    @classmethod
    def _random_string(cls, length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_letters, k=length))


class ChannelFactory(BaseFactory):
    """Factory for creating Channel test instances."""
    
    @classmethod
    def create(
        cls,
        number: Optional[int] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> Channel:
        """Create a Channel instance."""
        return Channel(
            number=number or cls._next_id(),
            name=name or f"Test Channel {cls._random_string()}",
            logo_url=kwargs.get("logo_url"),
            group=kwargs.get("group", "Test Group"),
            enabled=kwargs.get("enabled", kwargs.get("is_enabled", True)),
        )
    
    @classmethod
    def create_batch(cls, count: int, **kwargs) -> List[Channel]:
        """Create multiple Channel instances."""
        return [cls.create(**kwargs) for _ in range(count)]
    
    @classmethod
    def create_dict(
        cls,
        number: Optional[int] = None,
        name: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create Channel data as dictionary."""
        return {
            "number": number or cls._next_id(),
            "name": name or f"Test Channel {cls._random_string()}",
            "logo_url": kwargs.get("logo_url"),
            "group": kwargs.get("group", "Test Group"),
            "enabled": kwargs.get("enabled", kwargs.get("is_enabled", True)),
        }


class PlaylistFactory(BaseFactory):
    """Factory for creating Playlist test instances."""
    
    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        **kwargs
    ) -> Playlist:
        """Create a Playlist instance."""
        return Playlist(
            name=name or f"Test Playlist {cls._random_string()}",
            description=kwargs.get("description", "Test playlist description"),
            is_enabled=kwargs.get("is_enabled", True),
        )
    
    @classmethod
    def create_with_items(
        cls,
        item_count: int = 5,
        **kwargs
    ) -> Playlist:
        """Create a Playlist with items."""
        playlist = cls.create(**kwargs)
        playlist.items = [
            PlaylistItemFactory.create(position=i)
            for i in range(item_count)
        ]
        return playlist
    
    @classmethod
    def create_dict(cls, name: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Create Playlist data as dictionary."""
        return {
            "name": name or f"Test Playlist {cls._random_string()}",
            "description": kwargs.get("description", "Test playlist"),
            "is_enabled": kwargs.get("is_enabled", True),
        }


class PlaylistItemFactory(BaseFactory):
    """Factory for creating PlaylistItem test instances."""
    
    @classmethod
    def create(
        cls,
        position: Optional[int] = None,
        **kwargs
    ) -> PlaylistItem:
        """Create a PlaylistItem instance."""
        return PlaylistItem(
            position=position if position is not None else cls._next_id(),
            title=kwargs.get("title", f"Test Item {cls._random_string()}"),
            source_url=kwargs.get("source_url", f"http://example.com/video_{cls._random_string()}.mp4"),
            source_type=kwargs.get("source_type", "url"),
            duration=kwargs.get("duration", random.randint(60, 7200)),
        )
    
    @classmethod
    def create_batch(cls, count: int, **kwargs) -> List[PlaylistItem]:
        """Create multiple PlaylistItem instances."""
        return [cls.create(position=i, **kwargs) for i in range(count)]


class MediaItemFactory(BaseFactory):
    """Factory for creating MediaItem test instances."""
    
    MEDIA_TYPES = ["movie", "episode", "show"]
    GENRES = ["Action", "Comedy", "Drama", "Horror", "Sci-Fi", "Documentary"]
    
    @classmethod
    def create(
        cls,
        media_type: Optional[str] = None,
        **kwargs
    ) -> MediaItem:
        """Create a MediaItem instance."""
        m_type = media_type or random.choice(cls.MEDIA_TYPES)
        
        item = MediaItem(
            title=kwargs.get("title", f"Test {m_type.title()} {cls._random_string()}"),
            media_type=m_type,
            year=kwargs.get("year", random.randint(1990, 2024)),
            duration=kwargs.get("duration", random.randint(1800, 10800)),
            library_source=kwargs.get("library_source", "local"),
            library_id=kwargs.get("library_id", 1),
        )
        
        if m_type == "episode":
            item.show_title = kwargs.get("show_title", f"Test Show {cls._random_string()}")
            item.season_number = kwargs.get("season_number", random.randint(1, 10))
            item.episode_number = kwargs.get("episode_number", random.randint(1, 24))
        
        return item
    
    @classmethod
    def create_movie(cls, **kwargs) -> MediaItem:
        """Create a movie MediaItem."""
        return cls.create(media_type="movie", **kwargs)
    
    @classmethod
    def create_episode(cls, **kwargs) -> MediaItem:
        """Create an episode MediaItem."""
        return cls.create(media_type="episode", **kwargs)
    
    @classmethod
    def create_show_with_episodes(
        cls,
        seasons: int = 3,
        episodes_per_season: int = 10,
        **kwargs
    ) -> List[MediaItem]:
        """Create a complete show with episodes."""
        show_title = kwargs.get("show_title", f"Test Show {cls._random_string()}")
        items = []
        
        for season in range(1, seasons + 1):
            for episode in range(1, episodes_per_season + 1):
                items.append(cls.create_episode(
                    show_title=show_title,
                    season_number=season,
                    episode_number=episode,
                    title=f"Episode {episode}",
                    **kwargs
                ))
        
        return items


class LocalLibraryFactory(BaseFactory):
    """Factory for creating LocalLibrary test instances."""
    
    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs
    ) -> LocalLibrary:
        """Create a LocalLibrary instance."""
        return LocalLibrary(
            name=name or f"Test Library {cls._random_string()}",
            path=path or f"/media/test_{cls._random_string()}",
            library_type=kwargs.get("library_type", "movie"),
            is_enabled=kwargs.get("is_enabled", True),
            file_extensions=kwargs.get("file_extensions", [".mp4", ".mkv"]),
            item_count=kwargs.get("item_count", 0),
        )
    
    @classmethod
    def create_dict(cls, **kwargs) -> Dict[str, Any]:
        """Create LocalLibrary data as dictionary."""
        return {
            "name": kwargs.get("name", f"Test Library {cls._random_string()}"),
            "path": kwargs.get("path", f"/media/test_{cls._random_string()}"),
            "library_type": kwargs.get("library_type", "movie"),
            "is_enabled": kwargs.get("is_enabled", True),
            "file_extensions": kwargs.get("file_extensions", [".mp4", ".mkv"]),
        }


class PlexLibraryFactory(BaseFactory):
    """Factory for creating PlexLibrary test instances."""
    
    @classmethod
    def create(
        cls,
        name: Optional[str] = None,
        **kwargs
    ) -> PlexLibrary:
        """Create a PlexLibrary instance."""
        return PlexLibrary(
            name=name or f"Plex Library {cls._random_string()}",
            server_url=kwargs.get("server_url", "http://localhost:32400"),
            token=kwargs.get("token", f"test_token_{cls._random_string()}"),
            library_key=kwargs.get("library_key", str(cls._next_id())),
            is_enabled=kwargs.get("is_enabled", True),
            item_count=kwargs.get("item_count", 0),
        )
