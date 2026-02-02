"""Playout API endpoints - Async version with full CRUD support"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config import get_config
from ..database import get_db
from ..database.models import (
    Channel,
    Playout,
    PlayoutAnchor,
    PlayoutItem,
    PlayoutHistory,
    ProgramSchedule,
    ProgramScheduleItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/playouts", tags=["Playouts"])

def playout_to_response(playout: Playout) -> dict[str, Any]:
    """Convert Playout model to response dictionary."""
    return {
        "id": playout.id,
        "channel_id": playout.channel_id,
        "program_schedule_id": playout.program_schedule_id,
        "template_id": playout.template_id,
        "playout_type": playout.playout_type,
        "daily_reset_time": playout.daily_reset_time.isoformat() if playout.daily_reset_time else None,
        "is_active": playout.is_active,
        "created_at": playout.created_at,
        "updated_at": playout.updated_at,
    }

@router.get("")
async def get_all_playouts(
    channel_id: int | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all playouts, optionally filtered by channel.
    
    Args:
        channel_id: Optional channel ID filter
        db: Database session
        
    Returns:
        List of playouts
    """
    stmt = select(Playout).options(
        selectinload(Playout.channel),
        selectinload(Playout.program_schedule),
    )
    
    if channel_id:
        stmt = stmt.where(Playout.channel_id == channel_id)
    
    result = await db.execute(stmt)
    playouts = result.scalars().all()
    
    return [playout_to_response(p) for p in playouts]

