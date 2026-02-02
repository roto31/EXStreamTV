"""
Video filters for FFmpeg pipeline.

Ported from ErsatzTV Filter/*.cs files.
"""

from dataclasses import dataclass
from typing import Optional

from exstreamtv.ffmpeg.filters.base import BaseFilter
from exstreamtv.ffmpeg.state.frame_state import FrameDataLocation, FrameSize, FrameState


@dataclass
class ScaleFilter(BaseFilter):
    """
    Scale video to target resolution.

    Ported from ErsatzTV ScaleFilter.cs.
    """

    target_size: FrameSize
    padded_size: Optional[FrameSize] = None
    cropped_size: Optional[FrameSize] = None
    is_anamorphic_edge_case: bool = False
    force_aspect_ratio: Optional[str] = None  # "increase" or "decrease"
    scaling_algorithm: str = "fast_bilinear"

    @property
    def filter_string(self) -> str:
        """Build scale filter string."""
        size = self.padded_size or self.target_size

        # Handle aspect ratio forcing
        aspect_ratio = ""
        if self.force_aspect_ratio:
            aspect_ratio = f":force_original_aspect_ratio={self.force_aspect_ratio}"
        elif self.padded_size and self.target_size != self.padded_size:
            if self.cropped_size:
                aspect_ratio = ":force_original_aspect_ratio=increase"
            else:
                aspect_ratio = ":force_original_aspect_ratio=decrease"

        scale = f"scale={size.width}:{size.height}:flags={self.scaling_algorithm}{aspect_ratio}"

        # Handle anamorphic content
        if self.is_anamorphic_edge_case:
            return f"scale=iw:sar*ih,setsar=1,{scale}"

        return f"{scale},setsar=1"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            scaled_size=self.target_size,
            padded_size=self.target_size,
            frame_data_location=FrameDataLocation.SOFTWARE,
            is_anamorphic=False,
        )


@dataclass
class PadFilter(BaseFilter):
    """
    Pad video to target size (add letterbox/pillarbox).

    Ported from ErsatzTV PadFilter.cs.
    """

    target_size: FrameSize
    pad_color: str = "black"

    @property
    def filter_string(self) -> str:
        return f"pad={self.target_size.width}:{self.target_size.height}:(ow-iw)/2:(oh-ih)/2:{self.pad_color}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(padded_size=self.target_size)


@dataclass
class CropFilter(BaseFilter):
    """
    Crop video to target size.

    Ported from ErsatzTV CropFilter.cs.
    """

    target_size: FrameSize

    @property
    def filter_string(self) -> str:
        return f"crop={self.target_size.width}:{self.target_size.height}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            cropped_size=self.target_size,
            scaled_size=self.target_size,
        )


@dataclass
class TonemapFilter(BaseFilter):
    """
    HDR to SDR tonemapping.

    Ported from ErsatzTV TonemapFilter.cs.
    """

    algorithm: str = "linear"  # linear, mobius, reinhard, hable
    target_pixel_format: str = "yuv420p"
    current_location: FrameDataLocation = FrameDataLocation.SOFTWARE

    @property
    def filter_string(self) -> str:
        tonemap = (
            f"zscale=transfer=linear,"
            f"tonemap={self.algorithm},"
            f"zscale=transfer=bt709,"
            f"format={self.target_pixel_format}"
        )

        # Add hwdownload if frame is in hardware
        if self.current_location == FrameDataLocation.HARDWARE:
            return f"hwdownload,format=nv12,{tonemap}"

        return tonemap

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            pixel_format=self.target_pixel_format,
            frame_data_location=FrameDataLocation.SOFTWARE,
            color_transfer="bt709",
        )


@dataclass
class DeinterlaceFilter(BaseFilter):
    """
    Deinterlace video using yadif or similar.

    Ported from ErsatzTV YadifFilter.cs.
    """

    mode: str = "send_frame"  # send_frame, send_field, send_frame_nospatial
    parity: str = "auto"  # tff, bff, auto
    deint: str = "all"  # all, interlaced

    @property
    def filter_string(self) -> str:
        return f"yadif=mode={self.mode}:parity={self.parity}:deint={self.deint}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(is_interlaced=False)


@dataclass
class PixelFormatFilter(BaseFilter):
    """
    Convert pixel format.

    Ported from ErsatzTV PixelFormatFilter.cs.
    """

    target_format: str = "yuv420p"

    @property
    def filter_string(self) -> str:
        return f"format={self.target_format}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(pixel_format=self.target_format)


@dataclass
class HardwareUploadFilter(BaseFilter):
    """
    Upload frames to GPU memory.

    Ported from ErsatzTV HardwareUploadFilter.cs.
    """

    device: Optional[str] = None
    derive_device: Optional[str] = None

    @property
    def filter_string(self) -> str:
        if self.derive_device:
            return f"hwupload=derive_device={self.derive_device}"
        return "hwupload"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            frame_data_location=FrameDataLocation.HARDWARE
        )


@dataclass
class HardwareDownloadFilter(BaseFilter):
    """
    Download frames from GPU memory.

    Ported from ErsatzTV HardwareDownloadFilter.cs.
    """

    output_format: Optional[str] = None

    @property
    def filter_string(self) -> str:
        if self.output_format:
            return f"hwdownload,format={self.output_format}"
        return "hwdownload"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state.with_updates(
            frame_data_location=FrameDataLocation.SOFTWARE,
            pixel_format=self.output_format or current_state.pixel_format,
        )


@dataclass
class RealtimeFilter(BaseFilter):
    """
    Realtime filter for live streaming pace.

    Ported from ErsatzTV RealtimeFilter.cs.
    """

    limit: Optional[float] = None  # Buffer limit in seconds
    speed: float = 1.0

    @property
    def filter_string(self) -> str:
        parts = ["realtime"]
        if self.limit:
            parts.append(f"limit={self.limit}")
        if self.speed != 1.0:
            parts.append(f"speed={self.speed}")

        if len(parts) == 1:
            return "realtime"
        return f"realtime={':'.join(parts[1:])}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state  # No state change


@dataclass
class WatermarkFilter(BaseFilter):
    """
    Overlay watermark on video.

    Ported from ErsatzTV OverlayWatermarkFilter.cs.
    """

    position: str = "top-right"  # top-left, top-right, bottom-left, bottom-right, center
    margin: int = 10
    opacity: float = 1.0
    watermark_input_index: int = 1

    @property
    def filter_string(self) -> str:
        positions = {
            "top-left": f"x={self.margin}:y={self.margin}",
            "top-right": f"x=main_w-overlay_w-{self.margin}:y={self.margin}",
            "bottom-left": f"x={self.margin}:y=main_h-overlay_h-{self.margin}",
            "bottom-right": f"x=main_w-overlay_w-{self.margin}:y=main_h-overlay_h-{self.margin}",
            "center": "x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2",
        }

        pos = positions.get(self.position, positions["top-right"])

        if self.opacity < 1.0:
            return f"[{self.watermark_input_index}:v]format=rgba,colorchannelmixer=aa={self.opacity}[wm];[0:v][wm]overlay={pos}"

        return f"overlay={pos}"

    def next_state(self, current_state: FrameState) -> FrameState:
        return current_state  # Watermark doesn't change video state
