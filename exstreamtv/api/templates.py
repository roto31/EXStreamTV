"""Templates API endpoints - Full CRUD support for scheduling templates"""

import logging
from datetime import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..database.models.template import Template, TemplateGroup, TemplateItem
from ..database.models.playout import Playout

logger = logging.getLogger(__name__)
router = APIRouter(prefix="", tags=["Templates"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class TemplateGroupCreate(BaseModel):
    """Schema for creating a template group."""
    name: str = Field(..., min_length=1, max_length=255)


class TemplateGroupUpdate(BaseModel):
    """Schema for updating a template group."""
    name: str | None = Field(None, min_length=1, max_length=255)


class TemplateGroupResponse(BaseModel):
    """Response schema for template group."""
    id: int
    name: str
    template_count: int = 0
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


class TemplateCreate(BaseModel):
    """Schema for creating a template."""
    name: str = Field(..., min_length=1, max_length=255)
    group_id: int | None = None
    is_enabled: bool = True


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""
    name: str | None = Field(None, min_length=1, max_length=255)
    group_id: int | None = None
    is_enabled: bool | None = None


class TemplateItemCreate(BaseModel):
    """Schema for creating a template item (time slot)."""
    start_time: str = Field(..., description="Start time in HH:MM format")
    block_id: int | None = None
    collection_type: str | None = None
    collection_id: int | None = None
    playback_order: str = Field(default="chronological")


class TemplateItemUpdate(BaseModel):
    """Schema for updating a template item."""
    start_time: str | None = None
    block_id: int | None = None
    collection_type: str | None = None
    collection_id: int | None = None
    playback_order: str | None = None


class TemplateItemResponse(BaseModel):
    """Response schema for template item."""
    id: int
    template_id: int
    start_time: str
    block_id: int | None
    collection_type: str | None
    collection_id: int | None
    playback_order: str

    class Config:
        from_attributes = True


class TemplateResponse(BaseModel):
    """Response schema for template."""
    id: int
    name: str
    group_id: int | None
    is_enabled: bool
    items: list[TemplateItemResponse] = []
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True


class ApplyTemplateRequest(BaseModel):
    """Request schema for applying a template to a channel."""
    day_of_week: int | None = Field(
        None,
        ge=0,
        le=6,
        description="Day of week (0=Sunday, 6=Saturday). None for all days."
    )


# ============================================================================
# Helper Functions
# ============================================================================


def parse_time_string(time_str: str) -> int:
    """Parse HH:MM string to minutes from midnight (stored as integer)."""
    try:
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        return hours * 60 + minutes
    except (ValueError, IndexError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid time format. Expected HH:MM, got: {time_str}"
        ) from e


def minutes_to_time_string(minutes: int) -> str:
    """Convert minutes from midnight to HH:MM string."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def template_to_response(template: Template) -> dict[str, Any]:
    """Convert Template model to response dictionary."""
    return {
        "id": template.id,
        "name": template.name,
        "group_id": template.group_id,
        "is_enabled": template.is_enabled,
        "items": [
            {
                "id": item.id,
                "template_id": item.template_id,
                "start_time": minutes_to_time_string(item.start_time) if isinstance(item.start_time, int) else str(item.start_time),
                "block_id": item.block_id,
                "collection_type": item.collection_type,
                "collection_id": item.collection_id,
                "playback_order": item.playback_order,
            }
            for item in (template.items or [])
        ],
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def template_group_to_response(group: TemplateGroup) -> dict[str, Any]:
    """Convert TemplateGroup model to response dictionary."""
    return {
        "id": group.id,
        "name": group.name,
        "template_count": len(group.templates) if group.templates else 0,
        "created_at": group.created_at,
        "updated_at": group.updated_at,
    }


# ============================================================================
# Template Group Endpoints
# ============================================================================


@router.get("/template-groups")
async def get_all_template_groups(
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all template groups.
    
    Returns:
        List of template groups with template counts.
    """
    stmt = select(TemplateGroup).options(selectinload(TemplateGroup.templates))
    result = await db.execute(stmt)
    groups = result.scalars().all()
    
    return [template_group_to_response(g) for g in groups]


@router.post("/template-groups", status_code=status.HTTP_201_CREATED)
async def create_template_group(
    group: TemplateGroupCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new template group.
    
    Args:
        group: Template group data.
        
    Returns:
        Created template group.
    """
    db_group = TemplateGroup(name=group.name)
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    
    logger.info(f"Created template group: {db_group.name}")
    return template_group_to_response(db_group)


@router.get("/template-groups/{group_id}")
async def get_template_group(
    group_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a template group by ID.
    
    Args:
        group_id: Template group ID.
        
    Returns:
        Template group details with templates.
    """
    stmt = select(TemplateGroup).where(TemplateGroup.id == group_id).options(
        selectinload(TemplateGroup.templates)
    )
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Template group not found")
    
    response = template_group_to_response(group)
    response["templates"] = [
        {"id": t.id, "name": t.name, "is_enabled": t.is_enabled}
        for t in group.templates
    ]
    return response


@router.put("/template-groups/{group_id}")
async def update_template_group(
    group_id: int,
    update: TemplateGroupUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a template group.
    
    Args:
        group_id: Template group ID.
        update: Fields to update.
        
    Returns:
        Updated template group.
    """
    stmt = select(TemplateGroup).where(TemplateGroup.id == group_id)
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Template group not found")
    
    if update.name is not None:
        group.name = update.name
    
    await db.commit()
    await db.refresh(group)
    
    logger.info(f"Updated template group {group_id}")
    return template_group_to_response(group)


@router.delete("/template-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_group(
    group_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a template group and all its templates.
    
    Args:
        group_id: Template group ID.
    """
    stmt = select(TemplateGroup).where(TemplateGroup.id == group_id)
    result = await db.execute(stmt)
    group = result.scalar_one_or_none()
    
    if not group:
        raise HTTPException(status_code=404, detail="Template group not found")
    
    await db.delete(group)
    await db.commit()
    
    logger.info(f"Deleted template group {group_id}")


# ============================================================================
# Template Endpoints
# ============================================================================


@router.get("/templates")
async def get_all_templates(
    group_id: int | None = None,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all templates, optionally filtered by group.
    
    Args:
        group_id: Optional group ID filter.
        
    Returns:
        List of templates.
    """
    stmt = select(Template).options(selectinload(Template.items))
    
    if group_id is not None:
        stmt = stmt.where(Template.group_id == group_id)
    
    result = await db.execute(stmt)
    templates = result.scalars().all()
    
    return [template_to_response(t) for t in templates]


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    template: TemplateCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new template.
    
    Args:
        template: Template data.
        
    Returns:
        Created template.
    """
    # Validate group if provided
    if template.group_id:
        stmt = select(TemplateGroup).where(TemplateGroup.id == template.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=400, detail="Template group not found")
    
    db_template = Template(
        name=template.name,
        group_id=template.group_id,
        is_enabled=template.is_enabled,
    )
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    
    logger.info(f"Created template: {db_template.name}")
    return template_to_response(db_template)


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get a template by ID with all items.
    
    Args:
        template_id: Template ID.
        
    Returns:
        Template details with items.
    """
    stmt = select(Template).where(Template.id == template_id).options(
        selectinload(Template.items),
        selectinload(Template.group),
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    response = template_to_response(template)
    if template.group:
        response["group_name"] = template.group.name
    return response


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    update: TemplateUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a template.
    
    Args:
        template_id: Template ID.
        update: Fields to update.
        
    Returns:
        Updated template.
    """
    stmt = select(Template).where(Template.id == template_id).options(
        selectinload(Template.items)
    )
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Validate group if being updated
    if update.group_id is not None and update.group_id > 0:
        stmt = select(TemplateGroup).where(TemplateGroup.id == update.group_id)
        result = await db.execute(stmt)
        group = result.scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=400, detail="Template group not found")
        template.group_id = update.group_id
    elif update.group_id == 0:
        template.group_id = None
    
    if update.name is not None:
        template.name = update.name
    if update.is_enabled is not None:
        template.is_enabled = update.is_enabled
    
    await db.commit()
    await db.refresh(template)
    
    logger.info(f"Updated template {template_id}")
    return template_to_response(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a template and all its items.
    
    Args:
        template_id: Template ID.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.delete(template)
    await db.commit()
    
    logger.info(f"Deleted template {template_id}")


# ============================================================================
# Template Item Endpoints
# ============================================================================


@router.post("/templates/{template_id}/items", status_code=status.HTTP_201_CREATED)
async def add_template_item(
    template_id: int,
    item: TemplateItemCreate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a time slot to a template.
    
    Args:
        template_id: Template ID.
        item: Time slot data.
        
    Returns:
        Created template item.
    """
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Validate that either block or collection is specified
    if item.block_id is None and item.collection_id is None:
        raise HTTPException(
            status_code=400,
            detail="Either block_id or collection_id must be specified"
        )
    
    start_time = parse_time_string(item.start_time)
    
    db_item = TemplateItem(
        template_id=template_id,
        start_time=start_time,
        block_id=item.block_id,
        collection_type=item.collection_type,
        collection_id=item.collection_id,
        playback_order=item.playback_order,
    )
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    
    logger.info(f"Added item to template {template_id}")
    return {
        "id": db_item.id,
        "template_id": db_item.template_id,
        "start_time": minutes_to_time_string(db_item.start_time) if isinstance(db_item.start_time, int) else str(db_item.start_time),
        "block_id": db_item.block_id,
        "collection_type": db_item.collection_type,
        "collection_id": db_item.collection_id,
        "playback_order": db_item.playback_order,
    }


@router.put("/templates/{template_id}/items/{item_id}")
async def update_template_item(
    template_id: int,
    item_id: int,
    update: TemplateItemUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a template item.
    
    Args:
        template_id: Template ID.
        item_id: Item ID.
        update: Fields to update.
        
    Returns:
        Updated template item.
    """
    stmt = select(TemplateItem).where(
        TemplateItem.id == item_id,
        TemplateItem.template_id == template_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Template item not found")
    
    if update.start_time is not None:
        item.start_time = parse_time_string(update.start_time)
    if update.block_id is not None:
        item.block_id = update.block_id if update.block_id > 0 else None
    if update.collection_type is not None:
        item.collection_type = update.collection_type
    if update.collection_id is not None:
        item.collection_id = update.collection_id if update.collection_id > 0 else None
    if update.playback_order is not None:
        item.playback_order = update.playback_order
    
    await db.commit()
    await db.refresh(item)
    
    logger.info(f"Updated template item {item_id}")
    return {
        "id": item.id,
        "template_id": item.template_id,
        "start_time": minutes_to_time_string(item.start_time) if isinstance(item.start_time, int) else str(item.start_time),
        "block_id": item.block_id,
        "collection_type": item.collection_type,
        "collection_id": item.collection_id,
        "playback_order": item.playback_order,
    }


@router.delete("/templates/{template_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template_item(
    template_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Remove a time slot from a template.
    
    Args:
        template_id: Template ID.
        item_id: Item ID.
    """
    stmt = select(TemplateItem).where(
        TemplateItem.id == item_id,
        TemplateItem.template_id == template_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Template item not found")
    
    await db.delete(item)
    await db.commit()
    
    logger.info(f"Deleted template item {item_id} from template {template_id}")


# ============================================================================
# Template Application Endpoint
# ============================================================================


@router.post("/templates/{template_id}/apply/{channel_id}")
async def apply_template_to_channel(
    template_id: int,
    channel_id: int,
    request: ApplyTemplateRequest,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Apply a template to a channel's playout.
    
    Args:
        template_id: Template ID.
        channel_id: Channel ID.
        request: Application options.
        
    Returns:
        Application result.
    """
    from ..database.models.channel import Channel
    from ..database.models.playout import PlayoutTemplate
    
    # Validate template exists
    stmt = select(Template).where(Template.id == template_id)
    result = await db.execute(stmt)
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Validate channel exists
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get or create playout for the channel
    stmt = select(Playout).where(
        Playout.channel_id == channel_id,
        Playout.is_active == True
    )
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        # Create a new playout for this channel
        playout = Playout(
            channel_id=channel_id,
            template_id=template_id,
            playout_type="continuous",
            is_active=True,
        )
        db.add(playout)
        await db.commit()
        await db.refresh(playout)
        
        logger.info(f"Created playout for channel {channel_id} with template {template_id}")
        return {
            "message": "Template applied successfully",
            "playout_id": playout.id,
            "template_id": template_id,
            "channel_id": channel_id,
            "day_of_week": request.day_of_week,
        }
    
    # Update existing playout to use this template
    playout.template_id = template_id
    await db.commit()
    
    logger.info(f"Applied template {template_id} to channel {channel_id}")
    return {
        "message": "Template applied successfully",
        "playout_id": playout.id,
        "template_id": template_id,
        "channel_id": channel_id,
        "day_of_week": request.day_of_week,
    }
