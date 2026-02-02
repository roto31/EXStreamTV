"""
EXStreamTV FFmpeg Encoders

Video and audio encoder implementations ported from ErsatzTV.
"""

from exstreamtv.ffmpeg.encoders.base import BaseEncoder, EncoderType, StreamKind
from exstreamtv.ffmpeg.encoders.video import (
    EncoderCopyVideo,
    EncoderH264VideoToolbox,
    EncoderHevcVideoToolbox,
    EncoderLibx264,
    EncoderLibx265,
    EncoderH264Nvenc,
    EncoderHevcNvenc,
    EncoderH264Qsv,
    EncoderHevcQsv,
    EncoderH264Vaapi,
    EncoderHevcVaapi,
    EncoderH264Amf,
    EncoderHevcAmf,
)
from exstreamtv.ffmpeg.encoders.audio import (
    EncoderAac,
    EncoderAc3,
    EncoderCopyAudio,
    EncoderPcmS16Le,
)

__all__ = [
    # Base
    "BaseEncoder",
    "EncoderType",
    "StreamKind",
    # Video - Software
    "EncoderCopyVideo",
    "EncoderLibx264",
    "EncoderLibx265",
    # Video - VideoToolbox (macOS)
    "EncoderH264VideoToolbox",
    "EncoderHevcVideoToolbox",
    # Video - NVENC (NVIDIA)
    "EncoderH264Nvenc",
    "EncoderHevcNvenc",
    # Video - QSV (Intel)
    "EncoderH264Qsv",
    "EncoderHevcQsv",
    # Video - VAAPI (Linux)
    "EncoderH264Vaapi",
    "EncoderHevcVaapi",
    # Video - AMF (AMD)
    "EncoderH264Amf",
    "EncoderHevcAmf",
    # Audio
    "EncoderAac",
    "EncoderAc3",
    "EncoderCopyAudio",
    "EncoderPcmS16Le",
]
