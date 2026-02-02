"""
EXStreamTV FFmpeg State Management

Ported from ErsatzTV with Python dataclasses.
"""

from exstreamtv.ffmpeg.state.frame_state import FrameDataLocation, FrameSize, FrameState
from exstreamtv.ffmpeg.state.ffmpeg_state import FFmpegState, HardwareAccelerationMode, OutputFormatKind

__all__ = [
    "FFmpegState",
    "FrameDataLocation",
    "FrameSize",
    "FrameState",
    "HardwareAccelerationMode",
    "OutputFormatKind",
]
