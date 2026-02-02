"""
Migration Infrastructure Tests

Tests for the enum_maps, schema_mapper, and validators modules.
"""

import pytest
from datetime import datetime, timedelta


class TestEnumMaps:
    """Test ErsatzTV enum conversion maps."""
    
    def test_hardware_acceleration_conversion(self):
        """Test hardware acceleration enum conversion."""
        from exstreamtv.importers.enum_maps import (
            HARDWARE_ACCELERATION_MAP,
            convert_hardware_acceleration,
        )
        
        assert convert_hardware_acceleration(0) == "none"
        assert convert_hardware_acceleration(1) == "nvenc"
        assert convert_hardware_acceleration(2) == "qsv"
        assert convert_hardware_acceleration(3) == "vaapi"
        assert convert_hardware_acceleration(4) == "videotoolbox"
        assert convert_hardware_acceleration(None) == "none"
    
    def test_video_format_conversion(self):
        """Test video format enum conversion."""
        from exstreamtv.importers.enum_maps import (
            VIDEO_FORMAT_MAP,
            convert_video_format,
        )
        
        assert convert_video_format(0) == "h264"
        assert convert_video_format(1) == "hevc"
        assert convert_video_format(2) == "mpeg2video"
        assert convert_video_format(4) == "av1"
    
    def test_audio_format_conversion(self):
        """Test audio format enum conversion."""
        from exstreamtv.importers.enum_maps import convert_audio_format
        
        assert convert_audio_format(0) == "aac"
        assert convert_audio_format(1) == "ac3"
        assert convert_audio_format(3) == "aac_latm"
    
    def test_scaling_behavior_conversion(self):
        """Test scaling behavior enum conversion."""
        from exstreamtv.importers.enum_maps import convert_scaling_behavior
        
        assert convert_scaling_behavior(0) == "scale_and_pad"
        assert convert_scaling_behavior(1) == "stretch"
        assert convert_scaling_behavior(2) == "crop"
    
    def test_streaming_mode_conversion(self):
        """Test streaming mode enum conversion."""
        from exstreamtv.importers.enum_maps import convert_streaming_mode
        
        assert convert_streaming_mode(0) == "transport_stream_hybrid"
        assert convert_streaming_mode(1) == "hls_hybrid"
        assert convert_streaming_mode(3) == "mpeg_ts"
    
    def test_playback_order_conversion(self):
        """Test playback order enum conversion."""
        from exstreamtv.importers.enum_maps import convert_playback_order
        
        assert convert_playback_order(0) == "chronological"
        assert convert_playback_order(1) == "shuffled"
        assert convert_playback_order(2) == "random"
    
    def test_collection_type_conversion(self):
        """Test collection type enum conversion."""
        from exstreamtv.importers.enum_maps import convert_collection_type
        
        assert convert_collection_type(0) == "collection"
        assert convert_collection_type(4) == "multi_collection"
        assert convert_collection_type(5) == "smart_collection"
        assert convert_collection_type(6) == "search"
    
    def test_deco_mode_conversion(self):
        """Test deco mode enum conversion."""
        from exstreamtv.importers.enum_maps import convert_deco_mode
        
        assert convert_deco_mode(0) == "none"
        assert convert_deco_mode(1) == "inherit"
        assert convert_deco_mode(2) == "override"
    
    def test_reverse_enum_conversion(self):
        """Test reverse enum conversion (string to int)."""
        from exstreamtv.importers.enum_maps import (
            HARDWARE_ACCELERATION_MAP,
            reverse_enum,
        )
        
        assert reverse_enum("none", HARDWARE_ACCELERATION_MAP) == 0
        assert reverse_enum("nvenc", HARDWARE_ACCELERATION_MAP) == 1
        assert reverse_enum("unknown", HARDWARE_ACCELERATION_MAP) == 0  # Default
    
    def test_convert_enum_with_default(self):
        """Test enum conversion with custom default."""
        from exstreamtv.importers.enum_maps import (
            HARDWARE_ACCELERATION_MAP,
            convert_enum,
        )
        
        assert convert_enum(999, HARDWARE_ACCELERATION_MAP, "fallback") == "fallback"
        assert convert_enum(None, HARDWARE_ACCELERATION_MAP, "fallback") == "fallback"


