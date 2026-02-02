"""HDHomeRun API endpoints for Plex/Emby/Jellyfin integration"""

import asyncio
import contextlib
import logging
import re
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..database import Channel, get_db
from ..streaming import StreamManager
from ..streaming.error_handler import ErrorHandler
from ..streaming.retry_manager import RetryManager

logger = logging.getLogger(__name__)

# Get config at module level for backwards compatibility with config.xyz usage
config = get_config()

# Cache for public IP detection (module-level)
_public_ip_cache: str | None = None
_public_ip_cache_time: float = 0.0

hdhomerun_router = APIRouter(prefix="/hdhomerun", tags=["HDHomeRun"])

stream_manager = StreamManager()

def _get_server_ip() -> str:
    """Get the actual server IP address for network-accessible URLs"""
    import socket

    try:
        # Connect to external address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Fallback to localhost if we can't determine IP
        return "127.0.0.1"

def _get_public_ip() -> str | None:
    """
    Get the public/external IP address of the server.
    This is useful when the public IP changes (e.g., after cable modem restart).
    Uses multiple services for reliability with caching to avoid rate limits.
    """
    global _public_ip_cache, _public_ip_cache_time

    import time

    cache_duration = 300  # Cache for 5 minutes

    # Check cache first
    if _public_ip_cache and (time.time() - _public_ip_cache_time) < cache_duration:
        return _public_ip_cache

    # List of services that return public IP (in order of preference)
    ip_services = [
        ("https://api.ipify.org?format=json", True),  # JSON format
        ("https://icanhazip.com", False),  # Plain text
        ("https://ifconfig.me/ip", False),  # Plain text
        ("https://api.ip.sb/ip", False),  # Plain text
        ("https://checkip.amazonaws.com", False),  # Plain text
    ]

    # Try each service (use httpx which is already in requirements)
    import httpx

    for service_url, is_json in ip_services:
        try:
            # Use sync client for simplicity (this function may be called from async context)
            with httpx.Client(timeout=5.0) as client:
                response = client.get(service_url)

            if response.status_code == 200:
                # Parse response
                ip = response.json().get("ip", "").strip() if is_json else response.text.strip()

                # Validate IP address format (basic check)
                if ip and "." in ip and len(ip.split(".")) == 4:
                    # Cache the result
                    _public_ip_cache = ip
                    _public_ip_cache_time = time.time()
                    logger.info(f"Detected public IP: {ip}")
                    return ip
        except Exception as e:
            logger.debug(f"Failed to get public IP from {service_url}: {e}")
            continue

    # If all services fail, return None
    logger.warning("Could not detect public IP address - remote access may not work")
    return None

def _get_public_url() -> str | None:
    """
    Get the public URL for remote access.
    Uses public_url from config if set, otherwise tries to detect public IP dynamically.
    """
    # If public_url is explicitly configured, use it
    if config.server.public_url:
        return config.server.public_url.rstrip("/")

    # Otherwise, try to detect public IP dynamically
    public_ip = _get_public_ip()
    if public_ip:
        # Use the same scheme and port as the server
        scheme = "https" if config.server.port == 443 else "http"
        port = config.server.port if config.server.port not in [80, 443] else ""
        public_url = f"{scheme}://{public_ip}:{port}" if port else f"{scheme}://{public_ip}"

        return public_url

    return None

def _is_remote_request(request: Request) -> bool:
    """
    Detect if request is coming from a remote client or through a reverse proxy (Plex Remote Access, etc.)
    Checks for indicators like X-Forwarded-For, X-Real-IP, or non-local IPs
    """
    if not request:
        return False

    # Check for reverse proxy headers (common with Plex Remote Access, nginx, etc.)
    forwarded_for = request.headers.get("X-Forwarded-For")
    real_ip = request.headers.get("X-Real-IP")
    forwarded_host = request.headers.get("X-Forwarded-Host")

    # If we have forwarded headers, likely going through a proxy (Plex Remote Access, etc.)
    if forwarded_for or real_ip or forwarded_host:
        # Check if forwarded host is not a local IP
        if forwarded_host:
            host = forwarded_host.split(":")[0]
            # If it's not localhost/127.0.0.1 and not a private IP, it's remote
            if host not in ["localhost", "127.0.0.1"]:
                try:
                    import ipaddress

                    ip = ipaddress.ip_address(host)
                    # If it's a public IP (not private), it's remote
                    if not ip.is_private:
                        return True
                except (ValueError, OSError):
                    # If it's a domain name (not an IP), assume remote/proxy
                    if (
                        "." in host
                        and not host.startswith("192.168.")
                        and not host.startswith("10.")
                        and not host.startswith("172.")
                    ):
                        return True
        # Even if forwarded_host is local, if we have forwarded headers, we're behind a proxy
        # This could be Plex Remote Access proxying requests
        return True

    # Check client IP
    if request.client:
        client_ip = request.client.host
        if client_ip:
            try:
                import ipaddress

                ip = ipaddress.ip_address(client_ip)
                # If client IP is not private/local, it's remote
                if not ip.is_private and client_ip not in ["127.0.0.1", "::1", "localhost"]:
                    return True
            except (ValueError, OSError):
                pass

    return False

