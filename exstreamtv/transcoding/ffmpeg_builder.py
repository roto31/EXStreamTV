"""FFmpeg command builder from profiles"""

import logging
from pathlib import Path
from typing import Any

from ..config import config
from ..database.models import (
    AudioFormat,
    FFmpegProfile,
    HardwareAccelerationKind,
    Resolution,
    VideoFormat,
    Watermark,
)

logger = logging.getLogger(__name__)


def build_ffmpeg_command(
    profile: FFmpegProfile,
    input_url: str,
    watermark: Watermark | None = None,
    subtitle_path: str | None = None,
    codec_info: dict[str, Any] | None = None,
) -> list[str]:
    """
    Build FFmpeg command from profile with hardware acceleration, watermarks, and subtitles.

    Args:
        profile: FFmpeg profile to use
        input_url: Input stream URL
        watermark: Optional watermark to overlay
        subtitle_path: Optional path to subtitle file
        codec_info: Optional codec information from probe

    Returns:
        List of FFmpeg command arguments
    """
    cmd = [config.ffmpeg.ffmpeg_path]

    # Global options
    log_level = config.ffmpeg.log_level or "info"
    cmd.extend(["-loglevel", log_level])

    # Hardware acceleration (must come before input)
    if profile.hardware_acceleration != HardwareAccelerationKind.NONE:
        hwaccel = profile.hardware_acceleration.value
        cmd.extend(["-hwaccel", hwaccel])

        # Platform-specific hardware acceleration options
        if profile.hardware_acceleration == HardwareAccelerationKind.VAAPI:
            if profile.vaapi_device:
                cmd.extend(["-hwaccel_device", profile.vaapi_device])
            if profile.vaapi_driver:
                # VAAPI driver is typically set via environment, but we can note it
                logger.debug(f"Using VAAPI driver: {profile.vaapi_driver}")
        elif profile.hardware_acceleration == HardwareAccelerationKind.QSV:
            if profile.qsv_extra_hardware_frames:
                cmd.extend(["-qsv_device", str(profile.qsv_extra_hardware_frames)])
        elif profile.hardware_acceleration == HardwareAccelerationKind.NVENC:
            # NVENC uses CUDA
            cmd.extend(["-hwaccel", "cuda"])
            if config.ffmpeg.hwaccel_device:
                cmd.extend(["-hwaccel_device", config.ffmpeg.hwaccel_device])

    # Input options for HTTP streams
    if input_url.startswith("http"):
        cmd.extend(
            [
                "-timeout",
                "10000000",  # 10 second timeout
                "-user_agent",
                "Mozilla/5.0 (compatible; EXStreamTV/1.0)",
                "-reconnect",
                "1",
                "-reconnect_at_eof",
                "1",
                "-reconnect_streamed",
                "1",
                "-reconnect_delay_max",
                "2",
            ]
        )

    # Input flags
    cmd.extend(
        [
            "-fflags",
            "+genpts+discardcorrupt+fastseek",
            "-flags",
            "+low_delay",
            "-strict",
            "experimental",
            "-probesize",
            "1000000",
            "-analyzeduration",
            "2000000",
            "-i",
            input_url,
        ]
    )

    # Threads
    if profile.thread_count > 0:
        cmd.extend(["-threads", str(profile.thread_count)])
    elif config.ffmpeg.threads > 0:
        cmd.extend(["-threads", str(config.ffmpeg.threads)])

    # Add watermark image as second input if needed
    watermark_input_added = False
    if watermark and watermark.image:
        # Use absolute path relative to project root
        watermark_path = (
            Path(__file__).parent.parent.parent / "data" / "watermarks" / watermark.image
        )
        if watermark_path.exists():
            cmd.extend(["-i", str(watermark_path)])
            watermark_input_added = True

    # Video filters (scaling, watermark, subtitles)
    video_filters = []

    # Resolution scaling
    resolution = profile.resolution
    if resolution:
        scale_filter = _build_scale_filter(resolution, profile.scaling_behavior)
        if scale_filter:
            video_filters.append(scale_filter)

    # Watermark overlay (requires second input)
    if watermark_input_added:
        watermark_filter = _build_watermark_filter(watermark, resolution)
        if watermark_filter:
            video_filters.append(watermark_filter)

    # Subtitle overlay
    if subtitle_path and Path(subtitle_path).exists():
        subtitle_filter = f"subtitles={subtitle_path}"
        video_filters.append(subtitle_filter)

    # Apply video filters
    if video_filters:
        cmd.extend(["-vf", ",".join(video_filters)])

    # Video codec
    if profile.video_format == VideoFormat.COPY:
        cmd.extend(["-c:v", "copy"])
    else:
        encoder = _get_video_encoder(profile)
        cmd.extend(["-c:v", encoder])

        # Video codec options
        if profile.video_format == VideoFormat.H264:
            if profile.video_profile:
                cmd.extend(["-profile:v", profile.video_profile])
            if profile.allow_b_frames:
                cmd.extend(["-bf", "2"])
            else:
                cmd.extend(["-bf", "0"])

        if profile.video_preset:
            if profile.hardware_acceleration in (
                HardwareAccelerationKind.NVENC,
                HardwareAccelerationKind.QSV,
            ):
                cmd.extend(["-preset", profile.video_preset])
            else:
                cmd.extend(["-preset", profile.video_preset])

        # Bitrate
        cmd.extend(["-b:v", f"{profile.video_bitrate}k"])
        cmd.extend(["-maxrate", f"{profile.video_bitrate}k"])
        cmd.extend(["-bufsize", f"{profile.video_buffer_size}k"])

        # Pixel format
        if profile.bit_depth.value == "10bit":
            if profile.video_format in (VideoFormat.H264, VideoFormat.HEVC):
                cmd.extend(["-pix_fmt", "yuv420p10le"])
        else:
            cmd.extend(["-pix_fmt", "yuv420p"])

        # Deinterlace
        if profile.deinterlace_video is True:
            cmd.extend(["-deinterlace"])
        elif profile.deinterlace_video is False:
            # Explicitly disable deinterlacing
            pass

    # Audio codec
    if profile.audio_format == AudioFormat.COPY:
        cmd.extend(["-c:a", "copy"])
    else:
        encoder = _get_audio_encoder(profile)
        cmd.extend(["-c:a", encoder])

        # Audio options
        cmd.extend(["-b:a", f"{profile.audio_bitrate}k"])
        cmd.extend(["-ar", str(profile.audio_sample_rate)])
        cmd.extend(["-ac", str(profile.audio_channels)])

        # Normalize loudness
        if profile.normalize_loudness_mode.value == "loudnorm":
            cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])

    # Normalize framerate
    if profile.normalize_framerate:
        cmd.extend(["-r", "30"])  # Default to 30fps

    # Output format: MPEG-TS
    cmd.extend(
        ["-f", "mpegts", "-muxrate", f"{profile.video_bitrate + profile.audio_bitrate}k", "-"]
    )

    return cmd


