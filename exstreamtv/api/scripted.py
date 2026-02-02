"""Scripted Schedule API endpoints - ErsatzTV-compatible programmatic playout building

This module provides 25+ endpoints for building playouts programmatically,
supporting collections, marathons, playlists, padding, timing controls, and more.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..database.models.playout import Playout, PlayoutBuildSession

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scripted/build", tags=["Scripted Schedule"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class AddCollectionRequest(BaseModel):
    """Request to add a collection to the build."""
    collection_id: int
    count: int | None = None
    duration_minutes: int | None = None
    playback_order: str = "chronological"


class AddMarathonRequest(BaseModel):
    """Request to add a marathon (all episodes of a show) to the build."""
    show_id: int
    playback_order: str = "chronological"


class AddMultiCollectionRequest(BaseModel):
    """Request to add a multi-collection to the build."""
    multi_collection_id: int
    playback_order: str = "shuffled"


class AddPlaylistRequest(BaseModel):
    """Request to add a playlist to the build."""
    playlist_id: int
    count: int | None = None


class CreatePlaylistRequest(BaseModel):
    """Request to create and add a playlist."""
    name: str
    media_item_ids: list[int]


class AddSearchRequest(BaseModel):
    """Request to add search results to the build."""
    query: str
    count: int | None = None
    media_type: str | None = None


class AddShowRequest(BaseModel):
    """Request to add a specific show to the build."""
    show_title: str
    season: int | None = None
    count: int | None = None


class AddCountRequest(BaseModel):
    """Request to add a specific count of items."""
    collection_id: int
    count: int


class AddDurationRequest(BaseModel):
    """Request to add items for a specific duration."""
    collection_id: int
    duration_minutes: int


class PadToNextRequest(BaseModel):
    """Request to pad to the next time boundary."""
    minutes: int = Field(..., description="Pad to next N-minute boundary (e.g., 15, 30)")
    filler_preset_id: int | None = None


class PadUntilRequest(BaseModel):
    """Request to pad until a specific time."""
    target_time: str = Field(..., description="Target time in HH:MM format")
    filler_preset_id: int | None = None


class WaitUntilRequest(BaseModel):
    """Request to wait (no content) until a specific time."""
    target_time: str = Field(..., description="Target time in HH:MM format")


class SkipItemsRequest(BaseModel):
    """Request to skip items."""
    count: int = 1
    collection_id: int | None = None


class SkipToItemRequest(BaseModel):
    """Request to skip to a specific item."""
    item_index: int
    collection_id: int


class EpgGroupRequest(BaseModel):
    """Request to manage EPG grouping."""
    title: str


# ============================================================================
# Helper Functions
# ============================================================================


async def get_build_session(
    build_id: str,
    db: AsyncSession
) -> PlayoutBuildSession:
    """Get a build session by ID."""
    stmt = select(PlayoutBuildSession).where(PlayoutBuildSession.id == build_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Build session not found")
    
    if session.status != "building":
        raise HTTPException(status_code=400, detail=f"Build session is {session.status}")
    
    if session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Build session has expired")
    
    return session


def parse_time_string(time_str: str) -> datetime:
    """Parse HH:MM time string to datetime (today)."""
    try:
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        now = datetime.utcnow()
        return now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time format. Expected HH:MM, got: {time_str}"
        ) from e


def add_to_buffer(session: PlayoutBuildSession, item: dict) -> None:
    """Add an item to the session's content buffer."""
    try:
        buffer = json.loads(session.content_buffer)
    except json.JSONDecodeError:
        buffer = []
    
    buffer.append(item)
    session.content_buffer = json.dumps(buffer)


def get_buffer_count(session: PlayoutBuildSession) -> int:
    """Get the number of items in the content buffer."""
    try:
        buffer = json.loads(session.content_buffer)
        return len(buffer)
    except json.JSONDecodeError:
        return 0


# ============================================================================
# Build Context Endpoint
# ============================================================================