def _get_base_url_for_client(request: Request, force_public: bool = False) -> str:
    """
    Get base URL that works for network clients (AppleTV, Plex, etc.)
    - If public_url is configured and force_public=True: Always uses public_url (for lineup URLs)
    - If force_public=True and no public_url configured: Tries to detect public IP dynamically
    - For remote clients (Plex Remote Access): Uses public_url from config or detected IP
    - For local clients: Uses actual server IP, never localhost

    When Plex Remote Access is used, Plex proxies requests from remote clients.
    For lineup URLs, we should use public_url if configured, because Plex will use those URLs
    to stream to remote clients.
    """
    # If force_public=True, try to get public URL (configured or detected)
    # For lineup URLs, we MUST use public IP, so if detection fails, we still try to use it
    if force_public:
        public_url = _get_public_url()

        if public_url:

            return public_url
        else:
            # If public URL detection failed but force_public=True, log warning and fall through
            # This should not happen in normal operation, but we'll fall back to server IP
            logger.warning(
                "force_public=True but could not detect public IP - falling back to server IP"
            )

    # Only check for remote/proxy if force_public is not explicitly False
    # When force_public=False, we want to use request host or local IP, not public IP
    if force_public is not False:
        is_remote = _is_remote_request(request)

        # If remote/proxy, try to get public URL (configured or detected)
        if is_remote:
            public_url = _get_public_url()
            if public_url:

                return public_url

    # For local requests or when force_public=False, use request host or actual server IP
    scheme = request.url.scheme if request else "http"
    port = request.url.port if request else config.server.port

    # Use request host if available, otherwise use actual server IP
    if request and request.url and request.url.hostname:
        host = request.url.hostname
        # Replace localhost with actual server IP for network accessibility
        if host in ["localhost", "127.0.0.1"]:
            host = _get_server_ip()
    else:
        # Always use actual server IP for network accessibility
        host = _get_server_ip()

    if port and port not in [80, 443]:
        return f"{scheme}://{host}:{port}"
    else:
        return f"{scheme}://{host}"

# HDHomeRun device configuration (now uses config values)
HDHOMERUN_MODEL = "StreamTV"
HDHOMERUN_FIRMWARE = "1.0"

# Tuner status tracking
_tuner_status: dict[int, dict] = defaultdict(
    lambda: {
        "status": "Idle",
        "channel": None,
        "lock": "none",
        "client_count": 0,
        "last_activity": None,
    }
)

# Error handling and retry
error_handler = ErrorHandler()
retry_manager = RetryManager(error_handler=error_handler)

@hdhomerun_router.get("/device.xml")
async def device_description(request: Request):
    """HDHomeRun device description XML (UPnP)"""
    # Always use actual server IP for network accessibility
    base_url = _get_base_url_for_client(request)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <device>
        <deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>
        <friendlyName>EXStreamTV HDHomeRun</friendlyName>
        <manufacturer>StreamTV</manufacturer>
        <manufacturerURL>https://github.com/streamtv</manufacturerURL>
        <modelName>{HDHOMERUN_MODEL}</modelName>
        <modelNumber>{HDHOMERUN_FIRMWARE}</modelNumber>
        <UDN>uuid:{config.hdhomerun.device_id}</UDN>
        <serviceList>
            <service>
                <serviceType>urn:schemas-upnp-org:service:ContentDirectory:1</serviceType>
                <serviceId>urn:upnp-org:serviceId:ContentDirectory</serviceId>
                <SCPDURL>{base_url}/hdhomerun/service.xml</SCPDURL>
                <controlURL>{base_url}/hdhomerun/control</controlURL>
                <eventSubURL>{base_url}/hdhomerun/event</eventSubURL>
            </service>
        </serviceList>
    </device>
