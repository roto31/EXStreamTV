"""
Unit tests for library modules.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exstreamtv.media.libraries.base import (
    LibraryType,
    MediaType,
    LibraryItem,
    BaseLibrary,
    LibraryManager,
)
from exstreamtv.media.libraries.local import LocalLibrary
from exstreamtv.media.libraries.plex import PlexLibrary
from exstreamtv.media.libraries.jellyfin import JellyfinLibrary, EmbyLibrary


@pytest.mark.unit
class TestLibraryType:
    """Tests for LibraryType enum."""
    
    def test_library_types(self):
        """Test library type values."""
        assert LibraryType.LOCAL.value == "local"
        assert LibraryType.PLEX.value == "plex"
        assert LibraryType.JELLYFIN.value == "jellyfin"
        assert LibraryType.EMBY.value == "emby"


@pytest.mark.unit
class TestMediaType:
    """Tests for MediaType enum."""
    
    def test_media_types(self):
        """Test media type values."""
        assert MediaType.MOVIE.value == "movie"
        assert MediaType.SHOW.value == "show"
        assert MediaType.EPISODE.value == "episode"


@pytest.mark.unit
class TestLibraryItem:
    """Tests for LibraryItem dataclass."""
    
    def test_library_item_creation(self):
        """Test creating a library item."""
        item = LibraryItem(
            id="item_1",
            library_id=1,
            media_type=MediaType.MOVIE,
            title="Test Movie",
            path="/media/movies/test.mp4",
            duration=7200.0,
        )
        
        assert item.id == "item_1"
        assert item.media_type == MediaType.MOVIE
        assert item.title == "Test Movie"
        assert item.duration == 7200.0
    
    def test_library_item_with_metadata(self):
        """Test library item with metadata."""
        item = LibraryItem(
            id="item_1",
            library_id=1,
            media_type=MediaType.MOVIE,
            title="Test Movie",
            year=2024,
            description="A test movie",
            genres=["Action", "Comedy"],
            rating=8.5,
        )
        
        assert item.year == 2024
        assert "Action" in item.genres
        assert item.rating == 8.5


@pytest.mark.unit
class TestLibraryManager:
    """Tests for LibraryManager."""
    
    def test_add_library(self):
        """Test adding a library."""
        manager = LibraryManager()
        
        library = MagicMock(spec=BaseLibrary)
        library.library_id = 1
        library.name = "Test Library"
        
        manager.add_library(library)
        
        assert manager.get_library(1) is library
    
    def test_remove_library(self):
        """Test removing a library."""
        manager = LibraryManager()
        
        library = MagicMock(spec=BaseLibrary)
        library.library_id = 1
        
        manager.add_library(library)
        manager.remove_library(1)
        
        assert manager.get_library(1) is None
    
    def test_get_all_libraries(self):
        """Test getting all libraries."""
        manager = LibraryManager()
        
        for i in range(3):
            library = MagicMock(spec=BaseLibrary)
            library.library_id = i
            manager.add_library(library)
        
        all_libs = manager.get_all_libraries()
        
        assert len(all_libs) == 3
    
    @pytest.mark.asyncio
    async def test_sync_all(self):
        """Test syncing all libraries."""
        manager = LibraryManager()
        
        for i in range(2):
            library = MagicMock(spec=BaseLibrary)
            library.library_id = i
            library.sync = AsyncMock(return_value=[
                LibraryItem(
                    id=f"item_{i}",
                    library_id=i,
                    media_type=MediaType.MOVIE,
                    title=f"Movie {i}",
                )
            ])
            manager.add_library(library)
        
        results = await manager.sync_all()
        
        assert len(results) == 2
        assert 0 in results
        assert 1 in results


@pytest.mark.unit
class TestLocalLibrary:
    """Tests for LocalLibrary."""
    
    def test_local_library_creation(self, temp_dir: Path):
        """Test creating a local library."""
        library = LocalLibrary(
            library_id=1,
            name="Movies",
            path=str(temp_dir),
            extensions=[".mp4", ".mkv"],
        )
        
        assert library.library_id == 1
        assert library.name == "Movies"
        assert library.library_type == LibraryType.LOCAL
    
    @pytest.mark.asyncio
    async def test_local_library_connect(self, temp_dir: Path):
        """Test connecting to local library."""
        library = LocalLibrary(
            library_id=1,
            name="Movies",
            path=str(temp_dir),
        )
        
        result = await library.connect()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_local_library_invalid_path(self):
        """Test local library with invalid path."""
        library = LocalLibrary(
            library_id=1,
            name="Movies",
            path="/nonexistent/path",
        )
        
        result = await library.connect()
        
        assert result is False


@pytest.mark.unit
class TestPlexLibrary:
    """Tests for PlexLibrary."""
    
    def test_plex_library_creation(self):
        """Test creating a Plex library."""
        library = PlexLibrary(
            library_id=1,
            name="Plex Movies",
            server_url="http://localhost:32400",
            token="test_token",
            plex_library_key="1",
        )
        
        assert library.library_id == 1
        assert library.library_type == LibraryType.PLEX
        assert library.server_url == "http://localhost:32400"
    
    @pytest.mark.asyncio
    async def test_plex_library_connect(self, mock_plex_server):
        """Test connecting to Plex library."""
        library = PlexLibrary(
            library_id=1,
            name="Plex Movies",
            server_url="http://localhost:32400",
            token="test_token",
            plex_library_key="1",
        )
        
        result = await library.connect()
        
        # Should succeed with mock
        assert result is True
    
    @pytest.mark.asyncio
    async def test_plex_library_get_stream_url(self, mock_plex_server):
        """Test getting stream URL from Plex."""
        library = PlexLibrary(
            library_id=1,
            name="Plex Movies",
            server_url="http://localhost:32400",
            token="test_token",
            plex_library_key="1",
        )
        
        await library.connect()
        url = await library.get_stream_url("12345")
        
        assert url is not None
        assert "localhost:32400" in url


@pytest.mark.unit
class TestJellyfinLibrary:
    """Tests for JellyfinLibrary."""
    
    def test_jellyfin_library_creation(self):
        """Test creating a Jellyfin library."""
        library = JellyfinLibrary(
            library_id=1,
            name="Jellyfin Movies",
            server_url="http://localhost:8096",
            api_key="test_key",
            jellyfin_library_id="abc123",
        )
        
        assert library.library_id == 1
        assert library.library_type == LibraryType.JELLYFIN


@pytest.mark.unit
class TestEmbyLibrary:
    """Tests for EmbyLibrary."""
    
    def test_emby_library_creation(self):
        """Test creating an Emby library."""
        library = EmbyLibrary(
            library_id=1,
            name="Emby Movies",
            server_url="http://localhost:8096",
            api_key="test_key",
            emby_library_id="abc123",
        )
        
        assert library.library_id == 1
        assert library.library_type == LibraryType.EMBY
