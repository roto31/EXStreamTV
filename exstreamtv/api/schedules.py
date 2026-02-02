"""Schedules API endpoints - Async version with full CRUD support"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..api.schemas import ScheduleCreate, ScheduleResponse, ScheduleUpdate
from ..cache.manager import get_cache
from ..database import get_db
from ..database.models import Channel, ProgramSchedule, ProgramScheduleItem
from ..streaming.plex_api_client import request_plex_guide_reload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/schedules", tags=["Schedules"])

def schedule_to_response(schedule: ProgramSchedule) -> dict[str, Any]:
    """Convert ProgramSchedule model to response dictionary."""
    return {
        "id": schedule.id,
        "name": schedule.name,
        "channel_id": None,  # ProgramSchedule doesn't have direct channel_id
        "keep_multi_part_episodes_together": schedule.keep_multi_part_episodes,
        "treat_collections_as_shows": schedule.treat_collections_as_shows,
        "shuffle_schedule_items": schedule.shuffle_schedule_items,
        "random_start_point": schedule.random_start_point,
        "is_yaml_source": False,  # Add if field exists
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
    }

@router.get("", response_model=list[ScheduleResponse])
async def get_all_schedules(
    channel_id: int | None = None, 
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all schedules.

    Args:
        channel_id: Optional channel ID filter (via playouts)
        db: Database session

    Returns:
        list[ScheduleResponse]: List of schedules
    """
    try:
        stmt = select(ProgramSchedule).options(
            selectinload(ProgramSchedule.items)
        )
        
        result = await db.execute(stmt)
        schedules = result.scalars().all()
        return [schedule_to_response(s) for s in schedules]
    except Exception as e:
        raise

@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get schedule by ID.

    Args:
        schedule_id: Schedule ID
        db: Database session

    Returns:
        ScheduleResponse: Schedule details

    Raises:
        HTTPException: If schedule not found
    """
    stmt = select(ProgramSchedule).where(
        ProgramSchedule.id == schedule_id
    ).options(selectinload(ProgramSchedule.items))
    
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    return schedule_to_response(schedule)

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new schedule.

    Args:
        schedule: Schedule creation data
        db: Database session

    Returns:
        ScheduleResponse: Created schedule

    Raises:
        HTTPException: If channel not found
    """
    # Validate channel exists if provided
    if schedule.channel_id:
        stmt = select(Channel).where(Channel.id == schedule.channel_id)
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

    # Create the schedule
    db_schedule = ProgramSchedule(
        name=schedule.name,
        keep_multi_part_episodes=schedule.keep_multi_part_episodes_together,
        treat_collections_as_shows=schedule.treat_collections_as_shows,
        shuffle_schedule_items=schedule.shuffle_schedule_items,
        random_start_point=schedule.random_start_point,
    )
    
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Created schedule: {db_schedule.name}")
    return schedule_to_response(db_schedule)

@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int, 
    schedule: ScheduleUpdate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a schedule.

    Args:
        schedule_id: Schedule ID
        schedule: Schedule update data
        db: Database session

    Returns:
        ScheduleResponse: Updated schedule

    Raises:
        HTTPException: If schedule not found
    """
    stmt = select(ProgramSchedule).where(ProgramSchedule.id == schedule_id)
    result = await db.execute(stmt)
    db_schedule = result.scalar_one_or_none()
    
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Validate channel exists if changed
    update_data = schedule.model_dump(exclude_unset=True)
    
    if "channel_id" in update_data and update_data["channel_id"]:
        stmt = select(Channel).where(Channel.id == update_data["channel_id"])
        result = await db.execute(stmt)
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

    # Map schema fields to model fields
    field_mapping = {
        "keep_multi_part_episodes_together": "keep_multi_part_episodes",
    }
    
    for key, value in update_data.items():
        model_key = field_mapping.get(key, key)
        if hasattr(db_schedule, model_key):
            setattr(db_schedule, model_key, value)

    await db.commit()
    await db.refresh(db_schedule)
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Updated schedule: {db_schedule.name}")
    return schedule_to_response(db_schedule)

@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int, 
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a schedule.

    Args:
        schedule_id: Schedule ID
        db: Database session

    Raises:
        HTTPException: If schedule not found
    """
    stmt = select(ProgramSchedule).where(ProgramSchedule.id == schedule_id)
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    await db.commit()
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Deleted schedule: {schedule.name}")

