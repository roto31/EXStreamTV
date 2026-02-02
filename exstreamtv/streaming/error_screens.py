"""
Error Screen Generator for graceful stream failure handling.

Ported from dizqueTV's spawnError/spawnOffline with enhancements:
- Multiple visual modes: text, static, test pattern, custom image
- Multiple audio modes: silent, sine wave, white noise
- Configurable resolution and duration
- FFmpeg command builder for error streams

This provides a graceful user experience during stream failures
by displaying informative error screens instead of broken streams.
"""

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


class ErrorVisualMode(str, Enum):
    """Visual modes for error screens."""
    
    TEXT = "text"  # Text message on solid background
    STATIC = "static"  # TV static noise
    TEST_PATTERN = "test_pattern"  # Color bars test pattern
    BLACK = "black"  # Solid black screen
    CUSTOM_IMAGE = "custom_image"  # Custom offline image
    SLATE = "slate"  # Professional slate with channel info


class ErrorAudioMode(str, Enum):
    """Audio modes for error screens."""
    
    SILENT = "silent"  # No audio
    SINE = "sine"  # 1kHz test tone
    WHITE_NOISE = "white_noise"  # White noise
    BEEP = "beep"  # Periodic beep
    MUSIC_HOLD = "music_hold"  # Hold music (requires file)


@dataclass
class ErrorScreenConfig:
    """Configuration for error screen generation."""
    
    # Visual settings
    visual_mode: ErrorVisualMode = ErrorVisualMode.TEXT
    background_color: str = "#1a1a2e"  # Dark blue-gray
    text_color: str = "#ffffff"
    font_size: int = 48
    custom_image_path: Optional[str] = None
    
    # Audio settings
    audio_mode: ErrorAudioMode = ErrorAudioMode.SILENT
    audio_volume: float = 0.3
    hold_music_path: Optional[str] = None
    
    # Output settings
    width: int = 1920
    height: int = 1080
    framerate: int = 30
    video_bitrate: str = "2M"
    audio_bitrate: str = "128k"
    
    # Duration
    duration_seconds: Optional[float] = None  # None = infinite
    loop: bool = True
    
    # FFmpeg settings
    ffmpeg_path: str = "ffmpeg"


@dataclass
class ErrorScreenMessage:
    """Message content for error screens."""
    
    title: str = "Technical Difficulties"
    subtitle: str = "We'll be right back"
    channel_name: Optional[str] = None
    channel_number: Optional[int] = None
    error_code: Optional[str] = None
    timestamp: bool = True  # Show current time


