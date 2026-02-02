"""
EXStreamTV FFmpeg Filters

Video and audio filter implementations ported from ErsatzTV.
"""

from exstreamtv.ffmpeg.filters.base import BaseFilter, FilterChain
from exstreamtv.ffmpeg.filters.video import (
    CropFilter,
    DeinterlaceFilter,
    HardwareDownloadFilter,
    HardwareUploadFilter,
    PadFilter,
    PixelFormatFilter,
    RealtimeFilter,
    ScaleFilter,
    TonemapFilter,
    WatermarkFilter,
)
from exstreamtv.ffmpeg.filters.audio import (
    AudioNormalizeFilter,
    AudioPadFilter,
    AudioResampleFilter,
)

__all__ = [
    # Base
    "BaseFilter",
    "FilterChain",
    # Video
    "CropFilter",
    "DeinterlaceFilter",
    "HardwareDownloadFilter",
    "HardwareUploadFilter",
    "PadFilter",
    "PixelFormatFilter",
    "RealtimeFilter",
    "ScaleFilter",
    "TonemapFilter",
    "WatermarkFilter",
    # Audio
    "AudioNormalizeFilter",
    "AudioPadFilter",
    "AudioResampleFilter",
]