def _build_scale_filter(resolution: Resolution, scaling_behavior) -> str | None:
    """Build scale filter for resolution"""
    if scaling_behavior.value == "scale_and_pad":
        return f"scale={resolution.width}:{resolution.height}:force_original_aspect_ratio=decrease,pad={resolution.width}:{resolution.height}:(ow-iw)/2:(oh-ih)/2"
    elif scaling_behavior.value == "stretch":
        return f"scale={resolution.width}:{resolution.height}"
    elif scaling_behavior.value == "crop":
        return f"scale={resolution.width}:{resolution.height}:force_original_aspect_ratio=increase,crop={resolution.width}:{resolution.height}"
    return None


def _build_watermark_filter(watermark: Watermark, resolution: Resolution | None) -> str | None:
    """Build watermark overlay filter (watermark is second input [1:v])"""
    # Calculate position
    x_expr = _get_watermark_x_position(watermark)
    y_expr = _get_watermark_y_position(watermark)

    # Calculate size
    size_expr = _get_watermark_size(watermark, resolution)

    # Opacity
    opacity = watermark.opacity / 100.0 if watermark.opacity else 1.0

    # Scale and apply opacity to watermark (second input [1:v])
    watermark_filters = [f"scale={size_expr}"]
    if opacity < 1.0:
        watermark_filters.append(f"format=yuva420p,colorchannelmixer=aa={opacity}")

    # Build overlay filter
    if watermark.mode.value == "intermittent" and watermark.duration_seconds > 0:
        # Intermittent mode with duration
        overlay_expr = (
            f"overlay={x_expr}:{y_expr}:enable='between(t,0,{watermark.duration_seconds})'"
        )
    else:
        # Permanent mode
        overlay_expr = f"overlay={x_expr}:{y_expr}"

    # Full filter chain: process watermark, then overlay on main video
    # [0:v] is main video, [1:v] is watermark image
    return f"[1:v]{','.join(watermark_filters)}[wm];[0:v][wm]{overlay_expr}"