class TestSchemaMapper:
    """Test schema field mapping and conversion."""
    
    def test_map_row_basic(self):
        """Test basic row mapping."""
        from exstreamtv.importers.schema_mapper import map_row
        
        field_map = {
            "SourceName": "target_name",
            "SourceValue": "target_value",
        }
        
        row = {
            "SourceName": "Test",
            "SourceValue": 42,
        }
        
        result = map_row(row, field_map)
        
        assert result["target_name"] == "Test"
        assert result["target_value"] == 42
    
    def test_map_row_with_converter(self):
        """Test row mapping with converter function."""
        from exstreamtv.importers.schema_mapper import map_row
        from exstreamtv.importers.enum_maps import convert_hardware_acceleration
        
        field_map = {
            "HardwareAccelerationKind": ("hardware_acceleration", convert_hardware_acceleration),
        }
        
        row = {"HardwareAccelerationKind": 1}
        result = map_row(row, field_map)
        
        assert result["hardware_acceleration"] == "nvenc"
    
    def test_convert_datetime_string(self):
        """Test datetime string conversion."""
        from exstreamtv.importers.schema_mapper import convert_datetime
        
        dt = convert_datetime("2024-01-15T14:30:00")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 14
        assert dt.minute == 30
    
    def test_convert_datetime_already_datetime(self):
        """Test datetime conversion when already a datetime."""
        from exstreamtv.importers.schema_mapper import convert_datetime
        
        original = datetime(2024, 1, 15, 14, 30)
        result = convert_datetime(original)
        
        assert result == original
    
    def test_convert_datetime_none(self):
        """Test datetime conversion with None."""
        from exstreamtv.importers.schema_mapper import convert_datetime
        
        assert convert_datetime(None) is None
    
    def test_convert_time_string(self):
        """Test time string conversion."""
        from exstreamtv.importers.schema_mapper import convert_time
        
        result = convert_time("14:30:00")
        assert result == "14:30:00"
    
    def test_convert_time_timedelta(self):
        """Test time conversion from timedelta."""
        from exstreamtv.importers.schema_mapper import convert_time
        
        td = timedelta(hours=14, minutes=30, seconds=45)
        result = convert_time(td)
        
        assert result == "14:30:45"
    
    def test_convert_duration_to_minutes(self):
        """Test duration to minutes conversion."""
        from exstreamtv.importers.schema_mapper import convert_duration_to_minutes
        
        assert convert_duration_to_minutes(90) == 90
        assert convert_duration_to_minutes(timedelta(hours=1, minutes=30)) == 90
        assert convert_duration_to_minutes("01:30:00") == 90
    
    def test_generate_unique_id(self):
        """Test UUID generation."""
        from exstreamtv.importers.schema_mapper import generate_unique_id
        import uuid
        
        uid = generate_unique_id()
        
        # Should be valid UUID
        parsed = uuid.UUID(uid)
        assert str(parsed) == uid
    
    def test_convert_json_field_list(self):
        """Test JSON field conversion for lists."""
        from exstreamtv.importers.schema_mapper import convert_json_field
        
        result = convert_json_field(["a", "b", "c"])
        assert result == '["a", "b", "c"]'
    
    def test_convert_json_field_already_json(self):
        """Test JSON field conversion when already JSON string."""
        from exstreamtv.importers.schema_mapper import convert_json_field
        
        result = convert_json_field('{"key": "value"}')
        assert result == '{"key": "value"}'
    
    def test_parse_json_field(self):
        """Test JSON field parsing."""
        from exstreamtv.importers.schema_mapper import parse_json_field
        
        result = parse_json_field('["a", "b", "c"]')
        assert result == ["a", "b", "c"]
    
    def test_convert_bitrate(self):
        """Test bitrate conversion."""
        from exstreamtv.importers.schema_mapper import convert_bitrate
        
        assert convert_bitrate("4000k") == "4000k"
        assert convert_bitrate(4000) == "4000k"
        assert convert_bitrate(4000000) == "4000k"  # Convert bps to kbps


