"""
FFmpeg Profile Database Models

Defines FFmpegProfile and Resolution for encoding presets.
Compatible with ErsatzTV FFmpegProfile structure.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from exstreamtv.database.models.channel import Channel


class Resolution(Base, TimestampMixin):
    """
    Standard resolution preset.
    """
    
    __tablename__ = "resolutions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Common presets flag
    is_preset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    def __repr__(self) -> str:
        return f"<Resolution {self.name} ({self.width}x{self.height})>"


class FFmpegProfile(Base, TimestampMixin):
    """
    FFmpeg encoding profile.
    
    Defines a complete set of encoding settings for channels.
    """
    
    __tablename__ = "ffmpeg_profiles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    
    # Resolution
    resolution_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Video settings
    video_codec: Mapped[str] = mapped_column(String(50), nullable=False, default="libx264")
    video_bitrate: Mapped[str] = mapped_column(String(20), nullable=False, default="4000k")
    video_buffer_size: Mapped[str] = mapped_column(String(20), nullable=False, default="8000k")
    framerate: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    
    # Video quality settings
    quality_preset: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",  # ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
    )
    quality_crf: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-51, lower = better
    
    # Audio settings
    audio_codec: Mapped[str] = mapped_column(String(50), nullable=False, default="aac")
    audio_bitrate: Mapped[str] = mapped_column(String(20), nullable=False, default="128k")
    audio_channels: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    audio_sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=48000)
    
    # Audio normalization
    normalize_audio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    audio_loudness_target: Mapped[int] = mapped_column(Integer, nullable=False, default=-24)
    
    # Hardware acceleration
    hardware_acceleration: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="auto",  # auto, nvenc, qsv, vaapi, videotoolbox, amf, none
    )
    
    # Deinterlacing
    deinterlace: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Scaling mode: "stretch", "pad", "crop"
    scaling_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pad",
    )
    pad_color: Mapped[str] = mapped_column(String(10), nullable=False, default="black")
    
    # Thread count (0 = auto)
    thread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Output format settings
    # MPEG-TS settings
    mpegts_original_network_id: Mapped[int] = mapped_column(Integer, nullable=False, default=65281)
    mpegts_transport_stream_id: Mapped[int] = mapped_column(Integer, nullable=False, default=65281)
    mpegts_service_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mpegts_pmt_start_pid: Mapped[int] = mapped_column(Integer, nullable=False, default=480)
    mpegts_start_pid: Mapped[int] = mapped_column(Integer, nullable=False, default=481)
    
    # Custom FFmpeg flags (advanced)
    custom_video_filters: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_audio_filters: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_output_flags: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # === ErsatzTV-compatible fields ===
    
    # Video format settings
    video_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="h264",  # h264, hevc, mpeg2video, av1
    )
    video_profile: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,  # main, high, high10, etc.
    )
    allow_b_frames: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bit_depth: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="8bit",  # 8bit, 10bit
    )
    
    # Audio format settings
    audio_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="aac",  # aac, ac3, aac_latm, copy
    )
    audio_buffer_size: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="384k",
    )
    
    # Scaling behavior
    scaling_behavior: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="scale_and_pad",  # scale_and_pad, stretch, crop
    )
    
    # HDR/Tonemapping
    tonemap_algorithm: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,  # none, hable, reinhard, mobius, bt2390
    )
    
    # Audio normalization (ErsatzTV style)
    normalize_loudness_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="off",  # off, loudnorm, dynaudnorm
    )
    target_loudness: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # VAAPI settings
    vaapi_driver: Mapped[str | None] = mapped_column(String(50), nullable=True)
    vaapi_device: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # QSV settings
    qsv_extra_hardware_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Video processing
    normalize_framerate: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    deinterlace_video: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    
    # GOP settings (for MPEG-TS compliance)
    gop_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Keyframe interval
    
    # Watermark global settings
    global_watermark_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # State
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    channels: Mapped[list["Channel"]] = relationship(
        "Channel",
        back_populates="ffmpeg_profile",
    )
    
    def __repr__(self) -> str:
        return f"<FFmpegProfile {self.name}>"
    
    @property
    def resolution(self) -> tuple[int, int]:
        """Get resolution as (width, height) tuple."""
        if self.custom_width and self.custom_height:
            return (self.custom_width, self.custom_height)
        # Default to 1080p
        return (1920, 1080)
