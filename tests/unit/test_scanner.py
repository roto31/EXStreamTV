"""
Unit tests for media scanner modules.
"""

import asyncio
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exstreamtv.media.scanner.base import (
    ScanStatus,
    ScanProgress,
    ScanResult,
    MediaScanner,
)
from exstreamtv.media.scanner.ffprobe import (
    FFprobeAnalyzer,
    VideoStream,
    AudioStream,
    SubtitleStream,
    MediaInfo,
)
from exstreamtv.media.scanner.file_scanner import FileScanner, ScannedFile


@pytest.mark.unit
class TestScanProgress:
    """Tests for ScanProgress dataclass."""
    
    def test_default_values(self):
        """Test default progress values."""
        progress = ScanProgress()
        
        assert progress.total_files == 0
        assert progress.scanned_files == 0
        assert progress.errors == 0
    
    def test_percent_complete(self):
        """Test percent complete calculation."""
        progress = ScanProgress(total_files=100, scanned_files=50)
        
        assert progress.percent_complete == 50.0
    
    def test_percent_complete_zero_division(self):
        """Test percent complete with zero total files."""
        progress = ScanProgress(total_files=0, scanned_files=0)
        
        assert progress.percent_complete == 0.0


@pytest.mark.unit
class TestScanResult:
    """Tests for ScanResult dataclass."""
    
    def test_success_result(self):
        """Test creating a success result."""
        result = ScanResult.success(
            progress=ScanProgress(total_files=10, scanned_files=10),
            items=[{"title": "Test"}]
        )
        
        assert result.status == ScanStatus.COMPLETED
        assert len(result.items) == 1
    
    def test_failure_result(self):
        """Test creating a failure result."""
        result = ScanResult.failure(
            error="Scan failed",
            progress=ScanProgress(errors=1)
        )
        
        assert result.status == ScanStatus.FAILED
        assert "Scan failed" in result.errors


@pytest.mark.unit
class TestVideoStream:
    """Tests for VideoStream dataclass."""
    
    def test_video_stream_creation(self):
        """Test creating a video stream."""
        stream = VideoStream(
            index=0,
            codec_name="h264",
            codec_long_name="H.264 / AVC",
            width=1920,
            height=1080,
        )
        
        assert stream.codec_name == "h264"
        assert stream.width == 1920
        assert stream.height == 1080
    
    def test_video_stream_aspect_ratio(self):
        """Test video stream resolution property."""
        stream = VideoStream(
            index=0,
            codec_name="h264",
            codec_long_name="H.264 / AVC",
            width=1920,
            height=1080,
        )
        
        # Check resolution property
        assert stream.resolution == "1920x1080"
        
        # 16:9 aspect ratio
        aspect = stream.width / stream.height
        assert abs(aspect - 16/9) < 0.01
    
    def test_video_stream_hdr_detection(self):
        """Test HDR detection."""
        sdr_stream = VideoStream(
            index=0,
            codec_name="h264",
            codec_long_name="H.264 / AVC",
            width=1920,
            height=1080,
        )
        assert sdr_stream.is_hdr is False
        
        hdr_stream = VideoStream(
            index=0,
            codec_name="hevc",
            codec_long_name="HEVC",
            width=3840,
            height=2160,
            color_transfer="smpte2084",
        )
        assert hdr_stream.is_hdr is True


@pytest.mark.unit
class TestAudioStream:
    """Tests for AudioStream dataclass."""
    
    def test_audio_stream_creation(self):
        """Test creating an audio stream."""
        stream = AudioStream(
            index=1,
            codec_name="aac",
            codec_long_name="AAC (Advanced Audio Coding)",
            channels=2,
            sample_rate=48000,
            language="eng",
        )
        
        assert stream.codec_name == "aac"
        assert stream.channels == 2
        assert stream.language == "eng"