@router.get("/{schedule_id}/items")
async def get_schedule_items(
    schedule_id: int,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all items in a schedule.
    
    Args:
        schedule_id: Schedule ID
        db: Database session
        
    Returns:
        List of schedule items
    """
    stmt = select(ProgramSchedule).where(ProgramSchedule.id == schedule_id)
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    stmt = select(ProgramScheduleItem).where(
        ProgramScheduleItem.schedule_id == schedule_id
    ).order_by(ProgramScheduleItem.position)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    return [
        {
            "id": item.id,
            "schedule_id": item.schedule_id,
            "position": item.position,
            "collection_type": item.collection_type,
            "collection_id": item.collection_id,
            "custom_title": item.custom_title,
            "playback_mode": item.playback_mode,
            "multiple_count": item.multiple_count,
            "duration_minutes": item.duration_minutes,
            "start_time": str(item.start_time) if item.start_time else None,
            "playback_order": item.playback_order,
            "guide_mode": item.guide_mode,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in items
    ]

@router.post("/{schedule_id}/items")
async def add_schedule_item(
    schedule_id: int,
    collection_type: str,
    collection_id: int,
    playback_mode: str = "flood",
    playback_order: str = "chronological",
    custom_title: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add an item to a schedule.
    
    Args:
        schedule_id: Schedule ID
        collection_type: Type of collection ("playlist", "collection", "show", etc.)
        collection_id: ID of the collection/playlist
        playback_mode: Playback mode ("one", "multiple", "duration", "flood")
        playback_order: Playback order ("chronological", "shuffled", "random")
        custom_title: Optional custom title for EPG
        db: Database session
        
    Returns:
        Created schedule item
    """
    stmt = select(ProgramSchedule).where(ProgramSchedule.id == schedule_id)
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Get next position
    stmt = select(ProgramScheduleItem).where(
        ProgramScheduleItem.schedule_id == schedule_id
    ).order_by(ProgramScheduleItem.position.desc())
    
    result = await db.execute(stmt)
    last_item = result.scalar_first()
    next_position = (last_item.position + 1) if last_item else 1
    
    item = ProgramScheduleItem(
        schedule_id=schedule_id,
        position=next_position,
        collection_type=collection_type,
        collection_id=collection_id,
        playback_mode=playback_mode,
        playback_order=playback_order,
        custom_title=custom_title,
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Added item to schedule {schedule_id}: {collection_type} #{collection_id}")
    
    return {
        "id": item.id,
        "schedule_id": item.schedule_id,
        "position": item.position,
        "collection_type": item.collection_type,
        "collection_id": item.collection_id,
        "playback_mode": item.playback_mode,
        "playback_order": item.playback_order,
        "custom_title": item.custom_title,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }

@router.delete("/{schedule_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_schedule_item(
    schedule_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Remove an item from a schedule.
    
    Args:
        schedule_id: Schedule ID
        item_id: Schedule item ID
        db: Database session
    """
    stmt = select(ProgramScheduleItem).where(
        ProgramScheduleItem.id == item_id,
        ProgramScheduleItem.schedule_id == schedule_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    
    position = item.position
    
    await db.delete(item)
    
    # Reorder remaining items
    stmt = select(ProgramScheduleItem).where(
        ProgramScheduleItem.schedule_id == schedule_id,
        ProgramScheduleItem.position > position
    )
    result = await db.execute(stmt)
    remaining = result.scalars().all()
    
    for remaining_item in remaining:
        remaining_item.position -= 1
    
    await db.commit()
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Removed item {item_id} from schedule {schedule_id}")
