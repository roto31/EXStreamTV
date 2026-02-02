"""IPTV streaming endpoints (m3u, xmltv.xml, HLS)"""

import logging
import urllib.parse
from datetime import datetime, timedelta
from datetime import time as dt_time
from xml.sax.saxutils import escape as xml_escape

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
config = get_config()
from ..constants import (
    EPG_ASSIGNMENT_LOG_COUNT,
    EPG_CATEGORIES_LIMIT,
    EPG_MAX_PROGRAMMES_PER_CHANNEL,
    EPG_QUERY_LIMIT,
    EPG_TITLE_TRUNCATE_LENGTH,
    MAX_EPG_ITEMS_PER_CHANNEL,
)
from ..database import Channel, MediaItem, Playout, PlayoutItem, get_db
from ..scheduling import ScheduleEngine, ScheduleParser
from ..streaming import StreamManager, StreamSource
from ..streaming.plex_api_client import PlexAPIClient
from ..utils.paths import debug_log

logger = logging.getLogger(__name__)

router = APIRouter(tags=["IPTV"])

stream_manager = StreamManager()

def _xml(value) -> str:
    """Safely escape XML text/attribute values."""
    if value is None:
        return ""
    return xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})

def _resolve_logo_url(channel, base_url: str) -> str | None:
    """
    Build an absolute logo URL for M3U/XMLTV.
    - Uses channel.logo_path if provided.
    - Falls back to /static/channel_icons/channel_<number>.png.
    """
    # Ensure base_url is not localhost - Plex can't access localhost URLs
    if "localhost" in base_url or "127.0.0.1" in base_url:
        # Try to get actual IP address
        import socket

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                actual_ip = s.getsockname()[0]
            finally:
                s.close()
            # Replace localhost with actual IP
            base_url = base_url.replace("localhost", actual_ip).replace("127.0.0.1", actual_ip)
        except OSError:
            pass  # Keep original base_url if we can't determine IP

    logo_path = channel.logo_path
    if logo_path:
        if logo_path.startswith("http"):
            return logo_path
        if logo_path.startswith("/"):
            return f"{base_url}{logo_path}"
        return f"{base_url}/{logo_path}"
    # Default fallback based on channel number icon
    return f"{base_url}/static/channel_icons/channel_{channel.number}.png"

