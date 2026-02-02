"""Resolution API endpoints"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import ResolutionCreate, ResolutionResponse, ResolutionUpdate
from ..database import Resolution, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resolutions", tags=["Resolutions"])


@router.get("", response_model=list[ResolutionResponse])
async def get_all_resolutions(db: AsyncSession = Depends(get_db)) -> list[ResolutionResponse]:
    """Get all resolutions.

    Args:
        db: Database session

    Returns:
        list[ResolutionResponse]: List of all resolutions
    """
    result = await db.execute(
        select(Resolution).order_by(Resolution.width, Resolution.height)
    )
    return result.scalars().all()


@router.get("/{resolution_id}", response_model=ResolutionResponse)
async def get_resolution(resolution_id: int, db: AsyncSession = Depends(get_db)) -> ResolutionResponse:
    """Get resolution by ID.

    Args:
        resolution_id: Resolution ID
        db: Database session

    Returns:
        ResolutionResponse: Resolution details

    Raises:
        HTTPException: If resolution not found
    """
    result = await db.execute(
        select(Resolution).where(Resolution.id == resolution_id)
    )
    resolution = result.scalar_one_or_none()
    if not resolution:
        raise HTTPException(status_code=404, detail="Resolution not found")
    return resolution


@router.post("", response_model=ResolutionResponse, status_code=status.HTTP_201_CREATED)
async def create_resolution(
    resolution: ResolutionCreate, db: AsyncSession = Depends(get_db)
) -> ResolutionResponse:
    """Create a new resolution.

    Args:
        resolution: Resolution creation data
        db: Database session

    Returns:
        ResolutionResponse: Created resolution

    Raises:
        HTTPException: If resolution name already exists
    """
    # Check if resolution with same name exists
    result = await db.execute(
        select(Resolution).where(Resolution.name == resolution.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Resolution with this name already exists")

    db_resolution = Resolution(**resolution.model_dump())
    db.add(db_resolution)
    await db.commit()
    await db.refresh(db_resolution)
    return db_resolution


@router.put("/{resolution_id}", response_model=ResolutionResponse)
async def update_resolution(
    resolution_id: int, resolution_update: ResolutionUpdate, db: AsyncSession = Depends(get_db)
) -> ResolutionResponse:
    """Update a resolution.

    Args:
        resolution_id: Resolution ID
        resolution_update: Resolution update data
        db: Database session

    Returns:
        ResolutionResponse: Updated resolution

    Raises:
        HTTPException: If resolution not found or name conflicts
    """
    result = await db.execute(
        select(Resolution).where(Resolution.id == resolution_id)
    )
    resolution = result.scalar_one_or_none()
    if not resolution:
        raise HTTPException(status_code=404, detail="Resolution not found")

    # Check if name is being changed and conflicts with another resolution
    if resolution_update.name and resolution_update.name != resolution.name:
        result = await db.execute(
            select(Resolution).where(Resolution.name == resolution_update.name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Resolution with this name already exists")

    # Update fields
    for field, value in resolution_update.model_dump(exclude_unset=True).items():
        setattr(resolution, field, value)

    await db.commit()
    await db.refresh(resolution)
    return resolution


@router.delete("/{resolution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resolution(resolution_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a resolution.

    Args:
        resolution_id: Resolution ID
        db: Database session

    Raises:
        HTTPException: If resolution not found, is in use, or is not custom
    """
    result = await db.execute(
        select(Resolution).where(Resolution.id == resolution_id)
    )
    resolution = result.scalar_one_or_none()
    if not resolution:
        raise HTTPException(status_code=404, detail="Resolution not found")

    # Check if resolution is used by any FFmpeg profiles
    from ..database.models import FFmpegProfile
    from sqlalchemy import func

    result = await db.execute(
        select(func.count()).where(FFmpegProfile.resolution_id == resolution_id)
    )
    profiles_using = result.scalar()
    if profiles_using > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete resolution: it is used by {profiles_using} FFmpeg profile(s)",
        )

    # Don't allow deleting built-in resolutions
    if resolution.is_preset:
        raise HTTPException(status_code=400, detail="Cannot delete built-in resolution")

    await db.delete(resolution)
    await db.commit()
