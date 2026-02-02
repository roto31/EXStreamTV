"""
FFmpeg pipeline state configuration.

Ported from ErsatzTV FFmpegState.cs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class HardwareAccelerationMode(Enum):
    """Hardware acceleration modes."""

    NONE = "none"
    NVENC = "nvenc"
    QSV = "qsv"
    VAAPI = "vaapi"
    VIDEOTOOLBOX = "videotoolbox"
    AMF = "amf"
    V4L2M2M = "v4l2m2m"
    RKMPP = "rkmpp"


class OutputFormatKind(Enum):
    """Output format types."""

    MPEGTS = "mpegts"
    HLS = "hls"
    MKV = "mkv"
    MP4 = "mp4"


@dataclass
class FFmpegState:
    """
    Complete FFmpeg pipeline state configuration.

    Ported from ErsatzTV FFmpegState.cs with Python conventions.
    """

    # Debug options
    save_report: bool = False
    is_troubleshooting: bool = False

    # Hardware acceleration
    decoder_hardware_acceleration: HardwareAccelerationMode = HardwareAccelerationMode.NONE
    encoder_hardware_acceleration: HardwareAccelerationMode = HardwareAccelerationMode.NONE

    # VAAPI specific
    vaapi_driver: Optional[str] = None
    vaapi_device: Optional[str] = None

    # Timing
    start_time: Optional[float] = None  # seconds
    finish_time: Optional[float] = None  # seconds
    pts_offset: float = 0.0

    # Metadata
    do_not_map_metadata: bool = False
    metadata_service_provider: str = "EXStreamTV"
    metadata_service_name: Optional[str] = None
    metadata_audio_language: Optional[str] = None
    metadata_subtitle_language: Optional[str] = None
    metadata_subtitle_title: Optional[str] = None

    # Output format
    output_format: OutputFormatKind = OutputFormatKind.MPEGTS

    # HLS options
    hls_playlist_path: Optional[str] = None
    hls_segment_template: Optional[str] = None
    hls_init_template: Optional[str] = None
    hls_segment_options: Optional[str] = None

    # Performance
    thread_count: Optional[int] = None
    qsv_extra_hardware_frames: int = 64

    # Special modes
    is_song_with_progress: bool = False
    is_hdr_tonemap: bool = False
    tonemap_algorithm: str = "linear"

    @classmethod
    def for_concat(cls, channel_name: str, save_report: bool = False) -> "FFmpegState":
        """Create state for concat playlist mode."""
        return cls(
            save_report=save_report,
            decoder_hardware_acceleration=HardwareAccelerationMode.NONE,
            encoder_hardware_acceleration=HardwareAccelerationMode.NONE,
            do_not_map_metadata=True,
            metadata_service_provider="EXStreamTV",
            metadata_service_name=channel_name,
            output_format=OutputFormatKind.MPEGTS,
        )

    @classmethod
    def for_transcode(
        cls,
        decoder_hw: HardwareAccelerationMode = HardwareAccelerationMode.NONE,
        encoder_hw: HardwareAccelerationMode = HardwareAccelerationMode.NONE,
        channel_name: Optional[str] = None,
    ) -> "FFmpegState":
        """Create state for transcoding mode."""
        return cls(
            decoder_hardware_acceleration=decoder_hw,
            encoder_hardware_acceleration=encoder_hw,
            do_not_map_metadata=True,
            metadata_service_provider="EXStreamTV",
            metadata_service_name=channel_name,
            output_format=OutputFormatKind.MPEGTS,
        )

    @property
    def uses_hardware_decoder(self) -> bool:
        """Check if using hardware decoder."""
        return self.decoder_hardware_acceleration != HardwareAccelerationMode.NONE

    @property
    def uses_hardware_encoder(self) -> bool:
        """Check if using hardware encoder."""
        return self.encoder_hardware_acceleration != HardwareAccelerationMode.NONE

    @property
    def is_intel_vaapi_or_qsv(self) -> bool:
        """Check if using Intel VAAPI or QSV."""
        return self.encoder_hardware_acceleration in (
            HardwareAccelerationMode.VAAPI,
            HardwareAccelerationMode.QSV,
        )