</root>"""

    return Response(content=xml, media_type="application/xml")

@hdhomerun_router.get("/service.xml")
async def service_description(request: Request):
    """HDHomeRun service description XML (UPnP)"""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<scpd xmlns="urn:schemas-upnp-org:service-1-0">
    <specVersion>
        <major>1</major>
        <minor>0</minor>
    </specVersion>
    <actionList>
        <action>
            <name>GetSearchCapabilities</name>
        </action>
        <action>
            <name>GetSortCapabilities</name>
        </action>
        <action>
            <name>GetSystemUpdateID</name>
        </action>
        <action>
            <name>Browse</name>
            <argumentList>
                <argument>
                    <name>ObjectID</name>
                    <direction>in</direction>
                    <relatedStateVariable>A_ARG_TYPE_ObjectID</relatedStateVariable>
                </argument>
                <argument>
                    <name>BrowseFlag</name>
                    <direction>in</direction>
                    <relatedStateVariable>A_ARG_TYPE_BrowseFlag</relatedStateVariable>
                </argument>
                <argument>
                    <name>Filter</name>
                    <direction>in</direction>
                    <relatedStateVariable>A_ARG_TYPE_Filter</relatedStateVariable>
                </argument>
                <argument>
                    <name>StartingIndex</name>
                    <direction>in</direction>
                    <relatedStateVariable>A_ARG_TYPE_Index</relatedStateVariable>
                </argument>
                <argument>
                    <name>RequestedCount</name>
                    <direction>in</direction>
                    <relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable>
                </argument>
                <argument>
                    <name>SortCriteria</name>
                    <direction>in</direction>
                    <relatedStateVariable>A_ARG_TYPE_SortCriteria</relatedStateVariable>
                </argument>
                <argument>
                    <name>Result</name>
                    <direction>out</direction>
                    <relatedStateVariable>A_ARG_TYPE_Result</relatedStateVariable>
                </argument>
                <argument>
                    <name>NumberReturned</name>
                    <direction>out</direction>
                    <relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable>
                </argument>
                <argument>
                    <name>TotalMatches</name>
                    <direction>out</direction>
                    <relatedStateVariable>A_ARG_TYPE_Count</relatedStateVariable>
                </argument>
                <argument>
                    <name>UpdateID</name>
                    <direction>out</direction>
                    <relatedStateVariable>A_ARG_TYPE_UpdateID</relatedStateVariable>
                </argument>
            </argumentList>
        </action>
    </actionList>
    <serviceStateTable>
        <stateVariable sendEvents="yes">
            <name>SystemUpdateID</name>
            <dataType>ui4</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_ObjectID</name>
            <dataType>string</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_Result</name>
            <dataType>string</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_BrowseFlag</name>
            <dataType>string</dataType>
            <allowedValueList>
                <allowedValue>BrowseMetadata</allowedValue>
                <allowedValue>BrowseDirectChildren</allowedValue>
            </allowedValueList>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_Filter</name>
            <dataType>string</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_SortCriteria</name>
            <dataType>string</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_Index</name>
            <dataType>ui4</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_Count</name>
            <dataType>ui4</dataType>
        </stateVariable>
        <stateVariable sendEvents="no">
            <name>A_ARG_TYPE_UpdateID</name>
            <dataType>ui4</dataType>
        </stateVariable>
    </serviceStateTable>
</scpd>"""

    return Response(content=xml, media_type="application/xml")

@hdhomerun_router.post("/control")
async def control(request: Request):
    """HDHomeRun UPnP control endpoint"""
    # Most media servers don't actually use this, but we provide it for compatibility
    return Response(content="", status_code=200)

@hdhomerun_router.get("/event")
@hdhomerun_router.post("/event")
async def event(request: Request):
    """HDHomeRun UPnP event subscription endpoint"""
    # Most media servers don't actually use this, but we provide it for compatibility
    # UPnP uses both GET (subscribe) and POST (unsubscribe) for events
    return Response(content="", status_code=200)