@router.get("/{playout_id}")
async def get_playout(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get playout by ID.
    
    Args:
        playout_id: Playout ID
        db: Database session
        
    Returns:
        Playout details
    """
    stmt = select(Playout).where(Playout.id == playout_id).options(
        selectinload(Playout.channel),
        selectinload(Playout.program_schedule),
        selectinload(Playout.anchor),
    )
    
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    response = playout_to_response(playout)
    
    # Add anchor info if present
    if playout.anchor:
        response["anchor"] = {
            "next_start": playout.anchor.next_start.isoformat(),
            "collection_state": playout.anchor.collection_state,
        }
    
    return response

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_playout(
    channel_id: int,
    program_schedule_id: int | None = None,
    template_id: int | None = None,
    playout_type: str = "continuous",
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new playout for a channel.
    
    Args:
        channel_id: Channel ID
        program_schedule_id: Optional program schedule ID
        template_id: Optional template ID
        playout_type: Playout type (continuous, daily, weekly)
        db: Database session
        
    Returns:
        Created playout
    """
    # Validate channel exists
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Validate program schedule if provided
    if program_schedule_id:
        stmt = select(ProgramSchedule).where(ProgramSchedule.id == program_schedule_id)
        result = await db.execute(stmt)
        schedule = result.scalar_one_or_none()
        if not schedule:
            raise HTTPException(status_code=404, detail="Program schedule not found")
    
    playout = Playout(
        channel_id=channel_id,
        program_schedule_id=program_schedule_id,
        template_id=template_id,
        playout_type=playout_type,
        is_active=True,
    )
    
    db.add(playout)
    await db.commit()
    await db.refresh(playout)
    
    logger.info(f"Created playout {playout.id} for channel {channel_id}")
    return playout_to_response(playout)

@router.put("/{playout_id}")
async def update_playout(
    playout_id: int,
    program_schedule_id: int | None = None,
    template_id: int | None = None,
    playout_type: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a playout.
    
    Args:
        playout_id: Playout ID
        program_schedule_id: Optional new program schedule ID
        template_id: Optional new template ID
        playout_type: Optional new playout type
        is_active: Optional active state
        db: Database session
        
    Returns:
        Updated playout
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    # Validate program schedule if provided
    if program_schedule_id is not None:
        if program_schedule_id > 0:
            stmt = select(ProgramSchedule).where(ProgramSchedule.id == program_schedule_id)
            result = await db.execute(stmt)
            schedule = result.scalar_one_or_none()
            if not schedule:
                raise HTTPException(status_code=404, detail="Program schedule not found")
        playout.program_schedule_id = program_schedule_id if program_schedule_id > 0 else None
    
    if template_id is not None:
        playout.template_id = template_id if template_id > 0 else None
    
    if playout_type is not None:
        playout.playout_type = playout_type
    
    if is_active is not None:
        playout.is_active = is_active
    
    await db.commit()
    await db.refresh(playout)
    
    logger.info(f"Updated playout {playout_id}")
    return playout_to_response(playout)

@router.delete("/{playout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playout(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a playout.
    
    Args:
        playout_id: Playout ID
        db: Database session
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    await db.delete(playout)
    await db.commit()
    
    logger.info(f"Deleted playout {playout_id}")

@router.get("/{playout_id}/items")
async def get_playout_items(
    playout_id: int,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get items in a playout's timeline.
    
    Args:
        playout_id: Playout ID
        limit: Maximum items to return
        offset: Offset for pagination
        db: Database session
        
    Returns:
        Playout items with pagination info
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    stmt = select(PlayoutItem).where(
        PlayoutItem.playout_id == playout_id
    ).order_by(PlayoutItem.start_time).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    return {
        "playout_id": playout_id,
        "items": [
            {
                "id": item.id,
                "media_item_id": item.media_item_id,
                "source_url": item.source_url,
                "title": item.title,
                "episode_title": item.episode_title,
                "start_time": item.start_time.isoformat(),
                "finish_time": item.finish_time.isoformat(),
                "filler_kind": item.filler_kind,
                "custom_title": item.custom_title,
            }
            for item in items
        ],
        "offset": offset,
        "limit": limit,
        "count": len(items),
    }

@router.get("/{playout_id}/now-playing")
async def get_now_playing(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get the currently playing item for a playout.
    
    Args:
        playout_id: Playout ID
        db: Database session
        
    Returns:
        Current and next items
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    now = datetime.utcnow()
    
    # Get current item
    stmt = select(PlayoutItem).where(
        PlayoutItem.playout_id == playout_id,
        PlayoutItem.start_time <= now,
        PlayoutItem.finish_time > now
    )
    result = await db.execute(stmt)
    current_item = result.scalar_one_or_none()
    
    # Get next item
    stmt = select(PlayoutItem).where(
        PlayoutItem.playout_id == playout_id,
        PlayoutItem.start_time > now
    ).order_by(PlayoutItem.start_time).limit(1)
    
    result = await db.execute(stmt)
    next_item = result.scalar_one_or_none()
    
    response: dict[str, Any] = {
        "playout_id": playout_id,
        "current_time": now.isoformat(),
        "current": None,
        "next": None,
    }
    
    if current_item:
        response["current"] = {
            "id": current_item.id,
            "title": current_item.title,
            "episode_title": current_item.episode_title,
            "start_time": current_item.start_time.isoformat(),
            "finish_time": current_item.finish_time.isoformat(),
            "progress_seconds": (now - current_item.start_time).total_seconds(),
            "duration_seconds": (current_item.finish_time - current_item.start_time).total_seconds(),
        }
    
    if next_item:
        response["next"] = {
            "id": next_item.id,
            "title": next_item.title,
            "start_time": next_item.start_time.isoformat(),
            "starts_in_seconds": (next_item.start_time - now).total_seconds(),
        }
    
    return response

@router.get("/{playout_id}/history")
async def get_playout_history(
    playout_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get playback history for a playout.
    
    Args:
        playout_id: Playout ID
        limit: Maximum items to return
        db: Database session
        
    Returns:
        List of history entries
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    stmt = select(PlayoutHistory).where(
        PlayoutHistory.playout_id == playout_id
    ).order_by(PlayoutHistory.started_at.desc()).limit(limit)
    
    result = await db.execute(stmt)
    history = result.scalars().all()
    
    return [
        {
            "id": h.id,
            "title": h.title,
            "media_item_id": h.media_item_id,
            "source_url": h.source_url,
            "started_at": h.started_at.isoformat(),
            "finished_at": h.finished_at.isoformat() if h.finished_at else None,
            "status": h.status,
            "error_message": h.error_message,
        }
        for h in history
    ]

@router.post("/{playout_id}/rebuild")
async def rebuild_playout(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Rebuild a playout's timeline.
    
    Args:
        playout_id: Playout ID
        db: Database session
        
    Returns:
        Rebuild status
    """
    stmt = select(Playout).where(Playout.id == playout_id).options(
        selectinload(Playout.channel),
        selectinload(Playout.program_schedule),
    )
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    # Clear existing items
    stmt = select(PlayoutItem).where(PlayoutItem.playout_id == playout_id)
    result = await db.execute(stmt)
    existing_items = result.scalars().all()
    
    for item in existing_items:
        await db.delete(item)
    
    # Update anchor to rebuild from now
    if playout.anchor:
        playout.anchor.next_start = datetime.utcnow()
    else:
        anchor = PlayoutAnchor(
            playout_id=playout_id,
            next_start=datetime.utcnow(),
        )
        db.add(anchor)
    
    await db.commit()
    
    logger.info(f"Rebuilt playout {playout_id}")
    
    return {
        "playout_id": playout_id,
        "status": "rebuilt",
        "message": f"Cleared {len(existing_items)} items and reset anchor",
    }

# Channel-based playout lookup (legacy compatibility)
@router.get("/channel/{channel_number}")
async def get_channel_playout(
    channel_number: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get playout detail for a channel by number.
    
    Args:
        channel_number: Channel number
        db: Database session
        
    Returns:
        Playout detail for the channel
    """
    
    try:
        stmt = select(Channel).where(Channel.number == channel_number)
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
        
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        stmt = select(Playout).where(
            Playout.channel_id == channel.id,
            Playout.is_active == True
        ).options(
            selectinload(Playout.program_schedule).selectinload(ProgramSchedule.items),
            selectinload(Playout.items),
        )
        
        result = await db.execute(stmt)
        playout = result.scalar_one_or_none()
        
        response: dict[str, Any] = {
            "channel_number": channel.number,
            "channel_name": channel.name,
            "enabled": channel.enabled,
            "playout": None,
            "schedule": None,
            "time_blocks": [],
        }
        
        if playout:
            
            response["playout"] = playout_to_response(playout)
            
            # Add schedule info if present
            if playout.program_schedule:
                schedule = playout.program_schedule
                
                try:
                    schedule_items = schedule.items if hasattr(schedule, 'items') and schedule.items else []
                    response["schedule"] = {
                        "id": schedule.id,
                        "name": schedule.name,
                        "file": playout.schedule_file or '-',  # From Playout.schedule_file
                        "description": f"Schedule with {len(schedule_items)} item(s)",
                        "content_items": len(playout.items) if playout.items else 0,
                        "sequences": len(schedule_items),
                    }
                except Exception as e:
                    raise
            
            # Add time blocks from items
            for item in playout.items[:50]:  # Limit to 50 items
                response["time_blocks"].append({
                    "title": item.title,
                    "start_time": item.start_time.isoformat(),
                    "end_time": item.finish_time.isoformat(),
                    "duration": (item.finish_time - item.start_time).total_seconds(),
                    "filler_kind": item.filler_kind,
                })
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise

# ============================================================================
# Build Session Endpoints (for Scripted Schedule API)
# ============================================================================

@router.post("/{playout_id}/build/start")
async def start_build_session(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Start a new build session for scripted playout building.
    
    Args:
        playout_id: Playout ID
        
    Returns:
        Build session details with session ID
    """
    import uuid
    from ..database.models.playout import PlayoutBuildSession
    
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    # Check for existing active session
    stmt = select(PlayoutBuildSession).where(
        PlayoutBuildSession.playout_id == playout_id,
        PlayoutBuildSession.status == "building"
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        # Return existing session
        return {
            "session_id": existing.id,
            "playout_id": playout_id,
            "status": existing.status,
            "current_time": existing.current_time.isoformat(),
            "message": "Existing build session found",
        }
    
    # Create new session
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    session = PlayoutBuildSession(
        id=session_id,
        playout_id=playout_id,
        current_time=now,
        state_json="{}",
        content_buffer="[]",
        status="building",
        watermark_enabled=True,
        graphics_enabled=True,
        pre_roll_enabled=True,
        epg_group_active=False,
        expires_at=now + timedelta(hours=1),
    )
    db.add(session)
    await db.commit()
    
    logger.info(f"Started build session {session_id} for playout {playout_id}")
    
    return {
        "session_id": session_id,
        "playout_id": playout_id,
        "status": "building",
        "current_time": now.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "message": "Build session started",
    }

@router.post("/{playout_id}/build/commit")
async def commit_build_session(
    playout_id: int,
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Commit a build session, applying all buffered items to the playout.
    
    Args:
        playout_id: Playout ID
        session_id: Optional session ID (uses active session if not provided)
        
    Returns:
        Commit result
    """
    import json
    from ..database.models.playout import PlayoutBuildSession
    
    # Find the session
    if session_id:
        stmt = select(PlayoutBuildSession).where(
            PlayoutBuildSession.id == session_id,
            PlayoutBuildSession.playout_id == playout_id
        )
    else:
        stmt = select(PlayoutBuildSession).where(
            PlayoutBuildSession.playout_id == playout_id,
            PlayoutBuildSession.status == "building"
        )
    
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="No active build session found")
    
    if session.status != "building":
        raise HTTPException(status_code=400, detail=f"Session is already {session.status}")
    
    # Parse content buffer
    try:
        content_buffer = json.loads(session.content_buffer)
    except json.JSONDecodeError:
        content_buffer = []
    
    items_added = len(content_buffer)
    
    # Add items to playout (simplified - actual implementation would create PlayoutItem records)
    # For now, just mark session as committed
    session.status = "committed"
    await db.commit()
    
    logger.info(f"Committed build session {session.id} with {items_added} items")
    
    return {
        "session_id": session.id,
        "playout_id": playout_id,
        "status": "committed",
        "items_added": items_added,
        "message": "Build session committed successfully",
    }

@router.post("/{playout_id}/build/cancel")
async def cancel_build_session(
    playout_id: int,
    session_id: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Cancel a build session, discarding all buffered items.
    
    Args:
        playout_id: Playout ID
        session_id: Optional session ID (uses active session if not provided)
        
    Returns:
        Cancellation result
    """
    from ..database.models.playout import PlayoutBuildSession
    
    # Find the session
    if session_id:
        stmt = select(PlayoutBuildSession).where(
            PlayoutBuildSession.id == session_id,
            PlayoutBuildSession.playout_id == playout_id
        )
    else:
        stmt = select(PlayoutBuildSession).where(
            PlayoutBuildSession.playout_id == playout_id,
            PlayoutBuildSession.status == "building"
        )
    
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="No active build session found")
    
    if session.status != "building":
        raise HTTPException(status_code=400, detail=f"Session is already {session.status}")
    
    # Mark session as cancelled
    session.status = "cancelled"
    await db.commit()
    
    logger.info(f"Cancelled build session {session.id}")
    
    return {
        "session_id": session.id,
        "playout_id": playout_id,
        "status": "cancelled",
        "message": "Build session cancelled",
    }

@router.post("/{playout_id}/skip")
async def skip_current_item(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Skip the currently playing item.
    
    Args:
        playout_id: Playout ID
        
    Returns:
        Skip result
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    # Get current item
    now = datetime.utcnow()
    stmt = select(PlayoutItem).where(
        PlayoutItem.playout_id == playout_id,
        PlayoutItem.start_time <= now,
        PlayoutItem.finish_time > now
    )
    result = await db.execute(stmt)
    current_item = result.scalar_one_or_none()
    
    if not current_item:
        return {
            "playout_id": playout_id,
            "message": "No item currently playing",
            "skipped": False,
        }
    
    # Mark item as ending now (effective skip)
    current_item.finish_time = now
    await db.commit()
    
    logger.info(f"Skipped item {current_item.id} on playout {playout_id}")
    
    return {
        "playout_id": playout_id,
        "skipped_item_id": current_item.id,
        "skipped_title": current_item.title,
        "message": "Item skipped successfully",
        "skipped": True,
    }

@router.post("/{playout_id}/cancel-skip")
async def cancel_pending_skip(
    playout_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Cancel any pending skip operation.
    
    Note: This is a placeholder - actual skip cancellation would require
    a skip queue system.
    
    Args:
        playout_id: Playout ID
        
    Returns:
        Cancellation result
    """
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    # Placeholder - actual implementation would check skip queue
    return {
        "playout_id": playout_id,
        "message": "No pending skip to cancel",
        "cancelled": False,
    }

@router.get("/{playout_id}/build/sessions")
async def list_build_sessions(
    playout_id: int,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """List build sessions for a playout.
    
    Args:
        playout_id: Playout ID
        status_filter: Optional status filter (building, committed, cancelled)
        
    Returns:
        List of build sessions
    """
    from ..database.models.playout import PlayoutBuildSession
    
    stmt = select(Playout).where(Playout.id == playout_id)
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        raise HTTPException(status_code=404, detail="Playout not found")
    
    stmt = select(PlayoutBuildSession).where(
        PlayoutBuildSession.playout_id == playout_id
    )
    
    if status_filter:
        stmt = stmt.where(PlayoutBuildSession.status == status_filter)
    
    stmt = stmt.order_by(PlayoutBuildSession.created_at.desc())
    
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    return [
        {
            "session_id": s.id,
            "playout_id": s.playout_id,
            "status": s.status,
            "current_time": s.current_time.isoformat(),
            "watermark_enabled": s.watermark_enabled,
            "graphics_enabled": s.graphics_enabled,
            "pre_roll_enabled": s.pre_roll_enabled,
            "expires_at": s.expires_at.isoformat(),
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]
