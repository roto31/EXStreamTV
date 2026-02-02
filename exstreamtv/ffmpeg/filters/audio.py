"""
Audio filters for FFmpeg pipeline.

Ported from ErsatzTV audio filter implementations.
"""

from dataclasses import dataclass
from typing import Optional

from exstreamtv.ffmpeg.filters.base import BaseFilter
from exstreamtv.ffmpeg.state.frame_state import FrameState


@dataclass
class AudioNormalizeFilter(BaseFilter):
    """
    Normalize audio loudness.

    Ported from ErsatzTV NormalizeLoudnessFilter.cs.
    """

    target_lufs: float = -24.0  # Target loudness in LUFS
    target_lra: float = 7.0  # Loudness range
    target_tp: float = -2.0  # True peak limit

    @property
    def filter_string(self) -> str:
        return (
            f"loudnorm=I={self.target_lufs}:"
            f"LRA={self.target_lra}:"
            f"TP={self.target_tp}:"
            f"print_format=summary"
        )

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state  # Audio normalization doesn't change tracked state


@dataclass
class AudioResampleFilter(BaseFilter):
    """
    Resample audio to target sample rate and channels.

    Ported from ErsatzTV AudioResampleFilter.cs.
    """

    sample_rate: int = 48000
    channels: int = 2
    channel_layout: str = "stereo"  # mono, stereo, 5.1, 7.1

    @property
    def filter_string(self) -> str:
        return f"aresample={self.sample_rate},aformat=channel_layouts={self.channel_layout}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            audio_sample_rate=self.sample_rate,
            audio_channels=self.channels,
        )


@dataclass
class AudioPadFilter(BaseFilter):
    """
    Pad audio with silence.

    Ported from ErsatzTV AudioPadFilter.cs.
    """

    whole_len: Optional[float] = None  # Total length in seconds
    pad_len: Optional[float] = None  # Amount to pad in seconds
    pad_dur: Optional[str] = None  # Duration string (e.g., "00:00:01")
    packet_size: int = 2048

    @property
    def filter_string(self) -> str:
        parts = ["apad"]

        if self.whole_len:
            parts.append(f"whole_len={int(self.whole_len * 48000)}")  # Assuming 48kHz
        elif self.pad_len:
            parts.append(f"pad_len={int(self.pad_len * 48000)}")
        elif self.pad_dur:
            parts.append(f"pad_dur={self.pad_dur}")

        parts.append(f"packet_size={self.packet_size}")

        if len(parts) == 2:  # Just "apad" and packet_size
            return f"apad=packet_size={self.packet_size}"

        return f"apad={':'.join(parts[1:])}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state  # Padding doesn't change tracked state
