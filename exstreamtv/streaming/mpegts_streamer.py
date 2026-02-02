"""
MPEG-TS Streamer with FFmpeg integration.

Ported from StreamTV with all critical bug fixes preserved:
- Bitstream filters for H.264 PPS/SPS issues
- Real-time flag (-re) for pre-recorded content
- Error tolerance flags for corrupt streams
- VideoToolbox codec restrictions
- Extended timeouts for online sources
"""

import asyncio
import logging
import platform
import shutil
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from exstreamtv.config import get_config

logger = logging.getLogger(__name__)


class StreamSource(str, Enum):
    """Stream source types."""

    YOUTUBE = "youtube"
    ARCHIVE_ORG = "archive_org"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass
class CodecInfo:
    """Information about input stream codecs."""

    video_codec: str = "unknown"
    audio_codec: str = "unknown"
    width: int = 0
    height: int = 0
    framerate: float = 0.0
    duration: float = 0.0  # Duration in seconds (from probe)
    can_copy_video: bool = False
    can_copy_audio: bool = False
    is_hevc: bool = False  # True if HEVC/H.265 (needs different bitstream filter)


class MPEGTSStreamer:
    """
    MPEG-TS streaming via FFmpeg.
    
    Handles transcoding and stream copy with smart codec detection.
    Includes all StreamTV bug fixes for reliable streaming.
    """

    # H.264-compatible codecs that can be stream-copied
    H264_COMPATIBLE_CODECS = {"h264", "avc", "avc1"}
    
    # HEVC/H.265 codecs that can be stream-copied (with hevc_mp4toannexb filter)
    HEVC_COMPATIBLE_CODECS = {"hevc", "h265", "hev1", "hvc1"}
    
    # Audio codecs compatible with MPEG-TS
    AUDIO_COMPATIBLE_CODECS = {"aac", "mp3", "mp2", "ac3", "eac3"}
    
    # MPEG-4 codecs that don't support VideoToolbox hardware acceleration
    MPEG4_CODECS = {"mpeg4", "msmpeg4v3", "msmpeg4v2", "msmpeg4"}

    def __init__(
        self,
        ffmpeg_path: str | None = None,
        ffprobe_path: str | None = None,
        hardware_acceleration: str = "auto",
        channel_profile: str | None = None,
    ):
        """
        Initialize MPEG-TS streamer.
        
        Args:
            ffmpeg_path: Path to FFmpeg binary.
            ffprobe_path: Path to ffprobe binary.
            hardware_acceleration: HW accel mode (auto, videotoolbox, nvenc, qsv, none).
            channel_profile: Per-channel transcode profile (nvidia, intel, cpu).
        """
        config = get_config()
        
        self._ffmpeg_path = ffmpeg_path or config.ffmpeg.path
        self._ffprobe_path = ffprobe_path or config.ffmpeg.ffprobe_path
        self._hardware_acceleration = hardware_acceleration
        self._channel_profile = channel_profile
        self._processes: dict[str, subprocess.Popen] = {}
        
        # Validate FFmpeg exists
        # Validate FFmpeg exists
        if not shutil.which(self._ffmpeg_path):
            logger.warning(f"FFmpeg not found at {self._ffmpeg_path}")

    async def probe_stream(self, input_url: str) -> CodecInfo:
        """
        Probe input stream for codec information.
        
        Args:
            input_url: Input file or URL.
            
        Returns:
            CodecInfo with detected codecs.
        """
        try:
            cmd = [
                self._ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                input_url,
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=30)
            
            import json
            data = json.loads(stdout.decode("utf-8", errors="replace"))
            
            info = CodecInfo()
            
            # Extract duration from format metadata
            format_data = data.get("format", {})
            duration_str = format_data.get("duration")
            if duration_str:
                try:
                    info.duration = float(duration_str)
                except (ValueError, TypeError):
                    pass
            
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    info.video_codec = stream.get("codec_name", "unknown")
                    info.width = stream.get("width", 0)
                    info.height = stream.get("height", 0)
                    
                    fps_str = stream.get("r_frame_rate", "30/1")
                    if "/" in fps_str:
                        num, den = fps_str.split("/")
                        info.framerate = float(num) / float(den) if float(den) != 0 else 30.0
                    
                    # Check if H.264 or HEVC - both can be stream-copied with appropriate filters
                    is_h264 = info.video_codec in self.H264_COMPATIBLE_CODECS
                    is_hevc = info.video_codec in self.HEVC_COMPATIBLE_CODECS
                    info.can_copy_video = is_h264 or is_hevc
                    info.is_hevc = is_hevc
                    
                    # Also try to get duration from stream if not in format
                    if info.duration == 0 and stream.get("duration"):
                        try:
                            info.duration = float(stream.get("duration"))
                        except (ValueError, TypeError):
                            pass
                    
                elif stream.get("codec_type") == "audio":
                    info.audio_codec = stream.get("codec_name", "unknown")
                    info.can_copy_audio = info.audio_codec in self.AUDIO_COMPATIBLE_CODECS
            
            logger.debug(
                f"Probed stream: video={info.video_codec}, audio={info.audio_codec}, "
                f"duration={info.duration:.1f}s, copy_video={info.can_copy_video}, copy_audio={info.can_copy_audio}"
            )
            
            return info
            
        except Exception as e:
            logger.warning(f"Failed to probe stream: {e}")
            return CodecInfo()

    def build_ffmpeg_command(
        self,
        input_url: str,
        codec_info: CodecInfo | None = None,
        source: StreamSource = StreamSource.UNKNOWN,
        original_url: str | None = None,
        seek_offset: float = 0.0,
    ) -> list[str]:
        """
        Build FFmpeg command for MPEG-TS transcoding with smart codec selection.
        
        Preserves all StreamTV bug fixes:
        - Bitstream filters for H.264 issues
        - -re flag for pre-recorded content
        - Error tolerance flags
        - Hardware acceleration restrictions
        
        Args:
            input_url: Input file or URL (may be CDN URL).
            codec_info: Pre-probed codec information.
            source: Stream source type for optimizations.
            original_url: Original source URL (e.g., YouTube URL for CDN).
            seek_offset: Seek into the file by this many seconds (ErsatzTV-style).
            
        Returns:
            FFmpeg command as list of arguments.
        """
        config = get_config()
        
        cmd = [self._ffmpeg_path]
        
        # ErsatzTV-style: Seek to the correct position in the stream
        # This is critical for continuous streaming to match the EPG
        # Store for use after input options
        self._pending_seek_offset = seek_offset
        
        # Determine codec capabilities
        can_copy_video = codec_info.can_copy_video if codec_info else False
        can_copy_audio = codec_info.can_copy_audio if codec_info else False
        video_codec = codec_info.video_codec if codec_info else "unknown"
        
        # Detect source type from URL if not provided
        src_youtube = (
            source == StreamSource.YOUTUBE
            or "youtube.com" in input_url.lower()
            or "youtu.be" in input_url.lower()
            or "googlevideo.com" in input_url.lower()
        )
        src_archive = (
            source == StreamSource.ARCHIVE_ORG
            or "archive.org" in input_url.lower()
        )
        src_plex = (
            source == StreamSource.PLEX
            or "/library/metadata/" in input_url
            or "plex" in input_url.lower()
        )
        
        # Determine hardware acceleration
        chosen_hwaccel, chosen_encoder = self._get_hardware_settings(
            source, src_youtube, src_archive, src_plex
        )
        
        # Check for MPEG-4 (VideoToolbox doesn't support it)
        is_mpeg4 = video_codec in self.MPEG4_CODECS
        use_hwaccel = chosen_hwaccel and not can_copy_video and not is_mpeg4
        
        # Log encoding strategy
        # Check if HEVC for better log messages
        is_hevc_input = video_codec in self.HEVC_COMPATIBLE_CODECS
        codec_display = "HEVC/H.265" if is_hevc_input else "H.264"
        if can_copy_video and can_copy_audio:
            logger.info(f"Smart copy mode: Input already {codec_display}/AAC - zero transcoding! 🚀")
        elif can_copy_video:
            logger.info(f"Smart copy mode: Video {codec_display} - copying video, transcoding audio")
        elif is_mpeg4:
            logger.info(f"Software transcoding: MPEG-4 detected ({video_codec})")
        elif use_hwaccel:
            logger.info(f"Hardware-accelerated transcoding: Using {chosen_hwaccel} 🔥")
        else:
            logger.info("Software transcoding: Converting to H.264/AAC")
        
        # Global options
        log_level = getattr(config.ffmpeg, 'log_level', 'warning')
        cmd.extend(["-loglevel", log_level])
        
        # === INPUT OPTIONS (before -i) ===
        
        # Hardware acceleration for decoding
        if is_mpeg4:
            cmd.extend(["-hwaccel", "none"])
            logger.debug(f"Hardware acceleration disabled for MPEG-4: {video_codec}")
        elif use_hwaccel and not can_copy_video:
            # Use hardware decoder but keep output in system memory for encoder compatibility
            cmd.extend(["-hwaccel", chosen_hwaccel])
            logger.debug(f"Hardware decoding enabled: {chosen_hwaccel}")
        
        # HTTP input options
        if input_url.startswith("http"):
            self._add_http_input_options(
                cmd, input_url, src_archive, src_plex, src_youtube
            )
        
        # === ERROR TOLERANCE FLAGS (critical bug fix) ===
        is_prerecorded = src_archive or src_youtube
        is_piped = input_url.startswith("pipe:")
        
        if is_mpeg4:
            # MPEG-4/AVI often have timing issues
            cmd.extend([
                "-fflags", "+genpts+discardcorrupt+igndts",
                "-err_detect", "ignore_err",
                "-flags", "+low_delay",
                "-strict", "experimental",
                "-probesize", "5000000",
                "-analyzeduration", "5000000",
            ])
            
            # BUG FIX: -re for pre-recorded content (prevents buffer underruns)
            if is_prerecorded and not is_piped:
                cmd.append("-re")
                logger.debug("Using -re for MPEG-4 file content")
        else:
            cmd.extend([
                "-fflags", "+genpts+discardcorrupt+fastseek",
                "-flags", "+low_delay",
                "-strict", "experimental",
                "-probesize", "1000000",
                "-analyzeduration", "2000000",
            ])
            
            # BUG FIX: -re for pre-recorded content
            if is_prerecorded and not is_piped:
                cmd.append("-re")
                logger.debug("Using -re for pre-recorded file content")
        
        # ErsatzTV-style: Seek using INPUT seeking (-ss before -i)
        # Input seeking is FAST because it seeks to nearest keyframe before decoding
        # This is critical for continuous streaming to avoid long startup delays
        seek_offset_to_use = getattr(self, '_pending_seek_offset', 0)
        if seek_offset_to_use > 0:
            # Use input seeking (fast seek to keyframe)
            cmd.extend(["-ss", str(int(seek_offset_to_use))])
            logger.info(f"Seeking to {seek_offset_to_use:.1f}s into the stream (input seek - fast mode)")
            
            # #region agent log
            import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H6","location":"mpegts_streamer.py:build_command:seek","message":"FFmpeg input seek applied","data":{"seek_offset":seek_offset_to_use,"input_url":input_url[:80] if len(input_url)>80 else input_url},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
            # #endregion
            
            self._pending_seek_offset = 0  # Reset
        
        # Input URL
        cmd.extend(["-i", input_url])
        
        # === OUTPUT OPTIONS (after -i) ===
        
        # Threads
        threads = config.ffmpeg.threads
        if threads > 0 and not (can_copy_video and can_copy_audio):
            cmd.extend(["-threads", str(threads)])
        
        # Video codec selection
        is_hevc = codec_info.is_hevc if codec_info else False
        if can_copy_video:
            # BUG FIX: Bitstream filters for H.264/HEVC copy mode
            # HEVC requires hevc_mp4toannexb, H.264 requires h264_mp4toannexb
            if is_hevc:
                bsf_filter = "hevc_mp4toannexb,dump_extra"
                codec_name = "HEVC/H.265"
            else:
                bsf_filter = "h264_mp4toannexb,dump_extra"
                codec_name = "H.264"
            cmd.extend([
                "-c:v", "copy",
                "-bsf:v", bsf_filter,
            ])
            logger.debug(f"Video: Copy mode with {codec_name} bitstream filters")
        elif use_hwaccel:
            hw_encoder = self._get_hw_encoder(chosen_hwaccel, chosen_encoder)
            cmd.extend([
                "-c:v", hw_encoder,
                "-b:v", "6M",
                "-maxrate", "6M",
                "-bufsize", "12M",
                "-profile:v", "high",
                "-realtime", "1",
                "-allow_sw", "1",  # Allow software fallback if hardware encoder is busy
                "-pix_fmt", "yuv420p",
                "-bsf:v", "dump_extra",
            ])
            logger.debug(f"Video: Hardware encoding with {hw_encoder} (software fallback enabled)")
        else:
            # Software encoding
            preset = "ultrafast" if is_mpeg4 else "veryfast"
            cmd.extend([
                "-c:v", "libx264",
                "-preset", preset,
                "-crf", "23",
                "-maxrate", "6M",
                "-bufsize", "12M",
                "-profile:v", "high",
                "-level", "4.1",
                "-pix_fmt", "yuv420p",
                "-g", "50",
                "-bsf:v", "dump_extra",
            ])
            logger.debug(f"Video: Software encoding with preset={preset}")
        
        # Audio codec selection
        # NOTE: For hardware video encoding with audio copy, we may override this later
        # with audio transcoding + aresample for proper A/V sync
        if can_copy_audio and not use_hwaccel:
            # Only copy audio if NOT using hardware video encoding
            # Hardware encoding needs audio transcoding for proper sync
            cmd.extend(["-c:a", "copy"])
            logger.debug("Audio: Copy mode")
        elif can_copy_audio and use_hwaccel:
            # Hardware video encoding requires audio transcoding for sync
            cmd.extend([
                "-af", "aresample=async=1:min_hard_comp=0.100000:first_pts=0",
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
            ])
            logger.debug("Audio: Transcoding with aresample for hwaccel sync")
        else:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "192k",
                "-ar", "48000",
                "-ac", "2",
            ])
            logger.debug("Audio: Transcoding to AAC")
        
        # A/V sync parameters (critical for preventing audio ahead of video)
        # ErsatzTV-style: Always ensure proper timestamp handling
        sync_mode = "none"
        if can_copy_video and can_copy_audio:
            # Both copy = need to generate proper timestamps for MPEG-TS
            cmd.extend([
                "-vsync", "passthrough",
                "-copyts",              # Preserve original timestamps
                "-start_at_zero",       # Normalize to start at 0
            ])
            sync_mode = "copy_both"
            logger.debug("Added A/V sync flags (copy both - passthrough with copyts)")
        elif not can_copy_video and can_copy_audio and not use_hwaccel:
            # Software video transcode + audio copy = needs sync
            cmd.extend([
                "-async", "1",      # Audio sync to video timestamps
                "-vsync", "cfr",    # Constant frame rate for predictable timing
            ])
            sync_mode = "transcode_video"
            logger.debug("Added A/V sync flags (software transcode + copy audio)")
        elif can_copy_video and not can_copy_audio:
            # Video copy + audio transcode = also needs sync
            cmd.extend([
                "-async", "1",
                "-vsync", "passthrough",  # Pass through original video timing
            ])
            sync_mode = "transcode_audio"
            logger.debug("Added A/V sync flags (copy video + transcode audio)")
        elif use_hwaccel:
            # Hardware encoding - audio resample already added in audio section
            cmd.extend([
                "-vsync", "cfr",
            ])
            sync_mode = "hwaccel_resync"
            logger.debug("Added A/V sync flags (hardware encoding with aresample)")
        else:
            # Full transcode (both audio and video)
            cmd.extend([
                "-async", "1",
                "-vsync", "cfr",
            ])
            sync_mode = "full_transcode"
            logger.debug("Added A/V sync flags (full transcode)")
        
        # #region agent log
        import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H3","location":"mpegts_streamer.py:build_command","message":"FFmpeg sync mode","data":{"sync_mode":sync_mode,"can_copy_video":can_copy_video,"can_copy_audio":can_copy_audio,"use_hwaccel":use_hwaccel,"input_url":input_url[:80] if len(input_url)>80 else input_url},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
        # #endregion
        
        # MPEG-TS output format
        cmd.extend([
            "-f", "mpegts",
            "-muxrate", "4M",
            "-pcr_period", "20",
            "-flush_packets", "1",
            "-fflags", "+flush_packets",
            "-max_interleave_delta", "0",
        ])
        
        # Apply user-defined extra flags from config (e.g., "-max_muxing_queue_size 9999")
        extra_flags = config.ffmpeg.extra_flags
        if extra_flags:
            import shlex
            try:
                extra_args = shlex.split(extra_flags)
                cmd.extend(extra_args)
                logger.debug(f"Applied extra FFmpeg flags: {extra_flags}")
            except ValueError as e:
                logger.warning(f"Failed to parse extra_flags '{extra_flags}': {e}")
        
        # Output to stdout
        cmd.append("-")
        
        return cmd

    def _get_hardware_settings(
        self,
        source: StreamSource,
        src_youtube: bool,
        src_archive: bool,
        src_plex: bool,
    ) -> tuple[str | None, str | None]:
        """
        Determine hardware acceleration settings.
        
        Returns:
            Tuple of (hwaccel, encoder).
        """
        config = get_config()
        chosen_hwaccel = None
        chosen_encoder = None
        
        # Source-specific overrides
        if src_youtube:
            chosen_hwaccel = config.ffmpeg.youtube_hwaccel or chosen_hwaccel
            chosen_encoder = config.ffmpeg.youtube_video_encoder or chosen_encoder
        elif src_archive:
            chosen_hwaccel = config.ffmpeg.archive_org_hwaccel or chosen_hwaccel
            chosen_encoder = config.ffmpeg.archive_org_video_encoder or chosen_encoder
        elif src_plex:
            chosen_hwaccel = config.ffmpeg.plex_hwaccel or chosen_hwaccel
            chosen_encoder = config.ffmpeg.plex_video_encoder or chosen_encoder
        
        # Per-channel profile override
        if self._channel_profile:
            profile = self._channel_profile.lower()
            if profile == "nvidia":
                chosen_hwaccel = "cuda"
                chosen_encoder = "h264_nvenc"
            elif profile == "intel":
                chosen_hwaccel = "qsv"
                chosen_encoder = "h264_qsv"
            elif profile == "cpu":
                chosen_hwaccel = None
                chosen_encoder = "libx264"
        
        # Fallback to config/auto-detect
        if not chosen_hwaccel:
            hw_config = config.ffmpeg.hardware_acceleration
            # hw_config is a HardwareAccelerationConfig object, extract the preferred value
            hw_preferred = hw_config.preferred if hasattr(hw_config, 'preferred') else str(hw_config)
            hw_enabled = hw_config.enabled if hasattr(hw_config, 'enabled') else True
            
            if hw_enabled and hw_preferred == "auto":
                if platform.system() == "Darwin":
                    chosen_hwaccel = "videotoolbox"
                    logger.debug("Auto-detected macOS - using VideoToolbox")
            elif hw_enabled and hw_preferred and hw_preferred != "none":
                chosen_hwaccel = hw_preferred
        
        # Set encoder based on hwaccel
        if chosen_hwaccel and not chosen_encoder:
            encoder_map = {
                "videotoolbox": "h264_videotoolbox",
                "cuda": "h264_nvenc",
                "qsv": "h264_qsv",
                "vaapi": "h264_vaapi",
            }
            chosen_encoder = encoder_map.get(chosen_hwaccel)
        
        return chosen_hwaccel, chosen_encoder

    def _get_hw_encoder(
        self,
        hwaccel: str | None,
        encoder: str | None,
    ) -> str:
        """Get the appropriate hardware encoder name."""
        if encoder:
            return encoder
        
        encoder_map = {
            "videotoolbox": "h264_videotoolbox",
            "cuda": "h264_nvenc",
            "qsv": "h264_qsv",
            "vaapi": "h264_vaapi",
        }
        return encoder_map.get(hwaccel or "", "libx264")

    def _add_http_input_options(
        self,
        cmd: list[str],
        input_url: str,
        is_archive_org: bool,
        is_plex: bool,
        is_youtube: bool,
    ) -> None:
        """Add HTTP-specific input options."""
        # Set timeouts based on source
        # FIX: Increased default timeout from 30s to 60s because many sources
        # (especially StreamTV imported Archive.org items) may not be detected
        # properly and would timeout prematurely with the old 30s default
        if is_archive_org:
            timeout = "60000000"  # 60s for Archive.org
            reconnect_delay = "10"
        elif is_plex:
            timeout = "60000000"  # 60s for Plex
            reconnect_delay = "3"
        elif is_youtube:
            timeout = "45000000"  # 45s for YouTube (CDN URLs need time)
            reconnect_delay = "5"
        else:
            timeout = "60000000"  # 60s default (increased from 30s)
            reconnect_delay = "5"
            logger.debug("Using 60s timeout for unknown source type")
        
        # User agent for better CDN compatibility
        user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
        
        cmd.extend([
            "-timeout", timeout,
            "-user_agent", user_agent,
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", reconnect_delay,
            "-multiple_requests", "1",
        ])
        
        # Source-specific headers
        if is_archive_org:
            cmd.extend(["-headers", "Referer: https://archive.org/\r\n"])
            logger.debug("Added Archive.org headers")
        
        elif is_youtube or "googlevideo.com" in input_url.lower():
            headers = (
                "Referer: https://www.youtube.com/\r\n"
                f"User-Agent: {user_agent}\r\n"
                "Origin: https://www.youtube.com\r\n"
                "Accept: */*\r\n"
                "Accept-Language: en-US,en;q=0.9\r\n"
                "Accept-Encoding: identity\r\n"
            )
            cmd.extend(["-headers", headers])
            logger.debug("Added YouTube headers for CDN URL")

    async def stream(
        self,
        input_url: str,
        codec_info: CodecInfo | None = None,
        source: StreamSource = StreamSource.UNKNOWN,
        buffer_size: int = 65536,
        seek_offset: float = 0.0,
    ) -> AsyncIterator[bytes]:
        """
        Stream content as MPEG-TS.
        
        Args:
            input_url: Input file or URL.
            codec_info: Pre-probed codec information.
            source: Stream source type.
            buffer_size: Read buffer size.
            seek_offset: Seek into the file by this many seconds (ErsatzTV-style).
            
        Yields:
            MPEG-TS data chunks.
        """
        # Probe if no codec info provided
        if codec_info is None:
            codec_info = await self.probe_stream(input_url)
        
        # CRITICAL FIX: Validate seek_offset against probed duration
        # If we have a duration from probing and seek is past it, FFmpeg will produce no output
        actual_seek = seek_offset
        if seek_offset > 0 and codec_info.duration and codec_info.duration > 0:
            max_seek = max(0, codec_info.duration - 10)  # Leave at least 10 seconds
            if seek_offset >= codec_info.duration:
                logger.warning(
                    f"Seek offset {seek_offset:.0f}s >= duration {codec_info.duration:.0f}s - resetting to 0"
                )
                actual_seek = 0.0
            elif seek_offset > max_seek:
                logger.info(
                    f"Clamping seek offset from {seek_offset:.0f}s to {max_seek:.0f}s "
                    f"(duration: {codec_info.duration:.0f}s)"
                )
                actual_seek = max_seek
        
        # Build command
        cmd = self.build_ffmpeg_command(input_url, codec_info, source, seek_offset=actual_seek)
        
        logger.info(f"FFmpeg command: {' '.join(cmd)}")
        logger.debug(f"Starting FFmpeg: {' '.join(cmd[:10])}...")
        
        # Start FFmpeg process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        chunk_count = 0
        try:
            while True:
                chunk = await process.stdout.read(buffer_size)
                if not chunk:
                    break
                chunk_count += 1
                yield chunk
                
        except asyncio.CancelledError:
            logger.info("Stream cancelled, terminating FFmpeg")
            process.terminate()
            raise
            
        finally:
            # Ensure process is cleaned up
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
            
            # Log stderr if there were errors
            if process.returncode and process.returncode != 0:
                stderr = await process.stderr.read()
                if stderr:
                    logger.warning(f"FFmpeg stderr: {stderr.decode('utf-8', errors='replace')[:500]}")

    def cleanup(self, channel_id: str) -> None:
        """Clean up FFmpeg process for a channel."""
        if channel_id in self._processes:
            process = self._processes[channel_id]
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            del self._processes[channel_id]
