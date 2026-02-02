"""
Video encoders for FFmpeg pipeline.

Ported from ErsatzTV Encoder/*.cs files.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from exstreamtv.ffmpeg.encoders.base import BaseEncoder, EncoderType, StreamKind
from exstreamtv.ffmpeg.state.frame_state import FrameDataLocation, FrameState


@dataclass
class EncoderCopyVideo(BaseEncoder):
    """Copy video stream without re-encoding."""

    @property
    def name(self) -> str:
        return "copy"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.COPY

    @property
    def output_options(self) -> List[str]:
        # Include bitstream filter for H.264 copy (StreamTV bug fix)
        return [
            "-c:v", "copy",
            "-bsf:v", "h264_mp4toannexb,dump_extra",
        ]


@dataclass
class EncoderLibx264(BaseEncoder):
    """
    H.264 software encoder.

    Ported from ErsatzTV EncoderLibx264.cs.
    """

    preset: str = "veryfast"
    crf: int = 23
    profile: Optional[str] = "high"
    level: Optional[str] = "4.1"
    tune: Optional[str] = None

    @property
    def name(self) -> str:
        return "libx264"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def output_options(self) -> List[str]:
        opts = ["-c:v", self.name, "-preset", self.preset, "-crf", str(self.crf)]

        if self.profile:
            opts.extend(["-profile:v", self.profile])
        if self.level:
            opts.extend(["-level", self.level])
        if self.tune:
            opts.extend(["-tune", self.tune])

        return opts

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(video_format="h264")


@dataclass
class EncoderLibx265(BaseEncoder):
    """
    H.265/HEVC software encoder.

    Ported from ErsatzTV EncoderLibx265.cs.
    """

    preset: str = "medium"
    crf: int = 28
    profile: Optional[str] = "main"

    @property
    def name(self) -> str:
        return "libx265"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def output_options(self) -> List[str]:
        opts = ["-c:v", self.name, "-preset", self.preset, "-crf", str(self.crf)]

        if self.profile:
            opts.extend(["-profile:v", self.profile])

        # x265 uses -x265-params for additional options
        opts.extend(["-x265-params", "log-level=error"])

        return opts

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(video_format="hevc")


# ============ VideoToolbox (macOS) ============


@dataclass
class EncoderH264VideoToolbox(BaseEncoder):
    """
    H.264 VideoToolbox encoder for macOS.

    Ported from ErsatzTV EncoderH264VideoToolbox.cs.
    """

    profile: Optional[str] = "high"
    bitrate: Optional[str] = None  # e.g., "8M"
    allow_sw: bool = True

    @property
    def name(self) -> str:
        return "h264_videotoolbox"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.VIDEOTOOLBOX

    @property
    def output_options(self) -> List[str]:
        opts = ["-c:v", self.name]

        if self.profile:
            opts.extend(["-profile:v", self.profile.lower()])
        if self.bitrate:
            opts.extend(["-b:v", self.bitrate])
        if self.allow_sw:
            opts.extend(["-allow_sw", "1"])

        return opts

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="h264",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


@dataclass
class EncoderHevcVideoToolbox(BaseEncoder):
    """
    HEVC VideoToolbox encoder for macOS.

    Ported from ErsatzTV EncoderHevcVideoToolbox.cs.
    """

    profile: Optional[str] = "main"
    bitrate: Optional[str] = None
    allow_sw: bool = True

    @property
    def name(self) -> str:
        return "hevc_videotoolbox"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.VIDEOTOOLBOX

    @property
    def output_options(self) -> List[str]:
        opts = ["-c:v", self.name]

        if self.profile:
            opts.extend(["-profile:v", self.profile.lower()])
        if self.bitrate:
            opts.extend(["-b:v", self.bitrate])
        if self.allow_sw:
            opts.extend(["-allow_sw", "1"])

        return opts

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="hevc",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


# ============ NVENC (NVIDIA) ============


@dataclass
class EncoderH264Nvenc(BaseEncoder):
    """
    H.264 NVENC encoder for NVIDIA GPUs.

    Ported from ErsatzTV Nvenc/EncoderH264Nvenc.cs.
    """

    preset: str = "p4"  # p1 (fastest) to p7 (slowest)
    profile: str = "high"
    rc: str = "vbr"  # cbr, vbr, constqp
    cq: int = 23
    b_ref_mode: str = "disabled"

    @property
    def name(self) -> str:
        return "h264_nvenc"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.NVENC

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-preset", self.preset,
            "-profile:v", self.profile,
            "-rc", self.rc,
            "-cq", str(self.cq),
            "-b_ref_mode", self.b_ref_mode,
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="h264",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


@dataclass
class EncoderHevcNvenc(BaseEncoder):
    """HEVC NVENC encoder for NVIDIA GPUs."""

    preset: str = "p4"
    profile: str = "main"
    rc: str = "vbr"
    cq: int = 28

    @property
    def name(self) -> str:
        return "hevc_nvenc"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.NVENC

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-preset", self.preset,
            "-profile:v", self.profile,
            "-rc", self.rc,
            "-cq", str(self.cq),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="hevc",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


# ============ QSV (Intel) ============


@dataclass
class EncoderH264Qsv(BaseEncoder):
    """H.264 QSV encoder for Intel GPUs."""

    preset: str = "medium"
    profile: str = "high"
    global_quality: int = 25

    @property
    def name(self) -> str:
        return "h264_qsv"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.QSV

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-preset", self.preset,
            "-profile:v", self.profile,
            "-global_quality", str(self.global_quality),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="h264",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


@dataclass
class EncoderHevcQsv(BaseEncoder):
    """HEVC QSV encoder for Intel GPUs."""

    preset: str = "medium"
    profile: str = "main"
    global_quality: int = 28

    @property
    def name(self) -> str:
        return "hevc_qsv"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.QSV

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-preset", self.preset,
            "-profile:v", self.profile,
            "-global_quality", str(self.global_quality),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="hevc",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


# ============ VAAPI (Linux) ============


@dataclass
class EncoderH264Vaapi(BaseEncoder):
    """H.264 VAAPI encoder for Linux."""

    profile: str = "high"
    qp: int = 25

    @property
    def name(self) -> str:
        return "h264_vaapi"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.VAAPI

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-profile:v", self.profile,
            "-qp", str(self.qp),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="h264",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


@dataclass
class EncoderHevcVaapi(BaseEncoder):
    """HEVC VAAPI encoder for Linux."""

    profile: str = "main"
    qp: int = 28

    @property
    def name(self) -> str:
        return "hevc_vaapi"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.VAAPI

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-profile:v", self.profile,
            "-qp", str(self.qp),
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="hevc",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


# ============ AMF (AMD) ============


@dataclass
class EncoderH264Amf(BaseEncoder):
    """H.264 AMF encoder for AMD GPUs."""

    quality: str = "balanced"  # speed, balanced, quality
    profile: str = "high"
    rc: str = "vbr_latency"

    @property
    def name(self) -> str:
        return "h264_amf"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.AMF

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-quality", self.quality,
            "-profile:v", self.profile,
            "-rc", self.rc,
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="h264",
            frame_data_location=FrameDataLocation.HARDWARE,
        )


@dataclass
class EncoderHevcAmf(BaseEncoder):
    """HEVC AMF encoder for AMD GPUs."""

    quality: str = "balanced"
    profile: str = "main"
    rc: str = "vbr_latency"

    @property
    def name(self) -> str:
        return "hevc_amf"

    @property
    def kind(self) -> StreamKind:
        return StreamKind.VIDEO

    @property
    def encoder_type(self) -> EncoderType:
        return EncoderType.AMF

    @property
    def output_options(self) -> List[str]:
        return [
            "-c:v", self.name,
            "-quality", self.quality,
            "-profile:v", self.profile,
            "-rc", self.rc,
        ]

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            video_format="hevc",
            frame_data_location=FrameDataLocation.HARDWARE,
        )
