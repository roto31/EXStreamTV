"""Block and BlockGroup API endpoints - Full CRUD support for time-based programming blocks"""

import logging
from datetime import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..database.models.schedule import Block, BlockGroup, BlockItem

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Blocks"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class BlockGroupCreate(BaseModel):
    """Schema for creating a block group."""
    name: str = Field(..., min_length=1, max_length=255)


class BlockGroupUpdate(BaseModel):
    """Schema for updating a block group."""
    name: str | None = Field(None, min_length=1, max_length=255)


class BlockGroupResponse(BaseModel):
    """Response schema for block group."""
    id: int
    name: str
    block_count: int = 0
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


class BlockCreate(BaseModel):
    """Schema for creating a block."""
    name: str = Field(..., min_length=1, max_length=255)
    group_id: int | None = None
    start_time: str = Field(..., description="Start time in HH:MM format")
    duration_minutes: int = Field(..., ge=1)
    days_of_week: int = Field(default=127, ge=0, le=127, description="Bitmask: 1=Sun, 2=Mon, 4=Tue, 8=Wed, 16=Thu, 32=Fri, 64=Sat")


class BlockUpdate(BaseModel):
    """Schema for updating a block."""
    name: str | None = Field(None, min_length=1, max_length=255)
    group_id: int | None = None
    start_time: str | None = Field(None, description="Start time in HH:MM format")
    duration_minutes: int | None = Field(None, ge=1)
    days_of_week: int | None = Field(None, ge=0, le=127)


class BlockItemCreate(BaseModel):
    """Schema for creating a block item."""
    collection_type: str = Field(..., description="Type: playlist, collection, show, season")
    collection_id: int
    playback_order: str = Field(default="chronological", description="chronological, shuffled, random")
    include_in_guide: bool = True


class BlockItemUpdate(BaseModel):
    """Schema for updating a block item."""
    collection_type: str | None = None
    collection_id: int | None = None
    playback_order: str | None = None
    include_in_guide: bool | None = None


class BlockItemResponse(BaseModel):
    """Response schema for block item."""
    id: int
    block_id: int
    position: int
    collection_type: str
    collection_id: int
    playback_order: str
    include_in_guide: bool

    class Config:
        from_attributes = True


class BlockResponse(BaseModel):
    """Response schema for block."""
    id: int
    name: str
    group_id: int | None
    start_time: str
    duration_minutes: int
    days_of_week: int
    items: list[BlockItemResponse] = []
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


class ReorderRequest(BaseModel):
    """Schema for reordering items."""
    item_ids: list[int] = Field(..., description="List of item IDs in new order")


# ============================================================================
# Helper Functions
# ============================================================================


def parse_time_string(time_str: str) -> time:
    """Parse HH:MM string to time object."""
    try:
        parts = time_str.split(":")
        return time(hour=int(parts[0]), minute=int(parts[1]))
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time format. Expected HH:MM, got: {time_str}"
        ) from e


def time_to_string(t: time) -> str:
    """Convert time object to HH:MM string."""
    return t.strftime("%H:%M")


def block_to_response(block: Block) -> dict[str, Any]:
    """Convert Block model to response dictionary."""
    return {
        "id": block.id,
        "name": block.name,
        "group_id": block.group_id,
        "start_time": time_to_string(block.start_time),
        "duration_minutes": block.duration_minutes,
        "days_of_week": block.days_of_week,
        "items": [
            {
                "id": item.id,
                "block_id": item.block_id,
                "position": item.position,
                "collection_type": item.collection_type,
                "collection_id": item.collection_id,
                "playback_order": item.playback_order,
                "include_in_guide": item.include_in_guide,
            }
            for item in (block.items or [])
        ],
        "created_at": block.created_at,
        "updated_at": block.updated_at,
    }