class ErrorScreenGenerator:
    """
    Generates error/offline screens with FFmpeg.
    
    Features:
    - Multiple visual styles
    - Customizable text messages
    - Audio options
    - MPEG-TS output
    
    Usage:
        generator = ErrorScreenGenerator()
        
        async for chunk in generator.generate_error_stream(
            message=ErrorScreenMessage(title="Please Stand By"),
            config=ErrorScreenConfig(visual_mode=ErrorVisualMode.SLATE),
            duration=30,
        ):
            yield chunk
    """
    
    # Test pattern colors (SMPTE color bars)
    SMPTE_COLORS = [
        "#C0C0C0",  # Gray
        "#FFFF00",  # Yellow
        "#00FFFF",  # Cyan
        "#00FF00",  # Green
        "#FF00FF",  # Magenta
        "#FF0000",  # Red
        "#0000FF",  # Blue
    ]
    
    def __init__(self, config: Optional[ErrorScreenConfig] = None):
        """
        Initialize error screen generator.
        
        Args:
            config: Default configuration
        """
        self._config = config or ErrorScreenConfig()
        
        # Validate FFmpeg
        if not shutil.which(self._config.ffmpeg_path):
            logger.warning(f"FFmpeg not found at {self._config.ffmpeg_path}")
    
    def build_ffmpeg_command(
        self,
        message: ErrorScreenMessage,
        config: Optional[ErrorScreenConfig] = None,
        duration: Optional[float] = None,
    ) -> list[str]:
        """
        Build FFmpeg command for error screen generation.
        
        Args:
            message: Message content
            config: Configuration (uses default if not provided)
            duration: Override duration in seconds
            
        Returns:
            FFmpeg command as list of arguments
        """
        cfg = config or self._config
        dur = duration or cfg.duration_seconds
        
        cmd = [cfg.ffmpeg_path, "-y"]
        
        # Global options
        cmd.extend(["-loglevel", "warning"])
        
        # Build video source based on mode
        video_filter = self._build_video_source(cfg, message)
        
        # Input source (depends on mode)
        if cfg.visual_mode == ErrorVisualMode.CUSTOM_IMAGE and cfg.custom_image_path:
            # Use image as input
            cmd.extend([
                "-loop", "1",
                "-i", cfg.custom_image_path,
            ])
            if dur:
                cmd.extend(["-t", str(dur)])
        elif cfg.visual_mode == ErrorVisualMode.STATIC:
            # Generate noise
            cmd.extend([
                "-f", "lavfi",
                "-i", f"nullsrc=s={cfg.width}x{cfg.height}:r={cfg.framerate},geq=random(1)*255:128:128",
            ])
            if dur:
                cmd.extend(["-t", str(dur)])
        else:
            # Generate color/pattern with lavfi
            cmd.extend([
                "-f", "lavfi",
                "-i", video_filter,
            ])
            if dur:
                cmd.extend(["-t", str(dur)])
        
        # Audio source based on mode
        audio_filter = self._build_audio_source(cfg)
        if cfg.audio_mode == ErrorAudioMode.MUSIC_HOLD and cfg.hold_music_path:
            cmd.extend(["-stream_loop", "-1", "-i", cfg.hold_music_path])
        else:
            cmd.extend(["-f", "lavfi", "-i", audio_filter])
        
        # Video encoding
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-b:v", cfg.video_bitrate,
            "-pix_fmt", "yuv420p",
            "-g", str(cfg.framerate * 2),  # GOP size
        ])
        
        # Add text overlay if using text modes
        if cfg.visual_mode in (ErrorVisualMode.TEXT, ErrorVisualMode.SLATE, ErrorVisualMode.BLACK):
            text_filter = self._build_text_overlay(message, cfg)
            if text_filter:
                cmd.extend(["-vf", text_filter])
        
        # Audio encoding
        if cfg.audio_mode == ErrorAudioMode.SILENT:
            cmd.extend(["-an"])  # No audio
        else:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", cfg.audio_bitrate,
                "-ar", "48000",
                "-ac", "2",
            ])
        
        # Output format
        cmd.extend([
            "-f", "mpegts",
            "-muxrate", "4M",
            "-pcr_period", "20",
            "-flush_packets", "1",
            "-"
        ])
        
        return cmd
    
    def _build_video_source(
        self,
        cfg: ErrorScreenConfig,
        message: ErrorScreenMessage,
    ) -> str:
        """Build lavfi video source filter."""
        w, h, fps = cfg.width, cfg.height, cfg.framerate
        
        if cfg.visual_mode == ErrorVisualMode.TEST_PATTERN:
            # SMPTE color bars
            return f"smptebars=s={w}x{h}:r={fps}"
        
        elif cfg.visual_mode == ErrorVisualMode.STATIC:
            # Handled separately with geq
            return f"nullsrc=s={w}x{h}:r={fps}"
        
        elif cfg.visual_mode == ErrorVisualMode.BLACK:
            return f"color=c=black:s={w}x{h}:r={fps}"
        
        elif cfg.visual_mode == ErrorVisualMode.SLATE:
            # Professional slate - dark gray background
            return f"color=c=#2d2d2d:s={w}x{h}:r={fps}"
        
        else:  # TEXT mode or fallback
            # Use configured background color
            bg = cfg.background_color.replace("#", "0x")
            return f"color=c={bg}:s={w}x{h}:r={fps}"
    
    def _build_text_overlay(
        self,
        message: ErrorScreenMessage,
        cfg: ErrorScreenConfig,
    ) -> str:
        """Build drawtext filter for text overlay."""
        filters = []
        text_color = cfg.text_color
        
        # Title text (centered, large)
        title = self._escape_text(message.title)
        filters.append(
            f"drawtext=text='{title}':"
            f"fontcolor={text_color}:fontsize={cfg.font_size}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-{cfg.font_size}"
        )
        
        # Subtitle (below title)
        if message.subtitle:
            subtitle = self._escape_text(message.subtitle)
            filters.append(
                f"drawtext=text='{subtitle}':"
                f"fontcolor={text_color}:fontsize={cfg.font_size // 2}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2+{cfg.font_size // 2}"
            )
        
        # Channel info (top left)
        if message.channel_name:
            ch_text = f"Channel {message.channel_number}: {message.channel_name}" if message.channel_number else message.channel_name
            ch_text = self._escape_text(ch_text)
            filters.append(
                f"drawtext=text='{ch_text}':"
                f"fontcolor={text_color}:fontsize={cfg.font_size // 3}:"
                f"x=40:y=40"
            )
        
        # Timestamp (bottom right)
        if message.timestamp:
            filters.append(
                f"drawtext=text='%{{localtime\\:%H\\:%M\\:%S}}':"
                f"fontcolor={text_color}:fontsize={cfg.font_size // 3}:"
                f"x=w-text_w-40:y=h-text_h-40"
            )
        
        # Error code (bottom left)
        if message.error_code:
            err_text = self._escape_text(f"Error: {message.error_code}")
            filters.append(
                f"drawtext=text='{err_text}':"
                f"fontcolor=#ff6b6b:fontsize={cfg.font_size // 4}:"
                f"x=40:y=h-text_h-40"
            )
        
        return ",".join(filters)
    
    def _build_audio_source(self, cfg: ErrorScreenConfig) -> str:
        """Build lavfi audio source filter."""
        if cfg.audio_mode == ErrorAudioMode.SILENT:
            return "anullsrc=r=48000:cl=stereo"
        
        elif cfg.audio_mode == ErrorAudioMode.SINE:
            # 1kHz test tone
            vol = cfg.audio_volume
            return f"sine=f=1000:r=48000,volume={vol}"
        
        elif cfg.audio_mode == ErrorAudioMode.WHITE_NOISE:
            vol = cfg.audio_volume * 0.3  # Lower for noise
            return f"anoisesrc=r=48000:a={vol}"
        
        elif cfg.audio_mode == ErrorAudioMode.BEEP:
            # Periodic beep (1 second on, 2 seconds off)
            vol = cfg.audio_volume
            return f"sine=f=800:r=48000,agate=threshold=0.5,volume={vol}"
        
        else:
            return "anullsrc=r=48000:cl=stereo"
    
    def _escape_text(self, text: str) -> str:
        """Escape text for FFmpeg drawtext filter."""
        # Escape special characters
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace("%", "\\%")
        return text
    
    async def generate_error_stream(
        self,
        message: Optional[ErrorScreenMessage] = None,
        config: Optional[ErrorScreenConfig] = None,
        duration: Optional[float] = None,
        buffer_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        """
        Generate error screen stream.
        
        Args:
            message: Message content
            config: Configuration
            duration: Duration in seconds
            buffer_size: Read buffer size
            
        Yields:
            MPEG-TS data chunks
        """
        msg = message or ErrorScreenMessage()
        cfg = config or self._config
        
        cmd = self.build_ffmpeg_command(msg, cfg, duration)
        
        logger.info(f"Generating error screen: {msg.title}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        try:
            while True:
                chunk = await process.stdout.read(buffer_size)
                if not chunk:
                    break
                yield chunk
                
        except asyncio.CancelledError:
            logger.info("Error screen generation cancelled")
            process.terminate()
            raise
            
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            
            if process.returncode and process.returncode != 0:
                stderr = await process.stderr.read()
                if stderr:
                    logger.warning(f"Error screen FFmpeg error: {stderr.decode()[:500]}")
    
    async def generate_offline_stream(
        self,
        channel_name: Optional[str] = None,
        channel_number: Optional[int] = None,
        duration: Optional[float] = None,
        offline_image_path: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        Generate offline screen stream.
        
        Args:
            channel_name: Channel name to display
            channel_number: Channel number
            duration: Duration in seconds
            offline_image_path: Path to custom offline image
            
        Yields:
            MPEG-TS data chunks
        """
        message = ErrorScreenMessage(
            title="Off Air",
            subtitle="This channel is currently offline",
            channel_name=channel_name,
            channel_number=channel_number,
        )
        
        config = ErrorScreenConfig(
            visual_mode=ErrorVisualMode.CUSTOM_IMAGE if offline_image_path else ErrorVisualMode.SLATE,
            custom_image_path=offline_image_path,
            audio_mode=ErrorAudioMode.SILENT,
            background_color="#000000",
        )
        
        async for chunk in self.generate_error_stream(message, config, duration):
            yield chunk
    
    async def generate_buffering_stream(
        self,
        channel_name: Optional[str] = None,
        duration: float = 10.0,
    ) -> AsyncIterator[bytes]:
        """
        Generate buffering/loading screen.
        
        Args:
            channel_name: Channel name
            duration: Duration in seconds
            
        Yields:
            MPEG-TS data chunks
        """
        message = ErrorScreenMessage(
            title="Loading...",
            subtitle="Please wait",
            channel_name=channel_name,
        )
        
        config = ErrorScreenConfig(
            visual_mode=ErrorVisualMode.TEXT,
            background_color="#1a1a2e",
            audio_mode=ErrorAudioMode.SILENT,
        )
        
        async for chunk in self.generate_error_stream(message, config, duration):
            yield chunk
    
    async def generate_test_pattern(
        self,
        duration: float = 30.0,
        with_tone: bool = True,
    ) -> AsyncIterator[bytes]:
        """
        Generate test pattern with optional tone.
        
        Args:
            duration: Duration in seconds
            with_tone: Include 1kHz test tone
            
        Yields:
            MPEG-TS data chunks
        """
        message = ErrorScreenMessage(
            title="",
            subtitle="",
            timestamp=False,
        )
        
        config = ErrorScreenConfig(
            visual_mode=ErrorVisualMode.TEST_PATTERN,
            audio_mode=ErrorAudioMode.SINE if with_tone else ErrorAudioMode.SILENT,
            audio_volume=0.2,
        )
        
        async for chunk in self.generate_error_stream(message, config, duration):
            yield chunk


# Global error screen generator instance
_error_generator: Optional[ErrorScreenGenerator] = None


def get_error_screen_generator(
    config: Optional[ErrorScreenConfig] = None,
) -> ErrorScreenGenerator:
    """Get the global ErrorScreenGenerator instance."""
    global _error_generator
    if _error_generator is None:
        _error_generator = ErrorScreenGenerator(config)
    return _error_generator


async def generate_quick_error_stream(
    title: str = "Technical Difficulties",
    subtitle: str = "We'll be right back",
    duration: float = 30.0,
) -> AsyncIterator[bytes]:
    """
    Quick helper to generate an error stream.
    
    Args:
        title: Error title
        subtitle: Error subtitle
        duration: Duration in seconds
        
    Yields:
        MPEG-TS data chunks
    """
    generator = get_error_screen_generator()
    message = ErrorScreenMessage(title=title, subtitle=subtitle)
    
    async for chunk in generator.generate_error_stream(message, duration=duration):
        yield chunk
