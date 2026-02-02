"""
Unit tests for database models.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from exstreamtv.database.models.channel import Channel
from exstreamtv.database.models.playlist import Playlist, PlaylistItem
from exstreamtv.database.models.media import MediaItem
from exstreamtv.database.models.library import LocalLibrary, PlexLibrary
from exstreamtv.database.models.schedule import ProgramSchedule
from exstreamtv.database.models.playout import Playout, PlayoutItem


@pytest.mark.unit
class TestChannelModel:
    """Tests for Channel model."""
    
    def test_create_channel(self, db: Session):
        """Test creating a channel."""
        channel = Channel(
            number=1,
            name="Test Channel",
            logo_url="https://example.com/logo.png",
            group="Entertainment",
            enabled=True,
        )
        
        db.add(channel)
        db.commit()
        db.refresh(channel)
        
        assert channel.id is not None
        assert channel.number == 1
        assert channel.name == "Test Channel"
        assert channel.enabled is True
    
    def test_channel_unique_number(self, db: Session):
        """Test that channel numbers must be unique."""
        channel1 = Channel(number=1, name="Channel 1")
        channel2 = Channel(number=1, name="Channel 2")
        
        db.add(channel1)
        db.commit()
        
        db.add(channel2)
        
        with pytest.raises(Exception):  # IntegrityError
            db.commit()
    
    def test_channel_defaults(self, db: Session):
        """Test default channel values."""
        channel = Channel(number=1, name="Test")
        
        db.add(channel)
        db.commit()
        db.refresh(channel)
        
        assert channel.enabled is True
        assert channel.created_at is not None


@pytest.mark.unit
class TestPlaylistModel:
    """Tests for Playlist model."""
    
    def test_create_playlist(self, db: Session):
        """Test creating a playlist."""
        playlist = Playlist(
            name="Test Playlist",
            description="A test playlist",
        )
        
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        
        assert playlist.id is not None
        assert playlist.name == "Test Playlist"
    
    def test_playlist_with_items(self, db: Session):
        """Test playlist with items."""
        playlist = Playlist(name="With Items")
        db.add(playlist)
        db.commit()
        
        # Add items
        for i in range(3):
            item = PlaylistItem(
                playlist_id=playlist.id,
                position=i,
                title=f"Item {i}",
                source_url=f"https://example.com/video{i}.mp4",
            )
            db.add(item)
        
        db.commit()
        db.refresh(playlist)
        
        assert len(playlist.items) == 3
    
    def test_playlist_item_ordering(self, db: Session):
        """Test playlist item ordering by position."""
        playlist = Playlist(name="Ordered")
        db.add(playlist)
        db.commit()
        
        # Add items out of order
        for pos in [2, 0, 1]:
            item = PlaylistItem(
                playlist_id=playlist.id,
                position=pos,
                title=f"Item {pos}",
            )
            db.add(item)
        
        db.commit()
        db.refresh(playlist)
        
        # Items should be orderable by position
        sorted_items = sorted(playlist.items, key=lambda x: x.position)
        assert [i.position for i in sorted_items] == [0, 1, 2]


@pytest.mark.unit
class TestMediaItemModel:
    """Tests for MediaItem model."""
    
    def test_create_media_item(self, db: Session):
        """Test creating a media item."""
        item = MediaItem(
            title="Test Movie",
            media_type="movie",
            year=2024,
            duration=7200,
            library_source="local",
            library_id=1,
        )
        
        db.add(item)
        db.commit()
        db.refresh(item)
        
        assert item.id is not None
        assert item.title == "Test Movie"
        assert item.media_type == "movie"
    
    def test_episode_media_item(self, db: Session):
        """Test creating an episode media item."""
        item = MediaItem(
            title="Pilot",
            media_type="episode",
            show_title="Test Show",
            season_number=1,
            episode_number=1,
            library_source="plex",
            library_id=1,
        )
        
        db.add(item)
        db.commit()
        db.refresh(item)
        
        assert item.show_title == "Test Show"
        assert item.season_number == 1
        assert item.episode_number == 1


@pytest.mark.unit
class TestLibraryModels:
    """Tests for library models."""
    
    def test_create_local_library(self, db: Session):
        """Test creating a local library."""
        library = LocalLibrary(
            name="Movies",
            path="/media/movies",
            library_type="movie",
            file_extensions=[".mp4", ".mkv"],
        )
        
        db.add(library)
        db.commit()
        db.refresh(library)
        
        assert library.id is not None
        assert library.path == "/media/movies"
        assert ".mp4" in library.file_extensions
    
    def test_create_plex_library(self, db: Session):
        """Test creating a Plex library."""
        library = PlexLibrary(
            name="Plex Movies",
            server_url="http://localhost:32400",
            token="test_token",
            library_key="1",
        )
        
        db.add(library)
        db.commit()
        db.refresh(library)
        
        assert library.id is not None
        assert library.server_url == "http://localhost:32400"


@pytest.mark.unit
class TestScheduleModel:
    """Tests for ProgramSchedule model."""
    
    def test_create_schedule(self, db: Session):
        """Test creating a schedule."""
        schedule = ProgramSchedule(
            name="Daily Schedule",
        )
        
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        assert schedule.id is not None
        assert schedule.name == "Daily Schedule"


@pytest.mark.unit
class TestPlayoutModel:
    """Tests for Playout model."""
    
    def test_create_playout(self, db: Session):
        """Test creating a playout."""
        # First create a channel
        channel = Channel(number=1, name="Test")
        db.add(channel)
        db.commit()
        
        playout = Playout(
            channel_id=channel.id,
            is_active=True,
        )
        
        db.add(playout)
        db.commit()
        db.refresh(playout)
        
        assert playout.id is not None
        assert playout.channel_id == channel.id
    
    def test_playout_with_items(self, db: Session):
        """Test playout with items."""
        channel = Channel(number=1, name="Test")
        db.add(channel)
        db.commit()
        
        playout = Playout(channel_id=channel.id)
        db.add(playout)
        db.commit()
        
        # Add playout items
        start_time = datetime.now()
        for i in range(5):
            item = PlayoutItem(
                playout_id=playout.id,
                start_time=start_time + timedelta(hours=i),
                duration=3600,
                title=f"Program {i}",
            )
            db.add(item)
        
        db.commit()
        db.refresh(playout)
        
        assert len(playout.items) == 5
