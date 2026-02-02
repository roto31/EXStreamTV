"""
Schema Mapper for ErsatzTV and StreamTV Migration

Provides field mapping dictionaries and type conversion functions
for translating between ErsatzTV/StreamTV schemas and EXStreamTV.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from exstreamtv.importers.enum_maps import (
    convert_audio_format,
    convert_collection_type,
    convert_deco_mode,
    convert_fixed_start_time_behavior,
    convert_hardware_acceleration,
    convert_playback_mode,
    convert_playback_order,
    convert_scaling_behavior,
    convert_streaming_mode,
    convert_video_format,
    convert_watermark_location,
)

logger = logging.getLogger(__name__)


# ============================================================================
# FFmpeg Profile Field Mapping
# ============================================================================
FFMPEG_PROFILE_FIELD_MAP = {
    # ErsatzTV field -> EXStreamTV field
    "Id": "id",
    "Name": "name",
    "ResolutionId": "resolution_id",
    "ThreadCount": "thread_count",
    "HardwareAccelerationKind": ("hardware_acceleration", convert_hardware_acceleration),
    "VaapiDriver": "vaapi_driver",
    "VaapiDevice": "vaapi_device",
    "QsvExtraHardwareFrames": "qsv_extra_hardware_frames",
    "VideoFormat": ("video_format", convert_video_format),
    "VideoProfile": "video_profile",
    "AllowBFrames": "allow_b_frames",
    "BitDepth": "bit_depth",
    "VideoBitrate": "video_bitrate",
    "VideoBufferSize": "video_buffer_size",
    "AudioFormat": ("audio_format", convert_audio_format),
    "AudioBitrate": "audio_bitrate",
    "AudioChannels": "audio_channels",
    "AudioSampleRate": "audio_sample_rate",
    "AudioBufferSize": "audio_buffer_size",
    "ScalingBehavior": ("scaling_behavior", convert_scaling_behavior),
    "NormalizeFramerate": "normalize_framerate",
    "DeinterlaceVideo": "deinterlace_video",
    "NormalizeLoudnessMode": "normalize_loudness_mode",
    "TargetLoudness": "target_loudness",
}


# ============================================================================
# Channel Field Mapping
# ============================================================================
CHANNEL_FIELD_MAP = {
    "Id": "id",
    "UniqueId": "unique_id",
    "Number": "number",
    "Name": "name",
    "Group": "group",
    "Categories": "categories",
    "SortNumber": "sort_number",
    "FfmpegProfileId": "ffmpeg_profile_id",
    "FallbackFillerId": "fallback_filler_id",
    "WatermarkId": "watermark_id",
    "StreamingMode": ("streaming_mode", convert_streaming_mode),
    "PreferChannelLogo": "prefer_channel_logo",
    "SubtitleMode": "subtitle_mode",
    "PreferredAudioLanguageCode": "preferred_audio_language_code",
    "PreferredAudioTitle": "preferred_audio_title",
    "PreferredSubtitleLanguageCode": "preferred_subtitle_language_code",
    "MusicVideoCreditsMode": "music_video_credits_mode",
    "MusicVideoCreditsTemplate": "music_video_credits_template",
}


# ============================================================================
# Program Schedule Field Mapping
# ============================================================================
PROGRAM_SCHEDULE_FIELD_MAP = {
    "Id": "id",
    "Name": "name",
    "KeepMultiPartEpisodes": "keep_multi_part_episodes",
    "TreatCollectionsAsShows": "treat_collections_as_shows",
    "ShuffleScheduleItems": "shuffle_schedule_items",
    "RandomStartPoint": "random_start_point",
    "FixedStartTimeBehavior": ("fixed_start_time_behavior", convert_fixed_start_time_behavior),
}


# ============================================================================
# Program Schedule Item Field Mapping
# ============================================================================
PROGRAM_SCHEDULE_ITEM_FIELD_MAP = {
    "Id": "id",
    "ProgramScheduleId": "schedule_id",
    "Index": "position",
    "CollectionType": ("collection_type", convert_collection_type),
    "CollectionId": "collection_id",
    "MultiCollectionId": "multi_collection_id",
    "SmartCollectionId": "smart_collection_id",
    "PlaybackMode": ("playback_mode", convert_playback_mode),
    "PlaybackOrder": ("playback_order", convert_playback_order),
    "MultipleCount": "multiple_count",
    "PlayoutDuration": "playout_duration_minutes",
    "CustomTitle": "custom_title",
    "GuideMode": "guide_mode",
    "PreRollFillerId": "pre_roll_filler_id",
    "MidRollFillerId": "mid_roll_filler_id",
    "PostRollFillerId": "post_roll_filler_id",
    "TailFillerId": "tail_filler_id",
    "FallbackFillerId": "fallback_filler_id",
}


# ============================================================================
# Playout Field Mapping
# ============================================================================
PLAYOUT_FIELD_MAP = {
    "Id": "id",
    "ChannelId": "channel_id",
    "ProgramScheduleId": "program_schedule_id",
    "TemplateId": "template_id",
    "DecoId": "deco_id",
    "ScheduleKind": "schedule_kind",
    "ExternalJsonFile": "schedule_file",
    "Seed": "seed",
}


# ============================================================================
# Block Field Mapping
# ============================================================================
BLOCK_FIELD_MAP = {
    "Id": "id",
    "BlockGroupId": "group_id",
    "Name": "name",
    "StartTime": "start_time",
    "DurationMinutes": "duration_minutes",
    "Minutes": "minutes",
    "DaysOfWeek": "days_of_week",
    "StopScheduling": "stop_scheduling",
}


# ============================================================================
# Block Item Field Mapping
# ============================================================================
BLOCK_ITEM_FIELD_MAP = {
    "Id": "id",
    "BlockId": "block_id",
    "Index": "position",
    "CollectionType": ("collection_type", convert_collection_type),
    "CollectionId": "collection_id",
    "MultiCollectionId": "multi_collection_id",
    "SmartCollectionId": "smart_collection_id",
    "PlaybackOrder": ("playback_order", convert_playback_order),
    "IncludeInGuide": "include_in_guide",
    "DisableWatermarks": "disable_watermarks",
}


# ============================================================================
# Deco Field Mapping
# ============================================================================
DECO_FIELD_MAP = {
    "Id": "id",
    "Name": "name",
    "WatermarkMode": ("watermark_mode", convert_deco_mode),
    "WatermarkId": "watermark_id",
    "GraphicsElementsMode": ("graphics_elements_mode", convert_deco_mode),
    "BreakContentMode": ("break_content_mode", convert_deco_mode),
    "DefaultFillerMode": ("default_filler_mode", convert_deco_mode),
    "DefaultFillerCollectionId": "default_filler_collection_id",
    "DefaultFillerTrimToFit": "default_filler_trim_to_fit",
    "DeadAirFallbackMode": ("dead_air_fallback_mode", convert_deco_mode),
    "DeadAirFallbackCollectionId": "dead_air_fallback_collection_id",
}


# ============================================================================
# Watermark Field Mapping
# ============================================================================
WATERMARK_FIELD_MAP = {
    "Id": "id",
    "Name": "name",
    "Image": "image",
    "ImagePath": "image_path",
    "Mode": "mode",
    "ImageSource": "image_source",
    "Location": ("location", convert_watermark_location),
    "Size": "size",
    "WidthPercent": "width_percent",
    "HorizontalMarginPercent": "horizontal_margin_percent",
    "VerticalMarginPercent": "vertical_margin_percent",
    "FrequencyMinutes": "frequency_minutes",
    "DurationSeconds": "duration_seconds",
    "Opacity": "opacity",
    "PlaceWithinSourceContent": "place_within_source_content",
}


# ============================================================================
# Filler Preset Field Mapping
# ============================================================================
FILLER_PRESET_FIELD_MAP = {
    "Id": "id",
    "Name": "name",
    "FillerKind": "filler_kind",
    "FillerMode": "filler_mode",
    "Count": "count",
    "Duration": "duration_seconds",
    "PadToNearestMinute": "pad_to_minutes",
    "PlaybackOrder": ("playback_order", convert_playback_order),
    "AllowWatermarks": "allow_watermarks",
    "CollectionId": "collection_id",
    "SmartCollectionId": "smart_collection_id",
    "MultiCollectionId": "multi_collection_id",
}


# ============================================================================
# Plex Library Field Mapping
# ============================================================================
PLEX_LIBRARY_FIELD_MAP = {
    # Combined from PlexMediaSource, PlexConnection, Library tables
    "ServerName": "name",
    "Uri": "server_url",
    "ClientIdentifier": "client_identifier",
    "Key": "plex_library_key",
    "LibraryName": "plex_library_name",
    "MediaKind": "library_type",
}


# ============================================================================
# Media Item Field Mapping
# ============================================================================
MEDIA_ITEM_FIELD_MAP = {
    "Id": "id",
    "Title": "title",
    "PlexKey": "external_id",
    "Year": "year",
    "ContentRating": "content_rating",
    "Plot": "description",
    "Tagline": "tagline",
    "ReleaseDate": "release_date",
    "EpisodeNumber": "episode_number",
    "SeasonNumber": "season_number",
}


# ============================================================================
# Media File Field Mapping
# ============================================================================
MEDIA_FILE_FIELD_MAP = {
    "Id": "id",
    "Path": "path",
    "Duration": "duration_seconds",
    "Width": "width",
    "Height": "height",
}


# ============================================================================
# Helper Functions
# ============================================================================

def map_row(row: dict[str, Any], field_map: dict[str, Any]) -> dict[str, Any]:
    """
    Map a database row using a field mapping dictionary.
    
    Args:
        row: Source row as dictionary
        field_map: Field mapping dictionary
        
    Returns:
        Mapped dictionary with EXStreamTV field names
    """
    result = {}
    
    for source_field, target in field_map.items():
        if source_field not in row:
            continue
            
        value = row[source_field]
        
        if isinstance(target, tuple):
            # Tuple means (field_name, converter_function)
            target_field, converter = target
            try:
                value = converter(value)
            except Exception as e:
                logger.warning(f"Error converting {source_field}: {e}")
        else:
            target_field = target
        
        result[target_field] = value
    
    return result


def convert_datetime(value: Any) -> datetime | None:
    """Convert various datetime formats to Python datetime."""
    if value is None:
        return None
    
    if isinstance(value, datetime):
        return value
    
    if isinstance(value, str):
        # Try various formats
        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse datetime: {value}")
        return None
    
    # SQLite might return as float (Unix timestamp)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (ValueError, OSError):
            return None
    
    return None


def convert_time(value: Any) -> str | None:
    """Convert time value to HH:MM:SS string."""
    if value is None:
        return None
    
    if isinstance(value, str):
        # Already a string, validate format
        if ":" in value:
            return value
        return None
    
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    if isinstance(value, (int, float)):
        # Assume it's total seconds
        total_seconds = int(value)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    return None


def convert_duration_to_minutes(value: Any) -> int | None:
    """Convert duration value to minutes."""
    if value is None:
        return None
    
    if isinstance(value, int):
        return value
    
    if isinstance(value, timedelta):
        return int(value.total_seconds() / 60)
    
    if isinstance(value, str):
        # Try to parse HH:MM:SS
        try:
            parts = value.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 60 + minutes + (1 if seconds >= 30 else 0)
            elif len(parts) == 2:
                hours, minutes = map(int, parts)
                return hours * 60 + minutes
        except ValueError:
            pass
    
    return None


def generate_unique_id() -> str:
    """Generate a new UUID for channel unique_id."""
    return str(uuid.uuid4())


def convert_json_field(value: Any) -> str | None:
    """Convert a value to JSON string for storage."""
    if value is None:
        return None
    
    if isinstance(value, str):
        # Already a string, validate it's valid JSON
        try:
            json.loads(value)
            return value
        except json.JSONDecodeError:
            # Not valid JSON, wrap it
            return json.dumps([value])
    
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    
    return json.dumps(value)


def parse_json_field(value: str | None) -> Any:
    """Parse a JSON string field."""
    if value is None:
        return None
    
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def convert_bitrate(value: Any) -> str:
    """Convert bitrate to string format (e.g., '4000k')."""
    if value is None:
        return "4000k"
    
    if isinstance(value, str):
        if value.endswith(("k", "K", "m", "M")):
            return value.lower()
        return f"{value}k"
    
    if isinstance(value, int):
        if value > 10000:
            # Probably in bps, convert to kbps
            return f"{value // 1000}k"
        return f"{value}k"
    
    return "4000k"
