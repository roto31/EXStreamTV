"""Watermark API endpoints"""

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import WatermarkCreate, WatermarkResponse, WatermarkUpdate
from ..database import Watermark, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watermarks", tags=["Watermarks"])

# Directory for storing watermark images
# Use absolute path relative to project root
WATERMARKS_DIR = Path(__file__).parent.parent.parent / "data" / "watermarks"
WATERMARKS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("", response_model=list[WatermarkResponse])
async def get_all_watermarks(db: AsyncSession = Depends(get_db)) -> list[WatermarkResponse]:
    """Get all watermarks.

    Args:
        db: Database session

    Returns:
        list[WatermarkResponse]: List of all watermarks
    """
    result = await db.execute(select(Watermark).order_by(Watermark.name))
    return result.scalars().all()


@router.get("/{watermark_id}", response_model=WatermarkResponse)
async def get_watermark(watermark_id: int, db: AsyncSession = Depends(get_db)) -> WatermarkResponse:
    """Get watermark by ID.

    Args:
        watermark_id: Watermark ID
        db: Database session

    Returns:
        WatermarkResponse: Watermark details

    Raises:
        HTTPException: If watermark not found
    """
    result = await db.execute(
        select(Watermark).where(Watermark.id == watermark_id)
    )
    watermark = result.scalar_one_or_none()
    if not watermark:
        raise HTTPException(status_code=404, detail="Watermark not found")
    return watermark


@router.post("", response_model=WatermarkResponse, status_code=status.HTTP_201_CREATED)
async def create_watermark(
    watermark: WatermarkCreate, db: AsyncSession = Depends(get_db)
) -> WatermarkResponse:
    """Create a new watermark.

    Args:
        watermark: Watermark creation data
        db: Database session

    Returns:
        WatermarkResponse: Created watermark

    Raises:
        HTTPException: If watermark name already exists
    """
    # Check if watermark with same name exists
    result = await db.execute(
        select(Watermark).where(Watermark.name == watermark.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Watermark with this name already exists")

    db_watermark = Watermark(**watermark.model_dump(exclude={"image"}))
    db.add(db_watermark)
    await db.commit()
    await db.refresh(db_watermark)
    return db_watermark


@router.put("/{watermark_id}", response_model=WatermarkResponse)
async def update_watermark(
    watermark_id: int, watermark_update: WatermarkUpdate, db: AsyncSession = Depends(get_db)
) -> WatermarkResponse:
    """Update a watermark.

    Args:
        watermark_id: Watermark ID
        watermark_update: Watermark update data
        db: Database session

    Returns:
        WatermarkResponse: Updated watermark

    Raises:
        HTTPException: If watermark not found or name conflicts
    """
    result = await db.execute(
        select(Watermark).where(Watermark.id == watermark_id)
    )
    watermark = result.scalar_one_or_none()
    if not watermark:
        raise HTTPException(status_code=404, detail="Watermark not found")

    # Check if name is being changed and conflicts with another watermark
    if watermark_update.name and watermark_update.name != watermark.name:
        result = await db.execute(
            select(Watermark).where(Watermark.name == watermark_update.name)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Watermark with this name already exists")

    # Update fields
    for field, value in watermark_update.model_dump(exclude_unset=True, exclude={"image"}).items():
        setattr(watermark, field, value)

    await db.commit()
    await db.refresh(watermark)
    return watermark


@router.delete("/{watermark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watermark(watermark_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a watermark.

    Args:
        watermark_id: Watermark ID
        db: Database session

    Raises:
        HTTPException: If watermark not found or is in use by channels
    """
    result = await db.execute(
        select(Watermark).where(Watermark.id == watermark_id)
    )
    watermark = result.scalar_one_or_none()
    if not watermark:
        raise HTTPException(status_code=404, detail="Watermark not found")

    # Check if watermark is used by any channels
    from ..database.models import Channel

    result = await db.execute(
        select(func.count()).select_from(Channel).where(Channel.watermark_id == watermark_id)
    )
    channels_using = result.scalar()
    if channels_using > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete watermark: it is used by {channels_using} channel(s)",
        )

    # Delete image file if it exists
    if watermark.image:
        image_path = WATERMARKS_DIR / watermark.image
        if image_path.exists():
            try:
                image_path.unlink()
                logger.info(f"Deleted watermark image: {image_path}")
            except Exception as e:
                logger.warning(f"Failed to delete watermark image {image_path}: {e}")

    await db.delete(watermark)
    await db.commit()


@router.post("/{watermark_id}/image", response_model=WatermarkResponse)
async def upload_watermark_image(
    watermark_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)
):
    """Upload or update watermark image"""
    result = await db.execute(
        select(Watermark).where(Watermark.id == watermark_id)
    )
    watermark = result.scalar_one_or_none()
    if not watermark:
        raise HTTPException(status_code=404, detail="Watermark not found")

    # Validate file type
    allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    # Generate filename
    file_ext = Path(file.filename).suffix if file.filename else ".png"
    if not file_ext:
        file_ext = ".png"
    filename = f"watermark_{watermark_id}{file_ext}"
    file_path = WATERMARKS_DIR / filename

    # Delete old image if it exists
    if watermark.image:
        old_path = WATERMARKS_DIR / watermark.image
        if old_path.exists() and old_path != file_path:
            try:
                old_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete old watermark image: {e}")

    # Save new image
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Update watermark record
        watermark.image = filename
        watermark.original_content_type = file.content_type
        await db.commit()
        await db.refresh(watermark)

        logger.info(f"Uploaded watermark image: {file_path}")
        return watermark

    except Exception as e:
        logger.exception(f"Failed to save watermark image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e!s}")


@router.delete("/{watermark_id}/image", response_model=WatermarkResponse)
async def delete_watermark_image(watermark_id: int, db: AsyncSession = Depends(get_db)):
    """Delete watermark image"""
    result = await db.execute(
        select(Watermark).where(Watermark.id == watermark_id)
    )
    watermark = result.scalar_one_or_none()
    if not watermark:
        raise HTTPException(status_code=404, detail="Watermark not found")

    if not watermark.image:
        raise HTTPException(status_code=400, detail="Watermark has no image")

    # Delete image file
    image_path = WATERMARKS_DIR / watermark.image
    if image_path.exists():
        try:
            image_path.unlink()
            logger.info(f"Deleted watermark image: {image_path}")
        except Exception as e:
            logger.warning(f"Failed to delete watermark image {image_path}: {e}")

    # Update watermark record
    watermark.image = None
    watermark.original_content_type = None
    await db.commit()
    await db.refresh(watermark)

    return watermark
