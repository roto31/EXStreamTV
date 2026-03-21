"""Deco API endpoints - Full CRUD support for decorative content (bumpers, breaks, station IDs)"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..database.models.deco import DecoGroup, DecoTemplate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Deco"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class DecoGroupCreate(BaseModel):
    """Schema for creating a deco group."""
    name: str = Field(..., min_length=1, max_length=255)


class DecoGroupUpdate(BaseModel):
    """Schema for updating a deco group."""
    name: str | None = Field(None, min_length=1, max_length=255)


class DecoGroupResponse(BaseModel):
    """Response schema for deco group."""
    id: int
    name: str
    deco_count: int = 0
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


class DecoCreate(BaseModel):
    """Schema for creating a deco item."""
    name: str = Field(..., min_length=1, max_length=255)
    group_id: int | None = None
    deco_type: str = Field(
        default="bumper",
        description="Type: bumper, commercial, station_id, promo, credits"
    )
    media_item_id: int | None = None
    file_path: str | None = None
    duration_seconds: int | None = None
    static_duration_seconds: int = Field(default=5, ge=1)
    weight: int = Field(default=1, ge=1)


class DecoUpdate(BaseModel):
    """Schema for updating a deco item."""
    name: str | None = Field(None, min_length=1, max_length=255)
    group_id: int | None = None
    deco_type: str | None = None
    media_item_id: int | None = None
    file_path: str | None = None
    duration_seconds: int | None = None
    static_duration_seconds: int | None = None
    weight: int | None = None


class DecoResponse(BaseModel):
    """Response schema for deco item."""
    id: int
    name: str
    group_id: int | None
    deco_type: str
    media_item_id: int | None
    file_path: str | None
    duration_seconds: int | None
    static_duration_seconds: int
    weight: int
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


# ============================================================================
# Helper Functions
# ============================================================================


def deco_to_response(deco: DecoTemplate) -> dict[str, Any]:
    """Convert DecoTemplate model to response dictionary."""
    return {
        "id": deco.id,
        "name": deco.name,
        "group_id": deco.group_id,
        "deco_type": deco.deco_type,
        "media_item_id": deco.media_item_id,
        "file_path": deco.file_path,
        "duration_seconds": deco.duration_seconds,
        "static_duration_seconds": deco.static_duration_seconds,
        "weight": deco.weight,
        "created_at": deco.created_at,
        "updated_at": deco.updated_at,
    }


def deco_group_to_response(group: DecoGroup) -> dict[str, Any]:
    """Convert DecoGroup model to response dictionary."""
    return {
        "id": group.id,
        "name": group.name,
        "deco_count": len(group.decos) if group.decos else 0,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


# ============================================================================
# Deco Group Endpoints
# ============================================================================


@router.get("/deco-groups")
async def get_all_deco_groups(
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all deco groups.
    
    Returns:
        List of deco groups with deco counts.
    """
    stmt = select(DecoGroup).options(selectinload(DecoGroup.decos))
    result = await db.execute(stmt)
    groups = result.scalars().all()
    
    return [deco_group_to_response(g) for g in groups]


