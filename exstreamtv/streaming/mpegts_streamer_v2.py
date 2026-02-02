"""
MPEG-TS Streamer v2 Compatibility Module

Re-exports from the main mpegts_streamer module.
"""

from exstreamtv.streaming.mpegts_streamer import *

# Import specific classes if they exist
try:
    from exstreamtv.streaming.mpegts_streamer import (
        MpegTSStreamer,
    )
    MpegTSStreamerV2 = MpegTSStreamer
    MPEGTSStreamerV2 = MpegTSStreamer  # Alternative casing
except ImportError:
    class MpegTSStreamerV2:
        """Placeholder for MpegTSStreamer."""
        pass
    MPEGTSStreamerV2 = MpegTSStreamerV2

__all__ = ["MpegTSStreamerV2", "MPEGTSStreamerV2"]
