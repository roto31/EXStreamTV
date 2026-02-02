"""Filler Presets API endpoints - Full CRUD support for filler content management"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..database.models.filler import FillerPreset, FillerPresetItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/filler-presets", tags=["Filler Presets"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class FillerPresetCreate(BaseModel):
    """Schema for creating a filler preset."""
    name: str = Field(..., min_length=1, max_length=255)
    filler_mode: str = Field(
        default="duration",
        description="Mode: count, duration, or pad"
    )
    count: int | None = Field(None, ge=1, description="For count mode")
    duration_seconds: int | None = Field(None, ge=1, description="For duration mode")
    pad_to_minutes: int | None = Field(None, ge=1, description="For pad mode")
    playback_order: str = Field(
        default="shuffled",
        description="Order: chronological, shuffled, random"
    )
    allow_repeats: bool = True


class FillerPresetUpdate(BaseModel):
    """Schema for updating a filler preset."""
    name: str | None = Field(None, min_length=1, max_length=255)
    filler_mode: str | None = None
    count: int | None = None
    duration_seconds: int | None = None
    pad_to_minutes: int | None = None
    playback_order: str | None = None
    allow_repeats: bool | None = None


class FillerPresetItemCreate(BaseModel):
    """Schema for creating a filler preset item."""
    collection_type: str | None = Field(None, description="Type: playlist, collection")
    collection_id: int | None = None
    media_item_id: int | None = None
    weight: int = Field(default=1, ge=1, description="Selection weight")
    min_duration_seconds: int | None = None
    max_duration_seconds: int | None = None


class FillerPresetItemUpdate(BaseModel):
    """Schema for updating a filler preset item."""
    collection_type: str | None = None
    collection_id: int | None = None
    media_item_id: int | None = None
    weight: int | None = None
    min_duration_seconds: int | None = None
    max_duration_seconds: int | None = None


class FillerPresetItemResponse(BaseModel):
    """Response schema for filler preset item."""
    id: int
    preset_id: int
    collection_type: str | None
    collection_id: int | None
    media_item_id: int | None
    weight: int
    min_duration_seconds: int | None
    max_duration_seconds: int | None

    class Config:
        from_attributes = True


class FillerPresetResponse(BaseModel):
    """Response schema for filler preset."""
    id: int
    name: str
    filler_mode: str
    count: int | None
    duration_seconds: int | None
    pad_to_minutes: int | None
    playback_order: str
    allow_repeats: bool
    items: list[FillerPresetItemResponse] = []
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


# ============================================================================
# Helper Functions
# ============================================================================


def preset_to_response(preset: FillerPreset) -> dict[str, Any]:
    """Convert FillerPreset model to response dictionary."""
    return {
        "id": preset.id,
        "name": preset.name,
        "filler_mode": preset.filler_mode,
        "count": preset.count,
        "duration_seconds": preset.duration_seconds,
        "pad_to_minutes": preset.pad_to_minutes,
        "playback_order": preset.playback_order,
        "allow_repeats": preset.allow_repeats,
        "items": [
            {
                "id": item.id,
                "preset_id": item.preset_id,
                "collection_type": item.collection_type,
                "collection_id": item.collection_id,
                "media_item_id": item.media_item_id,
                "weight": item.weight,
                "min_duration_seconds": item.min_duration_seconds,
                "max_duration_seconds": item.max_duration_seconds,
            }
            for item in (preset.items or [])
        ],
        "created_at": preset.created_at,
        "updated_at": preset.updated_at,
    }


def item_to_response(item: FillerPresetItem) -> dict[str, Any]:
    """Convert FillerPresetItem model to response dictionary."""
    return {
        "id": item.id,
        "preset_id": item.preset_id,
        "collection_type": item.collection_type,
        "collection_id": item.collection_id,
        "media_item_id": item.media_item_id,
        "weight": item.weight,
        "min_duration_seconds": item.min_duration_seconds,
        "max_duration_seconds": item.max_duration_seconds,
    }


# ============================================================================
# Filler Preset Endpoints
# ============================================================================


@router.get("")
async def get_all_filler_presets(
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all filler presets.
    
    Returns:
        List of filler presets with item counts.
    """
    stmt = select(FillerPreset).options(selectinload(FillerPreset.items))
    result = await db.execute(stmt)
    presets = result.scalars().all()
    
    return [preset_to_response(p) for p in presets]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_filler_preset(
    preset: FillerPresetCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new filler preset.
    
    Args:
        preset: Filler preset data.
        
    Returns:
        Created filler preset.
    """
    # Validate mode-specific fields
    if preset.filler_mode == "count" and preset.count is None:
        raise HTTPException(
            status_code=400,
            detail="count is required when filler_mode is 'count'"
        )
    if preset.filler_mode == "duration" and preset.duration_seconds is None:
        raise HTTPException(
            status_code=400,
            detail="duration_seconds is required when filler_mode is 'duration'"
        )
    if preset.filler_mode == "pad" and preset.pad_to_minutes is None:
        raise HTTPException(
            status_code=400,
            detail="pad_to_minutes is required when filler_mode is 'pad'"
        )
    
    db_preset = FillerPreset(
        name=preset.name,
        filler_mode=preset.filler_mode,
        count=preset.count,
        duration_seconds=preset.duration_seconds,
        pad_to_minutes=preset.pad_to_minutes,
        playback_order=preset.playback_order,
        allow_repeats=preset.allow_repeats,
    )
    db.add(db_preset)
    await db.commit()
    await db.refresh(db_preset)
    
    logger.info(f"Created filler preset: {db_preset.name}")
    return preset_to_response(db_preset)


@router.get("/{preset_id}")
async def get_filler_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a filler preset by ID with all items.
    
    Args:
        preset_id: Filler preset ID.
        
    Returns:
        Filler preset details with items.
    """
    stmt = select(FillerPreset).where(FillerPreset.id == preset_id).options(
        selectinload(FillerPreset.items)
    )
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Filler preset not found")
    
    return preset_to_response(preset)


@router.put("/{preset_id}")
async def update_filler_preset(
    preset_id: int,
    update: FillerPresetUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a filler preset.
    
    Args:
        preset_id: Filler preset ID.
        update: Fields to update.
        
    Returns:
        Updated filler preset.
    """
    stmt = select(FillerPreset).where(FillerPreset.id == preset_id).options(
        selectinload(FillerPreset.items)
    )
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Filler preset not found")
    
    if update.name is not None:
        preset.name = update.name
    if update.filler_mode is not None:
        preset.filler_mode = update.filler_mode
    if update.count is not None:
        preset.count = update.count
    if update.duration_seconds is not None:
        preset.duration_seconds = update.duration_seconds
    if update.pad_to_minutes is not None:
        preset.pad_to_minutes = update.pad_to_minutes
    if update.playback_order is not None:
        preset.playback_order = update.playback_order
    if update.allow_repeats is not None:
        preset.allow_repeats = update.allow_repeats
    
    await db.commit()
    await db.refresh(preset)
    
    logger.info(f"Updated filler preset {preset_id}")
    return preset_to_response(preset)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filler_preset(
    preset_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a filler preset and all its items.
    
    Args:
        preset_id: Filler preset ID.
    """
    stmt = select(FillerPreset).where(FillerPreset.id == preset_id)
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Filler preset not found")
    
    await db.delete(preset)
    await db.commit()
    
    logger.info(f"Deleted filler preset {preset_id}")


# ============================================================================
# Filler Preset Item Endpoints
# ============================================================================


@router.post("/{preset_id}/items", status_code=status.HTTP_201_CREATED)
async def add_filler_item(
    preset_id: int,
    item: FillerPresetItemCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add an item to a filler preset.
    
    Args:
        preset_id: Filler preset ID.
        item: Item data.
        
    Returns:
        Created filler item.
    """
    stmt = select(FillerPreset).where(FillerPreset.id == preset_id)
    result = await db.execute(stmt)
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Filler preset not found")
    
    # Validate that either collection or media item is specified
    if item.collection_id is None and item.media_item_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either collection_id or media_item_id must be specified"
        )
    
    db_item = FillerPresetItem(
        preset_id=preset_id,
        collection_type=item.collection_type,
        collection_id=item.collection_id,
        media_item_id=item.media_item_id,
        weight=item.weight,
        min_duration_seconds=item.min_duration_seconds,
        max_duration_seconds=item.max_duration_seconds,
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    
    logger.info(f"Added item to filler preset {preset_id}")
    return item_to_response(db_item)


@router.put("/{preset_id}/items/{item_id}")
async def update_filler_item(
    preset_id: int,
    item_id: int,
    update: FillerPresetItemUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a filler preset item.
    
    Args:
        preset_id: Filler preset ID.
        item_id: Item ID.
        update: Fields to update.
        
    Returns:
        Updated filler item.
    """
    stmt = select(FillerPresetItem).where(
        FillerPresetItem.id == item_id,
        FillerPresetItem.preset_id == preset_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Filler item not found")
    
    if update.collection_type is not None:
        item.collection_type = update.collection_type
    if update.collection_id is not None:
        item.collection_id = update.collection_id
    if update.media_item_id is not None:
        item.media_item_id = update.media_item_id
    if update.weight is not None:
        item.weight = update.weight
    if update.min_duration_seconds is not None:
        item.min_duration_seconds = update.min_duration_seconds
    if update.max_duration_seconds is not None:
        item.max_duration_seconds = update.max_duration_seconds
    
    await db.commit()
    await db.refresh(item)
    
    logger.info(f"Updated filler item {item_id}")
    return item_to_response(item)


@router.delete("/{preset_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filler_item(
    preset_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Remove an item from a filler preset.
    
    Args:
        preset_id: Filler preset ID.
        item_id: Item ID.
    """
    stmt = select(FillerPresetItem).where(
        FillerPresetItem.id == item_id,
        FillerPresetItem.preset_id == preset_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Filler item not found")
    
    await db.delete(item)
    await db.commit()
    
    logger.info(f"Deleted filler item {item_id} from preset {preset_id}")
