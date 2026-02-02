"""
Base encoder classes for FFmpeg pipeline.

Ported from ErsatzTV EncoderBase.cs and IEncoder.cs.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from exstreamtv.ffmpeg.state.frame_state import FrameState


class StreamKind(Enum):
    """Type of stream being encoded."""

    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"


class EncoderType(Enum):
    """Encoder implementation type."""

    COPY = "copy"
    SOFTWARE = "software"
    VIDEOTOOLBOX = "videotoolbox"
    NVENC = "nvenc"
    QSV = "qsv"
    VAAPI = "vaapi"
    AMF = "amf"
    V4L2M2M = "v4l2m2m"
    RKMPP = "rkmpp"


class BaseEncoder(ABC):
    """
    Abstract base class for FFmpeg encoders.

    Ported from ErsatzTV EncoderBase.cs.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """FFmpeg encoder name (e.g., 'libx264', 'h264_videotoolbox')."""
        pass

    @property
    @abstractmethod
    def kind(self) -> StreamKind:
        """Type of stream this encoder handles."""
        pass

    @property
    def encoder_type(self) -> EncoderType:
        """Type of encoder implementation."""
        return EncoderType.SOFTWARE

    @property
    def global_options(self) -> List[str]:
        """Global FFmpeg options for this encoder."""
        return []

    @property
    def filter_options(self) -> List[str]:
        """Filter options for this encoder."""
        return []

    @property
    def output_options(self) -> List[str]:
        """
        Output options for this encoder.

        Default implementation returns -c:v/-c:a/-c:s with encoder name.
        """
        codec_flag = {
            StreamKind.VIDEO: "-c:v",
            StreamKind.AUDIO: "-c:a",
            StreamKind.SUBTITLE: "-c:s",
        }[self.kind]

        return [codec_flag, self.name]

    def next_state(self, current_state: FrameState) -> FrameState:
        """
        Calculate the next frame state after encoding.

        Args:
            current_state: Current frame state.

        Returns:
            Updated frame state.
        """
        return current_state

    @property
    def filter(self) -> str:
        """Any filter that must be applied for this encoder."""
        return ""
