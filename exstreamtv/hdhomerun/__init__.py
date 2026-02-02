"""
EXStreamTV HDHomeRun Emulation Module

Provides HDHomeRun tuner emulation for integration with:
- Plex Live TV & DVR
- Jellyfin Live TV
- Emby Live TV
- Any HDHomeRun-compatible client

Components:
- hdhomerun_router: FastAPI router for HDHomeRun API endpoints
- SSDPServer: SSDP server for device discovery
"""

from exstreamtv.hdhomerun.api import hdhomerun_router
from exstreamtv.hdhomerun.ssdp_server import SSDPServer

__all__ = ["SSDPServer", "hdhomerun_router"]