@hdhomerun_router.get("/discover.json")
async def discover(request: Request, db: AsyncSession = Depends(get_db)):
    """HDHomeRun device discovery endpoint"""

    # Use request host or local server IP (do not force public IP)
    if request:
        base_url = _get_base_url_for_client(request, force_public=False)
    elif config.server.public_url:
        base_url = config.server.public_url.rstrip("/")
    else:
        base_url = config.server.base_url

    # Get enabled channels count
    stmt = select(Channel).where(Channel.enabled == True)
    result = await db.execute(stmt)
    channel_count = len(result.scalars().all())

    response = {
        "FriendlyName": config.hdhomerun.friendly_name,
        "ModelNumber": HDHOMERUN_MODEL,
        "FirmwareName": f"streamtv-{HDHOMERUN_FIRMWARE}",
        "FirmwareVersion": HDHOMERUN_FIRMWARE,
        "DeviceID": config.hdhomerun.device_id,
        "DeviceAuth": "streamtv",
        "BaseURL": f"{base_url}/hdhomerun",
        "LineupURL": f"{base_url}/hdhomerun/lineup.json",
        # EPG/Guide URL for Plex DVR to fetch programme data
        "GuideURL": f"{base_url}/hdhomerun/epg",
        "TunerCount": config.hdhomerun.tuner_count,
    }

    return response

def _validate_mpegts_chunk(chunk: bytes) -> bool:
    """Validate that a chunk is valid MPEG-TS format"""
    if len(chunk) < 188:
        return False

    # MPEG-TS sync byte is 0x47
    sync_byte = 0x47

    # Check first packet
    if chunk[0] != sync_byte:
        # Check if sync byte is at position 188 (second packet)
        if len(chunk) >= 188 and chunk[188] == sync_byte:
            return True
        # Search for sync byte in first 188 bytes (might have initialization data)
        # This handles cases where FFmpeg outputs a few bytes before the first packet
        for i in range(1, min(len(chunk), 188)):
            if chunk[i] == sync_byte:
                # Found sync byte - check if it's at a valid packet boundary (multiple of 188)
                # Or if the next packet (i + 188) also has sync byte
                if i + 188 <= len(chunk) and chunk[i + 188] == sync_byte:
                    return True
        return False

    # Check multiple packets if available
    for i in range(0, min(len(chunk), 188 * 3), 188):
        if i + 188 <= len(chunk) and chunk[i] != sync_byte:
            return False

    return True

