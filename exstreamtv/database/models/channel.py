"""
Channel Database Models

Defines Channel and related models for streaming configuration.
Compatible with ErsatzTV channel structure.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from exstreamtv.database.models.base import Base, TimestampMixin


class PlayoutMode(str, Enum):
    """Playout mode for a channel."""
    CONTINUOUS = "continuous"
    ON_DEMAND = "on_demand"
    SCHEDULED = "scheduled"
    FLOOD = "flood"
    LOOP = "loop"


class StreamingMode(str, Enum):
    """Streaming mode for channel output."""
    TRANSPORT_STREAM_HYBRID = "transport_stream_hybrid"
    HLS_HYBRID = "hls_hybrid"
    HLS_DIRECT = "hls_direct"
    MPEG_TS = "mpeg_ts"


class StreamSource(str, Enum):
    """Source type for streaming content."""
    YOUTUBE = "youtube"
    ARCHIVE_ORG = "archive_org"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"
    LOCAL = "local"


if TYPE_CHECKING:
    from exstreamtv.database.models.filler import FillerPreset
    from exstreamtv.database.models.playout import Playout
    from exstreamtv.database.models.profile import FFmpegProfile


class Channel(Base, TimestampMixin):
    """
    Channel model representing a streaming channel.
    
    Combines StreamTV channel structure with ErsatzTV extensions.
    """
    
    __tablename__ = "channels"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # ErsatzTV: Unique identifier (UUID for stable references)
    unique_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    
    # Basic channel info
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # ErsatzTV: Custom sort order (decimal for flexible ordering)
    sort_number: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # ErsatzTV: Category tags (comma-separated or JSON array)
    categories: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Group/Category (for organizing in IPTV apps)
    group: Mapped[str | None] = mapped_column(String(100), nullable=True, default="General")
    
    # Channel state
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Logos and branding
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Playout mode
    playout_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PlayoutMode.CONTINUOUS.value
    )
    
    # Streaming mode: "iptv", "hdhomerun", "both"
    streaming_mode: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default=StreamingMode.TRANSPORT_STREAM_HYBRID.value
    )
    
    # FFmpeg profile for this channel
    ffmpeg_profile_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ffmpeg_profiles.id"),
        nullable=True,
    )
    
    # Fallback filler (ErsatzTV feature)
    fallback_filler_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("filler_presets.id"),
        nullable=True,
    )
    
    # Watermark configuration
    watermark_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("channel_watermarks.id"),
        nullable=True,
    )
    
    # Legacy transcoding field
    transcode_profile: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # YAML-defined channel flag
    is_yaml_source: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # ErsatzTV-compatible settings
    transcode_mode: Mapped[str | None] = mapped_column(String(50), nullable=True, default="on_demand")
    subtitle_mode: Mapped[str | None] = mapped_column(String(50), nullable=True, default="none")
    preferred_audio_language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    preferred_audio_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_subtitle_language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    stream_selector_mode: Mapped[str | None] = mapped_column(String(50), nullable=True, default="default")
    stream_selector: Mapped[str | None] = mapped_column(Text, nullable=True)
    music_video_credits_mode: Mapped[str | None] = mapped_column(String(50), nullable=True, default="none")
    music_video_credits_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    song_video_mode: Mapped[str | None] = mapped_column(String(50), nullable=True, default="default")
    idle_behavior: Mapped[str | None] = mapped_column(String(50), nullable=True, default="stop_on_disconnect")
    playout_source: Mapped[str | None] = mapped_column(String(50), nullable=True, default="generated")
    mirror_source_channel_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playout_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Offset in seconds
    show_in_epg: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Prefer channel logo over content logo
    prefer_channel_logo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # ErsatzTV: Offline mode configuration
    offline_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="offline_image"  # "offline_image", "filler", "last_frame"
    )
    offline_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    ffmpeg_profile: Mapped[Optional["FFmpegProfile"]] = relationship(
        "FFmpegProfile",
        back_populates="channels",
    )
    fallback_filler: Mapped[Optional["FillerPreset"]] = relationship(
        "FillerPreset",
        foreign_keys=[fallback_filler_id],
    )
    watermark: Mapped[Optional["ChannelWatermark"]] = relationship(
        "ChannelWatermark",
        back_populates="channel",
    )
    playouts: Mapped[list["Playout"]] = relationship(
        "Playout",
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Channel {self.number}: {self.name}>"


class ChannelWatermark(Base, TimestampMixin):
    """
    Watermark configuration for a channel.
    
    ErsatzTV feature: overlay graphics on channel output.
    """
    
    __tablename__ = "channel_watermarks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Name for identification
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="Default")
    
    # Image source
    image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(Text, nullable=True)  # Base64 encoded image
    original_content_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Mode: "permanent", "intermittent"
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="permanent")
    
    # Image source type: "custom", "channel_logo"
    image_source: Mapped[str] = mapped_column(String(20), nullable=False, default="custom")
    
    # Position: "top_left", "top_right", "bottom_left", "bottom_right"
    location: Mapped[str] = mapped_column(String(20), nullable=False, default="bottom_right")
    
    # Size: "small", "medium", "large"
    size: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    
    # Size (percentage of screen width)
    width_percent: Mapped[float] = mapped_column(Integer, nullable=False, default=10)
    
    # Margin percentages
    horizontal_margin_percent: Mapped[float] = mapped_column(Integer, nullable=False, default=2)
    vertical_margin_percent: Mapped[float] = mapped_column(Integer, nullable=False, default=2)
    
    # For intermittent mode
    frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Opacity (0-100)
    opacity: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    opacity_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Place within source content boundaries
    place_within_source_content: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Z-index for layering
    z_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Relationship
    channel: Mapped[Optional["Channel"]] = relationship(
        "Channel",
        back_populates="watermark",
    )
    
    def __repr__(self) -> str:
        return f"<ChannelWatermark {self.id} at {self.location}>"


class ChannelFFmpegProfile(Base):
    """
    Per-channel FFmpeg overrides.
    
    Allows customizing encoding settings for specific channels.
    """
    
    __tablename__ = "channel_ffmpeg_profiles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("channels.id"),
        nullable=False,
    )
    
    # Override settings (null means use default)
    video_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    audio_codec: Mapped[str | None] = mapped_column(String(50), nullable=True)
    video_bitrate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    audio_bitrate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    framerate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hardware_acceleration: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    def __repr__(self) -> str:
        return f"<ChannelFFmpegProfile for channel {self.channel_id}>"


class ChannelPlaybackPosition(Base, TimestampMixin):
    """
    Tracks playback position for on-demand channels.
    
    Used to resume playback from where the user left off.
    """
    
    __tablename__ = "channel_playback_positions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("channels.id"),
        nullable=False,
        unique=True,
    )
    channel_number: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # Current media item being played
    current_media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_item_media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Position within current item (seconds)
    position_seconds: Mapped[float] = mapped_column(Integer, nullable=False, default=0)
    
    # Playlist/schedule index
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_item_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Total items watched in session
    total_items_watched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    # Last played timestamp
    last_played_at: Mapped[str | None] = mapped_column(DateTime, nullable=True)
    
    # Anchor time for continuous streaming (ErsatzTV-style)
    # This is when the playout conceptually "started" for time-based position calculation
    playout_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Enhanced position tracking for EPG sync
    current_item_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    elapsed_seconds_in_item: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    
    def __repr__(self) -> str:
        return f"<ChannelPlaybackPosition channel={self.channel_id} pos={self.position_seconds}s>"
