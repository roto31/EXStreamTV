"""
EXStreamTV FFmpeg Module

Comprehensive FFmpeg pipeline with ErsatzTV-style architecture.

Features:
- Hardware capability detection (VideoToolbox, NVENC, QSV, VAAPI, AMF)
- State-tracked filter chains
- Multiple encoder implementations
- Bug-fix preservation from StreamTV

Submodules:
- state: Frame and pipeline state management
- filters: Video and audio filters
- encoders: Video and audio encoders
- capabilities: Hardware detection
- pipeline: Command generation
"""

# State management
from exstreamtv.ffmpeg.state import (
    FFmpegState,
    FrameDataLocation,
    FrameSize,
    FrameState,
    HardwareAccelerationMode,
    OutputFormatKind,
)

# Filters
from exstreamtv.ffmpeg.filters import (
    AudioNormalizeFilter,
    AudioPadFilter,
    AudioResampleFilter,
    BaseFilter,
    CropFilter,
    DeinterlaceFilter,
    FilterChain,
    HardwareDownloadFilter,
    HardwareUploadFilter,
    PadFilter,
    PixelFormatFilter,
    RealtimeFilter,
    ScaleFilter,
    TonemapFilter,
    WatermarkFilter,
)

# Encoders
from exstreamtv.ffmpeg.encoders import (
    BaseEncoder,
    EncoderAac,
    EncoderAc3,
    EncoderCopyAudio,
    EncoderCopyVideo,
    EncoderH264Amf,
    EncoderH264Nvenc,
    EncoderH264Qsv,
    EncoderH264Vaapi,
    EncoderH264VideoToolbox,
    EncoderHevcAmf,
    EncoderHevcNvenc,
    EncoderHevcQsv,
    EncoderHevcVaapi,
    EncoderHevcVideoToolbox,
    EncoderLibx264,
    EncoderLibx265,
    EncoderPcmS16Le,
    EncoderType,
    StreamKind,
)

# Pipeline
from exstreamtv.ffmpeg.pipeline import FFmpegPipeline

# Capabilities
from exstreamtv.ffmpeg.capabilities import HardwareCapabilityDetector

# Stream pickers (Tunarr-style)
from exstreamtv.ffmpeg.subtitle_picker import (
    SubtitleStreamPicker,
    SubtitleStream,
    SubtitlePreferences,
    SubtitleType,
    get_subtitle_picker,
)
from exstreamtv.ffmpeg.audio_picker import (
    AudioStreamPicker,
    AudioStream,
    AudioPreferences,
    AudioLayout,
    get_audio_picker,
)

__all__ = [
    # State
    "FFmpegState",
    "FrameDataLocation",
    "FrameSize",
    "FrameState",
    "HardwareAccelerationMode",
    "OutputFormatKind",
    # Filters - Base
    "BaseFilter",
    "FilterChain",
    # Filters - Video
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
    # Filters - Audio
    "AudioNormalizeFilter",
    "AudioPadFilter",
    "AudioResampleFilter",
    # Encoders - Base
    "BaseEncoder",
    "EncoderType",
    "StreamKind",
    # Encoders - Video Copy
    "EncoderCopyVideo",
    # Encoders - Video Software
    "EncoderLibx264",
    "EncoderLibx265",
    # Encoders - Video Hardware
    "EncoderH264VideoToolbox",
    "EncoderHevcVideoToolbox",
    "EncoderH264Nvenc",
    "EncoderHevcNvenc",
    "EncoderH264Qsv",
    "EncoderHevcQsv",
    "EncoderH264Vaapi",
    "EncoderHevcVaapi",
    "EncoderH264Amf",
    "EncoderHevcAmf",
    # Encoders - Audio
    "EncoderAac",
    "EncoderAc3",
    "EncoderCopyAudio",
    "EncoderPcmS16Le",
    # Pipeline
    "FFmpegPipeline",
    # Capabilities
    "HardwareCapabilityDetector",
    # Stream pickers (Tunarr)
    "SubtitleStreamPicker",
    "SubtitleStream",
    "SubtitlePreferences",
    "SubtitleType",
    "get_subtitle_picker",
    "AudioStreamPicker",
    "AudioStream",
    "AudioPreferences",
    "AudioLayout",
    "get_audio_picker",
]
