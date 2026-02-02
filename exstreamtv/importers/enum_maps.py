"""
ErsatzTV Enum Conversion Maps

ErsatzTV stores many settings as integer enums in SQLite.
This module provides mappings to convert those integers to
meaningful string values used in EXStreamTV.

Based on ErsatzTV source code analysis.
"""

from typing import Any

# ============================================================================
# Hardware Acceleration
# ============================================================================
# ErsatzTV HardwareAccelerationKind enum
HARDWARE_ACCELERATION_MAP = {
    0: "none",
    1: "nvenc",
    2: "qsv",
    3: "vaapi",
    4: "videotoolbox",
    5: "amf",
    6: "auto",
}

# ============================================================================
# Video Format
# ============================================================================
# ErsatzTV FFmpegProfileVideoFormat enum
VIDEO_FORMAT_MAP = {
    0: "h264",
    1: "hevc",
    2: "mpeg2video",
    3: "copy",
    4: "av1",
}

# ============================================================================
# Video Profile
# ============================================================================
# ErsatzTV FFmpegProfileVideoProfile enum
VIDEO_PROFILE_MAP = {
    0: None,  # none
    1: "main",
    2: "high",
    3: "high10",
    4: "high422",
    5: "high444",
}

# ============================================================================
# Bit Depth
# ============================================================================
VIDEO_BIT_DEPTH_MAP = {
    0: "8bit",
    1: "10bit",
    2: "12bit",
}

# ============================================================================
# Audio Format
# ============================================================================
# ErsatzTV FFmpegProfileAudioFormat enum
AUDIO_FORMAT_MAP = {
    0: "aac",
    1: "ac3",
    2: "copy",
    3: "aac_latm",
    4: "eac3",
    5: "flac",
    6: "opus",
}

# ============================================================================
# Scaling Behavior
# ============================================================================
# ErsatzTV ScalingBehavior enum
SCALING_BEHAVIOR_MAP = {
    0: "scale_and_pad",
    1: "stretch",
    2: "crop",
}

# ============================================================================
# Normalize Loudness Mode
# ============================================================================
# ErsatzTV NormalizeLoudnessMode enum
NORMALIZE_LOUDNESS_MODE_MAP = {
    0: "off",
    1: "loudnorm",
    2: "dynaudnorm",
}

# ============================================================================
# Tonemap Algorithm
# ============================================================================
# ErsatzTV TonemapAlgorithm enum
TONEMAP_ALGORITHM_MAP = {
    0: None,  # none
    1: "hable",
    2: "reinhard",
    3: "mobius",
    4: "bt2390",
}

# ============================================================================
# Streaming Mode
# ============================================================================
# ErsatzTV StreamingMode enum
STREAMING_MODE_MAP = {
    0: "transport_stream_hybrid",
    1: "hls_hybrid",
    2: "hls_direct",
    3: "mpeg_ts",
    4: "http_live_streaming_direct",
}

# ============================================================================
# Playout Type / Schedule Kind
# ============================================================================
# ErsatzTV PlayoutType enum
PLAYOUT_TYPE_MAP = {
    0: "flood",
    1: "block",
    2: "external",
    3: "yaml",
}

# ============================================================================
# Playback Order
# ============================================================================
# ErsatzTV PlaybackOrder enum
PLAYBACK_ORDER_MAP = {
    0: "chronological",
    1: "shuffled",
    2: "random",
    3: "shuffle_in_order",
    4: "multiepisode_shuffle",
}

# ============================================================================
# Playback Mode
# ============================================================================
# ErsatzTV PlaybackMode enum (for schedule items)
PLAYBACK_MODE_MAP = {
    0: "one",
    1: "multiple",
    2: "duration",
    3: "flood",
}

# ============================================================================
# Guide Mode
# ============================================================================
# ErsatzTV GuideMode enum
GUIDE_MODE_MAP = {
    0: "normal",
    1: "filler",
}

# ============================================================================
# Collection Type
# ============================================================================
# ErsatzTV CollectionType enum
COLLECTION_TYPE_MAP = {
    0: "collection",
    1: "television_show",
    2: "television_season",
    3: "artist",
    4: "multi_collection",
    5: "smart_collection",
    6: "search",
}

# ============================================================================
# Filler Kind
# ============================================================================
# ErsatzTV FillerKind enum
FILLER_KIND_MAP = {
    0: "none",
    1: "pre_roll",
    2: "mid_roll",
    3: "post_roll",
    4: "tail",
    5: "fallback",
    6: "guide",
}

# ============================================================================
# Filler Mode
# ============================================================================
# ErsatzTV FillerMode enum
FILLER_MODE_MAP = {
    0: "none",
    1: "count",
    2: "duration",
    3: "pad",
}

# ============================================================================
# Deco Mode (Watermark, Graphics, etc.)
# ============================================================================
# ErsatzTV DecoMode enum (used for various deco settings)
DECO_MODE_MAP = {
    0: "none",
    1: "inherit",
    2: "override",
}