class TestValidators:
    """Test migration validators."""
    
    def test_validation_result_basic(self):
        """Test ValidationResult basic operations."""
        from exstreamtv.importers.validators import ValidationResult
        
        result = ValidationResult()
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_validation_result_add_error(self):
        """Test adding error to ValidationResult."""
        from exstreamtv.importers.validators import ValidationResult
        
        result = ValidationResult()
        result.add_error("Test error")
        
        assert result.is_valid is False
        assert "Test error" in result.errors
    
    def test_validation_result_add_warning(self):
        """Test adding warning (doesn't invalidate)."""
        from exstreamtv.importers.validators import ValidationResult
        
        result = ValidationResult()
        result.add_warning("Test warning")
        
        assert result.is_valid is True
        assert "Test warning" in result.warnings
    
    def test_validation_result_merge(self):
        """Test merging ValidationResults."""
        from exstreamtv.importers.validators import ValidationResult
        
        result1 = ValidationResult()
        result1.add_info("Info 1")
        result1.counts["channels"] = 10
        
        result2 = ValidationResult()
        result2.add_error("Error 1")
        result2.counts["playouts"] = 5
        
        result1.merge(result2)
        
        assert result1.is_valid is False
        assert "Info 1" in result1.info
        assert "Error 1" in result1.errors
        assert result1.counts["channels"] == 10
        assert result1.counts["playouts"] == 5
    
    def test_validation_result_to_dict(self):
        """Test ValidationResult to dict conversion."""
        from exstreamtv.importers.validators import ValidationResult
        
        result = ValidationResult()
        result.add_info("Test info")
        result.add_warning("Test warning")
        result.counts["items"] = 42
        
        result_dict = result.to_dict()
        
        assert result_dict["is_valid"] is True
        assert result_dict["error_count"] == 0
        assert result_dict["warning_count"] == 1
        assert "Test info" in result_dict["info"]


class TestFFmpegProfileFieldMap:
    """Test FFmpeg profile field mapping."""
    
    def test_ffmpeg_profile_mapping(self):
        """Test complete FFmpeg profile mapping."""
        from exstreamtv.importers.schema_mapper import (
            FFMPEG_PROFILE_FIELD_MAP,
            map_row,
        )
        
        ersatztv_row = {
            "Id": 1,
            "Name": "Default Profile",
            "HardwareAccelerationKind": 1,  # nvenc
            "VideoFormat": 0,  # h264
            "AudioFormat": 0,  # aac
            "VideoBitrate": "4000k",
            "AudioBitrate": "128k",
        }
        
        result = map_row(ersatztv_row, FFMPEG_PROFILE_FIELD_MAP)
        
        assert result["id"] == 1
        assert result["name"] == "Default Profile"
        assert result["hardware_acceleration"] == "nvenc"
        assert result["video_format"] == "h264"
        assert result["audio_format"] == "aac"


class TestChannelFieldMap:
    """Test Channel field mapping."""
    
    def test_channel_mapping(self):
        """Test complete channel mapping."""
        from exstreamtv.importers.schema_mapper import (
            CHANNEL_FIELD_MAP,
            map_row,
        )
        
        ersatztv_row = {
            "Id": 1,
            "UniqueId": "550e8400-e29b-41d4-a716-446655440000",
            "Number": "100",
            "Name": "Test Channel",
            "StreamingMode": 0,  # transport_stream_hybrid
        }
        
        result = map_row(ersatztv_row, CHANNEL_FIELD_MAP)
        
        assert result["id"] == 1
        assert result["unique_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert result["number"] == "100"
        assert result["name"] == "Test Channel"
        assert result["streaming_mode"] == "transport_stream_hybrid"


class TestProgramScheduleItemFieldMap:
    """Test ProgramScheduleItem field mapping."""
    
    def test_schedule_item_mapping(self):
        """Test schedule item mapping with marathon settings."""
        from exstreamtv.importers.schema_mapper import (
            PROGRAM_SCHEDULE_ITEM_FIELD_MAP,
            map_row,
        )
        
        ersatztv_row = {
            "Id": 1,
            "ProgramScheduleId": 1,
            "Index": 1,
            "CollectionType": 5,  # smart_collection
            "PlaybackMode": 3,    # flood
            "PlaybackOrder": 0,   # chronological
        }
        
        result = map_row(ersatztv_row, PROGRAM_SCHEDULE_ITEM_FIELD_MAP)
        
        assert result["id"] == 1
        assert result["schedule_id"] == 1
        assert result["position"] == 1
        assert result["collection_type"] == "smart_collection"
        assert result["playback_mode"] == "flood"
        assert result["playback_order"] == "chronological"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
