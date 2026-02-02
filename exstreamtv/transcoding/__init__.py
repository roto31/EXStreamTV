"""Transcoding module for StreamTV"""

from .hardware import detect_hardware_acceleration, get_available_hardware_acceleration

__all__ = [
    "detect_hardware_acceleration",
    "get_available_hardware_acceleration",
]