@pytest.mark.unit
class TestMediaInfo:
    """Tests for MediaInfo dataclass."""
    
    def test_media_info_creation(self):
        """Test creating media info."""
        info = MediaInfo(
            path=Path("/test/video.mp4"),
            format_name="mp4",
            format_long_name="QuickTime / MOV",
            duration=timedelta(seconds=3600),
            size=1024 * 1024 * 100,
            bit_rate=2000000,
            video_streams=[
                VideoStream(
                    index=0, 
                    codec_name="h264", 
                    codec_long_name="H.264 / AVC",
                    width=1920, 
                    height=1080
                )
            ],
            audio_streams=[
                AudioStream(
                    index=1, 
                    codec_name="aac",
                    codec_long_name="AAC",
                    channels=2
                )
            ],
            subtitle_streams=[],
        )
        
        assert info.format_name == "mp4"
        assert info.duration == timedelta(seconds=3600)
        assert len(info.video_streams) == 1
        assert len(info.audio_streams) == 1
        assert info.has_video is True
        assert info.has_audio is True
    
    def test_primary_streams(self):
        """Test primary stream access."""
        video = VideoStream(
            index=0, 
            codec_name="h264", 
            codec_long_name="H.264",
            width=1920, 
            height=1080
        )
        audio = AudioStream(
            index=1, 
            codec_name="aac",
            codec_long_name="AAC",
            channels=2
        )
        
        info = MediaInfo(
            path=Path("/test/video.mp4"),
            format_name="mp4",
            format_long_name="QuickTime",
            duration=timedelta(seconds=100),
            size=1000000,
            bit_rate=80000,
            video_streams=[video],
            audio_streams=[audio],
        )
        
        assert info.primary_video == video
        assert info.primary_audio == audio


@pytest.mark.unit
class TestFFprobeAnalyzer:
    """Tests for FFprobeAnalyzer."""
    
    @pytest.fixture
    def analyzer(self):
        """Create FFprobe analyzer."""
        return FFprobeAnalyzer()
    
    def test_default_ffprobe_path(self, analyzer: FFprobeAnalyzer):
        """Test default FFprobe path is set."""
        # Should be set to either 'ffprobe' or a valid path found by shutil.which
        assert analyzer.ffprobe_path is not None
        assert len(analyzer.ffprobe_path) > 0
    
    def test_custom_ffprobe_path(self):
        """Test custom FFprobe path."""
        analyzer = FFprobeAnalyzer(ffprobe_path="/custom/ffprobe")
        assert analyzer.ffprobe_path == "/custom/ffprobe"


@pytest.mark.unit
class TestFileScanner:
    """Tests for FileScanner."""
    
    def test_file_scanner_creation(self, temp_dir: Path):
        """Test creating a file scanner."""
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
        )
        
        assert scanner.library_id == 1
        assert scanner.library_path == Path(temp_dir)
    
    def test_default_extensions(self, temp_dir: Path):
        """Test default media extensions."""
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
        )
        
        assert ".mp4" in scanner.extensions
        assert ".mkv" in scanner.extensions
        assert ".avi" in scanner.extensions
    
    def test_custom_extensions(self, temp_dir: Path):
        """Test custom media extensions."""
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
            extensions={".custom", ".ext"},
        )
        
        assert ".custom" in scanner.extensions
        assert ".mp4" not in scanner.extensions
    
    def test_is_media_file(self, temp_dir: Path):
        """Test media file detection."""
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
        )
        
        assert scanner.is_media_file(Path("video.mp4")) is True
        assert scanner.is_media_file(Path("video.mkv")) is True
        assert scanner.is_media_file(Path("document.txt")) is False
        assert scanner.is_media_file(Path("image.jpg")) is False
    
    def test_get_relative_path(self, temp_dir: Path):
        """Test getting relative path."""
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
        )
        
        full_path = temp_dir / "subdir" / "video.mp4"
        rel_path = scanner.get_relative_path(full_path)
        
        assert rel_path == Path("subdir/video.mp4")
    
    @pytest.mark.asyncio
    async def test_discover_files(self, temp_dir: Path):
        """Test file discovery."""
        # Create test files
        (temp_dir / "video1.mp4").touch()
        (temp_dir / "video2.mkv").touch()
        (temp_dir / "document.txt").touch()
        
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "video3.mp4").touch()
        
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
        )
        
        files = scanner._discover_files(temp_dir)
        
        media_files = [f for f in files if scanner.is_media_file(f)]
        assert len(media_files) == 3
    
    @pytest.mark.asyncio
    async def test_scan_empty_directory(self, temp_dir: Path):
        """Test scanning empty directory."""
        scanner = FileScanner(
            library_id=1,
            library_path=str(temp_dir),
        )
        
        result = await scanner.scan()
        
        # Empty dir should complete with warning, not fail
        assert result.status in [ScanStatus.COMPLETED, ScanStatus.CANCELLED]


@pytest.mark.unit
class TestScannedFile:
    """Tests for ScannedFile dataclass."""
    
    def test_scanned_file_creation(self, temp_dir: Path):
        """Test creating a scanned file."""
        file_path = temp_dir / "video.mp4"
        
        scanned = ScannedFile(
            path=file_path,
            relative_path=Path("video.mp4"),
            size=1024 * 1024,
            modified_time=1700000000.0,
            media_info=None,
        )
        
        assert scanned.path == file_path
        assert scanned.size == 1024 * 1024
