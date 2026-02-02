"""FFmpeg Profile API endpoints - Async version"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import (
    FFmpegProfileCreate,
    FFmpegProfileResponse,
    FFmpegProfileUpdate,
    HardwareAccelerationResponse,
)
from ..database import get_db
from ..database.models import Channel, FFmpegProfile, Resolution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ffmpeg-profiles", tags=["FFmpeg Profiles"])


def profile_to_response(profile: FFmpegProfile) -> dict[str, Any]:
    """Convert FFmpegProfile model to response dictionary."""
    return {
        "id": profile.id,
        "name": profile.name,
        "resolution_id": profile.resolution_id,
        "thread_count": profile.thread_count,
        "hardware_acceleration": profile.hardware_acceleration,
        "video_codec": profile.video_codec,
        "video_bitrate": profile.video_bitrate,
        "video_buffer_size": profile.video_buffer_size,
        "framerate": profile.framerate,
        "quality_preset": profile.quality_preset,
        "quality_crf": profile.quality_crf,
        "audio_codec": profile.audio_codec,
        "audio_bitrate": profile.audio_bitrate,
        "audio_channels": profile.audio_channels,
        "audio_sample_rate": profile.audio_sample_rate,
        "normalize_audio": profile.normalize_audio,
        "audio_loudness_target": profile.audio_loudness_target,
        "deinterlace": profile.deinterlace,
        "scaling_mode": profile.scaling_mode,
        "pad_color": profile.pad_color,
        "is_default": profile.is_default,
        "is_enabled": profile.is_enabled,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.get("")
async def get_all_ffmpeg_profiles(
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all FFmpeg profiles.

    Args:
        db: Database session

    Returns:
        list: List of all FFmpeg profiles
    """
    stmt = select(FFmpegProfile).order_by(FFmpegProfile.name)
    result = await db.execute(stmt)
    profiles = result.scalars().all()
    
    return [profile_to_response(p) for p in profiles]


@router.get("/{profile_id}")
async def get_ffmpeg_profile(
    profile_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get FFmpeg profile by ID.

    Args:
        profile_id: FFmpeg profile ID
        db: Database session

    Returns:
        FFmpegProfileResponse: FFmpeg profile details

    Raises:
        HTTPException: If profile not found
    """
    stmt = select(FFmpegProfile).where(FFmpegProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="FFmpeg profile not found")
    
    return profile_to_response(profile)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_ffmpeg_profile(
    profile: FFmpegProfileCreate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new FFmpeg profile.

    Args:
        profile: FFmpeg profile creation data
        db: Database session

    Returns:
        FFmpegProfileResponse: Created FFmpeg profile

    Raises:
        HTTPException: If profile name already exists or resolution not found
    """
    # Check if profile with same name exists
    stmt = select(FFmpegProfile).where(FFmpegProfile.name == profile.name)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="FFmpeg profile with this name already exists")

    # Verify resolution exists
    stmt = select(Resolution).where(Resolution.id == profile.resolution_id)
    result = await db.execute(stmt)
    resolution = result.scalar_one_or_none()
    
    if not resolution:
        raise HTTPException(status_code=400, detail="Resolution not found")

    profile_data = profile.model_dump()
    
    # Convert enum values to strings
    for field in ["hardware_acceleration", "video_format", "audio_format", 
                  "bit_depth", "scaling_behavior", "tonemap_algorithm", 
                  "normalize_loudness_mode"]:
        if field in profile_data and hasattr(profile_data[field], "value"):
            profile_data[field] = profile_data[field].value
    
    db_profile = FFmpegProfile(**profile_data)
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    
    logger.info(f"Created FFmpeg profile: {db_profile.name}")
    return profile_to_response(db_profile)


@router.put("/{profile_id}")
async def update_ffmpeg_profile(
    profile_id: int, 
    profile_update: FFmpegProfileUpdate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update an FFmpeg profile.

    Args:
        profile_id: FFmpeg profile ID
        profile_update: FFmpeg profile update data
        db: Database session

    Returns:
        FFmpegProfileResponse: Updated FFmpeg profile

    Raises:
        HTTPException: If profile not found, name conflicts, or resolution not found
    """
    stmt = select(FFmpegProfile).where(FFmpegProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="FFmpeg profile not found")

    update_data = profile_update.model_dump(exclude_unset=True)

    # Check if name is being changed and conflicts with another profile
    if "name" in update_data and update_data["name"] != profile.name:
        stmt = select(FFmpegProfile).where(FFmpegProfile.name == update_data["name"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=400, detail="FFmpeg profile with this name already exists"
            )

    # Verify resolution if being changed
    if "resolution_id" in update_data and update_data["resolution_id"] != profile.resolution_id:
        stmt = select(Resolution).where(Resolution.id == update_data["resolution_id"])
        result = await db.execute(stmt)
        resolution = result.scalar_one_or_none()
        if not resolution:
            raise HTTPException(status_code=400, detail="Resolution not found")

    # Convert enum values to strings
    for field in ["hardware_acceleration", "video_format", "audio_format", 
                  "bit_depth", "scaling_behavior", "tonemap_algorithm", 
                  "normalize_loudness_mode"]:
        if field in update_data and hasattr(update_data[field], "value"):
            update_data[field] = update_data[field].value

    # Update fields
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    
    logger.info(f"Updated FFmpeg profile: {profile.name}")
    return profile_to_response(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ffmpeg_profile(
    profile_id: int, 
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete an FFmpeg profile.

    Args:
        profile_id: FFmpeg profile ID
        db: Database session

    Raises:
        HTTPException: If profile not found or is in use by channels
    """
    stmt = select(FFmpegProfile).where(FFmpegProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="FFmpeg profile not found")

    # Check if profile is used by any channels
    from sqlalchemy import func
    stmt = select(func.count(Channel.id)).where(Channel.ffmpeg_profile_id == profile_id)
    result = await db.execute(stmt)
    channels_using = result.scalar() or 0
    
    if channels_using > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete FFmpeg profile: it is used by {channels_using} channel(s)",
        )

    await db.delete(profile)
    await db.commit()
    
    logger.info(f"Deleted FFmpeg profile: {profile.name}")


@router.get("/hardware-acceleration/available", response_model=HardwareAccelerationResponse)
async def get_available_hardware_acceleration_types() -> HardwareAccelerationResponse:
    """Get list of available hardware acceleration types.

    Returns:
        HardwareAccelerationResponse: Available hardware acceleration types
    """
    try:
        from ..transcoding.hardware import get_available_hardware_acceleration
        available = get_available_hardware_acceleration()
    except ImportError:
        # Fallback if hardware module not available
        available = ["none", "auto"]
    
    return HardwareAccelerationResponse(available=available)


@router.post("/{profile_id}/set-default")
async def set_default_profile(
    profile_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Set a profile as the default.
    
    Args:
        profile_id: FFmpeg profile ID to set as default
        db: Database session
        
    Returns:
        Updated profile
    """
    stmt = select(FFmpegProfile).where(FFmpegProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="FFmpeg profile not found")
    
    # Clear default from all other profiles
    stmt = select(FFmpegProfile).where(FFmpegProfile.is_default == True)
    result = await db.execute(stmt)
    current_defaults = result.scalars().all()
    
    for p in current_defaults:
        p.is_default = False
    
    # Set this profile as default
    profile.is_default = True
    
    await db.commit()
    await db.refresh(profile)
    
    logger.info(f"Set FFmpeg profile '{profile.name}' as default")
    return profile_to_response(profile)
