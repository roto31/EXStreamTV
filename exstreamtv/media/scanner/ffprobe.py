"""
FFprobe media analysis.

Extracts detailed media information using FFprobe.
"""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class VideoStream:
    """Video stream information."""

    index: int
    codec_name: str
    codec_long_name: str
    profile: Optional[str] = None
    width: int = 0
    height: int = 0
    coded_width: int = 0
    coded_height: int = 0
    display_aspect_ratio: Optional[str] = None
    sample_aspect_ratio: Optional[str] = None
    pix_fmt: Optional[str] = None
    level: Optional[int] = None
    color_range: Optional[str] = None
    color_space: Optional[str] = None
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    field_order: Optional[str] = None
    avg_frame_rate: Optional[str] = None
    r_frame_rate: Optional[str] = None
    bit_rate: Optional[int] = None
    bits_per_raw_sample: Optional[int] = None

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def is_interlaced(self) -> bool:
        return self.field_order not in (None, "progressive", "unknown")

    @property
    def is_hdr(self) -> bool:
        hdr_transfers = {"smpte2084", "arib-std-b67", "bt2020-10", "bt2020-12"}
        return self.color_transfer in hdr_transfers

    @property
    def frame_rate(self) -> Optional[float]:
        """Calculate frame rate from fraction string."""
        if not self.avg_frame_rate:
            return None
        try:
            num, den = self.avg_frame_rate.split("/")
            return float(num) / float(den) if float(den) > 0 else None
        except (ValueError, ZeroDivisionError):
            return None


@dataclass
class AudioStream:
    """Audio stream information."""

    index: int
    codec_name: str
    codec_long_name: str
    profile: Optional[str] = None
    sample_rate: Optional[int] = None
    channels: int = 2
    channel_layout: Optional[str] = None
    bit_rate: Optional[int] = None
    bits_per_sample: Optional[int] = None
    language: Optional[str] = None
    title: Optional[str] = None


@dataclass
class SubtitleStream:
    """Subtitle stream information."""

    index: int
    codec_name: str
    codec_long_name: str
    language: Optional[str] = None
    title: Optional[str] = None
    forced: bool = False
    default: bool = False


@dataclass
class MediaInfo:
    """Complete media file information."""

    path: Path
    format_name: str
    format_long_name: str
    duration: timedelta
    size: int
    bit_rate: int
    start_time: float = 0.0
    video_streams: List[VideoStream] = field(default_factory=list)
    audio_streams: List[AudioStream] = field(default_factory=list)
    subtitle_streams: List[SubtitleStream] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return len(self.video_streams) > 0

    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0

    @property
    def primary_video(self) -> Optional[VideoStream]:
        return self.video_streams[0] if self.video_streams else None

    @property
    def primary_audio(self) -> Optional[AudioStream]:
        return self.audio_streams[0] if self.audio_streams else None

    @property
    def title(self) -> Optional[str]:
        return self.tags.get("title")


class FFprobeAnalyzer:
    """
    Analyzes media files using FFprobe.

    Ported from ErsatzTV FFprobe integration.
    """

    def __init__(self, ffprobe_path: Optional[str] = None):
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or "ffprobe"

    async def analyze(self, path: Path, timeout: float = 30.0) -> MediaInfo:
        """
        Analyze a media file.

        Args:
            path: Path to media file.
            timeout: Timeout in seconds.

        Returns:
            MediaInfo with complete file analysis.
        """
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            if process.returncode != 0:
                error = stderr.decode("utf-8", errors="replace") if stderr else "Unknown error"
                raise RuntimeError(f"FFprobe failed: {error}")

            data = json.loads(stdout.decode("utf-8", errors="replace"))
            return self._parse_result(path, data)

        except asyncio.TimeoutError:
            raise RuntimeError(f"FFprobe timeout for {path}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"FFprobe output parse error: {e}")

    def _parse_result(self, path: Path, data: Dict[str, Any]) -> MediaInfo:
        """Parse FFprobe JSON output."""
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        # Parse format info
        duration_str = fmt.get("duration", "0")
        try:
            duration = timedelta(seconds=float(duration_str))
        except ValueError:
            duration = timedelta(0)

        media_info = MediaInfo(
            path=path,
            format_name=fmt.get("format_name", "unknown"),
            format_long_name=fmt.get("format_long_name", "Unknown"),
            duration=duration,
            size=int(fmt.get("size", 0)),
            bit_rate=int(fmt.get("bit_rate", 0)),
            start_time=float(fmt.get("start_time", 0)),
            tags=fmt.get("tags", {}),
        )

        # Parse streams
        for stream in streams:
            codec_type = stream.get("codec_type")

            if codec_type == "video":
                media_info.video_streams.append(self._parse_video_stream(stream))
            elif codec_type == "audio":
                media_info.audio_streams.append(self._parse_audio_stream(stream))
            elif codec_type == "subtitle":
                media_info.subtitle_streams.append(self._parse_subtitle_stream(stream))

        return media_info

    def _parse_video_stream(self, stream: Dict[str, Any]) -> VideoStream:
        """Parse video stream data."""
        return VideoStream(
            index=stream.get("index", 0),
            codec_name=stream.get("codec_name", "unknown"),
            codec_long_name=stream.get("codec_long_name", "Unknown"),
            profile=stream.get("profile"),
            width=stream.get("width", 0),
            height=stream.get("height", 0),
            coded_width=stream.get("coded_width", 0),
            coded_height=stream.get("coded_height", 0),
            display_aspect_ratio=stream.get("display_aspect_ratio"),
            sample_aspect_ratio=stream.get("sample_aspect_ratio"),
            pix_fmt=stream.get("pix_fmt"),
            level=stream.get("level"),
            color_range=stream.get("color_range"),
            color_space=stream.get("color_space"),
            color_transfer=stream.get("color_transfer"),
            color_primaries=stream.get("color_primaries"),
            field_order=stream.get("field_order"),
            avg_frame_rate=stream.get("avg_frame_rate"),
            r_frame_rate=stream.get("r_frame_rate"),
            bit_rate=int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else None,
            bits_per_raw_sample=int(stream.get("bits_per_raw_sample", 0))
            if stream.get("bits_per_raw_sample")
            else None,
        )

    def _parse_audio_stream(self, stream: Dict[str, Any]) -> AudioStream:
        """Parse audio stream data."""
        tags = stream.get("tags", {})
        return AudioStream(
            index=stream.get("index", 0),
            codec_name=stream.get("codec_name", "unknown"),
            codec_long_name=stream.get("codec_long_name", "Unknown"),
            profile=stream.get("profile"),
            sample_rate=int(stream.get("sample_rate", 0))
            if stream.get("sample_rate")
            else None,
            channels=stream.get("channels", 2),
            channel_layout=stream.get("channel_layout"),
            bit_rate=int(stream.get("bit_rate", 0)) if stream.get("bit_rate") else None,
            bits_per_sample=stream.get("bits_per_sample"),
            language=tags.get("language"),
            title=tags.get("title"),
        )

    def _parse_subtitle_stream(self, stream: Dict[str, Any]) -> SubtitleStream:
        """Parse subtitle stream data."""
        tags = stream.get("tags", {})
        disposition = stream.get("disposition", {})
        return SubtitleStream(
            index=stream.get("index", 0),
            codec_name=stream.get("codec_name", "unknown"),
            codec_long_name=stream.get("codec_long_name", "Unknown"),
            language=tags.get("language"),
            title=tags.get("title"),
            forced=disposition.get("forced", 0) == 1,
            default=disposition.get("default", 0) == 1,
        )
