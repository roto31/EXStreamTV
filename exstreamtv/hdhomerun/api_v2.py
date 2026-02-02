"""HDHomeRun API v2 - Following official HDHomeRun specification with all required endpoints and proper SSDP discovery"""

import asyncio
import logging
import socket

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..config import get_config
from ..database.models_v2 import Channel
from ..database.session import SessionLocal, get_db
from ..streaming.channel_manager_v2 import ChannelManagerV2
from ..streaming.mpegts_streamer_v2 import MPEGTSStreamerV2

logger = logging.getLogger(__name__)

# Get config at module level for backwards compatibility
config = get_config()

hdhomerun_router_v2 = APIRouter(prefix="/hdhomerun", tags=["HDHomeRun V2"])


class HDHomeRunAPIV2:
    """
    HDHomeRun API v2 - Following official HDHomeRun specification

    Reference: HDHomeRun API documentation
    Endpoints:
    - /discover.json - Device discovery
    - /lineup.json - Channel lineup
    - /lineup_status.json - Lineup status
    - /tuner<N>/stream - Stream endpoint
    - /tuner<N>/status.json - Tuner status
    """

    def __init__(self, db_session_factory=None, channel_manager: ChannelManagerV2 | None = None):
        """
        Initialize HDHomeRun API v2

        Args:
            db_session_factory: Database session factory
            channel_manager: Channel manager instance
        """
        self.db_session_factory = db_session_factory or (lambda: SessionLocal())
        self.channel_manager = channel_manager or ChannelManagerV2(
            db_session_factory=self.db_session_factory
        )
        self.mpegts_streamer = MPEGTSStreamerV2()

        # Device information
        self.device_id = (
            config.hdhomerun.device_id
            if hasattr(config, "hdhomerun") and hasattr(config.hdhomerun, "device_id")
            else "FFFFFFFF"
        )
        self.device_auth = (
            config.hdhomerun.device_auth
            if hasattr(config, "hdhomerun") and hasattr(config.hdhomerun, "device_auth")
            else ""
        )
        self.base_url = (
            config.server.base_url
            if hasattr(config.server, "base_url")
            else f"http://{self._get_server_ip()}:{config.server.port}"
        )

        # Expose router for FastAPI integration
        self.hdhomerun_router_v2 = hdhomerun_router_v2

    def _get_server_ip(self) -> str:
        """Get server IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    @hdhomerun_router_v2.get("/discover.json")
    async def discover(self, request: Request):
        """
        HDHomeRun discover endpoint

        Returns device information for discovery by Plex/Emby/Jellyfin
        """
        try:
            # Get server URL
            server_url = str(request.base_url).rstrip("/")

            # Build discover response
            discover_data = {
                "FriendlyName": "EXStreamTV HDHomeRun",
                "ModelNumber": "HDTC-2US",
                "FirmwareName": "hdhomerun2_streamtv",
                "FirmwareVersion": "2.0",
                "DeviceID": self.device_id,
                "DeviceAuth": self.device_auth,
                "BaseURL": f"{server_url}/hdhomerun",
                "LineupURL": f"{server_url}/hdhomerun/lineup.json",
            }

            return JSONResponse(content=discover_data)

        except Exception as e:
            logger.exception(f"Error in discover endpoint: {e}")
            raise

    @hdhomerun_router_v2.get("/lineup.json")
    async def lineup(self, request: Request, db: Session = Depends(get_db)):
        """
        HDHomeRun lineup endpoint

        Returns channel lineup in HDHomeRun format
        """
        try:
            channels = db.query(Channel).filter(Channel.enabled).order_by(Channel.number).all()

            lineup = []
            server_url = str(request.base_url).rstrip("/")

            for channel in channels:
                lineup.append(
                    {
                        "GuideNumber": str(channel.number),
                        "GuideName": channel.name,
                        "URL": f"{server_url}/hdhomerun/tuner{channel.number}/stream",
                    }
                )

            return JSONResponse(content=lineup)

        except Exception as e:
            logger.exception(f"Error in lineup endpoint: {e}")
            raise

    @hdhomerun_router_v2.get("/lineup_status.json")
    async def lineup_status(self):
        """HDHomeRun lineup status endpoint"""
        return JSONResponse(
            content={
                "ScanInProgress": 0,
                "ScanPossible": 1,
                "Source": "Cable",
                "SourceList": ["Cable"],
            }
        )

    @hdhomerun_router_v2.get("/tuner{channel_number}/stream")
    async def stream(self, channel_number: str, request: Request, db: Session = Depends(get_db)):
        """
        HDHomeRun stream endpoint

        Streams MPEG-TS for a specific channel
        """
        try:
            # Find channel
            channel = (
                db.query(Channel).filter(Channel.number == channel_number, Channel.enabled).first()
            )

            if not channel:
                raise HTTPException(status_code=404, detail=f"Channel {channel_number} not found")

            # Get channel stream
            channel_stream = await self.channel_manager.get_channel_stream(channel.id)
            if not channel_stream:
                # Start channel stream if not running
                await self.channel_manager.start_channel(channel)
                channel_stream = await self.channel_manager.get_channel_stream(channel.id)

            if not channel_stream:
                raise HTTPException(status_code=500, detail="Failed to start channel stream")

            # Create MPEG-TS stream
        except Exception as e:
            logger.exception(f"Error in stream endpoint: {e}")
            raise

    @hdhomerun_router_v2.get("/tuner{channel_number}/status.json")
    async def tuner_status(self, channel_number: str, db: Session = Depends(get_db)):
        """HDHomeRun tuner status endpoint"""
        try:
            channel = (
                db.query(Channel).filter(Channel.number == channel_number, Channel.enabled).first()
            )

            if not channel:
                return JSONResponse(content={"error": "Channel not found"})

            # Get channel stream status
            channel_stream = await self.channel_manager.get_channel_stream(channel.id)

            if channel_stream:
                position = channel_stream.get_current_position()
                return JSONResponse(
                    content={
                        "VChannel": str(channel.number),
                        "Locked": "1",
                        "SignalStrength": "100",
                        "SignalQuality": "100",
                        "SymbolQuality": "100",
                        "Streaming": "1",
                        "ClientCount": position.get("client_count", 0),
                    }
                )
            else:
                return JSONResponse(
                    content={
                        "VChannel": str(channel.number),
                        "Locked": "0",
                        "Streaming": "0",
                    }
                )

        except Exception as e:
            logger.exception(f"Error in tuner_status endpoint: {e}")
            return JSONResponse(content={"error": str(e)})


class SSDPDiscoveryV2:
    """
    SSDP (Simple Service Discovery Protocol) discovery v2

    Implements SSDP for automatic device discovery by Plex/Emby/Jellyfin
    """

    SSDP_MULTICAST_IP = "239.255.255.250"
    SSDP_PORT = 1900
    SSDP_ST = "urn:schemas-upnp-org:device:MediaServer:1"

    def __init__(self, base_url: str, device_id: str):
        """
        Initialize SSDP discovery

        Args:
            base_url: Base URL for device
            device_id: Device ID
        """
        self.base_url = base_url
        self.device_id = device_id
        self._running = False
        self._server_socket: socket.socket | None = None

    async def start(self):
        """Start SSDP discovery server"""
        if self._running:
            return

        self._running = True

        # Create UDP socket for SSDP
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("", self.SSDP_PORT))

        # Join multicast group
        try:
            mreq = socket.inet_aton(self.SSDP_MULTICAST_IP) + socket.inet_aton("0.0.0.0")
            self._server_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as e:
            logger.warning(f"Could not join SSDP multicast group: {e}")

        # Start listening loop
        asyncio.create_task(self._listen_loop())
        logger.info("SSDP discovery server started")

    async def stop(self):
        """Stop SSDP discovery server"""
        self._running = False
        if self._server_socket:
            self._server_socket.close()
        logger.info("SSDP discovery server stopped")

    async def _listen_loop(self):
        """Listen for SSDP M-SEARCH requests"""
        while self._running:
            try:
                data, addr = await asyncio.get_event_loop().sock_recvfrom(self._server_socket, 1024)

                # Parse SSDP request
                request = data.decode("utf-8", errors="ignore")

                if "M-SEARCH" in request and self.SSDP_ST in request:
                    # Send response
                    await self._send_ssdp_response(addr)

            except Exception as e:
                if self._running:
                    logger.exception(f"Error in SSDP listen loop: {e}")
                await asyncio.sleep(1)

    async def _send_ssdp_response(self, addr: tuple):
        """Send SSDP response"""
        response = f"""HTTP/1.1 200 OK\r
CACHE-CONTROL: max-age=1800\r
ST: {self.SSDP_ST}\r
USN: uuid:{self.device_id}::{self.SSDP_ST}\r
LOCATION: {self.base_url}/hdhomerun/discover.json\r
SERVER: StreamTV/2.0 UPnP/1.0\r
\r
"""

        try:
            await asyncio.get_event_loop().sock_sendto(
                self._server_socket, response.encode("utf-8"), addr
            )
        except Exception as e:
            logger.debug(f"Error sending SSDP response: {e}")