# ============================================================================
# Watermark Mode
# ============================================================================
# ErsatzTV ChannelWatermarkMode enum
WATERMARK_MODE_MAP = {
    0: "permanent",
    1: "intermittent",
}

# ============================================================================
# Watermark Location
# ============================================================================
# ErsatzTV ChannelWatermarkLocation enum
WATERMARK_LOCATION_MAP = {
    0: "top_left",
    1: "top_right",
    2: "bottom_left",
    3: "bottom_right",
    4: "top_center",
    5: "bottom_center",
    6: "left_center",
    7: "right_center",
}

# ============================================================================
# Watermark Size
# ============================================================================
# ErsatzTV ChannelWatermarkSize enum
WATERMARK_SIZE_MAP = {
    0: "small",
    1: "medium",
    2: "large",
    3: "custom",
}

# ============================================================================
# Watermark Image Source
# ============================================================================
# ErsatzTV ChannelWatermarkImageSource enum
WATERMARK_IMAGE_SOURCE_MAP = {
    0: "custom",
    1: "channel_logo",
}

# ============================================================================
# Fixed Start Time Behavior
# ============================================================================
# ErsatzTV FixedStartTimeBehavior enum
FIXED_START_TIME_BEHAVIOR_MAP = {
    0: "skip",
    1: "fill",
    2: "skip_and_fill",
}

# ============================================================================
# Offline Mode
# ============================================================================
# ErsatzTV OfflineMode enum
OFFLINE_MODE_MAP = {
    0: "offline_image",
    1: "filler",
    2: "last_frame",
}

# ============================================================================
# Subtitle Mode
# ============================================================================
# ErsatzTV SubtitleMode enum
SUBTITLE_MODE_MAP = {
    0: "none",
    1: "default",
    2: "forced",
    3: "all",
}

# ============================================================================
# Music Video Credits Mode
# ============================================================================
MUSIC_VIDEO_CREDITS_MODE_MAP = {
    0: "none",
    1: "artist",
    2: "song",
    3: "artist_song",
}

# ============================================================================
# Helper Functions
# ============================================================================

def convert_enum(value: int | None, enum_map: dict[int, Any], default: Any = None) -> Any:
    """
    Convert an integer enum value to its string representation.
    
    Args:
        value: Integer value from ErsatzTV
        enum_map: Mapping dictionary
        default: Default value if not found
        
    Returns:
        String representation or default
    """
    if value is None:
        return default
    return enum_map.get(value, default)


def reverse_enum(value: str | None, enum_map: dict[int, Any], default: int = 0) -> int:
    """
    Convert a string value back to its integer representation.
    
    Args:
        value: String value
        enum_map: Mapping dictionary
        default: Default integer if not found
        
    Returns:
        Integer representation or default
    """
    if value is None:
        return default
    
    # Create reverse mapping
    reverse_map = {v: k for k, v in enum_map.items()}
    return reverse_map.get(value, default)


# Convenience functions for common conversions
def convert_hardware_acceleration(value: int | None) -> str:
    """Convert ErsatzTV hardware acceleration enum to string."""
    return convert_enum(value, HARDWARE_ACCELERATION_MAP, "none")


def convert_video_format(value: int | None) -> str:
    """Convert ErsatzTV video format enum to string."""
    return convert_enum(value, VIDEO_FORMAT_MAP, "h264")


def convert_audio_format(value: int | None) -> str:
    """Convert ErsatzTV audio format enum to string."""
    return convert_enum(value, AUDIO_FORMAT_MAP, "aac")


def convert_scaling_behavior(value: int | None) -> str:
    """Convert ErsatzTV scaling behavior enum to string."""
    return convert_enum(value, SCALING_BEHAVIOR_MAP, "scale_and_pad")


def convert_streaming_mode(value: int | None) -> str:
    """Convert ErsatzTV streaming mode enum to string."""
    return convert_enum(value, STREAMING_MODE_MAP, "transport_stream_hybrid")


def convert_playback_order(value: int | None) -> str:
    """Convert ErsatzTV playback order enum to string."""
    return convert_enum(value, PLAYBACK_ORDER_MAP, "chronological")


def convert_playback_mode(value: int | None) -> str:
    """Convert ErsatzTV playback mode enum to string."""
    return convert_enum(value, PLAYBACK_MODE_MAP, "flood")


def convert_collection_type(value: int | None) -> str:
    """Convert ErsatzTV collection type enum to string."""
    return convert_enum(value, COLLECTION_TYPE_MAP, "collection")


def convert_deco_mode(value: int | None) -> str:
    """Convert ErsatzTV deco mode enum to string."""
    return convert_enum(value, DECO_MODE_MAP, "inherit")


def convert_watermark_location(value: int | None) -> str:
    """Convert ErsatzTV watermark location enum to string."""
    return convert_enum(value, WATERMARK_LOCATION_MAP, "bottom_right")


def convert_fixed_start_time_behavior(value: int | None) -> str:
    """Convert ErsatzTV fixed start time behavior enum to string."""
    return convert_enum(value, FIXED_START_TIME_BEHAVIOR_MAP, "fill")
