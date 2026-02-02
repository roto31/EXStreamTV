"""Schedule Items API endpoints"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import ScheduleItemCreate, ScheduleItemResponse, ScheduleItemUpdate
from ..database import Collection, MediaItem, Playlist, Schedule, ScheduleItem, get_db

router = APIRouter(prefix="/schedule-items", tags=["Schedule Items"])


@router.get("", response_model=list[ScheduleItemResponse])
async def get_all_schedule_items(
    schedule_id: int | None = None, db: AsyncSession = Depends(get_db)
) -> list[Any]:
    """Get all schedule items, optionally filtered by schedule_id.

    Args:
        schedule_id: Optional schedule ID filter
        db: Database session

    Returns:
        list[ScheduleItemResponse]: List of schedule items
    """
    stmt = select(ScheduleItem)
    if schedule_id:
        stmt = stmt.where(ScheduleItem.schedule_id == schedule_id)
    stmt = stmt.order_by(ScheduleItem.position)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    return list(items)


@router.get("/{item_id}", response_model=ScheduleItemResponse)
async def get_schedule_item(item_id: int, db: AsyncSession = Depends(get_db)) -> Any:
    """Get schedule item by ID.

    Args:
        item_id: Schedule item ID
        db: Database session

    Returns:
        ScheduleItemResponse: Schedule item details

    Raises:
        HTTPException: If schedule item not found
    """
    stmt = select(ScheduleItem).where(ScheduleItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")
    return item


@router.post("", response_model=ScheduleItemResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule_item(
    item: ScheduleItemCreate, db: AsyncSession = Depends(get_db)
) -> Any:
    """Create a new schedule item.

    Args:
        item: Schedule item creation data
        db: Database session

    Returns:
        ScheduleItemResponse: Created schedule item

    Raises:
        HTTPException: If schedule, collection, media item, or playlist not found
    """
    # Validate schedule exists
    stmt = select(Schedule).where(Schedule.id == item.schedule_id)
    result = await db.execute(stmt)
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Validate collection/media/playlist references based on collection_type
    if item.collection_type == "collection" and item.collection_id:
        stmt = select(Collection).where(Collection.id == item.collection_id)
        result = await db.execute(stmt)
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
    elif item.collection_type == "media_item" and item.media_item_id:
        stmt = select(MediaItem).where(MediaItem.id == item.media_item_id)
        result = await db.execute(stmt)
        media = result.scalar_one_or_none()
        if not media:
            raise HTTPException(status_code=404, detail="Media item not found")
    elif item.collection_type == "playlist" and item.playlist_id:
        stmt = select(Playlist).where(Playlist.id == item.playlist_id)
        result = await db.execute(stmt)
        playlist = result.scalar_one_or_none()
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

    # Get item data
    item_data = item.model_dump(exclude_unset=True)
    
    # If no position specified, add to end
    if item_data.get("index") is None and item_data.get("position") is None:
        stmt = select(func.max(ScheduleItem.position)).where(
            ScheduleItem.schedule_id == item.schedule_id
        )
        result = await db.execute(stmt)
        max_pos = result.scalar() or 0
        item_data["position"] = max_pos + 1

    # Map 'index' to 'position' if needed
    if "index" in item_data and "position" not in item_data:
        item_data["position"] = item_data.pop("index")

    db_item = ScheduleItem(**item_data)
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item


@router.put("/{item_id}", response_model=ScheduleItemResponse)
async def update_schedule_item(
    item_id: int, item: ScheduleItemUpdate, db: AsyncSession = Depends(get_db)
) -> Any:
    """Update a schedule item.

    Args:
        item_id: Schedule item ID
        item: Schedule item update data
        db: Database session

    Returns:
        ScheduleItemResponse: Updated schedule item

    Raises:
        HTTPException: If schedule item or related entities not found
    """
    stmt = select(ScheduleItem).where(ScheduleItem.id == item_id)
    result = await db.execute(stmt)
    db_item = result.scalar_one_or_none()
    
    if not db_item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    # Validate references if changed
    update_data = item.model_dump(exclude_unset=True)
    if update_data.get("collection_id"):
        stmt = select(Collection).where(Collection.id == update_data["collection_id"])
        result = await db.execute(stmt)
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
    if update_data.get("media_item_id"):
        stmt = select(MediaItem).where(MediaItem.id == update_data["media_item_id"])
        result = await db.execute(stmt)
        media = result.scalar_one_or_none()
        if not media:
            raise HTTPException(status_code=404, detail="Media item not found")
    if update_data.get("playlist_id"):
        stmt = select(Playlist).where(Playlist.id == update_data["playlist_id"])
        result = await db.execute(stmt)
        playlist = result.scalar_one_or_none()
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")

    for key, value in update_data.items():
        setattr(db_item, key, value)

    db_item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(db_item)
    return db_item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_item(item_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a schedule item.

    Args:
        item_id: Schedule item ID
        db: Database session

    Raises:
        HTTPException: If schedule item not found
    """
    stmt = select(ScheduleItem).where(ScheduleItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    schedule_id = item.schedule_id
    item_position = item.position

    await db.delete(item)
    await db.commit()

    # Reorder remaining items
    stmt = select(ScheduleItem).where(
        ScheduleItem.schedule_id == schedule_id,
        ScheduleItem.position > item_position
    )
    result = await db.execute(stmt)
    remaining_items = result.scalars().all()
    
    for remaining_item in remaining_items:
        remaining_item.position -= 1
    await db.commit()


@router.post("/{item_id}/move", response_model=ScheduleItemResponse)
async def move_schedule_item(
    item_id: int,
    direction: str = Query(..., description="Direction to move: 'up' or 'down'"),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Move a schedule item up or down in the order.

    Args:
        item_id: Schedule item ID
        direction: Direction to move ('up' or 'down')
        db: Database session

    Returns:
        ScheduleItemResponse: Updated schedule item

    Raises:
        HTTPException: If schedule item not found or cannot be moved
    """
    stmt = select(ScheduleItem).where(ScheduleItem.id == item_id)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Schedule item not found")

    if direction == "up":
        if item.position == 0:
            raise HTTPException(status_code=400, detail="Item is already at the top")
        stmt = select(ScheduleItem).where(
            ScheduleItem.schedule_id == item.schedule_id,
            ScheduleItem.position == item.position - 1
        )
        result = await db.execute(stmt)
        other_item = result.scalar_one_or_none()
        if other_item:
            item.position, other_item.position = other_item.position, item.position
    elif direction == "down":
        stmt = select(func.max(ScheduleItem.position)).where(
            ScheduleItem.schedule_id == item.schedule_id
        )
        result = await db.execute(stmt)
        max_pos = result.scalar() or 0
        
        if item.position >= max_pos:
            raise HTTPException(status_code=400, detail="Item is already at the bottom")
        stmt = select(ScheduleItem).where(
            ScheduleItem.schedule_id == item.schedule_id,
            ScheduleItem.position == item.position + 1
        )
        result = await db.execute(stmt)
        other_item = result.scalar_one_or_none()
        if other_item:
            item.position, other_item.position = other_item.position, item.position
    else:
        raise HTTPException(status_code=400, detail="Direction must be 'up' or 'down'")

    await db.commit()
    await db.refresh(item)
    return item