def _get_watermark_x_position(watermark: Watermark) -> str:
    """Get X position expression for watermark"""
    if watermark.location.value in {"top_left", "bottom_left"}:
        margin = f"W*{watermark.horizontal_margin_percent / 100}"
        return margin
    elif watermark.location.value in {"top_right", "bottom_right"}:
        return f"W-w-{watermark.horizontal_margin_percent / 100}*W"
    else:  # center
        return "(W-w)/2"


def _get_watermark_y_position(watermark: Watermark) -> str:
    """Get Y position expression for watermark"""
    if watermark.location.value in {"top_left", "top_right"}:
        margin = f"H*{watermark.vertical_margin_percent / 100}"
        return margin
    elif watermark.location.value in {"bottom_left", "bottom_right"}:
        return f"H-h-{watermark.vertical_margin_percent / 100}*H"
    else:  # center
        return "(H-h)/2"


def _get_watermark_size(watermark: Watermark, resolution: Resolution | None) -> str:
    """Get size expression for watermark"""
    if watermark.size.value == "small":
        return "iw*0.05:-1"  # 5% of input width
    elif watermark.size.value == "medium":
        return "iw*0.1:-1"  # 10% of input width
    elif watermark.size.value == "large":
        return "iw*0.2:-1"  # 20% of input width
    else:  # custom
        width_pct = watermark.width_percent / 100.0
        return f"iw*{width_pct}:-1"


def _get_video_encoder(profile: FFmpegProfile) -> str:
    """Get video encoder name based on profile"""
    if profile.video_format == VideoFormat.H264:
        if profile.hardware_acceleration == HardwareAccelerationKind.NVENC:
            return "h264_nvenc"
        elif profile.hardware_acceleration == HardwareAccelerationKind.QSV:
            return "h264_qsv"
        elif profile.hardware_acceleration == HardwareAccelerationKind.VAAPI:
            return "h264_vaapi"
        elif profile.hardware_acceleration == HardwareAccelerationKind.VIDEOTOOLBOX:
            return "h264_videotoolbox"
        elif profile.hardware_acceleration == HardwareAccelerationKind.AMF:
            return "h264_amf"
        else:
            return "libx264"
    elif profile.video_format == VideoFormat.HEVC:
        if profile.hardware_acceleration == HardwareAccelerationKind.NVENC:
            return "hevc_nvenc"
        elif profile.hardware_acceleration == HardwareAccelerationKind.QSV:
            return "hevc_qsv"
        elif profile.hardware_acceleration == HardwareAccelerationKind.VAAPI:
            return "hevc_vaapi"
        elif profile.hardware_acceleration == HardwareAccelerationKind.VIDEOTOOLBOX:
            return "hevc_videotoolbox"
        elif profile.hardware_acceleration == HardwareAccelerationKind.AMF:
            return "hevc_amf"
        else:
            return "libx265"
    elif profile.video_format == VideoFormat.MPEG2VIDEO:
        return "mpeg2video"
    elif profile.video_format == VideoFormat.AV1:
        if profile.hardware_acceleration == HardwareAccelerationKind.NVENC:
            return "av1_nvenc"
        elif profile.hardware_acceleration == HardwareAccelerationKind.QSV:
            return "av1_qsv"
        else:
            return "libaom-av1"
    else:
        return "libx264"


def _get_audio_encoder(profile: FFmpegProfile) -> str:
    """Get audio encoder name based on profile"""
    if profile.audio_format == AudioFormat.AAC:
        return "aac"
    elif profile.audio_format == AudioFormat.AC3:
        return "ac3"
    elif profile.audio_format == AudioFormat.AACLATM:
        return "aac"
    else:
        return "aac"
