"""
FFmpeg Capabilities Detection Module

Detects available hardware acceleration and codec support.
"""

from exstreamtv.ffmpeg.capabilities.detector import (
    HardwareCapabilities,
    detect_hardware_acceleration,
    get_available_encoders,
    get_available_decoders,
)

# Alias for backwards compatibility
HardwareCapabilityDetector = HardwareCapabilities

__all__ = [
    "HardwareCapabilities",
    "HardwareCapabilityDetector",
    "detect_hardware_acceleration",
    "get_available_encoders",
    "get_available_decoders",
]