def block_group_to_response(group: BlockGroup) -> dict[str, Any]:
    """Convert BlockGroup model to response dictionary."""
    return {
        "id": group.id,
        "name": group.name,
        "block_count": len(group.blocks) if group.blocks else 0,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


# ============================================================================
# Block Group Endpoints
# ============================================================================


@router.get("/block-groups")
async def get_all_block_groups(
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all block groups.
    
    Returns:
        List of block groups with block counts.
    """
    stmt = select(BlockGroup).options(selectinload(BlockGroup.blocks))
    result = await db.execute(stmt)
    groups = result.scalars().all()
    
    return [block_group_to_response(g) for g in groups]


@router.post("/block-groups", status_code=status.HTTP_201_CREATED)
async def create_block_group(
    group: BlockGroupCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new block group.
    
    Args:
        group: Block group data.
        
    Returns:
        Created block group.
    """
    db_group = BlockGroup(name=group.name)
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    
    logger.info(f"Created block group: {db_group.name}")
    return block_group_to_response(db_group)


@router.get("/block-groups/{group_id}")
async def get_block_group(
    group_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a block group by ID.
    
    Args:
        group_id: Block group ID.
        
    Returns:
        Block group details.
    """
    stmt = select(BlockGroup).where(BlockGroup.id == group_id).options(
        selectinload(BlockGroup.blocks)
    )
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Block group not found")
    
    response = block_group_to_response(group)
    response["blocks"] = [
        {
            "id": b.id,
            "name": b.name,
            "start_time": time_to_string(b.start_time),
            "duration_minutes": b.duration_minutes,
        }
        for b in group.blocks
    ]
    return response


@router.put("/block-groups/{group_id}")
async def update_block_group(
    group_id: int,
    update: BlockGroupUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a block group.
    
    Args:
        group_id: Block group ID.
        update: Fields to update.
        
    Returns:
        Updated block group.
    """
    stmt = select(BlockGroup).where(BlockGroup.id == group_id)
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Block group not found")
    
    if update.name is not None:
        group.name = update.name
    
    await db.commit()
    await db.refresh(group)
    
    logger.info(f"Updated block group {group_id}")
    return block_group_to_response(group)


@router.delete("/block-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_group(
    group_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a block group and all its blocks.
    
    Args:
        group_id: Block group ID.
    """
    stmt = select(BlockGroup).where(BlockGroup.id == group_id)
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Block group not found")
    
    await db.delete(group)
    await db.commit()
    
    logger.info(f"Deleted block group {group_id}")


# ============================================================================
# Block Endpoints
# ============================================================================


@router.get("/blocks")
async def get_all_blocks(
    group_id: int | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all blocks, optionally filtered by group.
    
    Args:
        group_id: Optional group ID filter.
        
    Returns:
        List of blocks.
    """
    stmt = select(Block).options(selectinload(Block.items))
    
    if group_id is not None:
        stmt = stmt.where(Block.group_id == group_id)
    
    stmt = stmt.order_by(Block.start_time)
    result = await db.execute(stmt)
    blocks = result.scalars().all()
    
    return [block_to_response(b) for b in blocks]


@router.post("/blocks", status_code=status.HTTP_201_CREATED)
async def create_block(
    block: BlockCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new block.
    
    Args:
        block: Block data.
        
    Returns:
        Created block.
    """
    # Validate group if provided
    if block.group_id:
        stmt = select(BlockGroup).where(BlockGroup.id == block.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=400, detail="Block group not found")
    
    start_time = parse_time_string(block.start_time)
    
    db_block = Block(
        name=block.name,
        group_id=block.group_id,
        start_time=start_time,
        duration_minutes=block.duration_minutes,
        days_of_week=block.days_of_week,
    )
    db.add(db_block)
    await db.commit()
    await db.refresh(db_block)
    
    logger.info(f"Created block: {db_block.name}")
    return block_to_response(db_block)


@router.get("/blocks/{block_id}")
async def get_block(
    block_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a block by ID with all items.
    
    Args:
        block_id: Block ID.
        
    Returns:
        Block details with items.
    """
    stmt = select(Block).where(Block.id == block_id).options(
        selectinload(Block.items),
        selectinload(Block.group),
    )
    result = await db.execute(stmt)
    block = result.scalar_one_or_none()
    
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    response = block_to_response(block)
    if block.group:
        response["group_name"] = block.group.name
    return response


@router.put("/blocks/{block_id}")
async def update_block(
    block_id: int,
    update: BlockUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a block.
    
    Args:
        block_id: Block ID.
        update: Fields to update.
        
    Returns:
        Updated block.
    """
    stmt = select(Block).where(Block.id == block_id).options(selectinload(Block.items))
    result = await db.execute(stmt)
    block = result.scalar_one_or_none()
    
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    # Validate group if being updated
    if update.group_id is not None and update.group_id > 0:
        stmt = select(BlockGroup).where(BlockGroup.id == update.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=400, detail="Block group not found")
        block.group_id = update.group_id
    elif update.group_id == 0:
        block.group_id = None
    
    if update.name is not None:
        block.name = update.name
    if update.start_time is not None:
        block.start_time = parse_time_string(update.start_time)
    if update.duration_minutes is not None:
        block.duration_minutes = update.duration_minutes
    if update.days_of_week is not None:
        block.days_of_week = update.days_of_week
    
    await db.commit()
    await db.refresh(block)
    
    logger.info(f"Updated block {block_id}")
    return block_to_response(block)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block(
    block_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a block and all its items.
    
    Args:
        block_id: Block ID.
    """
    stmt = select(Block).where(Block.id == block_id)
    result = await db.execute(stmt)
    block = result.scalar_one_or_none()
    
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    await db.delete(block)
    await db.commit()
    
    logger.info(f"Deleted block {block_id}")


# ============================================================================
# Block Item Endpoints
# ============================================================================


@router.post("/blocks/{block_id}/items", status_code=status.HTTP_201_CREATED)
async def add_block_item(
    block_id: int,
    item: BlockItemCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add an item to a block.
    
    Args:
        block_id: Block ID.
        item: Item data.
        
    Returns:
        Created block item.
    """
    stmt = select(Block).where(Block.id == block_id).options(selectinload(Block.items))
    result = await db.execute(stmt)
    block = result.scalar_one_or_none()
    
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    # Calculate next position
    max_position = max((i.position for i in block.items), default=0)
    
    db_item = BlockItem(
        block_id=block_id,
        position=max_position + 1,
        collection_type=item.collection_type,
        collection_id=item.collection_id,
        playback_order=item.playback_order,
        include_in_guide=item.include_in_guide,
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    
    logger.info(f"Added item to block {block_id}")
    return {
        "id": db_item.id,
        "block_id": db_item.block_id,
        "position": db_item.position,
        "collection_type": db_item.collection_type,
        "collection_id": db_item.collection_id,
        "playback_order": db_item.playback_order,
        "include_in_guide": db_item.include_in_guide,
    }


@router.put("/blocks/{block_id}/items/{item_id}")
async def update_block_item(
    block_id: int,
    item_id: int,
    update: BlockItemUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a block item.
    
    Args:
        block_id: Block ID.
        item_id: Item ID.
        update: Fields to update.
        
    Returns:
        Updated block item.
    """
    stmt = select(BlockItem).where(
        BlockItem.id == item_id,
        BlockItem.block_id == block_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Block item not found")
    
    if update.collection_type is not None:
        item.collection_type = update.collection_type
    if update.collection_id is not None:
        item.collection_id = update.collection_id
    if update.playback_order is not None:
        item.playback_order = update.playback_order
    if update.include_in_guide is not None:
        item.include_in_guide = update.include_in_guide
    
    await db.commit()
    await db.refresh(item)
    
    logger.info(f"Updated block item {item_id}")
    return {
        "id": item.id,
        "block_id": item.block_id,
        "position": item.position,
        "collection_type": item.collection_type,
        "collection_id": item.collection_id,
        "playback_order": item.playback_order,
        "include_in_guide": item.include_in_guide,
    }


@router.delete("/blocks/{block_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_block_item(
    block_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Remove an item from a block.
    
    Args:
        block_id: Block ID.
        item_id: Item ID.
    """
    stmt = select(BlockItem).where(
        BlockItem.id == item_id,
        BlockItem.block_id == block_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Block item not found")
    
    await db.delete(item)
    await db.commit()
    
    logger.info(f"Deleted block item {item_id} from block {block_id}")


@router.post("/blocks/{block_id}/items/reorder")
async def reorder_block_items(
    block_id: int,
    reorder: ReorderRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Reorder items within a block.
    
    Args:
        block_id: Block ID.
        reorder: New order of item IDs.
        
    Returns:
        Success message.
    """
    stmt = select(Block).where(Block.id == block_id).options(selectinload(Block.items))
    result = await db.execute(stmt)
    block = result.scalar_one_or_none()
    
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    
    # Validate all IDs belong to this block
    item_map = {item.id: item for item in block.items}
    for item_id in reorder.item_ids:
        if item_id not in item_map:
            raise HTTPException(
                status_code=400,
                detail=f"Item {item_id} does not belong to block {block_id}"
            )
    
    # Update positions
    for position, item_id in enumerate(reorder.item_ids, start=1):
        item_map[item_id].position = position
    
    await db.commit()
    
    logger.info(f"Reordered items in block {block_id}")
    return {"message": "Items reordered successfully", "block_id": block_id}