@router.post("/deco-groups", status_code=status.HTTP_201_CREATED)
async def create_deco_group(
    group: DecoGroupCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new deco group.
    
    Args:
        group: Deco group data.
        
    Returns:
        Created deco group.
    """
    db_group = DecoGroup(name=group.name)
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    
    logger.info(f"Created deco group: {db_group.name}")
    return deco_group_to_response(db_group)


@router.get("/deco-groups/{group_id}")
async def get_deco_group(
    group_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a deco group by ID.
    
    Args:
        group_id: Deco group ID.
        
    Returns:
        Deco group details with decos.
    """
    stmt = select(DecoGroup).where(DecoGroup.id == group_id).options(
        selectinload(DecoGroup.decos)
    )
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Deco group not found")
    
    response = deco_group_to_response(group)
    response["decos"] = [deco_to_response(d) for d in group.decos]
    return response


@router.put("/deco-groups/{group_id}")
async def update_deco_group(
    group_id: int,
    update: DecoGroupUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a deco group.
    
    Args:
        group_id: Deco group ID.
        update: Fields to update.
        
    Returns:
        Updated deco group.
    """
    stmt = select(DecoGroup).where(DecoGroup.id == group_id)
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Deco group not found")
    
    if update.name is not None:
        group.name = update.name
    
    await db.commit()
    await db.refresh(group)
    
    logger.info(f"Updated deco group {group_id}")
    return deco_group_to_response(group)


@router.delete("/deco-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deco_group(
    group_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a deco group and all its decos.
    
    Args:
        group_id: Deco group ID.
    """
    stmt = select(DecoGroup).where(DecoGroup.id == group_id)
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Deco group not found")
    
    await db.delete(group)
    await db.commit()
    
    logger.info(f"Deleted deco group {group_id}")


# ============================================================================
# Deco Endpoints
# ============================================================================


@router.get("/deco")
async def get_all_decos(
    group_id: int | None = None,
    deco_type: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all decos, optionally filtered by group or type.
    
    Args:
        group_id: Optional group ID filter.
        deco_type: Optional type filter (bumper, commercial, station_id, promo, credits).
        
    Returns:
        List of decos.
    """
    stmt = select(DecoTemplate)
    
    if group_id is not None:
        stmt = stmt.where(DecoTemplate.group_id == group_id)
    if deco_type is not None:
        stmt = stmt.where(DecoTemplate.deco_type == deco_type)
    
    result = await db.execute(stmt)
    decos = result.scalars().all()
    
    return [deco_to_response(d) for d in decos]


@router.post("/deco", status_code=status.HTTP_201_CREATED)
async def create_deco(
    deco: DecoCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new deco item.
    
    Args:
        deco: Deco data.
        
    Returns:
        Created deco.
    """
    # Validate group if provided
    if deco.group_id:
        stmt = select(DecoGroup).where(DecoGroup.id == deco.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=400, detail="Deco group not found")
    
    # Validate that either media_item_id or file_path is provided
    if deco.media_item_id is None and deco.file_path is None:
        raise HTTPException(
            status_code=400,
            detail="Either media_item_id or file_path must be provided"
        )
    
    # Validate deco_type
    valid_types = ["bumper", "commercial", "station_id", "promo", "credits"]
    if deco.deco_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid deco_type. Must be one of: {', '.join(valid_types)}"
        )
    
    db_deco = DecoTemplate(
        name=deco.name,
        group_id=deco.group_id,
        deco_type=deco.deco_type,
        media_item_id=deco.media_item_id,
        file_path=deco.file_path,
        duration_seconds=deco.duration_seconds,
        static_duration_seconds=deco.static_duration_seconds,
        weight=deco.weight,
    )
    db.add(db_deco)
    await db.commit()
    await db.refresh(db_deco)
    
    logger.info(f"Created deco: {db_deco.name}")
    return deco_to_response(db_deco)


@router.get("/deco/{deco_id}")
async def get_deco(
    deco_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a deco by ID.
    
    Args:
        deco_id: Deco ID.
        
    Returns:
        Deco details.
    """
    stmt = select(DecoTemplate).where(DecoTemplate.id == deco_id).options(
        selectinload(DecoTemplate.group)
    )
    result = await db.execute(stmt)
    deco = result.scalar_one_or_none()
    
    if not deco:
        raise HTTPException(status_code=404, detail="Deco not found")
    
    response = deco_to_response(deco)
    if deco.group:
        response["group_name"] = deco.group.name
    return response


@router.put("/deco/{deco_id}")
async def update_deco(
    deco_id: int,
    update: DecoUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a deco.
    
    Args:
        deco_id: Deco ID.
        update: Fields to update.
        
    Returns:
        Updated deco.
    """
    stmt = select(DecoTemplate).where(DecoTemplate.id == deco_id)
    result = await db.execute(stmt)
    deco = result.scalar_one_or_none()
    
    if not deco:
        raise HTTPException(status_code=404, detail="Deco not found")
    
    # Validate group if being updated
    if update.group_id is not None and update.group_id > 0:
        stmt = select(DecoGroup).where(DecoGroup.id == update.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=400, detail="Deco group not found")
        deco.group_id = update.group_id
    elif update.group_id == 0:
        deco.group_id = None
    
    if update.name is not None:
        deco.name = update.name
    if update.deco_type is not None:
        valid_types = ["bumper", "commercial", "station_id", "promo", "credits"]
        if update.deco_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid deco_type. Must be one of: {', '.join(valid_types)}"
            )
        deco.deco_type = update.deco_type
    if update.media_item_id is not None:
        deco.media_item_id = update.media_item_id if update.media_item_id > 0 else None
    if update.file_path is not None:
        deco.file_path = update.file_path if update.file_path else None
    if update.duration_seconds is not None:
        deco.duration_seconds = update.duration_seconds
    if update.static_duration_seconds is not None:
        deco.static_duration_seconds = update.static_duration_seconds
    if update.weight is not None:
        deco.weight = update.weight
    
    await db.commit()
    await db.refresh(deco)
    
    logger.info(f"Updated deco {deco_id}")
    return deco_to_response(deco)


@router.delete("/deco/{deco_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deco(
    deco_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a deco.
    
    Args:
        deco_id: Deco ID.
    """
    stmt = select(DecoTemplate).where(DecoTemplate.id == deco_id)
    result = await db.execute(stmt)
    deco = result.scalar_one_or_none()
    
    if not deco:
        raise HTTPException(status_code=404, detail="Deco not found")
    
    await db.delete(deco)
    await db.commit()
    
    logger.info(f"Deleted deco {deco_id}")


# ============================================================================
# Utility Endpoints
# ============================================================================


@router.get("/deco/types")
async def get_deco_types() -> dict[str, list[str]]:
    """Get available deco types.
    
    Returns:
        List of valid deco types.
    """
    return {
        "types": ["bumper", "commercial", "station_id", "promo", "credits"],
        "descriptions": {
            "bumper": "Short transitional clips between programs",
            "commercial": "Advertisement or promotional content",
            "station_id": "Station identification clips",
            "promo": "Program promotional content",
            "credits": "Credit sequences",
        }
    }