@router.get("/iptv/channels.m3u")
async def get_channel_playlist(
    mode: str = "mixed",
    access_token: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Get IPTV channel playlist (M3U format)"""
    try:
        # Validate access token if required
        # Only require token if both api_key_required=True AND access_token is set
        if config.security.api_key_required and config.security.access_token:
            if access_token != config.security.access_token:
                raise HTTPException(status_code=401, detail="Invalid access token")

        stmt = select(Channel).where(Channel.enabled == True)
        result = await db.execute(stmt)
        channels = result.scalars().all()

        # Fix: Ensure playout_mode is properly converted from string to enum if needed
        from ..database.models import PlayoutMode

        for channel in channels:
            if isinstance(channel.playout_mode, str):
                # Convert string to enum instance
                try:
                    # Normalize the string (lowercase, handle dashes)
                    normalized = channel.playout_mode.lower().replace("-", "_")
                    # Try to match by value first (enum values are lowercase: "continuous", "on_demand")
                    matched = False
                    for mode in PlayoutMode:
                        if mode.value.lower() == normalized:
                            channel.playout_mode = mode
                            matched = True
                            break
                    if not matched:
                        # Try to match by name (enum names are uppercase: CONTINUOUS, ON_DEMAND)
                        name_upper = channel.playout_mode.upper().replace("-", "_")
                        if name_upper in ["CONTINUOUS", "ON_DEMAND"]:
                            channel.playout_mode = PlayoutMode[name_upper]
                        else:
                            # Try direct lookup
                            channel.playout_mode = PlayoutMode[channel.playout_mode.upper()]
                except (KeyError, AttributeError) as e:
                    # If conversion fails, default to CONTINUOUS
                    logger.warning(
                        f"Invalid playout_mode '{channel.playout_mode}' for channel {channel.number}, defaulting to CONTINUOUS: {e}"
                    )
                    channel.playout_mode = PlayoutMode.CONTINUOUS

        # Always derive base_url from the incoming request so tvg-logo/icon URLs match
        # the address Plex/clients use (avoids 127.0.0.1 vs LAN IP issues).
        # Never use localhost - Plex accesses from different machine
        base_url = config.server.base_url
        if request:
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port
            # Replace localhost/127.0.0.1 with actual hostname for Plex compatibility
            if host in ["localhost", "127.0.0.1"]:
                # Try to get the actual server IP from request headers
                forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get(
                    "Host"
                )
                if forwarded_host:
                    host = forwarded_host.split(":")[0]
                else:
                    # Fallback: get local IP address
                    import socket

                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        try:
                            s.connect(("8.8.8.8", 80))
                            host = s.getsockname()[0]
                        finally:
                            s.close()
                    except OSError:
                        host = request.url.hostname
            if port and port not in [80, 443]:
                base_url = f"{scheme}://{host}:{port}"
            else:
                base_url = f"{scheme}://{host}"

        m3u_content = "#EXTM3U\n"

        for channel in channels:
            try:
                token_param = f"?access_token={access_token}" if access_token else ""

                if mode in {"hls", "mixed"}:
                    stream_url = f"{base_url}/iptv/channel/{channel.number}.m3u8{token_param}"
                else:
                    stream_url = f"{base_url}/iptv/channel/{channel.number}.ts{token_param}"

                logo_url = _resolve_logo_url(channel, base_url)
                m3u_content += f'#EXTINF:-1 tvg-id="{channel.number}" tvg-name="{channel.name}"'
                if channel.group:
                    m3u_content += f' group-title="{channel.group}"'
                if logo_url:
                    m3u_content += f' tvg-logo="{logo_url}"'
                m3u_content += f",{channel.name}\n"
                m3u_content += f"{stream_url}\n"
            except Exception as e:
                logger.error(
                    f"Error processing channel {channel.number if channel else 'unknown'} for M3U: {e}",
                    exc_info=True,
                )
                # Continue with next channel instead of failing entire request

        return Response(content=m3u_content, media_type="application/vnd.apple.mpegurl")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating M3U playlist: {e}", exc_info=True)
        error_m3u = "#EXTM3U\n"
        error_m3u += f"#EXTINF:-1,Error: {e!s}\n"
        error_m3u += "#\n"
        return Response(
            content=error_m3u, media_type="application/vnd.apple.mpegurl", status_code=500
        )

@router.get("/iptv/xmltv.xml")
async def get_epg(
    access_token: str | None = None,
    request: Request = None,
    plain: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Get Electronic Program Guide (XMLTV format)"""
    import time

    perf_start_time = time.time()  # Performance timing (float)

    try:
        # Validate access token if required
        # Only require token if both api_key_required=True AND access_token is set
        if config.security.api_key_required and config.security.access_token:
            if access_token != config.security.access_token:
                raise HTTPException(status_code=401, detail="Invalid access token")

        # Query channels - handle enum validation errors with fallback to raw SQL
        try:
            stmt = select(Channel).where(Channel.enabled == True)
            result = await db.execute(stmt)
            channels = result.scalars().all()
        except (LookupError, ValueError) as query_error:
            # Handle SQLAlchemy enum validation errors by querying raw values and converting
            error_str = str(query_error)
            if (
                "is not among the defined enum values" in error_str
                or "streamingmode" in error_str.lower()
                or "playoutmode" in error_str.lower()
            ):
                logger.warning(
                    f"SQLAlchemy enum validation error when querying channels for XMLTV: {query_error}"
                )
                logger.info(
                    "Attempting to query channels using raw SQL to work around enum validation issue..."
                )
                # Query using raw SQL to avoid enum validation, then construct Channel objects
                from sqlalchemy import text

                raw_result = db.execute(
                    text("""
                    SELECT id, number, name, playout_mode, enabled, "group", logo_path,
                           streaming_mode, is_yaml_source, transcode_profile, created_at, updated_at
                    FROM channels WHERE enabled = 1
                """)
                ).fetchall()
                channels = []
                from ..database.models import PlayoutMode, StreamingMode

                for row in raw_result:
                    channel = Channel()
                    channel.id = row[0]
                    channel.number = row[1]
                    channel.name = row[2]
                    # Convert playout_mode string to enum
                    playout_mode_str = row[3] if row[3] else "continuous"
                    normalized = playout_mode_str.lower()
                    playout_mode_enum = PlayoutMode.CONTINUOUS
                    for mode in PlayoutMode:
                        if mode.value.lower() == normalized:
                            playout_mode_enum = mode
                            break
                    else:
                        try:
                            playout_mode_enum = PlayoutMode[playout_mode_str.upper()]
                        except KeyError:
                            playout_mode_enum = PlayoutMode.CONTINUOUS
                    channel.playout_mode = playout_mode_enum
                    # Convert streaming_mode string to enum
                    streaming_mode_str = row[7] if row[7] else "transport_stream_hybrid"
                    normalized = streaming_mode_str.lower()
                    streaming_mode_enum = StreamingMode.TRANSPORT_STREAM_HYBRID
                    for mode in StreamingMode:
                        if mode.value.lower() == normalized:
                            streaming_mode_enum = mode
                            break
                    else:
                        try:
                            streaming_mode_enum = StreamingMode[streaming_mode_str.upper()]
                        except KeyError:
                            streaming_mode_enum = StreamingMode.TRANSPORT_STREAM_HYBRID
                    channel.streaming_mode = streaming_mode_enum
                    channel.enabled = bool(row[4])
                    channel.group = row[5]
                    channel.logo_path = row[6]
                    channel.is_yaml_source = bool(row[8])
                    channel.transcode_profile = row[9]
                    channels.append(channel)
                logger.info(f"Loaded {len(channels)} channels using raw SQL query for XMLTV")
            else:
                # Re-raise if it's a different error
                raise

        # Fix: Ensure playout_mode is properly converted from string to enum if needed
        from ..database.models import PlayoutMode

        for channel in channels:
            if isinstance(channel.playout_mode, str):
                # Convert string to enum instance
                try:
                    # Normalize the string (lowercase, handle dashes)
                    normalized = channel.playout_mode.lower().replace("-", "_")
                    # Try to match by value first (enum values are lowercase: "continuous", "on_demand")
                    matched = False
                    for mode in PlayoutMode:
                        if mode.value.lower() == normalized:
                            channel.playout_mode = mode
                            matched = True
                            break
                    if not matched:
                        # Try to match by name (enum names are uppercase: CONTINUOUS, ON_DEMAND)
                        name_upper = channel.playout_mode.upper().replace("-", "_")
                        if name_upper in ["CONTINUOUS", "ON_DEMAND"]:
                            channel.playout_mode = PlayoutMode[name_upper]
                    else:
                        # Try direct lookup
                        channel.playout_mode = PlayoutMode[channel.playout_mode.upper()]
                except (KeyError, AttributeError) as e:
                    # If conversion fails, default to CONTINUOUS
                    logger.warning(
                        f"Invalid playout_mode '{channel.playout_mode}' for channel {channel.number}, defaulting to CONTINUOUS: {e}"
                    )
                    channel.playout_mode = PlayoutMode.CONTINUOUS

        logger.info(f"Generating XMLTV EPG for {len(channels)} channels")
        
        # #region agent log
        try:
            import json
            channel_ids_in_epg = [str(c.number).strip() for c in channels]
            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                f.write(json.dumps({"location":"iptv.py:xmltv:start","message":"XMLTV EPG generation started","data":{"channel_count":len(channels),"channel_ids":channel_ids_in_epg[:10],"client_ip":request.client.host if request and request.client else "unknown"},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H2-H4"}) + "\n")
        except: pass
        # #endregion

        # Always derive base_url from the incoming request so icon URLs work for Plex
        # Never use localhost - Plex accesses from different machine
        base_url = config.server.base_url
        if request:
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port
            # Replace localhost/127.0.0.1 with actual hostname for Plex compatibility
            if host in ["localhost", "127.0.0.1"]:
                # Try to get the actual server IP from request headers first
                forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get(
                    "Host"
                )
                if forwarded_host:
                    host = forwarded_host.split(":")[0]
                else:
                    # Fallback: get local IP address
                    import socket

                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        try:
                            s.connect(("8.8.8.8", 80))
                            host = s.getsockname()[0]
                        finally:
                            s.close()
                    except OSError:
                        # Last resort: use config base_url but replace localhost
                        if "localhost" in base_url or "127.0.0.1" in base_url:
                            import socket

                            try:
                                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                                try:
                                    s.connect(("8.8.8.8", 80))
                                    host = s.getsockname()[0]
                                finally:
                                    s.close()
                            except OSError:
                                host = request.url.hostname
            if port and port not in [80, 443]:
                base_url = f"{scheme}://{host}:{port}"
            else:
                base_url = f"{scheme}://{host}"

        # Generate EPG based on configured build days
        now = datetime.utcnow()
        build_days = config.playout.build_days
        end_time = now + timedelta(days=build_days)
        
        # #region agent log
        try:
            import json
            now_str = now.strftime("%Y%m%d%H%M%S +0000")
            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                f.write(json.dumps({"location":"iptv.py:xmltv:time_base","message":"EPG time base","data":{"now_utc":now_str,"now_iso":now.isoformat(),"build_days":build_days,"end_time":end_time.isoformat()},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H1-H5"}) + "\n")
        except: pass
        # #endregion

        # Build XML header; optionally include XSL stylesheet for browsers
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        if not plain:
            xml_content += '<?xml-stylesheet type="text/xsl" href="https://raw.githubusercontent.com/XMLTV/xmltv/master/xmltv.xsl"?>\n'
        xml_content += '<tv generator-info-name="StreamTV" generator-info-url="https://github.com/streamtv" source-info-name="StreamTV">\n'

        # Initialize Plex API client if configured for schedule/EPG integration
        plex_client = None
        plex_channel_map = {}
        if (
            config.plex.enabled
            and config.plex.base_url
            and config.plex.use_for_epg
            and config.plex.token
        ):
            try:
                plex_client = PlexAPIClient(base_url=config.plex.base_url, token=config.plex.token)
                logger.info(
                    f"Plex API client initialized for EPG/schedule integration (server: {config.plex.base_url})"
                )

                # Try to get channel mappings from Plex if DVR is configured
                try:
                    dvrs = await plex_client.get_dvrs()
                    if dvrs:
                        logger.info(f"Found {len(dvrs)} Plex DVR(s) for channel mapping")
                        # Store channel mappings for later use
                        for dvr in dvrs:
                            if dvr.get("enabled"):
                                # Get channels for this DVR's lineup if available
                                pass  # Channel mapping will be enhanced in future
                except Exception as e:
                    logger.debug(f"Plex DVR channel mapping: {e}")

            except Exception as e:
                logger.warning(
                    f"Plex API client initialization failed: {e}. EPG will use standard format."
                )
                plex_client = None

        # Channel definitions - ensure Plex-compatible format
        for channel in channels:
            # Use channel number as ID (Plex expects numeric or alphanumeric IDs)
            channel_id = str(channel.number).strip()
            xml_content += f'  <channel id="{_xml(channel_id)}">\n'

            # Primary display name (required)
            xml_content += f"    <display-name>{_xml(channel.name)}</display-name>\n"

            # Additional display names for grouping
            if channel.group:
                xml_content += f"    <display-name>{_xml(channel.group)}</display-name>\n"

            # Channel number as display name (Plex compatibility)
            xml_content += f"    <display-name>{_xml(channel_id)}</display-name>\n"

            # Logo/icon (Plex expects absolute URLs). Fall back to default icon by number.
            logo_url = _resolve_logo_url(channel, base_url)
            if logo_url:
                xml_content += f'    <icon src="{_xml(logo_url)}"/>\n'

            xml_content += "  </channel>\n"

        # Program listings - optimized with early exit
        
        for channel in channels:
            # Try to load schedule file first
            schedule_file = ScheduleParser.find_schedule_file(channel.number)
            schedule_items = []

            # Get playout_start_time from database to match actual stream timing
            # This ensures EPG metadata matches what's actually being streamed
            from exstreamtv.database.models import ChannelPlaybackPosition

            playback_pos = None
            try:
                # Use async query for AsyncSession
                stmt = select(ChannelPlaybackPosition).where(
                    ChannelPlaybackPosition.channel_id == channel.id
                )
                result = await db.execute(stmt)
                playback_pos = result.scalar_one_or_none()
            except Exception as e:
                # Handle missing columns in database schema
                if (
                    "no such column" in str(e).lower()
                    or "operationalerror" in str(e).__class__.__name__.lower()
                ):
                    logger.warning(
                        f"ChannelPlaybackPosition columns missing, using raw SQL query: {e}"
                    )
                    from sqlalchemy import text

                    # Query only columns that exist
                    result = db.execute(
                        text("""
                        SELECT id, channel_id, channel_number, last_item_index, last_item_media_id,
                               playout_start_time, last_position_update, last_played_at, total_items_watched,
                               current_item_start_time, elapsed_seconds_in_item,
                               created_at, updated_at
                        FROM channel_playback_positions
                        WHERE channel_id = :channel_id
                        LIMIT 1
                    """),
                        {"channel_id": channel.id},
                    )
                    row = result.fetchone()
                    if row:
                        # Create a minimal ChannelPlaybackPosition-like object
                        playback_pos = ChannelPlaybackPosition()
                        playback_pos.id = row[0]
                        playback_pos.channel_id = row[1]
                        playback_pos.channel_number = row[2]
                        playback_pos.last_item_index = row[3]
                        playback_pos.last_item_media_id = row[4]
                        playback_pos.playout_start_time = row[5]
                        playback_pos.last_position_update = row[6]
                        playback_pos.last_played_at = row[7]
                        playback_pos.total_items_watched = row[8]
                        playback_pos.current_item_start_time = row[9]  # Now included in query
                        playback_pos.elapsed_seconds_in_item = row[10] or 0  # Now included in query
                        playback_pos.created_at = row[11]
                        playback_pos.updated_at = row[12]
                else:
                    raise

            # Use playout_start_time if available (for CONTINUOUS channels), otherwise use now
            # This matches the logic in channel_manager._get_current_position()
            # Use enhanced position tracking if available
            playout_start_time = None
            current_item_start_time = None
            elapsed_seconds_in_item = 0

            if playback_pos:
                # Safely access playout_start_time (may not exist in older database schemas)
                playout_start_time = getattr(playback_pos, 'playout_start_time', None)
                if playout_start_time:
                    logger.debug(
                        f"Channel {channel.number}: Using playout_start_time {playout_start_time} for EPG"
                    )

                # Use enhanced position tracking (may not exist in older database schemas)
                current_item_start_time = getattr(playback_pos, 'current_item_start_time', None)
                if current_item_start_time:
                    elapsed_seconds_in_item = getattr(playback_pos, 'elapsed_seconds_in_item', 0) or 0
                    logger.debug(
                        f"Channel {channel.number}: Using enhanced position tracking - item started at {current_item_start_time}, elapsed {elapsed_seconds_in_item}s"
                    )
            
            if not playout_start_time:
                # No saved playout_start_time - use now (first time or ON_DEMAND channel)
                playout_start_time = now
                logger.debug(
                    f"Channel {channel.number}: No saved playout_start_time, using now ({now}) for EPG"
                )

            if schedule_file:
                # #region agent log
                try:
                    import json as _j
                    with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                        f.write(_j.dumps({"location":"iptv.py:xmltv:schedule_file_found","message":"Channel has schedule file - falling back to DB","data":{"channel_number":str(channel.number),"schedule_file":str(schedule_file)},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H6"}) + "\n")
                except: pass
                # #endregion
                try:
                    parsed_schedule = ScheduleParser.parse_file(schedule_file, schedule_file.parent)
                    # NOTE: ScheduleEngine expects sync Session, but we have AsyncSession
                    # Skip schedule engine for now and use parsed schedule directly or fallback to database
                    # TODO: Port ScheduleEngine to async or create sync session wrapper
                    logger.info(
                        f"Schedule file found for channel {channel.number}, but ScheduleEngine requires sync session"
                    )
                    # Fallback to database schedules
                    schedule_items = []
                except Exception as e:
                    logger.warning(f"Failed to load schedule file for EPG: {e}")

                    # Calculate total cycle duration (sum of all item durations)
                    total_duration = sum(
                        (item.get("media_item", {}).duration or 1800)
                        for item in schedule_items
                        if item.get("media_item")
                    )

                    # CRITICAL FIX: Use actual last_item_index from database (ErsatzTV-style approach)
                    # ErsatzTV tracks the current position and uses it for EPG generation
                    # This ensures EPG matches what's actually being streamed, accounting for timeline sync
                    if playback_pos and playback_pos.last_item_index is not None:
                        # Use the actual last_item_index saved by channel_manager
                        # Apply modulo to handle channels that have looped multiple times (ErsatzTV handles this the same way)
                        last_item_index_raw = playback_pos.last_item_index
                        if len(schedule_items) > 0:
                            current_item_index = last_item_index_raw % len(schedule_items)
                        else:
                            current_item_index = 0
                        
                        # #region agent log
                        import json as _json, time as _time; open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log","a").write(_json.dumps({"hypothesisId":"H3","location":"iptv.py:get_epg:using_last_item_index","message":"EPG using last_item_index from DB","data":{"channel_number":channel.number,"last_item_index_raw":last_item_index_raw,"wrapped_index":current_item_index,"schedule_items_count":len(schedule_items)},"timestamp":_time.time(),"sessionId":"debug-session"})+"\n")
                        # #endregion
                        
                        logger.info(
                            f"Channel {channel.number}: EPG using actual last_item_index {last_item_index_raw} from database (wrapped to {current_item_index} for {len(schedule_items)} items, ErsatzTV-style)"
                        )
                    elif total_duration > 0 and playout_start_time:
                        # Fallback: calculate from elapsed time if no saved last_item_index
                        elapsed = (now - playout_start_time).total_seconds()
                        cycle_position = elapsed % total_duration if total_duration > 0 else 0

                        # Find which item index corresponds to cycle_position
                        current_time = 0
                        current_item_index = 0
                        for idx, item in enumerate(schedule_items):
                            media_item = item.get("media_item")
                            if not media_item:
                                continue
                            duration = media_item.duration or 1800
                            if current_time + duration > cycle_position:
                                current_item_index = idx
                                break
                            current_time += duration
                            current_item_index = idx + 1

                        if current_item_index >= len(schedule_items):
                            current_item_index = 0
                        
                        logger.debug(
                            f"Channel {channel.number}: EPG calculated current item index {current_item_index} from elapsed time (fallback - no saved last_item_index)"
                        )
                    else:
                        # No playout_start_time or total_duration - start from 0
                        current_item_index = 0
                        logger.debug(
                            f"Channel {channel.number}: EPG using item index 0 (no playout_start_time or total_duration)"
                        )

                    # Assign start times for repeat=True schedules
                    # CRITICAL: Always reassign start times to ensure sequential, unique times
                    # Even if items already have start_time, we need to ensure they're sequential
                    # This fixes the issue where ScheduleEngine generates items with same start_time
                    items_without_time = sum(
                        1 for item in schedule_items if not item.get("start_time")
                    )

                    # Check if all items have the same start_time (another issue to fix)
                    start_times = [
                        item.get("start_time") for item in schedule_items if item.get("start_time")
                    ]
                    all_same_time = (
                        len({str(t) for t in start_times}) == 1 if start_times else False
                    )

                    if (
                        items_without_time > 0
                        or all_same_time
                        or len(start_times) != len(schedule_items)
                    ):
                        if items_without_time > 0:
                            logger.info(
                                f"Assigning start times to {items_without_time} items without start_time for channel {channel.number}"
                            )
                        elif all_same_time:
                            logger.info(
                                f"Reassigning start times for channel {channel.number} - all items had same start_time"
                            )
                        else:
                            logger.info(
                                f"Reassigning start times for channel {channel.number} - ensuring sequential times"
                            )

                        # Calculate when the current item started playing
                        # REUSE the current_item_index calculated above instead of recalculating
                        if total_duration > 0 and playout_start_time:
                            # Calculate how many full cycles have elapsed
                            elapsed = (now - playout_start_time).total_seconds()
                            cycles_completed = (
                                int(elapsed // total_duration) if total_duration > 0 else 0
                            )
                            cycle_position = elapsed % total_duration if total_duration > 0 else 0

                            # Find start time of current item within the cycle (reuse current_item_index from above)
                            current_time_in_cycle = 0
                            current_item_start_in_cycle = 0
                            # Use the current_item_index already calculated above (line 471-484)
                            for idx in range(current_item_index):
                                item = schedule_items[idx]
                                media_item = item.get("media_item")
                                if not media_item:
                                    continue
                                duration = media_item.duration or 1800
                                current_time_in_cycle += duration

                            current_item_start_in_cycle = current_time_in_cycle

                            # Calculate absolute start time of current item
                            current_item_start_time = playout_start_time + timedelta(
                                seconds=(cycles_completed * total_duration)
                                + current_item_start_in_cycle
                            )
                        else:
                            # Fallback: start from now
                            current_item_start_time = now
                            # current_item_index already set above

                        # Assign start times starting from current item
                        current_item_time = current_item_start_time
                        # Start from current_item_index to maintain continuity
                        # CRITICAL: Must assign sequential times to ALL items, overwriting any existing times
                        # This ensures Plex sees proper sequential programme times

                        # CRITICAL FIX: Don't rotate items - assign start times in natural order (0, 1, 2, ...)
                        # This matches how actual playback works (sequential, not rotated)
                        # Calculate the start time of item 0 based on current position in cycle
                        # If current_item_index = 5, item 0's start time should be:
                        #   current_item_start_time - (sum of durations of items 0-4)
                        if current_item_index > 0:
                            # Calculate how much time has elapsed before current_item_index
                            time_before_current = 0
                            for idx in range(current_item_index):
                                item = schedule_items[idx]
                                media_item = item.get("media_item")
                                if media_item:
                                    time_before_current += media_item.duration or 1800

                            # Item 0's start time = current_item_start_time - time_before_current
                            # But we need to account for cycles completed
                            item_0_start_time = current_item_start_time - timedelta(
                                seconds=time_before_current
                            )
                        else:
                            item_0_start_time = current_item_start_time

                        # CRITICAL FIX: If item_0_start_time is in the past (before now),
                        # reset to start from current_item_start_time to ensure items are visible in EPG
                        # This prevents all items from being filtered out when playout_start_time is in the past
                        # We want to show items starting from the current item, not from item 0 in a past cycle
                        if item_0_start_time < now:
                            logger.info(
                                f"Channel {channel.number}: item_0_start_time ({item_0_start_time}) is in the past. "
                                f"Resetting to start from current_item_start_time ({current_item_start_time}) to ensure EPG visibility."
                            )
                            # Start from the current item's start time, not item 0
                            # This ensures we show items from now onwards
                            item_0_start_time = current_item_start_time
                            # Adjust current_item_index to 0 since we're starting from current_item_start_time
                            # But we need to keep track of which item is actually playing
                            # Actually, don't adjust - we want to show items starting from current_item_index
                            # So we should start assigning from current_item_index, not from 0
                            # Let's start from current_item_index and assign times forward from there

                        # Now assign start times starting from current_item_index
                        # If item_0_start_time was in the past, we start from current_item_start_time
                        # Otherwise, we start from item_0_start_time and assign to all items
                        if item_0_start_time < now:
                            # CRITICAL FIX: All items have start times in the past
                            # Start assigning from NOW to ensure EPG has visible programmes
                            # This is the root cause of "Unknown Airing" - all programmes were in the past!
                            
                            logger.info(
                                f"Channel {channel.number}: All items in past (item_0={item_0_start_time}, now={now}). "
                                f"Resetting to start EPG from NOW."
                            )
                            
                            # Start from NOW and assign times sequentially for ALL items
                            # This ensures Plex sees a continuous schedule starting from the current time
                            current_item_time = now
                            current_item_index = 0  # Start from beginning of schedule
                            
                            # Assign times to all items starting from now
                            for idx in range(len(schedule_items)):
                                item = schedule_items[idx]
                                media_item = item.get("media_item")
                                if media_item:
                                    duration = media_item.duration or 1800
                                else:
                                    duration = 1800
                                    logger.warning(
                                        f"Schedule item missing media_item for channel {channel.number}"
                                    )
                                
                                # ALWAYS assign/update start_time to ensure sequential times
                                item["start_time"] = current_item_time
                                
                                # Increment time for next item
                                current_item_time = current_item_time + timedelta(seconds=duration)
                        else:
                            # Normal case: assign times starting from item_0_start_time
                            current_item_time = item_0_start_time
                            for idx, item in enumerate(schedule_items):
                                media_item = item.get("media_item")
                                if media_item:
                                    duration = media_item.duration or 1800
                                else:
                                    duration = 1800
                                    logger.warning(
                                        f"Schedule item missing media_item for channel {channel.number}"
                                    )

                                # ALWAYS assign/update start_time to ensure sequential times
                                # This fixes the issue where all items had the same start_time
                                item["start_time"] = current_item_time

                                # Increment time for next item
                                current_item_time = current_item_time + timedelta(seconds=duration)

                    # Filter to only items within time range (now to end_time)
                    # Ensure all items have start_time set
                    # CRITICAL: For continuous channels with playout_start_time in the past,
                    # we need to include items that are part of the current cycle, even if their
                    # start_time is in the past. The key is to include items that will be playing
                    # between now and end_time, regardless of their absolute start_time.
                    filtered_items = []
                    items_without_time = 0
                    items_in_past = 0
                    items_in_future = 0
                    items_currently_playing = 0
                    items_in_next_cycle = 0
                    
                    # For continuous channels, calculate the cycle duration to determine
                    # which items are part of the current/next cycle
                    cycle_duration = sum(
                        (item.get("media_item", {}).duration or 1800)
                        for item in schedule_items
                        if item.get("media_item")
                    ) if schedule_items else 0
                    
                    for item in schedule_items:
                        if not item.get("start_time"):
                            # Skip items without start_time - they should have been assigned above
                            items_without_time += 1
                            continue
                        start = item["start_time"]
                        # Include items that start between now and end_time
                        # Also include items that are currently playing (start < now but end > now)
                        media_item = item.get("media_item")
                        if media_item:
                            duration = media_item.duration or 1800
                            end = start + timedelta(seconds=duration)
                            
                            # CRITICAL FIX: Check if item is currently playing FIRST
                            # If it's currently playing, include it regardless of cycle
                            if start < now and end > now:
                                # Item is currently playing - include it
                                filtered_items.append(item)
                                items_currently_playing += 1
                                continue
                            
                            # Include if it starts in the future (within time range)
                            if start >= now and start <= end_time:
                                filtered_items.append(item)
                                items_in_future += 1
                                continue
                            
                            # For continuous channels, also include items from the next cycle
                            # if they would be playing between now and end_time
                            # Only check for next cycle if item is NOT currently playing
                            if cycle_duration > 0 and start < now:
                                # This item is in the past, but check if it's part of the next cycle
                                cycles_until_next = int((now - start).total_seconds() // cycle_duration) + 1
                                next_cycle_start = start + timedelta(seconds=cycles_until_next * cycle_duration)
                                next_cycle_end = next_cycle_start + timedelta(seconds=duration)
                                # Include if the next cycle occurrence is between now and end_time
                                if next_cycle_start <= end_time and next_cycle_end > now:
                                    filtered_items.append({
                                        **item,
                                        "start_time": next_cycle_start,  # Use next cycle start time
                                    })
                                    items_in_next_cycle += 1
                                    continue
                            
                            # Item doesn't match any criteria - it's in the past
                            items_in_past += 1
                        elif start >= now and start <= end_time:
                            filtered_items.append(item)
                            items_in_future += 1
                        else:
                            items_in_past += 1
                    
                    schedule_items = filtered_items
                    logger.info(
                        f"After filtering: {len(schedule_items)} items within time range ({now} to {end_time}) for channel {channel.number}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to load schedule file for EPG: {e}")

            # Fallback to database if schedule file not available
            if not schedule_items:
                
                # Get channel's playouts and their items
                stmt = select(Playout).where(Playout.channel_id == channel.id, Playout.is_active == True)
                result = await db.execute(stmt)
                playouts = result.scalars().all()
                logger.debug(
                    f"Channel {channel.number} ({channel.name}): Found {len(playouts)} active playouts"
                )
                # #region agent log
                try:
                    import json as _j
                    with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                        f.write(_j.dumps({"location":"iptv.py:xmltv:playouts_query","message":"Queried playouts for channel","data":{"channel_number":str(channel.number),"channel_name":channel.name,"num_playouts":len(playouts)},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H6"}) + "\n")
                except: pass
                # #endregion

                # Get playout items if we have playouts
                if playouts:
                    playout = playouts[0]  # Use first active playout
                    
                    # Get playback position to know where we are in the playout
                    from ..database.models import ChannelPlaybackPosition
                    anchor_stmt = select(ChannelPlaybackPosition).where(
                        ChannelPlaybackPosition.channel_id == channel.id
                    )
                    anchor_result = await db.execute(anchor_stmt)
                    playback_position = anchor_result.scalar_one_or_none()
                    
                    # Get current item index (where the channel is actually playing)
                    start_offset = 0
                    if playback_position and playback_position.last_item_index is not None:
                        start_offset = playback_position.last_item_index
                    
                    # Query playout items starting from the current position
                    # This ensures we get the items that are currently playing and will play next
                    stmt = (
                        select(PlayoutItem)
                        .where(PlayoutItem.playout_id == playout.id)
                        .order_by(PlayoutItem.id)  # Use ID for stable ordering
                        .offset(start_offset)
                        .limit(MAX_EPG_ITEMS_PER_CHANNEL)
                    )
                    result = await db.execute(stmt)
                    playout_items = result.scalars().all()
                    
                    if playout_items:
                        # Note: playback_position was already queried above when we got the offset
                        
                        # Get media items for these playout items
                        media_ids = [item.media_item_id for item in playout_items if item.media_item_id]
                        media_items_dict = {}
                        if media_ids:
                            stmt = select(MediaItem).where(MediaItem.id.in_(media_ids))
                            result = await db.execute(stmt)
                            media_items_dict = {mi.id: mi for mi in result.scalars().all()}
                        
                        # CRITICAL FIX: For continuous channels, recalculate EPG times based on
                        # current playback position rather than using old playout_item times
                        # This ensures EPG shows what's playing NOW and in the future
                        
                        # #region agent log
                        try:
                            import json as _j
                            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                                f.write(_j.dumps({"location":"iptv.py:xmltv:epg_calc_start","message":"Starting EPG time calculation","data":{"channel_number":str(channel.number),"channel_name":channel.name,"num_playout_items":len(playout_items),"now":now.isoformat()},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H8-H9-H10"}) + "\n")
                        except: pass
                        # #endregion
                        
                        # Calculate total cycle duration (sum of all item durations)
                        total_cycle_duration = 0
                        item_durations = []
                        for item in playout_items:
                            if item.start_time and item.finish_time:
                                duration = (item.finish_time - item.start_time).total_seconds()
                            else:
                                mi = media_items_dict.get(item.media_item_id) if item.media_item_id else None
                                duration = (mi.duration if mi and mi.duration else 1800)
                            item_durations.append(duration)
                            total_cycle_duration += duration
                        
                        # Get the current item index - since we queried with offset,
                        # the first item in playout_items IS the current item (index 0 in this subset)
                        current_item_index = 0
                        
                        # Calculate when the current item started playing
                        # We trust that the first item in our query is currently playing
                        # Assume the item just started (conservative approach for timing)
                        time_into_item = 0
                        current_item_start = now - timedelta(seconds=time_into_item)
                        
                        # Build schedule items starting from current item with proper times
                        schedule_time = current_item_start
                        items_added = 0
                        max_items_to_add = min(len(playout_items) * 2, EPG_MAX_PROGRAMMES_PER_CHANNEL)  # Allow cycling
                        
                        # Start from current item and go forward
                        idx = current_item_index
                        while items_added < max_items_to_add and schedule_time <= end_time:
                            item = playout_items[idx]
                            media_item = media_items_dict.get(item.media_item_id) if item.media_item_id else None
                            duration = item_durations[idx]
                            
                            item_end_time = schedule_time + timedelta(seconds=duration)
                            
                            # Only add items that end after now (currently playing or future)
                            if item_end_time > now:
                                schedule_items.append({
                                    "media_item": media_item,
                                    "title": item.title,
                                    "custom_title": item.custom_title,
                                    "filler_kind": item.filler_kind,
                                    "start_time": schedule_time,
                                    "finish_time": item_end_time,
                                })
                                items_added += 1
                            
                            schedule_time = item_end_time
                            idx = (idx + 1) % len(playout_items)  # Wrap around for continuous channels
                            
                            # Safety: prevent infinite loop
                            if items_added >= max_items_to_add:
                                break
                        
                        logger.debug(
                            f"Channel {channel.number} ({channel.name}): Generated {len(schedule_items)} EPG items from playout (current_idx={current_item_index})"
                        )

            # Generate EPG entries from schedule items
            # If no schedule items, add a placeholder programme so Plex can map the channel
            # Plex requires at least one programme entry per channel
            if not schedule_items:
                logger.warning(
                    f"No schedule items found for channel {channel.number} ({channel.name}) - adding placeholder"
                )
                # #region agent log
                try:
                    import json as _j
                    with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                        f.write(_j.dumps({"location":"iptv.py:xmltv:no_schedule_items","message":"Channel has no schedule items - using placeholder","data":{"channel_number":str(channel.number),"channel_name":channel.name,"channel_id":channel.id},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H6"}) + "\n")
                except: pass
                # #endregion
                # Add a placeholder programme for the full EPG build period to ensure Plex shows something
                # Use the full end_time instead of just 24 hours to cover the entire EPG period
                start_str = now.strftime("%Y%m%d%H%M%S +0000")
                end_str = end_time.strftime("%Y%m%d%H%M%S +0000")
                channel_id = str(channel.number).strip()
                xml_content += f'  <programme start="{_xml(start_str)}" stop="{_xml(end_str)}" channel="{_xml(channel_id)}">\n'
                # Use a more descriptive title that Plex will recognize
                xml_content += f'    <title lang="en">{_xml(channel.name)} - Live Stream</title>\n'
                xml_content += f'    <desc lang="en">Continuous live programming on {_xml(channel.name)}. This channel streams content 24/7.</desc>\n'
                xml_content += '    <category lang="en">General</category>\n'
                xml_content += '    <category lang="en">Live</category>\n'
                xml_content += "  </programme>\n"
            # Log first and last programme times for debugging
            elif schedule_items:
                first_start = schedule_items[0].get("start_time")
                last_item = schedule_items[-1] if schedule_items else None
                if first_start:
                    logger.debug(
                        f"Channel {channel.number} EPG: First programme at {first_start}, {len(schedule_items)} total items"
                    )

            programme_count = 0
            current_time = (
                now  # Initialize current_time for fallback case (ensures sequential times)
            )

            for schedule_item in schedule_items:
                if programme_count >= EPG_MAX_PROGRAMMES_PER_CHANNEL:
                    break

                media_item = schedule_item.get("media_item")
                if not media_item:
                    logger.debug(
                        f"Skipping schedule item without media_item for channel {channel.number}"
                    )
                    continue

                # Get start_time from schedule_item, or use current_time as fallback
                # CRITICAL: Each item must have a unique, sequential start_time for Plex
                if schedule_item.get("start_time"):
                    start_time = schedule_item["start_time"]
                else:
                    # Fallback: use current_time and increment it
                    # This should rarely happen if schedule generation is working correctly
                    start_time = current_time if "current_time" in locals() else now

                # Use custom title if available, otherwise use media item title.
                # If missing, fall back to the URL basename to avoid Plex showing "Unknown Airing".
                # Plex shows "Unknown Airing" if title is empty, None, or missing
                title = schedule_item.get("custom_title")
                if not title:
                    # Get media item title, handling None safely
                    title = media_item.title if (media_item and media_item.title) else None
                
                # Ensure title is never None or empty - Plex shows "Unknown Airing" for empty titles
                if not title or (isinstance(title, str) and not title.strip()):
                    try:
                        from pathlib import Path

                        parsed_url = urllib.parse.unquote(media_item.url or "")
                        fallback_base = Path(parsed_url).name.rsplit(".", 1)[0]
                        title = fallback_base or channel.name
                    except Exception:
                        title = channel.name
                
                # Final safety check - ensure title is never empty
                # Convert to string and strip whitespace
                title = str(title) if title else str(channel.name)
                title = title.strip()
                
                # One more check after stripping - must never be empty
                if not title:
                    title = str(channel.name)

                # Initialize current_time for next iteration (if needed)
                if "current_time" not in locals():
                    current_time = start_time

                # Extract episode-specific information from metadata for better titles
                # Use structured metadata fields first (ErsatzTV-style)
                # Use getattr with defaults for attributes that may not exist in the model
                episode_title = getattr(media_item, 'episode_title', None)
                season_num = getattr(media_item, 'season_number', None)
                episode_num = getattr(media_item, 'episode_number', None)
                series_title = getattr(media_item, 'series_title', None) or getattr(media_item, 'show_title', None)
                air_date = getattr(media_item, 'episode_air_date', None)
                genres = getattr(media_item, 'genres', None)
                actors = getattr(media_item, 'actors', None)
                directors = getattr(media_item, 'directors', None)
                content_rating = getattr(media_item, 'content_rating', None)

                # Fallback to meta_data JSON if structured fields are not available
                if not episode_title or not season_num or not episode_num:
                    if getattr(media_item, 'meta_data', None):
                        try:
                            import json

                            meta = json.loads(media_item.meta_data)
                            if not episode_title:
                                episode_title = meta.get("episode_title") or meta.get("title")
                            if season_num is None:
                                season_num = meta.get("season")
                            if episode_num is None:
                                episode_num = meta.get("episode")
                            if not series_title:
                                series_title = meta.get("series_title") or meta.get("show")
                            if not air_date:
                                air_date = meta.get("air_date") or meta.get("date")
                            if not genres:
                                genres = meta.get("genres") or meta.get("categories")
                            if not actors:
                                actors = meta.get("actors")
                            if not directors:
                                directors = meta.get("directors")
                            if not content_rating:
                                content_rating = meta.get("content_rating") or meta.get("rating")
                        except Exception:
                            pass

                # Also try to extract season/episode from title if it matches patterns like "S03E05" or "S03E00"
                import re

                if season_num is None or episode_num is None:
                    title_match = re.search(r"[Ss](\d+)[Ee](\d+)", title)
                    if title_match:
                        if season_num is None:
                            season_num = int(title_match.group(1))
                        if episode_num is None:
                            episode_num = int(title_match.group(2))

                # For Sesame Street and similar shows, try to extract episode info from description
                # Descriptions like "Original air date: July 21, 1969" can help identify episodes
                # NOTE: air_date was already extracted from media_item.episode_air_date at line 1815
                # Only try to extract from description if we don't have it
                if not air_date and not episode_title and media_item.description:
                    desc = media_item.description
                    # If description has air date but no episode title, use air date as identifier
                    # Match full date including year: "July 21, 1969" or "November 10, 1969"
                    air_date_match = re.search(
                        r"Original air date:\s*([A-Za-z]+\s+\d+,\s+\d{4})", desc
                    )
                    if air_date_match:
                        air_date = air_date_match.group(1).strip()
                        if air_date:
                            # Use air date as episode identifier for better EPG display
                            episode_title = f"Original air date: {air_date}"

                # Enhance title with episode information if available
                # For series like Sesame Street and Mister Rogers, show episode details
                # Keep the main show name as title, use sub-title for episode details
                # Clean up title to remove collection suffixes and season/episode patterns for better display
                show_name = title
                # Remove season/episode pattern from title (e.g., "Show Name S03E00" -> "Show Name")
                title_clean = re.sub(r"\s+[Ss]\d+[Ee]\d+$", "", title)
                if title_clean != title and title_clean.strip():
                    show_name = title_clean
                    title = show_name

                # Remove collection suffixes like "- 1960s-1970s" for better display
                if " - " in title:
                    # Try to extract just the show name (before collection suffix)
                    parts = title.split(" - ")
                    if len(parts) >= 2:
                        # Check if second part looks like a collection name (e.g., "1960s-1970s", "Season 3")
                        second_part = parts[1]
                        if any(
                            x in second_part.lower()
                            for x in [
                                "season",
                                "1960s",
                                "1970s",
                                "1980s",
                                "1990s",
                                "2000s",
                                "2010s",
                            ]
                        ):
                            show_name = parts[0].strip()
                            # Only use cleaned name if it's not empty, otherwise keep original title
                            if show_name:
                                title = show_name

                if season_num is not None and episode_num is not None:
                    # Format: "Show Name" with sub-title "S03E05 - Episode Title"
                    # Don't modify title here, will use sub-title field below
                    pass
                elif episode_num is not None:
                    # Format: "Show Name" with sub-title "Episode X"
                    # Don't modify title, will use sub-title
                    pass
                elif episode_title and air_date:
                    # For Sesame Street with air dates, keep title clean, use sub-title
                    # Don't modify title here
                    pass

                duration = media_item.duration or 1800

                # Calculate start/end times
                # CRITICAL: Each programme must have a unique, sequential start_time
                # Plex requires non-overlapping programmes with proper time sequencing
                if schedule_item.get("start_time"):
                    start_time = schedule_item["start_time"]
                else:
                    # Fallback: use current_time and increment it for next item
                    # This ensures sequential times even if schedule items lack start_time
                    start_time = current_time

                # Use finish_time from playout item if available (ErsatzTV-style)
                # This is more accurate than calculating from media_item.duration
                if schedule_item.get("finish_time"):
                    end_time_prog = schedule_item["finish_time"]
                else:
                    # Fallback to calculated duration
                    end_time_prog = start_time + timedelta(seconds=duration)

                # Update current_time for next iteration to ensure sequential times
                current_time = end_time_prog

                # Only include if within EPG time range
                # CRITICAL: Items were already filtered, so they should ALL pass this check
                # The filtering logic includes items that:
                # 1. Start in the future (start >= now and start <= end_time)
                # 2. Are currently playing (start < now and end > now)
                # 3. Are in the next cycle (for continuous channels)
                # Since items were already filtered, we should include ALL of them here
                # But we double-check to ensure they're within the EPG time window for safety
                is_currently_playing = start_time < now and end_time_prog > now
                is_future = start_time >= now and start_time <= end_time
                # Also include items that end in the future (even if they started in the past)
                # This ensures items that are part of the current cycle are included
                ends_in_future = end_time_prog > now and end_time_prog <= end_time
                
                # CRITICAL FIX: Items were already filtered, so they should ALL be included
                # The filtering logic at line 984 already includes items that:
                # 1. Start in the future (start >= now and start <= end_time)
                # 2. Are currently playing (start < now and end > now)
                # 3. Are in the next cycle (for continuous channels)
                # Since items passed the filter, we should include ALL of them here
                # The double-check was causing items to be excluded incorrectly
                # Only exclude if the item is completely outside the EPG window (both start and end are in the past or too far in the future)
                should_include = True  # Include all filtered items
                
                # Safety check: only exclude if item is completely outside EPG window
                # This should rarely happen since items were already filtered
                if end_time_prog < now or start_time > end_time:
                    should_include = False
                    # #region agent log
                    if programme_count == 0:  # Only log first excluded item per channel
                        try:
                            import json as _j
                            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                                f.write(_j.dumps({"location":"iptv.py:xmltv:item_excluded","message":"Programme excluded - outside time window","data":{"channel_number":str(channel.number),"item_start":start_time.isoformat() if start_time else None,"item_end":end_time_prog.isoformat() if end_time_prog else None,"now":now.isoformat(),"epg_end":end_time.isoformat(),"reason":"end < now" if end_time_prog < now else "start > end_time","title":title[:50] if title else None},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H7"}) + "\n")
                        except: pass
                    # #endregion
                
                if should_include:
                    programme_count += 1
                    start_str = start_time.strftime("%Y%m%d%H%M%S +0000")
                    end_str = end_time_prog.strftime("%Y%m%d%H%M%S +0000")

                    # Use channel number as ID (must match channel definition)
                    channel_id = str(channel.number).strip()
                    xml_content += f'  <programme start="{_xml(start_str)}" stop="{_xml(end_str)}" channel="{_xml(channel_id)}">\n'

                    # Parse metadata JSON early to extract language and other metadata
                    meta = None
                    language_code = "en"  # Default to English
                    if media_item.meta_data:
                        try:
                            import json

                            meta = json.loads(media_item.meta_data)

                            # Extract language code from metadata
                            if meta.get("language"):
                                lang_str = str(meta.get("language", "")).strip()
                                if len(lang_str) >= 2:
                                    language_code = lang_str[:2].lower()
                                    # Map common language names to codes
                                    lang_map = {
                                        "english": "en",
                                        "en": "en",
                                        "spanish": "es",
                                        "es": "es",
                                        "french": "fr",
                                        "fr": "fr",
                                        "german": "de",
                                        "de": "de",
                                        "italian": "it",
                                        "it": "it",
                                        "japanese": "ja",
                                        "ja": "ja",
                                        "chinese": "zh",
                                        "zh": "zh",
                                    }
                                    if lang_str.lower() in lang_map:
                                        language_code = lang_map[lang_str.lower()]
                        except Exception:
                            pass

                    # Title is required by XMLTV spec and Plex
                    # Ensure title is never empty - fallback to channel name if somehow empty
                    # Plex shows "Unknown Airing" if title tag is missing or empty
                    final_title = str(title).strip() if title else None
                    if not final_title or final_title == "":
                        final_title = channel.name
                    
                    # Final safety check - must never be empty
                    if not final_title or final_title.strip() == "":
                        final_title = f"Channel {channel.number}"
                    
                    xml_content += (
                        f'    <title lang="{language_code}">{_xml(final_title)}</title>\n'
                    )
                    
                    # #region agent log
                    if programme_count <= 3:  # Only log first 3 programmes per channel
                        try:
                            import json as json_mod
                            with open("/Users/roto1231/Documents/XCode Projects/EXStreamTV/.cursor/debug.log", "a") as f:
                                f.write(json_mod.dumps({"location":"iptv.py:xmltv:programme","message":"EPG programme created","data":{"channel_id":channel_id,"channel_name":channel.name,"start":start_str,"stop":end_str,"title":final_title[:60],"programme_num":programme_count},"timestamp":datetime.utcnow().isoformat(),"sessionId":"debug-session","hypothesisId":"H1-H2-H5"}) + "\n")
                        except: pass
                    # #endregion

                    # Add sub-title if we have episode-specific information
                    # This helps Plex display episode details better
                    if season_num is not None and episode_num is not None:
                        sub_title = f"S{int(season_num):02d}E{int(episode_num):02d}"
                        if (
                            episode_title
                            and episode_title != title
                            and "Original air date" not in episode_title
                        ):
                            sub_title = f"{sub_title} - {episode_title}"
                        xml_content += (
                            f'    <sub-title lang="{language_code}">{_xml(sub_title)}</sub-title>\n'
                        )
                    elif episode_num is not None:
                        sub_title = f"Episode {int(episode_num)}"
                        if (
                            episode_title
                            and episode_title != title
                            and "Original air date" not in episode_title
                        ):
                            sub_title = f"{sub_title} - {episode_title}"
                        xml_content += (
                            f'    <sub-title lang="{language_code}">{_xml(sub_title)}</sub-title>\n'
                        )
                    elif episode_title and air_date:
                        # For Sesame Street with air dates, use air date as sub-title
                        xml_content += (
                            f'    <sub-title lang="{language_code}">{_xml(air_date)}</sub-title>\n'
                        )
                    elif (
                        episode_title
                        and episode_title != title
                        and "Original air date" not in episode_title
                    ):
                        xml_content += f'    <sub-title lang="{language_code}">{_xml(episode_title)}</sub-title>\n'

                    # Description - always include for Plex compatibility
                    # Plex requires desc tag even if empty
                    desc = media_item.description or ""
                    # Enhance description with episode info if available
                    if episode_title and episode_title not in desc and episode_title != title:
                        desc = f"{episode_title}\n\n{desc}" if desc else episode_title
                    if not desc:
                        # Provide a non-empty description to avoid "Unknown Airing" in Plex
                        desc = title
                    if desc:
                        xml_content += f'    <desc lang="{language_code}">{_xml(desc)}</desc>\n'
                    else:
                        # Include empty desc to ensure Plex compatibility
                        xml_content += f'    <desc lang="{language_code}"></desc>\n'

                    # Thumbnail/icon - ensure absolute URL for Plex
                    if media_item.thumbnail:
                        # Ensure thumbnail URL is absolute
                        if media_item.thumbnail.startswith("http"):
                            # Already absolute, use as-is (may already include Plex token)
                            thumb_url = media_item.thumbnail
                        else:
                            # Relative path - make absolute
                            thumb_url = (
                                f"{base_url}{media_item.thumbnail}"
                                if media_item.thumbnail.startswith("/")
                                else f"{base_url}/{media_item.thumbnail}"
                            )
                        xml_content += f'    <icon src="{_xml(thumb_url)}"/>\n'

                    # Enhanced EPG metadata - use standard XMLTV fields only
                    # Plex expects at least one category
                    filler_kind = schedule_item.get("filler_kind")
                    categories_added = False

                    # Meta is already parsed above for language extraction

                    # Use categories from metadata (Archive.org subject/tags)
                    if meta:
                        # Archive.org subject field contains tags/categories
                        subjects = meta.get("subject", [])
                        if not subjects and meta.get("categories"):
                            # Fallback to categories field
                            subjects = meta.get("categories", [])

                        if isinstance(subjects, list) and subjects:
                            for cat in subjects[:EPG_CATEGORIES_LIMIT]:  # Limit categories for performance
                                if cat and str(cat).strip():
                                    xml_content += f'    <category lang="en">{_xml(str(cat).strip())}</category>\n'
                                    categories_added = True

                    # Use filler_kind if no categories from metadata
                    if not categories_added and filler_kind:
                        xml_content += f'    <category lang="en">{_xml(filler_kind)}</category>\n'
                        categories_added = True

                    # Default category if none found
                    if not categories_added:
                        xml_content += '    <category lang="en">General</category>\n'

                    # Credits (creators, contributors, publishers) - ErsatzTV-style
                    credits_items = []

                    # Use structured directors field first
                    if directors:
                        try:
                            import json

                            if isinstance(directors, str):
                                directors_list = (
                                    json.loads(directors)
                                    if directors.startswith("[")
                                    else [directors]
                                )
                            elif isinstance(directors, list):
                                directors_list = directors
                            else:
                                directors_list = []

                            for director in directors_list[:3]:  # Limit to 3 directors
                                if director and str(director).strip():
                                    credits_items.append(("director", str(director).strip()))
                        except Exception:
                            pass

                    # Fallback to uploader as director
                    if not credits_items and media_item.uploader:
                        credits_items.append(("director", media_item.uploader))

                    # Use structured actors field
                    if actors:
                        try:
                            import json

                            if isinstance(actors, str):
                                actors_list = (
                                    json.loads(actors) if actors.startswith("[") else [actors]
                                )
                            elif isinstance(actors, list):
                                actors_list = actors
                            else:
                                actors_list = []

                            for actor in actors_list[:5]:  # Limit to 5 actors
                                if actor and str(actor).strip():
                                    credits_items.append(("actor", str(actor).strip()))
                        except Exception:
                            pass

                    # Add publisher as producer/studio
                    if meta and meta.get("publisher"):
                        credits_items.append(("producer", meta.get("publisher")))

                    # Add contributors as actors or writers
                    if meta and meta.get("contributor"):
                        contributors = meta.get("contributor", [])
                        if isinstance(contributors, list):
                            # Use first contributor as writer, or split among roles
                            for idx, contrib in enumerate(
                                contributors[:3]
                            ):  # Limit to 3 contributors
                                if contrib and str(contrib).strip():
                                    role = "writer" if idx == 0 else "actor"
                                    credits_items.append((role, str(contrib).strip()))

                    if credits_items:
                        xml_content += "    <credits>\n"
                        for role, name in credits_items:
                            xml_content += f"      <{role}>{_xml(name)}</{role}>\n"
                        xml_content += "    </credits>\n"
                    elif media_item.uploader:
                        # Fallback to old format if no enhanced metadata
                        xml_content += "    <credits>\n"
                        xml_content += f"      <director>{_xml(media_item.uploader)}</director>\n"
                        xml_content += "    </credits>\n"

                    # Date/Year (standard XMLTV date field)
                    # Priority: episode_air_date > upload_date > meta.year
                    date_to_use = None
                    if air_date:
                        # Use episode air date from database (formatted as YYYY-MM-DD)
                        date_to_use = str(air_date)
                    elif media_item.upload_date:
                        date_to_use = str(media_item.upload_date)
                    elif meta and meta.get("year"):
                        # Use year if date not available
                        date_to_use = str(meta.get("year"))
                    if date_to_use:
                        xml_content += f"    <date>{_xml(date_to_use)}</date>\n"

                    # Language (add lang attribute to title/desc if available)
                    language_code = None
                    if meta and meta.get("language"):
                        lang_str = str(meta.get("language", "")).strip()
                        # Extract ISO 639-1 code (first 2 letters) if available
                        if len(lang_str) >= 2:
                            language_code = lang_str[:2].lower()
                            # Map common language names to codes
                            lang_map = {
                                "english": "en",
                                "en": "en",
                                "spanish": "es",
                                "es": "es",
                                "french": "fr",
                                "fr": "fr",
                                "german": "de",
                                "de": "de",
                                "italian": "it",
                                "it": "it",
                                "japanese": "ja",
                                "ja": "ja",
                                "chinese": "zh",
                                "zh": "zh",
                            }
                            if lang_str.lower() in lang_map:
                                language_code = lang_map[lang_str.lower()]

                    # Episode metadata (for series/episodes)
                    # PRIORITY: Use structured fields (season_num, episode_num) first, then fallback to meta_data JSON
                    final_season = season_num
                    final_episode = episode_num
                    
                    # Fallback to meta_data JSON if structured fields are not available
                    if meta and final_episode is None:
                        if meta.get("episode"):
                            final_episode = meta.get("episode")
                        if meta.get("season") and final_season is None:
                            final_season = meta.get("season")
                    
                    # Add episode numbering if we have episode info
                    if final_episode is not None:
                        # Onscreen episode number (e.g., "5" or "S03E05")
                        if final_season is not None:
                            onscreen_ep = f"S{int(final_season):02d}E{int(final_episode):02d}"
                        else:
                            onscreen_ep = str(final_episode)
                        xml_content += f'    <episode-num system="onscreen">{_xml(onscreen_ep)}</episode-num>\n'
                        
                        # XMLTV_NS format: season-1.episode-1. (zero-indexed)
                        if final_season is not None:
                            try:
                                season_idx = int(final_season) - 1
                                episode_idx = int(final_episode) - 1
                                # XMLTV_NS format is "season.episode.part" (all zero-indexed)
                                season_ep = f"{season_idx}.{episode_idx}."
                                xml_content += f'    <episode-num system="xmltv_ns">{_xml(season_ep)}</episode-num>\n'
                            except (ValueError, TypeError):
                                pass

                    # Only include standard XMLTV fields - remove custom fields that might confuse Plex
                    # URL field is optional in XMLTV and can cause issues if it's not accessible
                    # We'll skip it to avoid Plex metadata grab failures

                    xml_content += "  </programme>\n"

                current_time = end_time_prog

                if current_time > end_time:
                    break

        xml_content += "</tv>\n"

        # Clean up Plex API client if used
        if plex_client:
            try:
                await plex_client.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Plex client cleanup: {e}")

        generation_time = time.time() - perf_start_time
        logger.info(f"XMLTV EPG generated in {generation_time:.2f}s ({len(xml_content)} bytes)")

        return Response(
            content=xml_content,
            media_type="application/xml; charset=utf-8",
            headers={
                "Content-Disposition": "inline; filename=xmltv.xml",
                "Cache-Control": "public, max-age=300",  # Cache for 5 minutes
                "X-Generated-At": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "X-Generation-Time": f"{generation_time:.2f}s",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import time
        error_traceback = traceback.format_exc()
        logger.error(f"Error generating XMLTV EPG: {e}", exc_info=True)
        logger.error(f"Error traceback: {error_traceback}")
        error_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        error_xml += '<tv generator-info-name="StreamTV">\n'
        error_xml += f"  <error>{_xml(str(e))}</error>\n"
        error_xml += "</tv>\n"
        return Response(
            content=error_xml,
            media_type="application/xml; charset=utf-8",
            status_code=500,
            headers={"Content-Disposition": "inline; filename=xmltv.xml"},
        )

@router.get("/iptv/channel/{channel_number}.m3u8")
async def get_hls_stream(
    channel_number: str,
    access_token: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Get HLS stream for a channel"""

    try:
        # Validate access token if required
        # If access_token is None in config, allow requests without token (for Plex compatibility)
        if config.security.api_key_required:
            # Only require token if both api_key_required=True AND access_token is set
            if config.security.api_key_required and config.security.access_token:
                if access_token != config.security.access_token:
                    raise HTTPException(status_code=401, detail="Invalid access token")

        # Query channel using raw SQL to avoid enum conversion issues
        from sqlalchemy import text

        from ..database.models import StreamingMode

        channel = None
        try:
            # Use async query for AsyncSession
            channel_stmt = select(Channel).where(
                Channel.number == channel_number,
                Channel.enabled == True
            )
            channel_result = await db.execute(channel_stmt)
            channel = channel_result.scalar_one_or_none()
        except (LookupError, ValueError) as e:
            # If enum conversion fails, query raw and convert manually
            logger.warning(f"Enum conversion error in HLS endpoint, using raw query: {e}")
            result = await db.execute(
                text("SELECT * FROM channels WHERE number = :number AND enabled = :enabled"),
                {"number": channel_number, "enabled": True},
            )
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Channel not found")

            # Create channel object from row
            channel = Channel()
            for key, value in row._mapping.items():
                if key == "streaming_mode" and value:
                    try:
                        setattr(channel, key, StreamingMode(value))
                    except ValueError:
                        setattr(channel, key, StreamingMode.TRANSPORT_STREAM_HYBRID)
                else:
                    setattr(channel, key, value)

        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        # Try to load schedule file first
        schedule_file = ScheduleParser.find_schedule_file(channel_number)
        schedule_items = []

        if schedule_file:
            try:
                logger.info(f"Loading schedule from: {schedule_file}")
                parsed_schedule = ScheduleParser.parse_file(schedule_file, schedule_file.parent)
                schedule_engine = ScheduleEngine(db)
                schedule_items = schedule_engine.generate_playlist_from_schedule(
                    channel,
                    parsed_schedule,
                    max_items=1000,  # Limit to prevent huge playlists
                )
                logger.info(f"Generated {len(schedule_items)} items from schedule")
            except Exception as e:
                logger.warning(f"Failed to load schedule file {schedule_file}: {e}")
                logger.info("Falling back to playlist-based streaming")

        # Fallback to playout items if schedule not available or failed
        if not schedule_items:
            
            # Get active playout for channel (same logic as ChannelManager) - async query
            playout_stmt = select(Playout).where(
                Playout.channel_id == channel.id,
                Playout.is_active == True
            )
            playout_result = await db.execute(playout_stmt)
            playout = playout_result.scalar_one_or_none()
            
            if not playout:
                raise HTTPException(status_code=404, detail="No active playout found for channel")

            # Get playout items joined with media items - async query
            items_stmt = select(PlayoutItem, MediaItem).outerjoin(
                MediaItem, PlayoutItem.media_item_id == MediaItem.id
            ).where(
                PlayoutItem.playout_id == playout.id
            ).order_by(PlayoutItem.start_time)
            items_result = await db.execute(items_stmt)
            playout_items = items_result.all()

            if not playout_items:
                raise HTTPException(status_code=404, detail="Playout has no items")

            # Convert playout items to schedule format
            for playout_item, media_item in playout_items:
                if media_item:
                    schedule_items.append(
                        {
                            "media_item": media_item,
                            "custom_title": playout_item.title,
                            "filler_kind": None,
                            "start_time": playout_item.start_time,
                        }
                    )

        # If we still have no items, return 404
        if not schedule_items:
            raise HTTPException(status_code=404, detail="No media items found for channel")

        # ------------------------------------------------------------------
        # Time-align playlist to behave like a live channel (join-in-progress)
        # ------------------------------------------------------------------
        #
        # We emulate the same playout timeline as ChannelManager:
        # - Playout starts at midnight UTC of the day the channel was created
        # - Use current UTC time to find position within the repeating schedule
        # - Start the HLS playlist from the item that should be playing now
        #
        now_utc = datetime.utcnow()
        try:
            creation_date_utc = channel.created_at.replace(tzinfo=None)
        except Exception:
            creation_date_utc = now_utc
        playout_start_time = datetime.combine(creation_date_utc.date(), dt_time.min)

        elapsed_since_start = (now_utc - playout_start_time).total_seconds()
        elapsed_since_start = max(elapsed_since_start, 0)

        # Total duration of one full schedule loop
        total_schedule_duration = 0
        for item in schedule_items:
            media = item.get("media_item")
            if not media:
                continue
            dur = media.duration or 1800  # Default 30 minutes if unknown
            if dur <= 0:
                dur = 1800
            total_schedule_duration += dur

        # Fallback: if total duration is zero, start from the first item
        current_index = 0
        if total_schedule_duration > 0:
            loop_position = elapsed_since_start % total_schedule_duration
            time_offset = 0.0
            idx_candidate = 0
            for idx, item in enumerate(schedule_items):
                media = item.get("media_item")
                if not media:
                    continue
                dur = media.duration or 1800
                if dur <= 0:
                    dur = 1800

                if time_offset + dur > loop_position:
                    idx_candidate = idx
                    break
                time_offset += dur
                idx_candidate = idx + 1

            if idx_candidate >= len(schedule_items):
                idx_candidate = 0

            current_index = idx_candidate

        # Reorder items so playlist starts from the live position
        if current_index > 0:
            ordered_items = schedule_items[current_index:] + schedule_items[:current_index]
        else:
            ordered_items = schedule_items

        # Generate HLS playlist (ErsatzTV-compatible approach)
        # Create a playlist that ensures continuous playback of all videos in sequence,
        # starting from the item that should be live right now.
        # Note: This uses MP4 files as segments for simplicity; true HLS would use FFmpeg segmentation.

        base_url = config.server.base_url
        if request:
            scheme = request.url.scheme
            host = request.url.hostname
            port = request.url.port
            base_url = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"

        token_param = f"?access_token={access_token}" if access_token else ""

        m3u8_content = "#EXTM3U\n"
        m3u8_content += "#EXT-X-VERSION:3\n"

        # Calculate target duration (use max segment duration)
        max_duration = 0
        total_duration = 0
        for schedule_item in ordered_items:
            media_item = schedule_item["media_item"]
            if media_item:
                duration = media_item.duration or 1800
                max_duration = max(max_duration, duration)
                total_duration += duration

        # Target duration should be at least the longest segment
        target_duration = max(30, int(max_duration) + 1)
        m3u8_content += f"#EXT-X-TARGETDURATION:{target_duration}\n"
        # Use current_index as media sequence so players see this as a rolling playlist
        m3u8_content += f"#EXT-X-MEDIA-SEQUENCE:{current_index}\n"

        # Treat this as an EVENT-like playlist (no ENDLIST) so it feels live.
        # We intentionally omit #EXT-X-PLAYLIST-TYPE to keep clients flexible.

        # Add all schedule items in sequence with 100% metadata, starting from live position
        for idx, schedule_item in enumerate(ordered_items):
            media_item = schedule_item["media_item"]
            if media_item:
                duration = media_item.duration or 1800
                # Use custom title if available (ErsatzTV supports custom titles)
                title = schedule_item.get("custom_title") or media_item.title

                # Build comprehensive metadata string for EXTINF
                metadata_parts = [title]

                # Add ALL available metadata
                if media_item.description:
                    desc = (
                        media_item.description[:200]
                        .replace("\n", " ")
                        .replace("\r", " ")
                        .replace(",", "\\,")
                    )
                    metadata_parts.append(f"Description: {desc}")

                if media_item.uploader:
                    metadata_parts.append(f"Uploader: {media_item.uploader}")

                if media_item.upload_date:
                    metadata_parts.append(f"Date: {media_item.upload_date}")

                if media_item.view_count:
                    metadata_parts.append(f"Views: {media_item.view_count}")

                if media_item.source_id:
                    metadata_parts.append(f"Source ID: {media_item.source_id}")

                if media_item.source:
                    source_val = media_item.source.value if hasattr(media_item.source, 'value') else str(media_item.source)
                    metadata_parts.append(f"Source: {source_val}")

                # Parse and add meta_data JSON fields
                if media_item.meta_data:
                    import json

                    try:
                        meta = json.loads(media_item.meta_data)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        meta = None

                    if isinstance(meta, dict):
                        for key, value in meta.items():
                            if value and str(value) not in ["None", "null", ""]:
                                value_str = str(value)[:100].replace(",", "\\,")
                                metadata_parts.append(f"{key}: {value_str}")

                # Combine all metadata (escape commas for M3U8)
                full_metadata = " | ".join(metadata_parts).replace("\n", " ").replace("\r", " ")

                m3u8_content += f"#EXTINF:{duration:.3f},{full_metadata}\n"

                # Add custom metadata tags (some players support these)
                source_val = media_item.source.value if hasattr(media_item.source, 'value') else str(media_item.source)
                m3u8_content += f"#EXT-X-METADATA:SOURCE={source_val}\n"
                if media_item.uploader:
                    # Escape comma for M3U8 format (extract to variable to avoid f-string backslash issue in Python 3.10)
                    escaped_uploader = media_item.uploader.replace(",", "\\,")
                    m3u8_content += f"#EXT-X-METADATA:UPLOADER={escaped_uploader}\n"
                if media_item.upload_date:
                    m3u8_content += f"#EXT-X-METADATA:UPLOAD_DATE={media_item.upload_date}\n"
                if media_item.thumbnail:
                    m3u8_content += f"#EXT-X-METADATA:THUMBNAIL={media_item.thumbnail}\n"
                if media_item.view_count:
                    m3u8_content += f"#EXT-X-METADATA:VIEW_COUNT={media_item.view_count}\n"
                if media_item.source_id:
                    m3u8_content += f"#EXT-X-METADATA:SOURCE_ID={media_item.source_id}\n"

                # Stream URL points to the actual media stream
                # For direct HLS URLs, use MPEG-TS endpoint instead
                # Browsers cannot play DRM-protected HLS streams directly, so we need to transcode
                # However, include the original URL as a comment for the web player to use if possible
                if media_item.url and ".m3u8" in media_item.url.lower():
                    # Direct HLS stream - use MPEG-TS endpoint for browser compatibility
                    # The MPEG-TS endpoint will transcode the HLS stream for browser playback
                    # Include original URL as comment for web player
                    original_url = media_item.url
                    m3u8_content += f"#EXT-X-ORIGINAL-URL:{original_url}\n"
                    stream_url = f"{base_url}/iptv/channel/{channel.number}.ts{token_param}"
                    logger.debug(
                        f"Using MPEG-TS endpoint for HLS stream (media {media_item.id}), original URL: {original_url}"
                    )
                elif (media_item.source == StreamSource.YOUTUBE or 
                    (isinstance(media_item.source, str) and media_item.source.lower() == 'youtube') or
                    (media_item.url and ("youtube.com" in media_item.url or "youtu.be" in media_item.url))
                ):
                    # YouTube streams require FFmpeg transcoding to handle auth and format conversion
                    # Direct HTTP streaming from googlevideo.com URLs returns 403 errors
                    # Use the MPEG-TS endpoint which properly handles YouTube via yt-dlp + FFmpeg
                    stream_url = f"{base_url}/iptv/channel/{channel.number}.ts{token_param}"
                    logger.debug(
                        f"Using MPEG-TS endpoint for YouTube stream (media {media_item.id})"
                    )
                else:
                    # Non-HLS, non-YouTube stream - proxy through StreamTV endpoint
                    stream_url = f"{base_url}/iptv/stream/{media_item.id}{token_param}"
                m3u8_content += f"{stream_url}\n"

        # Mark end of playlist (VOD type)
        # Note: For live streaming, ErsatzTV would omit this and update the playlist dynamically
        m3u8_content += "#EXT-X-ENDLIST\n"

        logger.info(
            f"Generated HLS playlist with {len(schedule_items)} items (total duration: {total_duration}s)"
        )

        return Response(content=m3u8_content, media_type="application/vnd.apple.mpegurl")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error generating HLS stream for channel {channel_number}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Error generating HLS stream: {e!s}")

@router.get("/iptv/channel/{channel_number}.ts")
async def get_transport_stream(
    channel_number: str,
    access_token: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Get transport stream for a channel (TS format), using the same continuous
    playout method as the HDHomeRun endpoint (ErsatzTV-style).

    This returns a continuous MPEG-TS stream so clients (including Plex IPTV)
    can join the live channel in progress instead of starting from the first item.
    """
    # Validate access token if required
    # If access_token is None in config, allow requests without token (for Plex compatibility)
    if config.security.api_key_required:
        # Only require token if both api_key_required=True AND access_token is set
        if config.security.api_key_required and config.security.access_token:
            if access_token != config.security.access_token:
                raise HTTPException(status_code=401, detail="Invalid access token")

    # Use async SQLAlchemy
    stmt = select(Channel).where(Channel.number == channel_number, Channel.enabled == True)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()

    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    logger.info(
        f"IPTV TS stream request for channel {channel_number} from {request.client.host if request else 'unknown'}"
    )

    # Try to use ChannelManager for continuous streaming (same as HDHomeRun)
    try:
        channel_manager = None
        if request:
            app = request.app
            if hasattr(app, "state"):
                channel_manager = getattr(app.state, "channel_manager", None)

        if channel_manager:
            logger.info(
                f"Client connecting to continuous TS stream for channel {channel_number} ({channel.name}) via IPTV endpoint"
            )

            async def generate():
                try:
                    # Get the ChannelStream object
                    # Handle channel numbers like "1984.1" - try to parse as float then int
                    try:
                        parsed_channel_num = int(float(channel_number))
                    except (ValueError, TypeError):
                        parsed_channel_num = 0
                    
                    channel_stream = await channel_manager.get_channel_stream(
                        channel_id=channel.id,
                        channel_number=parsed_channel_num,
                        channel_name=channel.name
                    )
                    
                    # Start channel if needed
                    if not channel_stream.is_running:
                        await channel_stream.start()
                    
                    # Now iterate over the stream's chunks
                    async for chunk in channel_stream.get_stream():
                        yield chunk
                except Exception as e:
                    logger.error(
                        f"Error in continuous TS stream for channel {channel_number} ({channel.name}): {e}",
                        exc_info=True,
                    )
                    # Don't raise - let the client handle the connection error gracefully
                    return

            return StreamingResponse(
                generate(),
                media_type="video/mp2t",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Cache-Control": "no-cache, no-store, must-revalidate, private",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Transfer-Encoding": "chunked",
                },
            )
        else:
            # Fallback to on-demand MPEG-TS streamer (like HDHomeRun fallback)
            from ..streaming.mpegts_streamer import MPEGTSStreamer

            base_url = config.server.base_url
            if request:
                scheme = request.url.scheme
                host = request.url.hostname
                port = request.url.port
                base_url = f"{scheme}://{host}:{port}" if port else f"{scheme}://{host}"

            streamer = MPEGTSStreamer(db)
            logger.info(
                f"Streaming channel {channel_number} ({channel.name}) via MPEG-TS (IPTV on-demand fallback)"
            )

            async def generate():
                try:
                    async for chunk in streamer.create_continuous_stream(channel, base_url):
                        yield chunk
                except Exception as e:
                    logger.error(
                        f"Error in MPEG-TS IPTV stream generation for channel {channel_number} ({channel.name}): {e}",
                        exc_info=True,
                    )
                    # Don't raise - let the client handle the connection error gracefully
                    return

            return StreamingResponse(
                generate(),
                media_type="video/mp2t",
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                    "Cache-Control": "no-cache, no-store, must-revalidate, private",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Transfer-Encoding": "chunked",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming channel {channel_number} via IPTV TS: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error streaming channel: {e!s}")

@router.options("/iptv/stream/{media_id}")
async def stream_media_options(media_id: int):
    """Handle CORS preflight for stream endpoint"""
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Range, Content-Type",
            "Access-Control-Max-Age": "3600",
        }
    )

@router.head("/iptv/stream/{media_id}")
@router.get("/iptv/stream/{media_id}")
async def stream_media(
    media_id: int,
    access_token: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Stream a media item directly (supports GET and HEAD)"""
    
    # Only require token if both api_key_required=True AND access_token is set
    if config.security.api_key_required and config.security.access_token:
        if access_token != config.security.access_token:
            raise HTTPException(status_code=401, detail="Invalid access token")

    # Use async SQLAlchemy
    stmt = select(MediaItem).where(MediaItem.id == media_id)
    result = await db.execute(stmt)
    media_item = result.scalar_one_or_none()
    
    if not media_item:
        raise HTTPException(status_code=404, detail="Media item not found")

    # For Plex items without URLs, use MediaURLResolver
    if not media_item.url and media_item.source == 'plex':
        
        try:
            # Import MediaURLResolver
            from exstreamtv.streaming.url_resolver import MediaURLResolver
            
            # Resolve Plex URL
            url_resolver = MediaURLResolver()
            resolved = await url_resolver.resolve(media_item)
            
            if not resolved or not resolved.url:
                logger.error(f"Failed to resolve Plex URL for media {media_id}")
                raise HTTPException(status_code=500, detail="Failed to resolve Plex stream URL")
            
            # Redirect to the resolved Plex URL
            logger.info(f"Redirecting to resolved Plex URL for media {media_id}")
            return RedirectResponse(url=resolved.url, status_code=302)
        except Exception as e:
            
            logger.error(f"Error resolving Plex URL for media {media_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to resolve stream URL: {e}")

    # Validate media item has a URL
    if not media_item.url:
        logger.error(f"Media item {media_id} has no URL")
        raise HTTPException(status_code=400, detail="Media item has no URL configured")

    try:
        # Get streaming URL
        try:
            stream_url = await stream_manager.get_stream_url(media_item.url)
            if not stream_url:
                raise ValueError("Stream URL is empty")
        except ValueError as e:
            logger.exception(
                f"Error getting stream URL for media {media_id} (URL: {media_item.url}): {e}"
            )
            raise HTTPException(
                status_code=400, detail=f"Unsupported media source or invalid URL: {e!s}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error getting stream URL for media {media_id}: {e}", exc_info=True
            )
            raise HTTPException(status_code=500, detail=f"Failed to get stream URL: {e!s}")

        # Detect source for authenticated streaming
        try:
            source = stream_manager.detect_source(media_item.url)
        except Exception as e:
            logger.warning(f"Error detecting source for media {media_id}, using UNKNOWN: {e}")
            # Detect source from URL
            if "youtube.com" in media_item.url or "youtu.be" in media_item.url:
                source = StreamSource.YOUTUBE
            elif "archive.org" in media_item.url:
                source = StreamSource.ARCHIVE_ORG
            elif "plex://" in media_item.url or "/library/metadata/" in media_item.url:
                source = StreamSource.PLEX
            else:
                source = StreamSource.UNKNOWN

        # Handle range requests for seeking
        range_header = request.headers.get("Range") if request else None
        start = None
        end = None

        # Browsers often send "bytes=0-" for initial load, handle that
        if range_header:
            # Parse range header: "bytes=start-end"
            range_match = range_header.replace("bytes=", "").split("-")
            if range_match[0]:
                try:
                    start = int(range_match[0])
                except ValueError:
                    start = None
            if len(range_match) > 1 and range_match[1]:
                try:
                    end = int(range_match[1])
                except ValueError:
                    end = None

        # Get content length and type from upstream
        content_length = None
        upstream_content_type = "video/mp4"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Try HEAD request first
                try:
                    # Follow redirects and validate the stream URL
                    head_response = await client.head(
                        stream_url, follow_redirects=True, timeout=10.0
                    )

                    # If redirected, use the final URL
                    if head_response.status_code in [301, 302, 303, 307, 308]:
                        redirect_url = head_response.headers.get("Location")
                        if redirect_url:
                            if redirect_url.startswith("/"):
                                from urllib.parse import urlparse

                                parsed = urlparse(stream_url)
                                redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                            stream_url = redirect_url
                            logger.info(f"Stream URL redirected to: {stream_url}")
                            # Re-validate the redirected URL
                            head_response = await client.head(
                                stream_url, follow_redirects=True, timeout=10.0
                            )
                    content_length = head_response.headers.get("Content-Length")
                    upstream_content_type = head_response.headers.get("Content-Type", "video/mp4")
                except httpx.HTTPError:
                    pass

                # If HEAD doesn't work or no Content-Length, try a small range request
                if not content_length:
                    try:
                        range_headers = {"Range": "bytes=0-1023"}
                        test_response = await client.get(
                            stream_url, headers=range_headers, follow_redirects=True, timeout=10.0
                        )
                        content_range = test_response.headers.get("Content-Range")
                        if content_range:
                            # Extract total from "bytes 0-1023/1234567"
                            if "/" in content_range:
                                content_length = content_range.split("/")[-1]
                        if not content_length:
                            content_length = test_response.headers.get("Content-Length")
                        if (
                            not upstream_content_type
                            or upstream_content_type == "application/octet-stream"
                        ):
                            upstream_content_type = test_response.headers.get(
                                "Content-Type", "video/mp4"
                            )
                    except httpx.HTTPError:
                        pass
        except Exception as e:
            logger.warning(f"Could not determine content length: {e}")
            # Continue without content length - browser will handle it

        # Determine content type
        content_type = upstream_content_type
        if not content_type or content_type == "application/octet-stream":
            if source == StreamSource.YOUTUBE:
                content_type = "video/mp4"
            elif source == StreamSource.ARCHIVE_ORG:
                if media_item.url.endswith(".mp4"):
                    content_type = "video/mp4"
                elif media_item.url.endswith(".webm"):
                    content_type = "video/webm"
                else:
                    content_type = "video/mp4"
            elif source == StreamSource.PLEX:
                # Plex typically serves MP4 or MKV, default to MP4
                content_type = "video/mp4"
            else:
                content_type = "video/mp4"

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": content_type,
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Range, Content-Type",
        }

        # Don't set Content-Length for streaming responses - it causes issues with range requests
        # The Content-Length will be determined by the actual stream
        # Only set it for HEAD requests where we're not streaming

        # Handle HEAD request - return headers only
        if request and request.method == "HEAD":
            # Add Content-Range header if range request
            if range_header and content_length:
                try:
                    total_size = int(content_length)
                    range_start = start or 0
                    range_end = end if end is not None else (total_size - 1)
                    actual_end = min(range_end, total_size - 1)
                    headers["Content-Range"] = f"bytes {range_start}-{actual_end}/{total_size}"
                    headers["Content-Length"] = str(actual_end - range_start + 1)
                    return Response(status_code=206, headers=headers)
                except (ValueError, TypeError):
                    pass
            return Response(status_code=200, headers=headers)

        # Stream the media for GET requests
        async def generate():
            try:
                # Pass original URL for YouTube 403 retry handling
                async for chunk in stream_manager.stream_chunked(
                    stream_url, start=start, end=end, source=source, original_url=media_item.url
                ):
                    yield chunk
            except httpx.HTTPError as e:
                logger.exception(f"HTTP error streaming media {media_id}: {e}")
                # Note: We can't raise HTTPException here since we're in a generator
                # The client will see a connection error
                raise
            except Exception as e:
                logger.error(f"Error in stream generator for media {media_id}: {e}", exc_info=True)
                raise

        # Add Content-Range header if range request
        # Note: Don't set Content-Length for streaming responses - let the stream determine it
        if range_header and content_length:
            try:
                total_size = int(content_length)
                range_start = start or 0
                range_end = end if end is not None else (total_size - 1)
                actual_end = min(range_end, total_size - 1)
                headers["Content-Range"] = f"bytes {range_start}-{actual_end}/{total_size}"
                # Remove Content-Length for streaming - it will be determined by the stream
                headers.pop("Content-Length", None)
                return StreamingResponse(
                    generate(),
                    status_code=206,  # Partial Content
                    headers=headers,
                    media_type=upstream_content_type,
                )
            except (ValueError, TypeError):
                pass

        return StreamingResponse(generate(), headers=headers, media_type=upstream_content_type)
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except httpx.TimeoutException as e:
        logger.exception(f"Timeout streaming media {media_id}: {e}")
        raise HTTPException(status_code=504, detail="Request to media source timed out")
    except httpx.HTTPError as e:
        logger.error(f"HTTP error streaming media {media_id}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to connect to media source: {e!s}")
    except ValueError as e:
        logger.exception(f"Invalid value error streaming media {media_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid request: {e!s}")
    except Exception as e:
        logger.error(f"Unexpected error streaming media {media_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {e!s}")
