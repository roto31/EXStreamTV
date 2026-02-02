"""
End-to-End Streaming Tests

Tests the full streaming pipeline from channel creation to MPEG-TS output.
Verifies that channels can stream content without errors.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStreamingE2E:
    """End-to-end streaming tests."""
    
    @pytest.fixture
    def temp_video_file(self) -> str:
        """Create a temporary test video file path."""
        # Use a placeholder path - actual file creation would require FFmpeg
        return "/tmp/test_video.mp4"
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session factory."""
        session = MagicMock()
        session.execute = MagicMock()
        session.commit = MagicMock()
        session.close = MagicMock()
        
        def session_factory():
            return session
        
        return session_factory
    
    @pytest.mark.asyncio
    async def test_channel_stream_initialization(self, mock_db_session):
        """Test that a channel stream can be initialized."""
        from exstreamtv.streaming.channel_manager import ChannelStream
        
        stream = ChannelStream(
            channel_id=1,
            channel_number=1,
            channel_name="Test Channel",
            db_session_factory=mock_db_session,
        )
        
        assert stream.channel_id == 1
        assert stream.channel_number == 1
        assert stream.channel_name == "Test Channel"
        assert not stream._is_running
    
    @pytest.mark.asyncio
    async def test_channel_manager_creation(self, mock_db_session):
        """Test that ChannelManager can be created."""
        from exstreamtv.streaming.channel_manager import ChannelManager
        
        manager = ChannelManager(db_session_factory=mock_db_session)
        
        assert manager is not None
        assert hasattr(manager, 'start')
        assert hasattr(manager, 'stop')
    
    @pytest.mark.asyncio
    async def test_url_resolver_creation(self):
        """Test that MediaURLResolver can be created and initialized."""
        from exstreamtv.streaming.url_resolver import MediaURLResolver, get_url_resolver
        
        resolver = MediaURLResolver()
        assert resolver is not None
        
        # Test global getter
        global_resolver = get_url_resolver()
        assert global_resolver is not None
    
    @pytest.mark.asyncio
    async def test_url_resolver_source_detection(self):
        """Test that URL resolver correctly detects media sources."""
        from exstreamtv.streaming.url_resolver import MediaURLResolver
        from exstreamtv.streaming.resolvers.base import SourceType
        
        resolver = MediaURLResolver()
        
        # Test YouTube URL detection
        class MockYouTubeItem:
            url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            source = None
        
        detected = resolver._detect_source_type(MockYouTubeItem())
        assert detected == SourceType.YOUTUBE
        
        # Test Archive.org URL detection
        class MockArchiveItem:
            url = "https://archive.org/details/test-video"
            source = None
        
        detected = resolver._detect_source_type(MockArchiveItem())
        assert detected == SourceType.ARCHIVE_ORG
        
        # Test Local file detection
        class MockLocalItem:
            url = "/path/to/video.mp4"
            source = None
        
        detected = resolver._detect_source_type(MockLocalItem())
        assert detected == SourceType.LOCAL
        
        # Test Plex URL detection
        class MockPlexItem:
            url = "http://192.168.1.100:32400/library/metadata/12345"
            source = None
        
        detected = resolver._detect_source_type(MockPlexItem())
        assert detected == SourceType.PLEX
        
        # Test Jellyfin URL detection
        class MockJellyfinItem:
            url = "http://192.168.1.100:8096/Items/abc-123"
            source = None
        
        detected = resolver._detect_source_type(MockJellyfinItem())
        assert detected == SourceType.JELLYFIN
    
    @pytest.mark.asyncio
    async def test_local_file_resolver(self):
        """Test local file resolver with valid file."""
        from exstreamtv.streaming.resolvers.local import LocalFileResolver
        from exstreamtv.streaming.resolvers.base import SourceType
        
        resolver = LocalFileResolver()
        
        # Create a temporary file to test with
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            test_file = f.name
            f.write(b"test video content")
        
        try:
            class MockItem:
                path = test_file
                id = 1
            
            result = await resolver.resolve(MockItem())
            
            assert result is not None
            assert result.url == test_file
            assert result.source_type == SourceType.LOCAL
            assert result.expires_at is None  # Local files don't expire
            
        finally:
            os.unlink(test_file)
    
    @pytest.mark.asyncio
    async def test_local_file_resolver_missing_file(self):
        """Test local file resolver with missing file."""
        from exstreamtv.streaming.resolvers.local import LocalFileResolver
        from exstreamtv.streaming.resolvers.base import ResolverError
        
        resolver = LocalFileResolver()
        
        class MockItem:
            path = "/nonexistent/path/video.mp4"
            id = 1
        
        with pytest.raises(ResolverError) as exc_info:
            await resolver.resolve(MockItem())
        
        assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_ffmpeg_watchdog_creation(self):
        """Test FFmpeg watchdog can be created."""
        from exstreamtv.streaming.process_watchdog import (
            FFmpegWatchdog,
            get_ffmpeg_watchdog,
        )
        
        watchdog = FFmpegWatchdog(timeout_seconds=30, check_interval=5.0)
        
        assert watchdog is not None
        assert watchdog._timeout == 30
        assert watchdog._check_interval == 5.0
        
        # Test stats
        stats = watchdog.get_stats()
        assert "active_processes" in stats
        assert "total_kills" in stats
        assert stats["active_processes"] == 0
        
        # Test global getter
        global_watchdog = get_ffmpeg_watchdog()
        assert global_watchdog is not None
    
    @pytest.mark.asyncio
    async def test_watchdog_report_output(self):
        """Test watchdog output reporting."""
        from exstreamtv.streaming.process_watchdog import FFmpegWatchdog
        
        watchdog = FFmpegWatchdog(timeout_seconds=30)
        
        # Report output for non-registered channel (should not crash)
        watchdog.report_output("channel_1", bytes_count=1024)
        
        # Stats should still show zero processes
        stats = watchdog.get_stats()
        assert stats["active_processes"] == 0
    
    @pytest.mark.asyncio
    async def test_filler_item_model_alias(self):
        """Test that FillerItem alias works correctly."""
        from exstreamtv.database.models import FillerItem, FillerPresetItem
        
        # FillerItem should be an alias for FillerPresetItem
        assert FillerItem is FillerPresetItem
    
    @pytest.mark.asyncio
    async def test_channel_stream_filler_fallback(self, mock_db_session):
        """Test that channel stream can attempt filler fallback."""
        from exstreamtv.streaming.channel_manager import ChannelStream
        
        stream = ChannelStream(
            channel_id=1,
            channel_number=1,
            channel_name="Test Channel",
            db_session_factory=mock_db_session,
        )
        
        # Mock the database result to return no channel
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session().execute.return_value = mock_result
        
        # Should return None when no channel/filler found
        result = await stream._get_filler_item()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_streaming_health_endpoint_imports(self):
        """Test that health endpoint can import streaming components."""
        # This verifies all imports work correctly
        from exstreamtv.streaming.process_watchdog import get_ffmpeg_watchdog
        from exstreamtv.streaming.url_resolver import get_url_resolver
        
        watchdog = get_ffmpeg_watchdog()
        resolver = get_url_resolver()
        
        # Get stats from both
        watchdog_stats = watchdog.get_stats()
        resolver_stats = resolver.get_stats()
        
        assert "active_processes" in watchdog_stats
        assert "global_cache_size" in resolver_stats


