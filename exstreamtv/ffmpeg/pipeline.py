"""
FFmpeg Pipeline

Main pipeline coordinator for building and executing FFmpeg commands.
Ported from ErsatzTV with StreamTV bug fixes preserved.
"""

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from exstreamtv.config import get_config
from exstreamtv.ffmpeg.capabilities import HardwareCapabilities, detect_hardware_acceleration

logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    """Information about an input stream."""
    path: str
    duration_seconds: float = 0
    width: int = 0
    height: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    framerate: float = 0
    is_online: bool = False  # True for YouTube/Archive.org streams


@dataclass
class OutputSettings:
    """Output encoding settings."""
    resolution: tuple[int, int] = (1920, 1080)
    video_codec: str = "h264"
    video_bitrate: str = "4000k"
    audio_codec: str = "aac"
    audio_bitrate: str = "128k"
    framerate: int = 30
    scaling_mode: str = "pad"  # pad, stretch, crop
    pad_color: str = "black"
    normalize_audio: bool = True


@dataclass
class FFmpegPipeline:
    """
    FFmpeg command pipeline builder.
    
    Builds complete FFmpeg commands with:
    - Hardware acceleration
    - Input handling (files, URLs, streams)
    - Filter chains
    - Output encoding
    - Bug fixes from StreamTV
    """
    
    capabilities: HardwareCapabilities = field(default_factory=detect_hardware_acceleration)
    
    # StreamTV bug fix flags
    use_bitstream_filters: bool = True  # Fix H.264 PPS/SPS issues
    use_realtime_flag: bool = True  # -re for pre-recorded content
    use_error_tolerance: bool = True  # fflags for corrupt streams
    
    def build_command(
        self,
        input_source: str | StreamInfo,
        output_settings: Optional[OutputSettings] = None,
        output_path: str = "pipe:1",
        output_format: str = "mpegts",
    ) -> list[str]:
        """
        Build a complete FFmpeg command.
        
        Args:
            input_source: Input file path, URL, or StreamInfo
            output_settings: Encoding settings (uses defaults if None)
            output_path: Output path or pipe:1 for stdout
            output_format: Output format (mpegts, hls, etc.)
            
        Returns:
            FFmpeg command as list of arguments
        """
        config = get_config()
        settings = output_settings or OutputSettings()
        
        cmd = [config.ffmpeg.path]
        
        # Hide banner
        cmd.extend(["-hide_banner", "-loglevel", "warning"])
        
        # Determine input info
        if isinstance(input_source, StreamInfo):
            input_path = input_source.path
            is_online = input_source.is_online
            video_codec = input_source.video_codec
        else:
            input_path = input_source
            is_online = self._is_online_source(input_path)
            video_codec = ""
        
        # Bug Fix: Error tolerance for corrupt streams
        if self.use_error_tolerance:
            cmd.extend([
                "-fflags", "+genpts+discardcorrupt+igndts",
                "-err_detect", "ignore_err",
            ])
        
        # Bug Fix: Real-time flag for pre-recorded content
        # Prevents transcoding faster than real-time
        if self.use_realtime_flag and not is_online:
            cmd.append("-re")
        
        # Timeouts for online sources
        if is_online:
            timeout = config.ffmpeg.timeouts.youtube if "youtube" in input_path.lower() else config.ffmpeg.timeouts.archive_org
            cmd.extend([
                "-timeout", str(timeout * 1000000),  # microseconds
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
            ])
        
        # Hardware acceleration for decoding
        hw_accel = self._get_hardware_accel_input_flags(video_codec)
        cmd.extend(hw_accel)
        
        # Input
        cmd.extend(["-i", input_path])
        
        # Build filter chain
        filters = self._build_filter_chain(settings)
        if filters:
            cmd.extend(["-vf", filters])
        
        # Video encoding
        encoder = self.capabilities.get_encoder(settings.video_codec)
        cmd.extend(["-c:v", encoder])
        
        # Bug Fix: Bitstream filters for H.264
        if self.use_bitstream_filters and settings.video_codec == "h264":
            cmd.extend(["-bsf:v", "h264_mp4toannexb,dump_extra"])
        
        # Video bitrate
        cmd.extend(["-b:v", settings.video_bitrate])
        
        # Framerate
        cmd.extend(["-r", str(settings.framerate)])
        
        # Audio encoding
        cmd.extend(["-c:a", settings.audio_codec])
        cmd.extend(["-b:a", settings.audio_bitrate])
        cmd.extend(["-ar", "48000"])
        cmd.extend(["-ac", "2"])
        
        # Audio normalization
        if settings.normalize_audio:
            cmd.extend(["-af", "loudnorm=I=-24:TP=-2:LRA=7"])
        
        # Output format
        cmd.extend(["-f", output_format])
        
        # MPEG-TS specific flags
        if output_format == "mpegts":
            cmd.extend([
                "-mpegts_flags", "resend_headers",
                "-pcr_period", "40",
            ])
        
        # Output
        cmd.append(output_path)
        
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")
        return cmd
    
    def _is_online_source(self, path: str) -> bool:
        """Check if source is an online stream."""
        online_indicators = [
            "youtube.com", "youtu.be",
            "archive.org",
            "http://", "https://",
            "rtmp://", "rtsp://",
        ]
        path_lower = path.lower()
        return any(ind in path_lower for ind in online_indicators)
    
    def _get_hardware_accel_input_flags(self, video_codec: str) -> list[str]:
        """Get hardware acceleration flags for input/decoding."""
        from exstreamtv.ffmpeg.capabilities import HardwareAccelType
        
        method = self.capabilities.preferred_method
        
        if method == HardwareAccelType.NONE:
            return []
        
        # Bug Fix: VideoToolbox only supports certain codecs
        # MPEG-4 and some other codecs need software decoding
        mpeg4_codecs = ["mpeg4", "msmpeg4v3", "msmpeg4v2", "msmpeg4"]
        if method == HardwareAccelType.VIDEOTOOLBOX and video_codec in mpeg4_codecs:
            logger.debug(f"VideoToolbox doesn't support {video_codec}, using software")
            return []
        
        flags = []
        if method == HardwareAccelType.VIDEOTOOLBOX:
            flags = ["-hwaccel", "videotoolbox"]
        elif method == HardwareAccelType.NVENC:
            flags = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        elif method == HardwareAccelType.QSV:
            flags = ["-hwaccel", "qsv", "-hwaccel_output_format", "qsv"]
        elif method == HardwareAccelType.VAAPI:
            flags = ["-hwaccel", "vaapi", "-hwaccel_output_format", "vaapi"]
        elif method == HardwareAccelType.AMF:
            flags = ["-hwaccel", "d3d11va"]
        
        return flags
    
    def _build_filter_chain(self, settings: OutputSettings) -> str:
        """Build video filter chain."""
        filters = []
        
        width, height = settings.resolution
        
        # Scaling with padding
        if settings.scaling_mode == "pad":
            filters.append(
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={settings.pad_color}"
            )
        elif settings.scaling_mode == "stretch":
            filters.append(f"scale={width}:{height}")
        elif settings.scaling_mode == "crop":
            filters.append(
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )
        
        # Format conversion for compatibility
        filters.append("format=yuv420p")
        
        return ",".join(filters)
    
    def probe(self, input_path: str) -> Optional[StreamInfo]:
        """
        Probe input file/stream for stream information.
        
        Args:
            input_path: Path to input file or URL
            
        Returns:
            StreamInfo or None if probe failed
        """
        config = get_config()
        
        try:
            cmd = [
                config.ffmpeg.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                input_path,
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.warning(f"ffprobe failed for {input_path}")
                return None
            
            import json
            data = json.loads(result.stdout)
            
            info = StreamInfo(
                path=input_path,
                is_online=self._is_online_source(input_path),
            )
            
            # Get format duration
            if "format" in data and "duration" in data["format"]:
                info.duration_seconds = float(data["format"]["duration"])
            
            # Get video stream info
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    info.width = stream.get("width", 0)
                    info.height = stream.get("height", 0)
                    info.video_codec = stream.get("codec_name", "")
                    # Parse framerate
                    fps_str = stream.get("r_frame_rate", "30/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        info.framerate = float(num) / float(den)
                elif stream.get("codec_type") == "audio":
                    info.audio_codec = stream.get("codec_name", "")
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to probe {input_path}: {e}")
            return None
