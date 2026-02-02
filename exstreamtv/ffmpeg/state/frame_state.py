"""
Frame state tracking for FFmpeg pipeline.

Ported from ErsatzTV FrameState.cs and FrameSize.cs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FrameDataLocation(Enum):
    """Where the frame data resides."""

    SOFTWARE = "software"
    HARDWARE = "hardware"


@dataclass(frozen=True)
class FrameSize:
    """Video frame dimensions."""

    width: int
    height: int

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"

    @classmethod
    def from_string(cls, size_str: str) -> "FrameSize":
        """Parse from 'WxH' format."""
        parts = size_str.lower().split("x")
        return cls(width=int(parts[0]), height=int(parts[1]))

    @property
    def aspect_ratio(self) -> float:
        """Calculate aspect ratio."""
        return self.width / self.height if self.height > 0 else 0


@dataclass
class FrameState:
    """
    Tracks the current state of video frames through the FFmpeg pipeline.

    Ported from ErsatzTV FrameState.cs.
    """

    # Frame dimensions
    scaled_size: Optional[FrameSize] = None
    padded_size: Optional[FrameSize] = None
    cropped_size: Optional[FrameSize] = None

    # Pixel format
    pixel_format: Optional[str] = None

    # Data location
    frame_data_location: FrameDataLocation = FrameDataLocation.SOFTWARE

    # Video properties
    video_format: Optional[str] = None  # h264, hevc, etc.
    is_anamorphic: bool = False
    is_interlaced: bool = False

    # Color space
    color_range: Optional[str] = None  # limited, full
    color_space: Optional[str] = None  # bt709, bt2020, etc.
    color_transfer: Optional[str] = None  # sdr, hdr10, etc.
    color_primaries: Optional[str] = None

    # Audio
    audio_format: Optional[str] = None
    audio_channels: int = 2
    audio_sample_rate: int = 48000

    def with_updates(self, **kwargs) -> "FrameState":
        """Create a new FrameState with updated values."""
        current = {
            "scaled_size": self.scaled_size,
            "padded_size": self.padded_size,
            "cropped_size": self.cropped_size,
            "pixel_format": self.pixel_format,
            "frame_data_location": self.frame_data_location,
            "video_format": self.video_format,
            "is_anamorphic": self.is_anamorphic,
            "is_interlaced": self.is_interlaced,
            "color_range": self.color_range,
            "color_space": self.color_space,
            "color_transfer": self.color_transfer,
            "color_primaries": self.color_primaries,
            "audio_format": self.audio_format,
            "audio_channels": self.audio_channels,
            "audio_sample_rate": self.audio_sample_rate,
        }
        current.update(kwargs)
        return FrameState(**current)

    @property
    def is_hdr(self) -> bool:
        """Check if content is HDR."""
        hdr_transfers = {"smpte2084", "arib-std-b67", "bt2020-10", "bt2020-12"}
        return self.color_transfer in hdr_transfers if self.color_transfer else False

    @property
    def needs_tonemap(self) -> bool:
        """Check if HDR tonemapping is needed for SDR output."""
        return self.is_hdr
