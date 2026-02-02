"""
Audio encoders for FFmpeg pipeline.

Ported from ErsatzTV audio encoder implementations.
"""

from dataclasses import dataclass
from typing import List, Optional

from exstreamtv.ffmpeg.encoders.base import BaseEncoder, EncoderType, StreamKind
from exstreamtv.ffmpeg.state.frame_state import FrameState


@dataclass
class EncoderCopyAudio(BaseEncoder):
    """Copy audio stream without re-encoding."""

    @property
    def name(self) -> str:
        return "copy"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.AUDIO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.COPY


@dataclass
class EncoderAac(BaseEncoder):
    """
    AAC audio encoder.

    Ported from ErsatzTV EncoderAac.cs.
    """

    bitrate: str = "192k"
    channels: int = 2
    sample_rate: int = 48000

    @property
    def name(self) -> str:
        return "aac"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.AUDIO

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:a", self.name,
            "-b:a", self.bitrate,
            "-ac", str(self.channels),
            "-ar", str(self.sample_rate),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            audio_format="aac",
            audio_channels=self.channels,
            audio_sample_rate=self.sample_rate,
        )


@dataclass
class EncoderAc3(BaseEncoder):
    """
    AC3/Dolby Digital audio encoder.

    Ported from ErsatzTV EncoderAc3.cs.
    """

    bitrate: str = "384k"
    channels: int = 6  # 5.1

    @property
    def name(self) -> str:
        return "ac3"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.AUDIO

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:a", self.name,
            "-b:a", self.bitrate,
            "-ac", str(self.channels),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            audio_format="ac3",
            audio_channels=self.channels,
        )


@dataclass
class EncoderPcmS16Le(BaseEncoder):
    """
    PCM signed 16-bit little-endian audio encoder.

    Ported from ErsatzTV EncoderPcmS16Le.cs.
    """

    sample_rate: int = 48000
    channels: int = 2

    @property
    def name(self) -> str:
        return "pcm_s16le"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.AUDIO

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:a", self.name,
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            audio_format="pcm_s16le",
            audio_channels=self.channels,
            audio_sample_rate=self.sample_rate,
        )