@hdhomerun_router.get("/lineup.json")
async def lineup(request: Request, db: AsyncSession = Depends(get_db)):
    """HDHomeRun channel lineup with improved error handling"""

    try:
        # Query channels - handle enum validation errors with fallback to raw SQL
        try:
            stmt = select(Channel).where(Channel.enabled == True).order_by(Channel.number)
            result = await db.execute(stmt)
            channels = result.scalars().all()
        except (LookupError, ValueError, Exception) as query_error:
            # Handle SQLAlchemy enum validation errors by querying raw values and converting
            error_str = str(query_error)
            type(query_error).__name__
            # Check if this is an enum validation error (can be LookupError or the message contains the enum error text)
            if (
                isinstance(query_error, LookupError)
                or "is not among the defined enum values" in error_str
                or "channeltranscodemode" in error_str.lower()
                or "transcodemode" in error_str.lower()
            ):
                logger.warning(
                    f"SQLAlchemy enum validation error when querying channels for HDHomeRun lineup: {query_error}"
                )
                logger.info(
                    "Attempting to query channels using raw SQL to work around enum validation issue..."
                )
                # Query using raw SQL to avoid enum validation, then construct Channel objects
                from sqlalchemy import text

                raw_result = db.execute(
                    text("""
                    SELECT * FROM channels WHERE enabled = 1 ORDER BY number
                """)
                ).fetchall()
                channels = []
                # Conditionally import enums from v1 or v2 models based on config
                if config.v2.enabled:
                    from ..database.models_v2 import (
                        ChannelTranscodeMode,
                        PlayoutMode,
                        StreamingMode,
                    )
                else:
                    from ..database.models import (
                        ChannelTranscodeMode,
                        PlayoutMode,
                        StreamingMode,
                    )
                for row in raw_result:
                    channel = Channel()
                    # Copy all attributes from row, converting enum strings to enums
                    for key, value in row._mapping.items():
                        if value is None:
                            setattr(channel, key, None)
                        elif key == "playout_mode" and isinstance(value, str):
                            normalized = value.lower()
                            enum_val = PlayoutMode.CONTINUOUS
                            for mode in PlayoutMode:
                                if mode.value.lower() == normalized:
                                    enum_val = mode
                                    break
                            else:
                                with contextlib.suppress(KeyError):
                                    enum_val = PlayoutMode[value.upper()]
                            setattr(channel, key, enum_val)
                        elif key == "streaming_mode" and isinstance(value, str):
                            normalized = value.lower()
                            enum_val = StreamingMode.TRANSPORT_STREAM_HYBRID
                            for mode in StreamingMode:
                                if mode.value.lower() == normalized:
                                    enum_val = mode
                                    break
                            else:
                                with contextlib.suppress(KeyError):
                                    enum_val = StreamingMode[value.upper()]
                            setattr(channel, key, enum_val)
                        elif key == "transcode_mode" and isinstance(value, str):
                            normalized = value.lower()
                            enum_val = ChannelTranscodeMode.ON_DEMAND
                            for mode in ChannelTranscodeMode:
                                if mode.value.lower() == normalized:
                                    enum_val = mode
                                    break
                            else:
                                with contextlib.suppress(KeyError):
                                    enum_val = ChannelTranscodeMode[value.upper()]
                            setattr(channel, key, enum_val)
                        elif key in [
                            "subtitle_mode",
                            "stream_selector_mode",
                            "music_video_credits_mode",
                            "song_video_mode",
                            "idle_behavior",
                            "playout_source",
                        ] and isinstance(value, str):
                            # These will be handled by @reconstructor, just set as string for now
                            setattr(channel, key, value)
                        else:
                            setattr(channel, key, value)
                    channels.append(channel)
                logger.info(
                    f"Loaded {len(channels)} channels using raw SQL query for HDHomeRun lineup"
                )
            else:
                # Re-raise if it's a different error
                raise

        if not channels:
            logger.warning("No enabled channels found for HDHomeRun lineup")
            return []
    except Exception as e:
        error_context = {
            "endpoint": "lineup.json",
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        error_handler.handle_error(e, error_context)
        logger.error(f"Error generating HDHomeRun lineup: {e}", exc_info=True)
        # Return empty lineup rather than failing completely
        return []

    # Use request host or local server IP (do not force public IP)
    # Plex will use the URLs from the request host, which works better for local network access
    if request:
        base_url = _get_base_url_for_client(request, force_public=False)
    elif config.server.public_url:
        base_url = config.server.public_url.rstrip("/")
    else:
        base_url = config.server.base_url

    lineup_data = []

    for channel in channels:
        # HDHomeRun expects GuideNumber, GuideName, URL, and optionally HD
        # We'll use the channel number as GuideNumber
        guide_number = channel.number

        # Strip channel number prefix from GuideName to avoid duplication in Plex
        # Plex displays channels as "GuideNumber GuideName", so if name already
        # starts with the number, it gets doubled (e.g., "2000 2000's Movies")
        guide_name = channel.name
        if guide_name and guide_number:
            # Check if name starts with the channel number
            name_stripped = guide_name.strip()
            number_str = str(guide_number).strip()

            if name_stripped.startswith(number_str):
                # Remove the number prefix
                remaining = name_stripped[len(number_str) :].strip()

                # Remove common patterns after the number (e.g., "'s ", " - ", " ", "-", "'s")
                # Handle patterns in order of specificity (longer patterns first)
                patterns_to_remove = [
                    r"^'s\s+",  # "'s " (apostrophe-s-space)
                    r"^[\s\-\.\_]+",  # Any combination of spaces, dashes, dots, underscores
                ]
                for pattern in patterns_to_remove:
                    remaining = re.sub(pattern, "", remaining)

                # Only use cleaned name if there's content left, otherwise keep original
                if remaining:
                    guide_name = remaining

        # Create stream URL - HDHomeRun expects MPEG-TS, but we'll use HLS
        # Plex/Emby/Jellyfin can handle HLS
        stream_url = f"{base_url}/hdhomerun/auto/v{channel.number}"

        channel_entry = {
            "GuideNumber": str(guide_number),
            "GuideName": guide_name,
            "URL": stream_url,
            "HD": 1 if "HD" in channel.name.upper() else 0,
        }

        lineup_data.append(channel_entry)

    # #region agent log
    try:
        import json
        lineup_guide_numbers = [entry["GuideNumber"] for entry in lineup_data[:10]]
        with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
            f.write(json.dumps({"location":"hdhomerun/api.py:lineup","message":"HDHomeRun lineup generated","data":{"channel_count":len(lineup_data),"guide_numbers":lineup_guide_numbers,"first_entry":lineup_data[0] if lineup_data else None},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H2"}) + "\n")
    except: pass
    # #endregion
    
    return lineup_data

@hdhomerun_router.get("/lineup_status.json")
async def lineup_status():
    """HDHomeRun lineup status"""
    return {
        "ScanInProgress": 0,
        "ScanPossible": 1,
        "Source": "Antenna",
        "SourceList": ["Antenna", "Cable"],
    }

@hdhomerun_router.get("/epg")
async def get_epg_data(request: Request = None, db: AsyncSession = Depends(get_db)):
    """
    HDHomeRun EPG endpoint - Returns XMLTV guide data for Plex DVR
    
    This is the endpoint that Plex DVR automatically fetches for guide data
    when using HDHomeRun tuners. This matches ErsatzTV's approach.
    """
    # #region agent log
    try:
        import json
        client_ip = request.client.host if request and request.client else "unknown"
        with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
            f.write(json.dumps({"location":"hdhomerun/api.py:epg","message":"HDHomeRun EPG endpoint called","data":{"client_ip":client_ip,"user_agent":request.headers.get("user-agent","unknown") if request else "unknown"},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H4"}) + "\n")
    except: pass
    # #endregion
    
    # Import the XMLTV generation from iptv module
    from ..api.iptv import get_epg
    
    # Call the existing XMLTV generation function
    # Pass through the request and db session
    return await get_epg(access_token=None, request=request, plain=True, db=db)

def _assign_tuner(channel_number: str) -> int:
    """Assign a tuner to a channel, returning tuner index"""
    # Find an available tuner (Idle or same channel)
    for i in range(config.hdhomerun.tuner_count):
        tuner_info = _tuner_status[i]
        if tuner_info["status"] == "Idle" or tuner_info["channel"] == channel_number:
            tuner_info["status"] = "Streaming"
            tuner_info["channel"] = channel_number
            tuner_info["lock"] = "tuner"
            tuner_info["client_count"] += 1
            tuner_info["last_activity"] = datetime.utcnow()
            return i

    # All tuners busy, use first one (round-robin)
    tuner_info = _tuner_status[0]
    tuner_info["status"] = "Streaming"
    tuner_info["channel"] = channel_number
    tuner_info["lock"] = "tuner"
    tuner_info["client_count"] += 1
    tuner_info["last_activity"] = datetime.utcnow()
    return 0

def _release_tuner(tuner_index: int):
    """Release a tuner"""
    tuner_info = _tuner_status[tuner_index]
    tuner_info["client_count"] = max(0, tuner_info["client_count"] - 1)
    if tuner_info["client_count"] == 0:
        tuner_info["status"] = "Idle"
        tuner_info["channel"] = None
        tuner_info["lock"] = "none"

@hdhomerun_router.get("/auto/v{channel_number}")
async def stream_channel(
    channel_number: str, request: Request = None, db: AsyncSession = Depends(get_db)
):
    """Stream a channel (HDHomeRun format) - Returns MPEG-TS for Plex compatibility with retry logic and validation"""
    logger.info(
        f"HDHomeRun stream request for channel {channel_number} from {request.client.host if request else 'unknown'}"
    )

    # Query channel with error handling
    channel = None
    try:
        stmt = select(Channel).where(
            Channel.number == channel_number,
            Channel.enabled == True
        )
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
    except Exception as e:
        error_context = {
            "endpoint": "stream_channel",
            "channel_number": channel_number,
            "error_type": type(e).__name__,
        }
        error_handler.handle_error(e, error_context)
        logger.error(f"Error querying channel {channel_number}: {e}", exc_info=True)

    if not channel:
        logger.warning(f"Channel {channel_number} not found or not enabled")
        raise HTTPException(status_code=404, detail="Channel not found")

    # Assign tuner
    tuner_index = None
    try:
        tuner_index = _assign_tuner(channel_number)
        logger.debug(f"Assigned tuner {tuner_index} to channel {channel_number}")
    except Exception as e:
        logger.error(f"Error assigning tuner: {e}", exc_info=True)
        # Continue without tuner tracking if assignment fails

    # Try MPEG-TS streaming first (requires FFmpeg)
    try:
        # Use ChannelManager for continuous streaming (ErsatzTV-style)
        # Get ChannelManager from app state
        channel_manager = None
        if request:
            app = request.app
            if hasattr(app, "state"):
                channel_manager = getattr(app.state, "channel_manager", None)

        if channel_manager:
            # Use the continuous stream from ChannelManager
            logger.info(
                f"Client connecting to continuous stream for channel {channel_number} ({channel.name})"
            )

            async def generate():
                chunk_count = 0
                try:
                    logger.debug(f"Starting stream generation for channel {channel_number}")

                    # Get or create the ChannelStream for this channel
                    channel_stream = await channel_manager.get_channel_stream(
                        channel.id,
                        int(channel.number),
                        channel.name
                    )
                    
                    # Get the async stream generator from ChannelStream
                    async for chunk in channel_stream.get_stream():
                        chunk_count += 1

                        # Validate first chunk is valid MPEG-TS
                        if chunk_count == 1:
                            if _validate_mpegts_chunk(chunk):
                                logger.info(
                                    f"First chunk validated for channel {channel_number} ({len(chunk)} bytes, valid MPEG-TS)"
                                )
                            else:
                                # Check if sync byte exists anywhere in chunk (might have leading data)
                                sync_byte = 0x47
                                sync_pos = chunk.find(sync_byte)
                                if sync_pos >= 0:
                                    logger.debug(
                                        f"First chunk for channel {channel_number} has sync byte at position {sync_pos} "
                                        f"(not at start), but continuing - likely initialization data"
                                )
                                else:
                                    logger.warning(
                                            f"First chunk for channel {channel_number} may not be valid MPEG-TS "
                                            f"(no sync byte 0x47 found in {len(chunk)} bytes), but continuing..."
                                    )

                        yield chunk

                    logger.info(
                        f"Stream generation completed for channel {channel_number} ({chunk_count} chunks total)"
                    )
                except asyncio.CancelledError:
                    # Client disconnected - this is normal, don't log as error
                    logger.debug(
                        f"Stream cancelled for channel {channel_number} (client disconnected)"
                    )
                    return
                except Exception as e:

                    error_context = {
                        "endpoint": "stream_channel",
                        "channel_number": channel_number,
                        "chunk_count": chunk_count,
                        "error_type": type(e).__name__,
                    }
                    error_handler.handle_error(e, error_context)
                    logger.error(
                        f"Error in continuous stream for channel {channel_number}: {e}",
                        exc_info=True,
                    )
                    # Don't raise - let the client handle the connection error gracefully
                    # Raising here causes Plex to show "Error tuning channel"
                    return
                finally:
                    _release_tuner(tuner_index)

            return StreamingResponse(
                generate(),
                media_type="video/mp2t",  # MPEG-TS MIME type
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Cache-Control": "no-cache, no-store, must-revalidate, private",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable buffering (nginx)
                    "Transfer-Encoding": "chunked",  # Chunked transfer for streaming
                },
            )
        else:

            async def generate():
                chunk_count = 0
                try:
                    logger.debug(f"Starting stream generation for channel {channel_number}")

                    # Get or create the ChannelStream for this channel
                    channel_stream = await channel_manager.get_channel_stream(
                        channel.id,
                        int(channel.number),
                        channel.name
                    )
                    
                    # Get the async stream generator from ChannelStream
                    async for chunk in channel_stream.get_stream():
                        chunk_count += 1

                        # Validate first chunk is valid MPEG-TS
                        if chunk_count == 1:
                            if _validate_mpegts_chunk(chunk):
                                logger.info(
                                    f"First chunk validated for channel {channel_number} ({len(chunk)} bytes, valid MPEG-TS)"
                                )
                            else:
                                # Check if sync byte exists anywhere in chunk (might have leading data)
                                sync_byte = 0x47
                                sync_pos = chunk.find(sync_byte)
                                if sync_pos >= 0:
                                    logger.debug(
                                        f"First chunk for channel {channel_number} has sync byte at position {sync_pos} "
                                        f"(not at start), but continuing - likely initialization data"
                                )
                                else:
                                    logger.warning(
                                            f"First chunk for channel {channel_number} may not be valid MPEG-TS "
                                            f"(no sync byte 0x47 found in {len(chunk)} bytes), but continuing..."
                                    )

                        yield chunk

                    logger.info(
                        f"Stream generation completed for channel {channel_number} ({chunk_count} chunks total)"
                    )
                except asyncio.CancelledError:
                    # Client disconnected - this is normal, don't log as error
                    logger.debug(
                        f"Stream cancelled for channel {channel_number} (client disconnected)"
                    )
                    return
                except Exception as e:

                    error_context = {
                        "endpoint": "stream_channel",
                        "channel_number": channel_number,
                        "chunk_count": chunk_count,
                        "error_type": type(e).__name__,
                    }
                    error_handler.handle_error(e, error_context)
                    logger.error(
                        f"Error in continuous stream for channel {channel_number}: {e}",
                        exc_info=True,
                    )
                    # Don't raise - let the client handle the connection error gracefully
                    # Raising here causes Plex to show "Error tuning channel"
                    return
                finally:
                    _release_tuner(tuner_index)

            return StreamingResponse(
                generate(),
                media_type="video/mp2t",  # MPEG-TS MIME type
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Cache-Control": "no-cache, no-store, must-revalidate, private",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable buffering (nginx)
                    "Transfer-Encoding": "chunked",  # Chunked transfer for streaming
                },
            )

    except RuntimeError as e:
        # FFmpeg not available, fall back to HLS
        if "FFmpeg not found" in str(e):
            logger.warning(f"FFmpeg not available, falling back to HLS: {e}")
            from ..api.iptv import get_hls_stream

            try:
                logger.info(
                    f"Streaming channel {channel_number} ({channel.name}) via HLS (FFmpeg fallback)"
                )
                response = await get_hls_stream(channel_number, None, request, db)
                if hasattr(response, "headers"):
                    response.headers["Access-Control-Allow-Origin"] = "*"
                    response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
                    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                return response
            except Exception as e:
                error_context = {
                    "endpoint": "stream_channel",
                    "channel_number": channel_number,
                    "fallback": "HLS",
                    "error_type": type(e).__name__,
                }
                error_handler.handle_error(e, error_context)
                logger.error(f"Error streaming via HLS fallback: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Error streaming channel: {e!s}")
        else:
            raise
    except HTTPException:
        raise
    except Exception as e:
        error_context = {
            "endpoint": "stream_channel",
            "channel_number": channel_number,
            "error_type": type(e).__name__,
        }
        error_handler.handle_error(e, error_context)
        logger.error(f"Error streaming channel {channel_number} via HDHomeRun: {e}", exc_info=True)
        
        raise HTTPException(status_code=500, detail=f"Error streaming channel: {e!s}")
    finally:
        # Ensure tuner is released even if exception occurs
        if tuner_index is not None:
            try:
                _release_tuner(tuner_index)
            except Exception as e:
                logger.warning(f"Error releasing tuner: {e}")

@hdhomerun_router.get("/tuner{n}/stream")
async def tuner_stream(
    n: int, 
    channel: str = None, 
    url: str = None,
    request: Request = None, 
    db: AsyncSession = Depends(get_db)
):
    """HDHomeRun tuner stream endpoint - supports both 'channel' and 'url' parameters for Plex compatibility"""
    if n < 0 or n >= config.hdhomerun.tuner_count:
        raise HTTPException(status_code=404, detail="Tuner not found")

    # Support both 'channel' and 'url' parameters (Plex uses 'url')
    channel_param = channel or url
    if not channel_param:
        raise HTTPException(status_code=400, detail="Missing required query parameter 'channel' or 'url'")

    # Parse channel parameter (format: auto:v<channel_number> or auto/v<channel_number>)
    channel_number = channel_param.replace("auto:v", "").replace("auto/v", "")
    if channel_number.startswith("v"):
        channel_number = channel_number[1:]  # Remove 'v' prefix

    # Stream the channel
    return await stream_channel(channel_number, request, db)

@hdhomerun_router.get("/status.json")
async def status():
    """HDHomeRun device status with enhanced tuner reporting"""
    tuner_status_list = []
    for i in range(config.hdhomerun.tuner_count):
        tuner_info = _tuner_status[i]
        tuner_status_list.append(
            {
                "Tuner": i,
                "Status": tuner_info["status"],
                "Channel": tuner_info["channel"],
                "Lock": tuner_info["lock"],
                "ClientCount": tuner_info["client_count"],
                "LastActivity": tuner_info["last_activity"].isoformat()
                if tuner_info["last_activity"]
                else None,
            }
        )

    return {
        "FriendlyName": config.hdhomerun.friendly_name,
        "ModelNumber": HDHOMERUN_MODEL,
        "FirmwareName": f"streamtv-{HDHOMERUN_FIRMWARE}",
        "FirmwareVersion": HDHOMERUN_FIRMWARE,
        "DeviceID": config.hdhomerun.device_id,
        "DeviceAuth": "streamtv",
        "TunerCount": config.hdhomerun.tuner_count,
        "TunerStatus": tuner_status_list,
    }