@router.get("/{build_id}/context")
async def get_build_context(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get the current build context.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Current build state and context
    """
    session = await get_build_session(build_id, db)
    
    try:
        state = json.loads(session.state_json)
    except json.JSONDecodeError:
        state = {}
    
    return {
        "build_id": build_id,
        "playout_id": session.playout_id,
        "status": session.status,
        "current_time": session.current_time.isoformat(),
        "items_buffered": get_buffer_count(session),
        "watermark_enabled": session.watermark_enabled,
        "graphics_enabled": session.graphics_enabled,
        "pre_roll_enabled": session.pre_roll_enabled,
        "epg_group_active": session.epg_group_active,
        "epg_group_title": session.epg_group_title,
        "expires_at": session.expires_at.isoformat(),
        "state": state,
    }


# ============================================================================
# Content Addition Endpoints
# ============================================================================


@router.post("/{build_id}/add-collection")
async def add_collection(
    build_id: str,
    request: AddCollectionRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a collection to the build.
    
    Args:
        build_id: Build session ID
        request: Collection details
        
    Returns:
        Items added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "collection",
        "collection_id": request.collection_id,
        "count": request.count,
        "duration_minutes": request.duration_minutes,
        "playback_order": request.playback_order,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-collection",
        "collection_id": request.collection_id,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-marathon")
async def add_marathon(
    build_id: str,
    request: AddMarathonRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a marathon (all episodes of a show) to the build.
    
    Args:
        build_id: Build session ID
        request: Marathon details
        
    Returns:
        Marathon added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "marathon",
        "show_id": request.show_id,
        "playback_order": request.playback_order,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-marathon",
        "show_id": request.show_id,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-multi-collection")
async def add_multi_collection(
    build_id: str,
    request: AddMultiCollectionRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a multi-collection to the build.
    
    Args:
        build_id: Build session ID
        request: Multi-collection details
        
    Returns:
        Multi-collection added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "multi_collection",
        "multi_collection_id": request.multi_collection_id,
        "playback_order": request.playback_order,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-multi-collection",
        "multi_collection_id": request.multi_collection_id,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-playlist")
async def add_playlist(
    build_id: str,
    request: AddPlaylistRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a playlist to the build.
    
    Args:
        build_id: Build session ID
        request: Playlist details
        
    Returns:
        Playlist added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "playlist",
        "playlist_id": request.playlist_id,
        "count": request.count,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-playlist",
        "playlist_id": request.playlist_id,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/create-playlist")
async def create_and_add_playlist(
    build_id: str,
    request: CreatePlaylistRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new playlist and add it to the build.
    
    Args:
        build_id: Build session ID
        request: Playlist creation details
        
    Returns:
        Playlist created and added
    """
    session = await get_build_session(build_id, db)
    
    # Create playlist (simplified - actual implementation would use Playlist model)
    add_to_buffer(session, {
        "type": "inline_playlist",
        "name": request.name,
        "media_item_ids": request.media_item_ids,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "create-playlist",
        "name": request.name,
        "item_count": len(request.media_item_ids),
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-search")
async def add_search(
    build_id: str,
    request: AddSearchRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add search results to the build.
    
    Args:
        build_id: Build session ID
        request: Search details
        
    Returns:
        Search results added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "search",
        "query": request.query,
        "count": request.count,
        "media_type": request.media_type,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-search",
        "query": request.query,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-smart-collection")
async def add_smart_collection(
    build_id: str,
    collection_id: int,
    count: int | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a smart collection to the build.
    
    Args:
        build_id: Build session ID
        collection_id: Smart collection ID
        count: Optional item count
        
    Returns:
        Smart collection added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "smart_collection",
        "collection_id": collection_id,
        "count": count,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-smart-collection",
        "collection_id": collection_id,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-show")
async def add_show(
    build_id: str,
    request: AddShowRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a TV show to the build.
    
    Args:
        build_id: Build session ID
        request: Show details
        
    Returns:
        Show added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "show",
        "show_title": request.show_title,
        "season": request.season,
        "count": request.count,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-show",
        "show_title": request.show_title,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-all")
async def add_all(
    build_id: str,
    collection_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add all items from a collection to the build.
    
    Args:
        build_id: Build session ID
        collection_id: Collection ID
        
    Returns:
        All items added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "collection_all",
        "collection_id": collection_id,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-all",
        "collection_id": collection_id,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-count")
async def add_count(
    build_id: str,
    request: AddCountRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a specific count of items from a collection.
    
    Args:
        build_id: Build session ID
        request: Count details
        
    Returns:
        Items added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "collection_count",
        "collection_id": request.collection_id,
        "count": request.count,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-count",
        "collection_id": request.collection_id,
        "count": request.count,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/add-duration")
async def add_duration(
    build_id: str,
    request: AddDurationRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add items to fill a specific duration.
    
    Args:
        build_id: Build session ID
        request: Duration details
        
    Returns:
        Items added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "collection_duration",
        "collection_id": request.collection_id,
        "duration_minutes": request.duration_minutes,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "add-duration",
        "collection_id": request.collection_id,
        "duration_minutes": request.duration_minutes,
        "items_buffered": get_buffer_count(session),
    }


# ============================================================================
# Padding/Timing Endpoints
# ============================================================================


@router.post("/{build_id}/pad-to-next")
async def pad_to_next(
    build_id: str,
    request: PadToNextRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Pad to the next time boundary.
    
    Args:
        build_id: Build session ID
        request: Padding details
        
    Returns:
        Padding added
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "pad_to_next",
        "minutes": request.minutes,
        "filler_preset_id": request.filler_preset_id,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "pad-to-next",
        "minutes": request.minutes,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/pad-until")
async def pad_until(
    build_id: str,
    request: PadUntilRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Pad until a specific time.
    
    Args:
        build_id: Build session ID
        request: Target time details
        
    Returns:
        Padding added
    """
    session = await get_build_session(build_id, db)
    target = parse_time_string(request.target_time)
    
    add_to_buffer(session, {
        "type": "pad_until",
        "target_time": target.isoformat(),
        "filler_preset_id": request.filler_preset_id,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "pad-until",
        "target_time": request.target_time,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/pad-until-exact")
async def pad_until_exact(
    build_id: str,
    request: PadUntilRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Pad until an exact time (with precision).
    
    Args:
        build_id: Build session ID
        request: Target time details
        
    Returns:
        Padding added
    """
    session = await get_build_session(build_id, db)
    target = parse_time_string(request.target_time)
    
    add_to_buffer(session, {
        "type": "pad_until_exact",
        "target_time": target.isoformat(),
        "filler_preset_id": request.filler_preset_id,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "pad-until-exact",
        "target_time": request.target_time,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/wait-until")
async def wait_until(
    build_id: str,
    request: WaitUntilRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Wait (no content) until a specific time.
    
    Args:
        build_id: Build session ID
        request: Target time details
        
    Returns:
        Wait added
    """
    session = await get_build_session(build_id, db)
    target = parse_time_string(request.target_time)
    
    add_to_buffer(session, {
        "type": "wait_until",
        "target_time": target.isoformat(),
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "wait-until",
        "target_time": request.target_time,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/wait-until-exact")
async def wait_until_exact(
    build_id: str,
    request: WaitUntilRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Wait until an exact time (with precision).
    
    Args:
        build_id: Build session ID
        request: Target time details
        
    Returns:
        Wait added
    """
    session = await get_build_session(build_id, db)
    target = parse_time_string(request.target_time)
    
    add_to_buffer(session, {
        "type": "wait_until_exact",
        "target_time": target.isoformat(),
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "wait-until-exact",
        "target_time": request.target_time,
        "items_buffered": get_buffer_count(session),
    }


# ============================================================================
# Content Control Endpoints
# ============================================================================


@router.get("/{build_id}/peek-next/{content_type}")
async def peek_next(
    build_id: str,
    content_type: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Peek at the next item of a content type without consuming it.
    
    Args:
        build_id: Build session ID
        content_type: Type to peek (collection, playlist, show)
        
    Returns:
        Next item preview
    """
    session = await get_build_session(build_id, db)
    
    # Placeholder - actual implementation would look at collection state
    return {
        "build_id": build_id,
        "content_type": content_type,
        "next_item": None,
        "message": "Peek functionality requires collection state tracking",
    }


@router.post("/{build_id}/skip-items")
async def skip_items(
    build_id: str,
    request: SkipItemsRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Skip items in the current collection.
    
    Args:
        build_id: Build session ID
        request: Skip details
        
    Returns:
        Skip result
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "skip_items",
        "count": request.count,
        "collection_id": request.collection_id,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "skip-items",
        "count": request.count,
        "items_buffered": get_buffer_count(session),
    }


@router.post("/{build_id}/skip-to-item")
async def skip_to_item(
    build_id: str,
    request: SkipToItemRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Skip to a specific item in a collection.
    
    Args:
        build_id: Build session ID
        request: Skip details
        
    Returns:
        Skip result
    """
    session = await get_build_session(build_id, db)
    
    add_to_buffer(session, {
        "type": "skip_to_item",
        "item_index": request.item_index,
        "collection_id": request.collection_id,
        "added_at": datetime.utcnow().isoformat(),
    })
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "skip-to-item",
        "item_index": request.item_index,
        "collection_id": request.collection_id,
        "items_buffered": get_buffer_count(session),
    }


# ============================================================================
# EPG/Graphics Endpoints
# ============================================================================


@router.post("/{build_id}/epg-group/start")
async def start_epg_group(
    build_id: str,
    request: EpgGroupRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Start an EPG group (items will be grouped under this title).
    
    Args:
        build_id: Build session ID
        request: EPG group details
        
    Returns:
        EPG group started
    """
    session = await get_build_session(build_id, db)
    
    session.epg_group_active = True
    session.epg_group_title = request.title
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "epg-group/start",
        "title": request.title,
        "epg_group_active": True,
    }


@router.post("/{build_id}/epg-group/stop")
async def stop_epg_group(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Stop the current EPG group.
    
    Args:
        build_id: Build session ID
        
    Returns:
        EPG group stopped
    """
    session = await get_build_session(build_id, db)
    
    previous_title = session.epg_group_title
    session.epg_group_active = False
    session.epg_group_title = None
    
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "epg-group/stop",
        "previous_title": previous_title,
        "epg_group_active": False,
    }


@router.post("/{build_id}/graphics/on")
async def graphics_on(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Enable graphics.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Graphics enabled
    """
    session = await get_build_session(build_id, db)
    
    session.graphics_enabled = True
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "graphics/on",
        "graphics_enabled": True,
    }


@router.post("/{build_id}/graphics/off")
async def graphics_off(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Disable graphics.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Graphics disabled
    """
    session = await get_build_session(build_id, db)
    
    session.graphics_enabled = False
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "graphics/off",
        "graphics_enabled": False,
    }


@router.post("/{build_id}/watermark/on")
async def watermark_on(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Enable watermark.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Watermark enabled
    """
    session = await get_build_session(build_id, db)
    
    session.watermark_enabled = True
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "watermark/on",
        "watermark_enabled": True,
    }


@router.post("/{build_id}/watermark/off")
async def watermark_off(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Disable watermark.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Watermark disabled
    """
    session = await get_build_session(build_id, db)
    
    session.watermark_enabled = False
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "watermark/off",
        "watermark_enabled": False,
    }


@router.post("/{build_id}/pre-roll/on")
async def pre_roll_on(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Enable pre-roll.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Pre-roll enabled
    """
    session = await get_build_session(build_id, db)
    
    session.pre_roll_enabled = True
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "pre-roll/on",
        "pre_roll_enabled": True,
    }


@router.post("/{build_id}/pre-roll/off")
async def pre_roll_off(
    build_id: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Disable pre-roll.
    
    Args:
        build_id: Build session ID
        
    Returns:
        Pre-roll disabled
    """
    session = await get_build_session(build_id, db)
    
    session.pre_roll_enabled = False
    await db.commit()
    
    return {
        "build_id": build_id,
        "action": "pre-roll/off",
        "pre_roll_enabled": False,
    }
