"""Hardware acceleration detection and capabilities"""

import logging
import platform
import shutil
import subprocess
from pathlib import Path

from ..config import config
from ..database.models import HardwareAccelerationKind

logger = logging.getLogger(__name__)


def get_ffmpeg_path() -> str:
    """Get FFmpeg executable path"""
    return config.ffmpeg.ffmpeg_path


def detect_hardware_acceleration() -> list[HardwareAccelerationKind]:
    """
    Detect available hardware acceleration types by querying FFmpeg.

    Returns:
        List of available hardware acceleration kinds
    """
    available = []

    try:
        ffmpeg_path = get_ffmpeg_path()

        # Check if FFmpeg exists
        if not Path(ffmpeg_path).exists() and not shutil.which(ffmpeg_path):
            logger.warning(f"FFmpeg not found at {ffmpeg_path}")
            return available

        # Run ffmpeg -hwaccels to get list of supported hardware acceleration
        result = subprocess.run(
            [ffmpeg_path, "-hwaccels"], check=False, capture_output=True, text=True, timeout=5
        )

        if result.returncode != 0:
            logger.warning(f"Failed to query FFmpeg hardware acceleration: {result.stderr}")
            return available

        output = result.stdout.lower()

        # Map FFmpeg hardware acceleration names to our enum values
        hwaccel_map = {
            "nvenc": HardwareAccelerationKind.NVENC,
            "qsv": HardwareAccelerationKind.QSV,
            "vaapi": HardwareAccelerationKind.VAAPI,
            "videotoolbox": HardwareAccelerationKind.VIDEOTOOLBOX,
            "amf": HardwareAccelerationKind.AMF,
            "v4l2m2m": HardwareAccelerationKind.V4L2M2M,
            "rkmpp": HardwareAccelerationKind.RKMPP,
        }

        # Check for each hardware acceleration type
        for hw_name, hw_kind in hwaccel_map.items():
            if hw_name in output:
                available.append(hw_kind)
                logger.info(f"Detected hardware acceleration: {hw_kind.value}")

        # Platform-specific checks
        system = platform.system().lower()

        # macOS: VideoToolbox is usually available
        if system == "darwin" and HardwareAccelerationKind.VIDEOTOOLBOX not in available:
            # Try to verify VideoToolbox support
            try:
                result = subprocess.run(
                    [ffmpeg_path, "-hide_banner", "-encoders"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if "videotoolbox" in result.stdout.lower():
                    available.append(HardwareAccelerationKind.VIDEOTOOLBOX)
                    logger.info("Detected VideoToolbox hardware acceleration")
            except Exception as e:
                logger.debug(f"Could not verify VideoToolbox: {e}")

        # Linux: Check for VAAPI devices
        if system == "linux" and HardwareAccelerationKind.VAAPI not in available:
            # Check if /dev/dri/renderD* devices exist
            import glob

            if glob.glob("/dev/dri/renderD*"):
                # VAAPI might be available even if not in hwaccels list
                try:
                    result = subprocess.run(
                        [ffmpeg_path, "-hide_banner", "-encoders"],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if (
                        "h264_vaapi" in result.stdout.lower()
                        or "hevc_vaapi" in result.stdout.lower()
                    ):
                        available.append(HardwareAccelerationKind.VAAPI)
                        logger.info("Detected VAAPI hardware acceleration")
                except Exception as e:
                    logger.debug(f"Could not verify VAAPI: {e}")

        # Always include NONE as fallback
        if HardwareAccelerationKind.NONE not in available:
            available.insert(0, HardwareAccelerationKind.NONE)

    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg hardware acceleration detection timed out")
    except FileNotFoundError:
        logger.warning(f"FFmpeg not found at {ffmpeg_path}")
    except Exception as e:
        logger.error(f"Error detecting hardware acceleration: {e}", exc_info=True)

    # Always return at least NONE
    if not available:
        available = [HardwareAccelerationKind.NONE]

    return available


def get_available_hardware_acceleration() -> list[str]:
    """
    Get list of available hardware acceleration types as strings.

    Returns:
        List of hardware acceleration kind values (e.g., ["none", "nvenc", "qsv"])
    """
    return [hw.value for hw in detect_hardware_acceleration()]


def check_hardware_codec_support(hardware_accel: HardwareAccelerationKind, codec: str) -> bool:
    """
    Check if a specific codec is supported by the hardware acceleration.

    Args:
        hardware_accel: Hardware acceleration kind
        codec: Codec name (e.g., "h264", "hevc")

    Returns:
        True if codec is supported, False otherwise
    """
    try:
        ffmpeg_path = get_ffmpeg_path()

        # Get encoders
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode != 0:
            return False

        output = result.stdout.lower()
        codec_lower = codec.lower()

        # Map hardware acceleration to encoder prefixes
        encoder_map = {
            HardwareAccelerationKind.NVENC: f"{codec_lower}_nvenc",
            HardwareAccelerationKind.QSV: f"{codec_lower}_qsv",
            HardwareAccelerationKind.VAAPI: f"{codec_lower}_vaapi",
            HardwareAccelerationKind.VIDEOTOOLBOX: f"{codec_lower}_videotoolbox",
            HardwareAccelerationKind.AMF: f"{codec_lower}_amf",
            HardwareAccelerationKind.V4L2M2M: f"{codec_lower}_v4l2m2m",
            HardwareAccelerationKind.RKMPP: f"{codec_lower}_rkmpp",
        }

        encoder_name = encoder_map.get(hardware_accel)
        return bool(encoder_name and encoder_name in output)

    except Exception as e:
        logger.debug(f"Error checking codec support: {e}")
        return False


def get_vaapi_devices() -> list[str]:
    """
    Get list of available VAAPI devices on Linux.

    Returns:
        List of device paths (e.g., ["/dev/dri/renderD128"])
    """
    devices = []

    if platform.system().lower() != "linux":
        return devices

    try:
        import glob

        devices = glob.glob("/dev/dri/renderD*")
        devices.sort()
    except Exception as e:
        logger.debug(f"Error getting VAAPI devices: {e}")

    return devices


def get_vaapi_displays() -> list[str]:
    """
    Get list of available VAAPI displays.

    Returns:
        List of display names (e.g., [":0.0"])
    """
    displays = []

    if platform.system().lower() != "linux":
        return displays

    try:
        # Common display names
        displays = [":0.0", ":0", ":1.0", ":1"]
    except Exception as e:
        logger.debug(f"Error getting VAAPI displays: {e}")

    return displays
