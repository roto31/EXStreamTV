"""
EXStreamTV - Unified IPTV Streaming Platform

Combines the best of StreamTV and ErsatzTV:
- Direct online streaming (YouTube, Archive.org)
- Local media library support (Plex, Jellyfin, Emby, local folders)
- Hardware-accelerated transcoding
- Advanced scheduling and playout engine
- AI-powered log analysis and error detection
"""

__version__ = "2.0.1"
__author__ = "EXStreamTV Contributors"
__license__ = "MIT"

from exstreamtv.config import get_config, load_config

__all__ = [
    "__version__",
    "get_config",
    "load_config",
]
