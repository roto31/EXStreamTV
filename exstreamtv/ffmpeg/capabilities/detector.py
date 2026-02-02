"""
Hardware Acceleration Detection

Detects available hardware acceleration methods and codec support.
Ported from StreamTV transcoding/hardware.py with enhancements.
"""

import logging
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class HardwareAccelType(Enum):
    """Hardware acceleration types."""
    NONE = "none"
    VIDEOTOOLBOX = "videotoolbox"  # macOS
    NVENC = "nvenc"  # NVIDIA
    QSV = "qsv"  # Intel Quick Sync
    VAAPI = "vaapi"  # Linux VA-API
    AMF = "amf"  # AMD


@dataclass
class HardwareCapabilities:
    """
    Detected hardware acceleration capabilities.
    """
    # Available acceleration methods
    available_methods: list[HardwareAccelType] = field(default_factory=list)
    
    # Preferred method (auto-detected or configured)
    preferred_method: HardwareAccelType = HardwareAccelType.NONE
    
    # Available hardware encoders
    hw_encoders: dict[str, list[str]] = field(default_factory=dict)
    
    # Available hardware decoders
    hw_decoders: dict[str, list[str]] = field(default_factory=dict)
    
    # FFmpeg path
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    
    # Platform info
    platform: str = field(default_factory=platform.system)
    
    def has_hardware_acceleration(self) -> bool:
        """Check if any hardware acceleration is available."""
        return len(self.available_methods) > 0
    
    def get_encoder(self, codec: str) -> str:
        """
        Get the best encoder for a codec.
        
        Args:
            codec: Target codec (h264, hevc, etc.)
            
        Returns:
            Encoder name (e.g., h264_videotoolbox, libx264)
        """
        # Check hardware encoders
        if self.preferred_method != HardwareAccelType.NONE:
            method_name = self.preferred_method.value
            if codec in self.hw_encoders:
                for encoder in self.hw_encoders[codec]:
                    if method_name in encoder:
                        return encoder
        
        # Fallback to software
        software_encoders = {
            "h264": "libx264",
            "hevc": "libx265",
            "h265": "libx265",
            "vp9": "libvpx-vp9",
        }
        return software_encoders.get(codec, f"lib{codec}")


def detect_hardware_acceleration(
    ffmpeg_path: str = "ffmpeg",
    ffprobe_path: str = "ffprobe",
    preferred: str = "auto",
) -> HardwareCapabilities:
    """
    Detect available hardware acceleration.
    
    Args:
        ffmpeg_path: Path to ffmpeg binary
        ffprobe_path: Path to ffprobe binary
        preferred: Preferred method (auto, nvenc, qsv, vaapi, videotoolbox, amf, none)
        
    Returns:
        HardwareCapabilities with detected capabilities
    """
    caps = HardwareCapabilities(
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
    )
    
    # Find FFmpeg
    actual_ffmpeg = shutil.which(ffmpeg_path) or ffmpeg_path
    
    # Get available hwaccels
    try:
        result = subprocess.run(
            [actual_ffmpeg, "-hwaccels"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        hwaccels_output = result.stdout.lower()
        
        # Detect available methods
        if "videotoolbox" in hwaccels_output:
            caps.available_methods.append(HardwareAccelType.VIDEOTOOLBOX)
        if "cuda" in hwaccels_output or "nvenc" in hwaccels_output:
            caps.available_methods.append(HardwareAccelType.NVENC)
        if "qsv" in hwaccels_output:
            caps.available_methods.append(HardwareAccelType.QSV)
        if "vaapi" in hwaccels_output:
            caps.available_methods.append(HardwareAccelType.VAAPI)
        if "amf" in hwaccels_output or "d3d11va" in hwaccels_output:
            caps.available_methods.append(HardwareAccelType.AMF)
            
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"Failed to detect hwaccels: {e}")
    
    # Get available encoders
    try:
        result = subprocess.run(
            [actual_ffmpeg, "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        encoders_output = result.stdout.lower()
        
        # H.264 encoders
        h264_encoders = []
        if "h264_videotoolbox" in encoders_output:
            h264_encoders.append("h264_videotoolbox")
        if "h264_nvenc" in encoders_output:
            h264_encoders.append("h264_nvenc")
        if "h264_qsv" in encoders_output:
            h264_encoders.append("h264_qsv")
        if "h264_vaapi" in encoders_output:
            h264_encoders.append("h264_vaapi")
        if "h264_amf" in encoders_output:
            h264_encoders.append("h264_amf")
        caps.hw_encoders["h264"] = h264_encoders
        
        # HEVC encoders
        hevc_encoders = []
        if "hevc_videotoolbox" in encoders_output:
            hevc_encoders.append("hevc_videotoolbox")
        if "hevc_nvenc" in encoders_output:
            hevc_encoders.append("hevc_nvenc")
        if "hevc_qsv" in encoders_output:
            hevc_encoders.append("hevc_qsv")
        if "hevc_vaapi" in encoders_output:
            hevc_encoders.append("hevc_vaapi")
        if "hevc_amf" in encoders_output:
            hevc_encoders.append("hevc_amf")
        caps.hw_encoders["hevc"] = hevc_encoders
        caps.hw_encoders["h265"] = hevc_encoders
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"Failed to detect encoders: {e}")
    
    # Determine preferred method
    if preferred == "auto":
        # Auto-select based on platform and availability
        system = platform.system()
        if system == "Darwin" and HardwareAccelType.VIDEOTOOLBOX in caps.available_methods:
            caps.preferred_method = HardwareAccelType.VIDEOTOOLBOX
        elif HardwareAccelType.NVENC in caps.available_methods:
            caps.preferred_method = HardwareAccelType.NVENC
        elif HardwareAccelType.QSV in caps.available_methods:
            caps.preferred_method = HardwareAccelType.QSV
        elif HardwareAccelType.VAAPI in caps.available_methods:
            caps.preferred_method = HardwareAccelType.VAAPI
        elif HardwareAccelType.AMF in caps.available_methods:
            caps.preferred_method = HardwareAccelType.AMF
        else:
            caps.preferred_method = HardwareAccelType.NONE
    elif preferred != "none":
        try:
            method = HardwareAccelType(preferred)
            if method in caps.available_methods:
                caps.preferred_method = method
        except ValueError:
            logger.warning(f"Unknown hardware acceleration method: {preferred}")
    
    logger.info(
        f"Hardware acceleration: {caps.preferred_method.value}, "
        f"available: {[m.value for m in caps.available_methods]}"
    )
    
    return caps


def get_available_encoders(ffmpeg_path: str = "ffmpeg") -> list[str]:
    """Get list of all available encoders."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-encoders", "-hide_banner"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        encoders = []
        for line in result.stdout.split("\n"):
            if line.strip() and not line.startswith(" "):
                continue
            parts = line.split()
            if len(parts) >= 2:
                encoders.append(parts[1])
        return encoders
    except Exception as e:
        logger.error(f"Failed to get encoders: {e}")
        return []


def get_available_decoders(ffmpeg_path: str = "ffmpeg") -> list[str]:
    """Get list of all available decoders."""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-decoders", "-hide_banner"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        decoders = []
        for line in result.stdout.split("\n"):
            if line.strip() and not line.startswith(" "):
                continue
            parts = line.split()
            if len(parts) >= 2:
                decoders.append(parts[1])
        return decoders
    except Exception as e:
        logger.error(f"Failed to get decoders: {e}")
        return []