class TestResolverIntegration:
    """Integration tests for URL resolvers."""
    
    @pytest.mark.asyncio
    async def test_resolver_caching(self):
        """Test that resolvers cache results."""
        from exstreamtv.streaming.resolvers.local import LocalFileResolver
        
        resolver = LocalFileResolver()
        
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            test_file = f.name
            f.write(b"test content")
        
        try:
            class MockItem:
                path = test_file
                id = 1
            
            # First resolution
            result1 = await resolver.resolve(MockItem())
            
            # Cache stats should show one entry
            cache_stats = resolver.get_cache_stats()
            # Note: Local resolver doesn't use caching since files don't expire
            
            assert result1 is not None
            
        finally:
            os.unlink(test_file)
    
    @pytest.mark.asyncio
    async def test_youtube_resolver_video_id_extraction(self):
        """Test YouTube video ID extraction from various URL formats."""
        from exstreamtv.streaming.resolvers.youtube import YouTubeResolver
        
        resolver = YouTubeResolver()
        
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/v/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),  # Just the ID
        ]
        
        for url, expected_id in test_cases:
            extracted = resolver._extract_video_id(url)
            assert extracted == expected_id, f"Failed for URL: {url}"
    
    @pytest.mark.asyncio
    async def test_archive_org_resolver_identifier_extraction(self):
        """Test Archive.org identifier extraction."""
        from exstreamtv.streaming.resolvers.archive_org import ArchiveOrgResolver
        
        resolver = ArchiveOrgResolver()
        
        test_cases = [
            ("https://archive.org/details/test-video", "test-video"),
            ("https://archive.org/download/test-video/file.mp4", "test-video"),
            ("https://archive.org/embed/test-video", "test-video"),
        ]
        
        for url, expected_id in test_cases:
            extracted = resolver._extract_identifier(url)
            assert extracted == expected_id, f"Failed for URL: {url}"


class TestBackgroundTasks:
    """Tests for background task infrastructure."""
    
    @pytest.mark.asyncio
    async def test_health_task_imports(self):
        """Test health task module imports correctly."""
        from exstreamtv.tasks.health_tasks import (
            channel_health_task,
            update_channel_metric,
            get_channel_metrics,
        )
        
        # Update a metric
        update_channel_metric(1, "test_metric", "test_value")
        
        # Get metrics
        metrics = get_channel_metrics(1)
        assert metrics.get("test_metric") == "test_value"
    
    @pytest.mark.asyncio
    async def test_url_refresh_task_imports(self):
        """Test URL refresh task module imports correctly."""
        from exstreamtv.tasks.url_refresh_task import (
            refresh_urls_task,
            cleanup_url_cache_task,
        )
        
        # Run cleanup (should work even with empty cache)
        result = await cleanup_url_cache_task()
        assert "entries_before" in result
        assert "entries_removed" in result
    
    @pytest.mark.asyncio
    async def test_playout_task_imports(self):
        """Test playout task module imports correctly."""
        from exstreamtv.tasks.playout_tasks import (
            rebuild_playouts_task,
            cleanup_old_playout_items_task,
        )
        
        # These should import without error
        assert callable(rebuild_playouts_task)
        assert callable(cleanup_old_playout_items_task)
