"""Player API endpoints for React Player control."""

import logging
import socket
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from exstreamtv.config import config
from exstreamtv.database import get_db
from exstreamtv.database.models import Channel, ChannelPlaybackPosition, MediaItem, PlayoutItem, Playout
from exstreamtv.streaming.channel_manager import ChannelManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/player", tags=["player"])


def _get_local_ip_address() -> str | None:
    """Try to determine the host machine's LAN IP address.

    Returns:
        str | None: Local IP address if detected, otherwise None.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # This doesn't send traffic; it just forces the OS to pick a route.
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        return None


def _derive_base_url(request: Request) -> str:
    """Derive a public-facing base URL for the current request.

    This mirrors the approach in `iptv.py` so clients get URLs that work
    both locally and behind reverse proxies.

    Args:
        request: FastAPI request.

    Returns:
        str: Base URL like "http(s)://host[:port]".
    """
    base_url = config.server.base_url

    scheme = request.url.scheme
    host = request.url.hostname
    port = request.url.port

    if host in {"localhost", "127.0.0.1"}:
        forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host")
        if forwarded_host:
            host = forwarded_host.split(":")[0]
        else:
            detected_ip = _get_local_ip_address()
            if detected_ip:
                host = detected_ip

    if port and port not in {80, 443}:
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


@router.get("/channel/{channel_number}/stream")
async def get_channel_stream(
    channel_number: str, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get stream URL for a channel.

    Args:
        channel_number: Channel number to get stream for.
        request: Optional request (used to derive a client-reachable base URL).
        db: Database session.

    Returns:
        dict[str, Any]: Dictionary with channel_number, channel_name, stream_url, format

    Raises:
        HTTPException: If channel not found, disabled, or error occurs
    """
    try:
        stmt = select(Channel).where(Channel.number == channel_number)
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_number} not found")

        if not channel.enabled:
            raise HTTPException(status_code=400, detail=f"Channel {channel_number} is disabled")

        base_url = _derive_base_url(request)

        # Return HLS stream URL for browser compatibility
        stream_url = f"{base_url}/iptv/channel/{channel_number}.m3u8"

        return {
            "channel_number": channel_number,
            "channel_name": channel.name,
            "stream_url": stream_url,
            "format": "hls",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream URL for channel {channel_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channel/{channel_number}/switch")
async def switch_channel(
    channel_number: str, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Switch to a channel.

    Args:
        channel_number: Channel number to switch to.
        request: Optional request (used to derive a client-reachable base URL).
        db: Database session.

    Returns:
        dict[str, str]: Dictionary with status, channel_number, channel_name, stream_url

    Raises:
        HTTPException: If channel not found, disabled, or error occurs
    """
    try:
        stmt = select(Channel).where(Channel.number == channel_number)
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_number} not found")

        if not channel.enabled:
            raise HTTPException(status_code=400, detail=f"Channel {channel_number} is disabled")

        base_url = _derive_base_url(request)

        # Get stream URL
        stream_url = f"{base_url}/iptv/channel/{channel_number}.m3u8"

        return {
            "status": "switched",
            "channel_number": channel_number,
            "channel_name": channel.name,
            "stream_url": stream_url,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching to channel {channel_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channel/{channel_number}/metadata")
async def get_channel_metadata(
    channel_number: str, request: Request, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get current playing metadata for a channel.

    Args:
        channel_number: Channel number to get metadata for
        request: FastAPI request (used to access app.state.channel_manager)
        db: Database session

    Returns:
        dict[str, Any]: Dictionary with channel metadata and current playing item info

    Raises:
        HTTPException: If channel not found or error occurs
    """
    try:
        stmt = select(Channel).where(Channel.number == channel_number)
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail=f"Channel {channel_number} not found")

        # Get playback position
        stmt = select(ChannelPlaybackPosition).where(ChannelPlaybackPosition.channel_id == channel.id)
        result = await db.execute(stmt)
        playback_pos = result.scalar_one_or_none()

        # Get current playing item using channel manager from app state
        position = {
            "item_index": 0,
            "elapsed_seconds": 0,
            "elapsed_seconds_in_item": 0,
            "current_item_start_time": None,
            "playout_start_time": None,
        }
        
        # Try to get position from ChannelStream if available
        if hasattr(request.app.state, "channel_manager") and request.app.state.channel_manager:
            channel_manager = request.app.state.channel_manager
            # ChannelManager uses channel.id (integer) as key in _channels dict
            channel_key = channel.id
            if channel_key in channel_manager._channels:
                channel_stream = channel_manager._channels[channel_key]
                try:
                    position = await channel_stream._get_current_position()
                except Exception as e:
                    logger.warning(f"Could not get current position from ChannelStream: {e}")
                    # Fall back to playback position from database
                    if playback_pos:
                        position["item_index"] = playback_pos.last_item_index or 0
                        position["elapsed_seconds_in_item"] = playback_pos.elapsed_seconds_in_item or 0
                        position["current_item_start_time"] = playback_pos.current_item_start_time
                        position["playout_start_time"] = playback_pos.playout_start_time
        elif playback_pos:
            # Fall back to playback position from database if ChannelManager not available
            position["item_index"] = playback_pos.last_item_index or 0
            position["elapsed_seconds_in_item"] = playback_pos.elapsed_seconds_in_item or 0
            position["current_item_start_time"] = playback_pos.current_item_start_time
            position["playout_start_time"] = playback_pos.playout_start_time

        metadata = {
            "channel_number": channel_number,
            "channel_name": channel.name,
            "current_item_index": position.get("item_index", 0),
            "elapsed_seconds": position.get("elapsed_seconds", 0),
            "elapsed_seconds_in_item": position.get("elapsed_seconds_in_item", 0),
            "current_item_start_time": position.get("current_item_start_time"),
            "playout_start_time": position.get("playout_start_time"),
        }

        # Try to get media item metadata from current position
        current_item_index = position.get("item_index", 0)
        
        # First, try to get media item from ChannelStream's schedule items if available
        media_item = None
        if hasattr(request.app.state, "channel_manager") and request.app.state.channel_manager:
            channel_manager = request.app.state.channel_manager
            # ChannelManager uses channel.id (integer) as key
            channel_key = channel.id
            if channel_key in channel_manager._channels:
                channel_stream = channel_manager._channels[channel_key]
                # Note: ChannelStream doesn't expose _schedule_items, so skip this for now
                # schedule_items = channel_stream._schedule_items
                # if schedule_items and current_item_index < len(schedule_items):
                #     schedule_item = schedule_items[current_item_index]
                #     media_item = schedule_item.get("media_item")
        
        # Fall back to playback position's last_item_media_id if we don't have schedule items
        if not media_item and playback_pos and playback_pos.last_item_media_id:
            stmt = select(MediaItem).where(MediaItem.id == playback_pos.last_item_media_id)
            result = await db.execute(stmt)
            media_item = result.scalar_one_or_none()

        if media_item:
            # Use getattr with defaults for attributes that may not exist on all MediaItem versions
            # MediaItem model uses: show_title (not series_title), title (not episode_title for episodes)
            metadata.update(
                {
                    "title": getattr(media_item, 'title', None),
                    "series_title": getattr(media_item, 'series_title', None) or getattr(media_item, 'show_title', None),
                    "episode_title": getattr(media_item, 'episode_title', None),
                    "season_number": getattr(media_item, 'season_number', None),
                    "episode_number": getattr(media_item, 'episode_number', None),
                    "description": getattr(media_item, 'description', None),
                    "thumbnail": getattr(media_item, 'thumbnail', None),
                    "duration": getattr(media_item, 'duration', None),
                }
            )

        return metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata for channel {channel_number}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/control")
async def player_control(
    action: str = Query(..., description="Control action: play, pause, seek, volume"),
    value: float | None = Query(None, description="Value for seek (seconds) or volume (0-1)"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Control player playback (play, pause, seek, volume).

    Args:
        action: Control action (play, pause, seek, volume)
        value: Value for seek (seconds) or volume (0-1)
        db: Database session

    Returns:
        dict[str, str]: Status dictionary with action and value

    Raises:
        HTTPException: If control action fails
    """
    try:
        # This endpoint is for future use - actual control is handled client-side
        # Could be extended to control server-side streaming if needed

        return {"status": "ok", "action": action, "value": value}
    except Exception as e:
        logger.error(f"Error in player control: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
