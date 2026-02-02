"""Pydantic schemas for API requests and responses"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

# Import StreamSource and PlayoutMode from database models to ensure consistency
try:
    from ..database.models import PlayoutMode, StreamSource
except ImportError:
    from enum import Enum

    class StreamSource(str, Enum):
        YOUTUBE = "youtube"
        ARCHIVE_ORG = "archive_org"

    class PlayoutMode(str, Enum):
        CONTINUOUS = "continuous"
        ON_DEMAND = "on_demand"


# Channel Schemas
try:
    from ..database.models import (
        ChannelIdleBehavior,
        ChannelMusicVideoCreditsMode,
        ChannelPlayoutSource,
        ChannelSongVideoMode,
        ChannelStreamSelectorMode,
        ChannelSubtitleMode,
        ChannelTranscodeMode,
        StreamingMode,
    )
except ImportError:
    # Fallback enums if models not available
    from enum import Enum

    class StreamingMode(str, Enum):
        TRANSPORT_STREAM_HYBRID = "transport_stream_hybrid"

    class ChannelTranscodeMode(str, Enum):
        ON_DEMAND = "on_demand"

    class ChannelSubtitleMode(str, Enum):
        NONE = "none"

    class ChannelStreamSelectorMode(str, Enum):
        DEFAULT = "default"

    class ChannelMusicVideoCreditsMode(str, Enum):
        NONE = "none"

    class ChannelSongVideoMode(str, Enum):
        DEFAULT = "default"

    class ChannelIdleBehavior(str, Enum):
        STOP_ON_DISCONNECT = "stop_on_disconnect"

    class ChannelPlayoutSource(str, Enum):
        GENERATED = "generated"


class ChannelBase(BaseModel):
    number: str
    name: str
    group: str | None = None
    enabled: bool = True
    logo_path: str | None = None
    playout_mode: PlayoutMode | str = PlayoutMode.CONTINUOUS  # Continuous or on-demand
    transcode_profile: str | None = None  # "cpu", "nvidia", "intel" (legacy)
    is_yaml_source: bool = False

    @field_validator("playout_mode", mode="before")
    @classmethod
    def validate_playout_mode(cls, v):
        """Convert string values to enum instances"""
        if isinstance(v, str):
            # Try to match by value first (lowercase)
            v_lower = v.lower()
            if v_lower == "continuous":
                return PlayoutMode.CONTINUOUS
            elif v_lower in {"on_demand", "on-demand"}:
                return PlayoutMode.ON_DEMAND
            # Try to match by name (uppercase)
            try:
                return PlayoutMode[v.upper()]
            except KeyError:
                # If neither works, try direct value match
                for mode in PlayoutMode:
                    if mode.value == v:
                        return mode
                raise ValueError(
                    f"Invalid playout_mode value: {v}. Must be one of: {[m.value for m in PlayoutMode]}"
                )
        return v

    # ErsatzTV-compatible settings
    ffmpeg_profile_id: int | None = None
    watermark_id: int | None = None
    streaming_mode: StreamingMode = StreamingMode.TRANSPORT_STREAM_HYBRID
    transcode_mode: ChannelTranscodeMode = ChannelTranscodeMode.ON_DEMAND
    subtitle_mode: ChannelSubtitleMode = ChannelSubtitleMode.NONE
    preferred_audio_language_code: str | None = None
    preferred_audio_title: str | None = None
    preferred_subtitle_language_code: str | None = None
    stream_selector_mode: ChannelStreamSelectorMode = ChannelStreamSelectorMode.DEFAULT
    stream_selector: str | None = None
    music_video_credits_mode: ChannelMusicVideoCreditsMode = ChannelMusicVideoCreditsMode.NONE
    music_video_credits_template: str | None = None
    song_video_mode: ChannelSongVideoMode = ChannelSongVideoMode.DEFAULT
    idle_behavior: ChannelIdleBehavior = ChannelIdleBehavior.STOP_ON_DISCONNECT
    playout_source: ChannelPlayoutSource = ChannelPlayoutSource.GENERATED
    mirror_source_channel_id: int | None = None
    playout_offset: int | None = None  # Offset in seconds
    show_in_epg: bool = True


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    number: str | None = None
    name: str | None = None
    group: str | None = None
    enabled: bool | None = None
    logo_path: str | None = None
    playout_mode: PlayoutMode | None = None
    transcode_profile: str | None = None
    # ErsatzTV-compatible settings
    ffmpeg_profile_id: int | None = None
    watermark_id: int | None = None
    streaming_mode: StreamingMode | None = None
    transcode_mode: ChannelTranscodeMode | None = None
    subtitle_mode: ChannelSubtitleMode | None = None
    preferred_audio_language_code: str | None = None
    preferred_audio_title: str | None = None
    preferred_subtitle_language_code: str | None = None
    stream_selector_mode: ChannelStreamSelectorMode | None = None
    stream_selector: str | None = None
    music_video_credits_mode: ChannelMusicVideoCreditsMode | None = None
    music_video_credits_template: str | None = None
    song_video_mode: ChannelSongVideoMode | None = None
    idle_behavior: ChannelIdleBehavior | None = None
    playout_source: ChannelPlayoutSource | None = None
    mirror_source_channel_id: int | None = None
    playout_offset: int | None = None
    show_in_epg: bool | None = None


class ChannelResponse(ChannelBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    # Include related objects
    ffmpeg_profile: Optional["FFmpegProfileResponse"] = None
    watermark: Optional["WatermarkResponse"] = None


# Media Item Schemas
class MediaItemBase(BaseModel):
    source: StreamSource
    url: str
    title: str
    description: str | None = None
    duration: int | None = None
    thumbnail: str | None = None


class MediaItemCreate(MediaItemBase):
    pass


class MediaItemResponse(MediaItemBase):
    id: int
    source_id: str
    uploader: str | None = None
    upload_date: str | None = None
    view_count: int | None = None
    meta_data: str | None = None  # JSON string with additional metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Collection Schemas
class CollectionBase(BaseModel):
    name: str
    description: str | None = None
    collection_type: str | None = "manual"  # "manual", "smart", "multi"
    search_query: str | None = None  # For smart collections


class CollectionCreate(CollectionBase):
    pass


class CollectionItemResponse(BaseModel):
    id: int
    media_item_id: int
    order: int
    media_item: MediaItemResponse | None = None

    class Config:
        from_attributes = True


class CollectionResponse(CollectionBase):
    id: int
    created_at: datetime
    updated_at: datetime
    items: list[CollectionItemResponse] = []

    class Config:
        from_attributes = True
        # Pydantic will automatically serialize enum values to their string values


# Playlist Schemas
class PlaylistBase(BaseModel):
    name: str
    description: str | None = None
    channel_id: int | None = None


class PlaylistCreate(PlaylistBase):
    pass


class PlaylistItemResponse(BaseModel):
    id: int
    media_item_id: int
    order: int
    media_item: MediaItemResponse | None = None

    class Config:
        from_attributes = True


class PlaylistResponse(PlaylistBase):
    id: int
    created_at: datetime
    updated_at: datetime
    items: list[PlaylistItemResponse] = []

    class Config:
        from_attributes = True


# Schedule Schemas
class ScheduleBase(BaseModel):
    name: str
    channel_id: int | None = None  # Optional - ProgramSchedule links via playouts
    keep_multi_part_episodes_together: bool = False
    treat_collections_as_shows: bool = False
    shuffle_schedule_items: bool = False
    random_start_point: bool = False
    is_yaml_source: bool = False
    # Legacy fields (optional for backward compatibility)
    playlist_id: int | None = None
    collection_id: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    repeat: bool = False


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    name: str | None = None
    channel_id: int | None = None
    keep_multi_part_episodes_together: bool | None = None
    treat_collections_as_shows: bool | None = None
    shuffle_schedule_items: bool | None = None
    random_start_point: bool | None = None


class ScheduleResponse(ScheduleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Schedule Item Schemas
class ScheduleItemBase(BaseModel):
    schedule_id: int
    index: int | None = None

    # Start Type
    start_type: str | None = "dynamic"  # "dynamic" or "fixed"
    start_time: datetime | None = None
    fixed_start_time_behavior: str | None = (
        None  # "start_immediately", "skip_item", "wait_for_next"
    )

    # Collection Type
    collection_type: str | None = (
        "collection"  # "collection", "television_show", "television_season", "artist", "multi_collection", "smart_collection", "playlist"
    )
    collection_id: int | None = None
    media_item_id: int | None = None
    playlist_id: int | None = None
    search_title: str | None = None
    search_query: str | None = None
    # Plex-specific collection types
    plex_show_key: str | None = None  # For TELEVISION_SHOW
    plex_season_key: str | None = None  # For TELEVISION_SEASON
    plex_artist_key: str | None = None  # For ARTIST

    # Playback Order
    playback_order: str | None = (
        "chronological"  # "chronological", "random", "shuffle", "shuffle_in_order", "season_episode"
    )

    # Playout Mode
    playout_mode: str | None = "one"  # "flood", "one", "multiple", "duration"
    multiple_mode: str | None = (
        None  # "count", "collection_size", "multi_episode_group_size", "playlist_item_size"
    )
    multiple_count: int | None = None
    playout_duration_hours: int | None = 0
    playout_duration_minutes: int | None = 0

    # Fill Options
    fill_with_group_mode: str | None = None  # "none", "ordered_groups", "shuffled_groups"
    tail_mode: str | None = None  # "none", "offline", "filler"
    tail_filler_collection_id: int | None = None
    discard_to_fill_attempts: int | None = None

    # Custom Title and Guide
    custom_title: str | None = None
    guide_mode: str | None = "normal"  # "normal", "custom", "hide"

    # Fillers
    pre_roll_filler_id: int | None = None
    mid_roll_filler_id: int | None = None
    post_roll_filler_id: int | None = None
    tail_filler_id: int | None = None
    fallback_filler_id: int | None = None

    # Overrides
    watermark_id: int | None = None
    preferred_audio_language: str | None = None
    preferred_audio_title: str | None = None
    preferred_subtitle_language: str | None = None
    subtitle_mode: str | None = None


class ScheduleItemCreate(ScheduleItemBase):
    pass


class ScheduleItemUpdate(BaseModel):
    index: int | None = None
    start_type: str | None = None
    start_time: datetime | None = None
    fixed_start_time_behavior: str | None = None
    collection_type: str | None = None
    collection_id: int | None = None
    media_item_id: int | None = None
    playlist_id: int | None = None
    search_title: str | None = None
    search_query: str | None = None
    plex_show_key: str | None = None
    plex_season_key: str | None = None
    plex_artist_key: str | None = None
    playback_order: str | None = None
    playout_mode: str | None = None
    multiple_mode: str | None = None
    multiple_count: int | None = None
    playout_duration_hours: int | None = None
    playout_duration_minutes: int | None = None
    fill_with_group_mode: str | None = None
    tail_mode: str | None = None
    tail_filler_collection_id: int | None = None
    discard_to_fill_attempts: int | None = None
    custom_title: str | None = None
    guide_mode: str | None = None
    pre_roll_filler_id: int | None = None
    mid_roll_filler_id: int | None = None
    post_roll_filler_id: int | None = None
    tail_filler_id: int | None = None
    fallback_filler_id: int | None = None
    watermark_id: int | None = None
    preferred_audio_language: str | None = None
    preferred_audio_title: str | None = None
    preferred_subtitle_language: str | None = None
    subtitle_mode: str | None = None


class ScheduleItemResponse(ScheduleItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Settings Schemas
class FFmpegSettingsBase(BaseModel):
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    log_level: str | None = None
    threads: int | None = None
    hwaccel: str | None = None
    hwaccel_device: str | None = None
    extra_flags: str | None = None
    # Per-source overrides
    youtube_hwaccel: str | None = None
    archive_org_hwaccel: str | None = None
    plex_hwaccel: str | None = None
    youtube_video_encoder: str | None = None
    archive_org_video_encoder: str | None = None
    plex_video_encoder: str | None = None


class FFmpegSettingsUpdate(FFmpegSettingsBase):
    pass


class FFmpegSettingsResponse(BaseModel):
    ffmpeg_path: str
    ffprobe_path: str
    log_level: str
    threads: int
    hwaccel: str | None
    hwaccel_device: str | None
    extra_flags: str | None
    youtube_hwaccel: str | None
    archive_org_hwaccel: str | None
    plex_hwaccel: str | None
    youtube_video_encoder: str | None
    archive_org_video_encoder: str | None
    plex_video_encoder: str | None

    class Config:
        from_attributes = True


# HDHomeRun Settings Schemas
class HDHomeRunSettingsBase(BaseModel):
    enabled: bool | None = None
    device_id: str | None = None
    friendly_name: str | None = None
    tuner_count: int | None = None
    enable_ssdp: bool | None = None


class HDHomeRunSettingsUpdate(HDHomeRunSettingsBase):
    pass


class HDHomeRunSettingsResponse(BaseModel):
    enabled: bool
    device_id: str
    friendly_name: str
    tuner_count: int
    enable_ssdp: bool

    class Config:
        from_attributes = True


# Playout Settings Schemas
class PlayoutSettingsBase(BaseModel):
    build_days: int | None = None


class PlayoutSettingsUpdate(PlayoutSettingsBase):
    pass


class PlayoutSettingsResponse(BaseModel):
    build_days: int

    class Config:
        from_attributes = True


# Plex Settings Schemas
class PlexSettingsBase(BaseModel):
    enabled: bool | None = None
    base_url: str | None = None
    token: str | None = None
    use_for_epg: bool | None = None


class PlexSettingsUpdate(PlexSettingsBase):
    pass


class PlexSettingsResponse(BaseModel):
    enabled: bool
    base_url: str | None
    token: str | None
    use_for_epg: bool

    class Config:
        from_attributes = True


# Resolution Schemas
class ResolutionBase(BaseModel):
    name: str
    width: int
    height: int
    is_custom: bool = True


class ResolutionCreate(ResolutionBase):
    pass


class ResolutionUpdate(BaseModel):
    name: str | None = None
    width: int | None = None
    height: int | None = None
    is_custom: bool | None = None


class ResolutionResponse(ResolutionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# FFmpeg Profile Schemas
try:
    from ..database.models import (
        AudioFormat,
        BitDepth,
        HardwareAccelerationKind,
        NormalizeLoudnessMode,
        ScalingBehavior,
        TonemapAlgorithm,
        VideoFormat,
    )
except ImportError:
    # Fallback enums if models not available
    from enum import Enum

    class HardwareAccelerationKind(str, Enum):
        NONE = "none"

    class VideoFormat(str, Enum):
        H264 = "h264"

    class AudioFormat(str, Enum):
        AAC = "aac"

    class BitDepth(str, Enum):
        EIGHT_BIT = "8bit"

    class ScalingBehavior(str, Enum):
        SCALE_AND_PAD = "scale_and_pad"

    class TonemapAlgorithm(str, Enum):
        LINEAR = "linear"

    class NormalizeLoudnessMode(str, Enum):
        OFF = "off"


class FFmpegProfileBase(BaseModel):
    name: str
    thread_count: int = 0
    hardware_acceleration: HardwareAccelerationKind = HardwareAccelerationKind.NONE
    vaapi_driver: str | None = None
    vaapi_device: str | None = None
    qsv_extra_hardware_frames: int | None = None
    resolution_id: int
    scaling_behavior: ScalingBehavior = ScalingBehavior.SCALE_AND_PAD
    video_format: VideoFormat = VideoFormat.H264
    video_profile: str | None = None
    video_preset: str | None = None
    allow_b_frames: bool = False
    bit_depth: BitDepth = BitDepth.EIGHT_BIT
    video_bitrate: int = 2000
    video_buffer_size: int = 4000
    tonemap_algorithm: TonemapAlgorithm = TonemapAlgorithm.LINEAR
    audio_format: AudioFormat = AudioFormat.AAC
    audio_bitrate: int = 192
    audio_buffer_size: int = 384
    normalize_loudness_mode: NormalizeLoudnessMode = NormalizeLoudnessMode.OFF
    audio_channels: int = 2
    audio_sample_rate: int = 48000
    normalize_framerate: bool = False
    deinterlace_video: bool | None = None


class FFmpegProfileCreate(FFmpegProfileBase):
    pass


class FFmpegProfileUpdate(BaseModel):
    name: str | None = None
    thread_count: int | None = None
    hardware_acceleration: HardwareAccelerationKind | None = None
    vaapi_driver: str | None = None
    vaapi_device: str | None = None
    qsv_extra_hardware_frames: int | None = None
    resolution_id: int | None = None
    scaling_behavior: ScalingBehavior | None = None
    video_format: VideoFormat | None = None
    video_profile: str | None = None
    video_preset: str | None = None
    allow_b_frames: bool | None = None
    bit_depth: BitDepth | None = None
    video_bitrate: int | None = None
    video_buffer_size: int | None = None
    tonemap_algorithm: TonemapAlgorithm | None = None
    audio_format: AudioFormat | None = None
    audio_bitrate: int | None = None
    audio_buffer_size: int | None = None
    normalize_loudness_mode: NormalizeLoudnessMode | None = None
    audio_channels: int | None = None
    audio_sample_rate: int | None = None
    normalize_framerate: bool | None = None
    deinterlace_video: bool | None = None


class FFmpegProfileResponse(FFmpegProfileBase):
    id: int
    created_at: datetime
    updated_at: datetime
    resolution: ResolutionResponse | None = None

    class Config:
        from_attributes = True


class HardwareAccelerationResponse(BaseModel):
    available: list[str]


# Watermark Schemas
try:
    from ..database.models import (
        ChannelWatermarkImageSource,
        ChannelWatermarkMode,
        WatermarkLocation,
        WatermarkSize,
    )
except ImportError:
    # Fallback enums if models not available
    from enum import Enum

    class ChannelWatermarkMode(str, Enum):
        PERMANENT = "permanent"

    class ChannelWatermarkImageSource(str, Enum):
        CUSTOM = "custom"

    class WatermarkLocation(str, Enum):
        BOTTOM_RIGHT = "bottom_right"

    class WatermarkSize(str, Enum):
        MEDIUM = "medium"


class WatermarkBase(BaseModel):
    name: str
    mode: ChannelWatermarkMode = ChannelWatermarkMode.PERMANENT
    image_source: ChannelWatermarkImageSource = ChannelWatermarkImageSource.CUSTOM
    location: WatermarkLocation = WatermarkLocation.BOTTOM_RIGHT
    size: WatermarkSize = WatermarkSize.MEDIUM
    width_percent: float = 10.0
    horizontal_margin_percent: float = 2.0
    vertical_margin_percent: float = 2.0
    frequency_minutes: int = 0
    duration_seconds: int = 0
    opacity: int = 100
    place_within_source_content: bool = True
    opacity_expression: str | None = None
    z_index: int = 0


class WatermarkCreate(WatermarkBase):
    image: str | None = None  # Path to image (set via upload endpoint)


class WatermarkUpdate(BaseModel):
    name: str | None = None
    mode: ChannelWatermarkMode | None = None
    image_source: ChannelWatermarkImageSource | None = None
    location: WatermarkLocation | None = None
    size: WatermarkSize | None = None
    width_percent: float | None = None
    horizontal_margin_percent: float | None = None
    vertical_margin_percent: float | None = None
    frequency_minutes: int | None = None
    duration_seconds: int | None = None
    opacity: int | None = None
    place_within_source_content: bool | None = None
    opacity_expression: str | None = None
    z_index: int | None = None
    image: str | None = None


class WatermarkResponse(WatermarkBase):
    id: int
    image: str | None = None
    original_content_type: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
