"""Channel API endpoints - Async version with full CRUD support"""

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..api.schemas import ChannelCreate, ChannelResponse, ChannelUpdate
from ..cache.manager import get_cache
from ..database import get_db
from ..database.models import (
    Channel,
    ChannelPlaybackPosition,
    FFmpegProfile,
    MediaItem,
    Playout,
    PlayoutItem,
    PlayoutMode,
    ProgramSchedule,
    StreamingMode,
)
from ..streaming.plex_api_client import request_plex_guide_reload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["Channels"])


# Helper to convert model to response dict
def channel_to_response(channel: Channel) -> dict[str, Any]:
    """Convert Channel model to response dictionary."""
    return {
        "id": channel.id,
        "number": str(channel.number) if channel.number is not None else "",
        "name": channel.name,
        "group": channel.group,
        "enabled": channel.enabled,
        "logo_path": channel.logo_path,
        "logo_url": channel.logo_url,
        "playout_mode": channel.playout_mode,
        "streaming_mode": channel.streaming_mode,
        "transcode_profile": channel.transcode_profile,
        "is_yaml_source": channel.is_yaml_source,
        "ffmpeg_profile_id": channel.ffmpeg_profile_id,
        "watermark_id": channel.watermark_id,
        "transcode_mode": channel.transcode_mode,
        "subtitle_mode": channel.subtitle_mode,
        "preferred_audio_language_code": channel.preferred_audio_language_code,
        "preferred_audio_title": channel.preferred_audio_title,
        "preferred_subtitle_language_code": channel.preferred_subtitle_language_code,
        "stream_selector_mode": channel.stream_selector_mode,
        "stream_selector": channel.stream_selector,
        "music_video_credits_mode": channel.music_video_credits_mode,
        "music_video_credits_template": channel.music_video_credits_template,
        "song_video_mode": channel.song_video_mode,
        "idle_behavior": channel.idle_behavior,
        "playout_source": channel.playout_source,
        "mirror_source_channel_id": channel.mirror_source_channel_id,
        "playout_offset": channel.playout_offset,
        "show_in_epg": channel.show_in_epg,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at,
    }


@router.get("", response_model=list[ChannelResponse])
async def get_all_channels(
    db: AsyncSession = Depends(get_db), 
    include_content_status: bool = False
) -> list[dict[str, Any]]:
    """Get all channels.

    Args:
        db: Async database session
        include_content_status: If True, includes 'has_content' field indicating if channel has schedules

    Returns:
        list[ChannelResponse]: List of all channels
    """
    # Query channels with relationships
    stmt = select(Channel).options(
        selectinload(Channel.ffmpeg_profile),
        selectinload(Channel.watermark)
    ).order_by(Channel.number)
    
    result = await db.execute(stmt)
    channels = result.scalars().all()
    
    if include_content_status:
        # Get channel IDs that have schedules
        # Note: ProgramSchedule may not have channel_id directly, check playout relationship
        channel_ids_with_content: set[int] = set()
        
        # Build response with content status
        response = []
        for channel in channels:
            data = channel_to_response(channel)
            data["has_content"] = channel.id in channel_ids_with_content
            response.append(data)
        return response
    
    return [channel_to_response(channel) for channel in channels]


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(channel_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Get channel by ID"""
    stmt = select(Channel).where(Channel.id == channel_id).options(
        selectinload(Channel.ffmpeg_profile),
        selectinload(Channel.watermark)
    )
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel_to_response(channel)


@router.get("/number/{channel_number}", response_model=ChannelResponse)
async def get_channel_by_number(
    channel_number: str, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get channel by number"""
    stmt = select(Channel).where(Channel.number == channel_number).options(
        selectinload(Channel.ffmpeg_profile),
        selectinload(Channel.watermark)
    )
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    return channel_to_response(channel)


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel: ChannelCreate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new channel"""
    # Check if channel number already exists
    stmt = select(Channel).where(Channel.number == channel.number)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Channel number already exists")

    # Validate FFmpeg profile if provided
    if channel.ffmpeg_profile_id:
        stmt = select(FFmpegProfile).where(FFmpegProfile.id == channel.ffmpeg_profile_id)
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=400, detail="FFmpeg profile not found")

    # Validate mirror source channel if provided
    if channel.mirror_source_channel_id:
        stmt = select(Channel).where(Channel.id == channel.mirror_source_channel_id)
        result = await db.execute(stmt)
        mirror_channel = result.scalar_one_or_none()
        if not mirror_channel:
            raise HTTPException(status_code=400, detail="Mirror source channel not found")

    # Create channel from input data
    channel_data = channel.model_dump(exclude_unset=True)
    
    # Convert enum values to strings for storage
    if "playout_mode" in channel_data and hasattr(channel_data["playout_mode"], "value"):
        channel_data["playout_mode"] = channel_data["playout_mode"].value
    if "streaming_mode" in channel_data and hasattr(channel_data["streaming_mode"], "value"):
        channel_data["streaming_mode"] = channel_data["streaming_mode"].value
    
    # Handle other enum fields
    for field in ["transcode_mode", "subtitle_mode", "stream_selector_mode", 
                  "music_video_credits_mode", "song_video_mode", "idle_behavior", 
                  "playout_source"]:
        if field in channel_data and hasattr(channel_data[field], "value"):
            channel_data[field] = channel_data[field].value
    
    db_channel = Channel(**channel_data)
    db.add(db_channel)
    await db.commit()
    await db.refresh(db_channel)
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Created channel {db_channel.number}: {db_channel.name}")
    return channel_to_response(db_channel)


@router.put("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int, 
    channel_update: ChannelUpdate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a channel"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Reject writes for YAML-authoritative channels until export exists
    if getattr(channel, "is_yaml_source", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel is defined in YAML. Edit the YAML file and re-import.",
        )

    update_data = channel_update.model_dump(exclude_unset=True)

    # Validate FFmpeg profile if being updated
    if "ffmpeg_profile_id" in update_data and update_data["ffmpeg_profile_id"] is not None:
        stmt = select(FFmpegProfile).where(FFmpegProfile.id == update_data["ffmpeg_profile_id"])
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=400, detail="FFmpeg profile not found")

    # Validate mirror source channel if being updated
    if (
        "mirror_source_channel_id" in update_data
        and update_data["mirror_source_channel_id"] is not None
    ):
        stmt = select(Channel).where(Channel.id == update_data["mirror_source_channel_id"])
        result = await db.execute(stmt)
        mirror_channel = result.scalar_one_or_none()
        if not mirror_channel:
            raise HTTPException(status_code=400, detail="Mirror source channel not found")
        if update_data["mirror_source_channel_id"] == channel_id:
            raise HTTPException(status_code=400, detail="Channel cannot mirror itself")

    # Convert enum values to strings for storage
    for field in ["playout_mode", "streaming_mode", "transcode_mode", "subtitle_mode", 
                  "stream_selector_mode", "music_video_credits_mode", "song_video_mode", 
                  "idle_behavior", "playout_source"]:
        if field in update_data and hasattr(update_data[field], "value"):
            update_data[field] = update_data[field].value

    for field, value in update_data.items():
        setattr(channel, field, value)

    await db.commit()
    await db.refresh(channel)
    
    cache = await get_cache()
    await cache.invalidate_channel(channel_id)
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Updated channel {channel.number}: {channel.name}")
    return channel_to_response(channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(channel_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a channel"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Reject deletes for YAML-authoritative channels until export exists
    if getattr(channel, "is_yaml_source", False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel is defined in YAML. Edit the YAML file and re-import.",
        )

    await db.delete(channel)
    await db.commit()
    
    cache = await get_cache()
    await cache.invalidate_epg()
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Deleted channel {channel.number}: {channel.name}")


class PlaybackPositionUpdate(BaseModel):
    """Playback position update model"""
    item_index: int
    media_id: int | None = None


@router.post("/{channel_id}/playback-position")
async def save_playback_position(
    channel_id: int, 
    position: PlaybackPositionUpdate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Save playback position for an on-demand channel"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if channel.playout_mode != PlayoutMode.ON_DEMAND.value:
        raise HTTPException(
            status_code=400, detail="Position tracking only available for on-demand channels"
        )

    # Get or create playback position record
    stmt = select(ChannelPlaybackPosition).where(
        ChannelPlaybackPosition.channel_id == channel_id
    )
    result = await db.execute(stmt)
    playback_pos = result.scalar_one_or_none()

    if not playback_pos:
        playback_pos = ChannelPlaybackPosition(
            channel_id=channel_id, 
            channel_number=channel.number
        )
        db.add(playback_pos)

    playback_pos.last_item_index = position.item_index
    playback_pos.last_item_media_id = position.media_id
    playback_pos.last_played_at = datetime.utcnow()
    playback_pos.total_items_watched = position.item_index

    await db.commit()
    await db.refresh(playback_pos)

    return {
        "success": True,
        "channel_id": channel_id,
        "item_index": playback_pos.last_item_index,
        "media_id": playback_pos.last_item_media_id,
        "last_played_at": playback_pos.last_played_at.isoformat()
        if playback_pos.last_played_at
        else None,
    }


@router.get("/{channel_id}/playback-position")
async def get_playback_position(
    channel_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get saved playback position for an on-demand channel"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    stmt = select(ChannelPlaybackPosition).where(
        ChannelPlaybackPosition.channel_id == channel_id
    )
    result = await db.execute(stmt)
    playback_pos = result.scalar_one_or_none()

    if not playback_pos:
        return {
            "item_index": 0,
            "media_id": None,
            "last_played_at": None,
            "resume_available": False,
        }

    return {
        "item_index": playback_pos.last_item_index,
        "media_id": playback_pos.last_item_media_id,
        "last_played_at": playback_pos.last_played_at.isoformat()
        if playback_pos.last_played_at
        else None,
        "total_items_watched": playback_pos.total_items_watched,
        "resume_available": True,
    }


@router.delete("/{channel_id}/playback-position", status_code=status.HTTP_204_NO_CONTENT)
async def reset_playback_position(channel_id: int, db: AsyncSession = Depends(get_db)):
    """Reset playback position for an on-demand channel (start from beginning)"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    stmt = select(ChannelPlaybackPosition).where(
        ChannelPlaybackPosition.channel_id == channel_id
    )
    result = await db.execute(stmt)
    playback_pos = result.scalar_one_or_none()

    if playback_pos:
        await db.delete(playback_pos)
        await db.commit()


@router.post("/{channel_id}/icon", response_model=ChannelResponse)
async def upload_channel_icon(
    channel_id: int, 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Upload a PNG icon for a channel"""
    # Validate channel exists
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Validate file is PNG
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext != ".png":
        raise HTTPException(status_code=400, detail="Only PNG files are allowed")

    # Validate content type
    if file.content_type and file.content_type not in ["image/png", "image/x-png"]:
        raise HTTPException(status_code=400, detail="File must be a PNG image")

    # Determine icons directory (relative to project root)
    project_root = Path(__file__).parent.parent.parent
    icons_dir = project_root / "data" / "channel_icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename: channel_{channel_id}.png
    icon_filename = f"channel_{channel_id}.png"
    icon_path = icons_dir / icon_filename

    try:
        # Save the uploaded file
        with open(icon_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update channel logo_path to point to the static file
        logo_url = f"/static/channel_icons/{icon_filename}"
        channel.logo_path = logo_url
        await db.commit()
        await db.refresh(channel)

        logger.info(f"Uploaded icon for channel {channel_id} ({channel.name}): {icon_path}")
        return channel_to_response(channel)
        
    except Exception as e:
        logger.exception(f"Error uploading icon for channel {channel_id}: {e}")
        # Clean up file if it was partially written
        if icon_path.exists():
            icon_path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to upload icon: {e!s}")


@router.delete("/{channel_id}/icon", response_model=ChannelResponse)
async def delete_channel_icon(
    channel_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Delete the icon for a channel"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if not channel.logo_path or not channel.logo_path.startswith("/static/channel_icons/"):
        raise HTTPException(status_code=404, detail="Channel has no uploaded icon")

    # Determine icons directory
    project_root = Path(__file__).parent.parent.parent
    icons_dir = project_root / "data" / "channel_icons"
    icon_filename = f"channel_{channel_id}.png"
    icon_path = icons_dir / icon_filename

    # Delete the file if it exists
    if icon_path.exists():
        try:
            icon_path.unlink()
            logger.info(f"Deleted icon for channel {channel_id} ({channel.name}): {icon_path}")
        except Exception as e:
            logger.exception(f"Error deleting icon file for channel {channel_id}: {e}")

    # Clear logo_path in database
    channel.logo_path = None
    await db.commit()
    await db.refresh(channel)

    cache = await get_cache()
    await cache.invalidate_channel(channel_id)
    await request_plex_guide_reload(force=False)

    return channel_to_response(channel)


# Additional utility endpoints

@router.get("/{channel_id}/playouts")
async def get_channel_playouts(
    channel_id: int, 
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all playouts for a channel"""
    from ..database.models import Playout
    
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    stmt = select(Playout).where(Playout.channel_id == channel_id)
    result = await db.execute(stmt)
    playouts = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "channel_id": p.channel_id,
            "program_schedule_id": p.program_schedule_id,
            "template_id": p.template_id,
            "playout_type": p.playout_type,
            "is_active": p.is_active,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in playouts
    ]


@router.post("/{channel_id}/toggle-enabled", response_model=ChannelResponse)
async def toggle_channel_enabled(
    channel_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Toggle channel enabled state"""
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    channel.enabled = not channel.enabled
    await db.commit()
    await db.refresh(channel)
    
    logger.info(f"Channel {channel.number} enabled: {channel.enabled}")
    return channel_to_response(channel)


# ============================================================================
# Filler Configuration Endpoints
# ============================================================================


class FillerConfigUpdate(BaseModel):
    """Filler configuration update model"""
    fallback_filler_id: int | None = None
    pre_roll_filler_id: int | None = None
    post_roll_filler_id: int | None = None


@router.get("/{channel_id}/filler")
async def get_channel_filler_config(
    channel_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get filler configuration for a channel.
    
    Args:
        channel_id: Channel ID
        
    Returns:
        Filler configuration with preset details
    """
    from ..database.models.filler import FillerPreset
    
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    config = {
        "channel_id": channel_id,
        "fallback_filler_id": getattr(channel, 'fallback_filler_id', None),
        "pre_roll_filler_id": getattr(channel, 'pre_roll_filler_id', None),
        "post_roll_filler_id": getattr(channel, 'post_roll_filler_id', None),
        "fallback_filler": None,
        "pre_roll_filler": None,
        "post_roll_filler": None,
    }
    
    # Get filler preset details
    for field in ['fallback_filler_id', 'pre_roll_filler_id', 'post_roll_filler_id']:
        preset_id = getattr(channel, field, None)
        if preset_id:
            stmt = select(FillerPreset).where(FillerPreset.id == preset_id)
            result = await db.execute(stmt)
            preset = result.scalar_one_or_none()
            if preset:
                key = field.replace('_id', '')
                config[key] = {
                    "id": preset.id,
                    "name": preset.name,
                    "filler_mode": preset.filler_mode,
                }
    
    return config


@router.put("/{channel_id}/filler")
async def update_channel_filler_config(
    channel_id: int,
    config: FillerConfigUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update filler configuration for a channel.
    
    Args:
        channel_id: Channel ID
        config: Filler configuration to update
        
    Returns:
        Updated configuration
    """
    from ..database.models.filler import FillerPreset
    
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Validate filler presets exist
    for field in ['fallback_filler_id', 'pre_roll_filler_id', 'post_roll_filler_id']:
        preset_id = getattr(config, field, None)
        if preset_id and preset_id > 0:
            stmt = select(FillerPreset).where(FillerPreset.id == preset_id)
            result = await db.execute(stmt)
            preset = result.scalar_one_or_none()
            if not preset:
                raise HTTPException(status_code=400, detail=f"Filler preset {preset_id} not found")
            if hasattr(channel, field):
                setattr(channel, field, preset_id)
        elif preset_id == 0:
            if hasattr(channel, field):
                setattr(channel, field, None)
    
    await db.commit()
    await db.refresh(channel)
    
    cache = await get_cache()
    await cache.invalidate_channel(channel_id)
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Updated filler config for channel {channel_id}")
    return await get_channel_filler_config(channel_id, db)


# ============================================================================
# Deco Configuration Endpoints
# ============================================================================


class DecoConfigUpdate(BaseModel):
    """Deco configuration update model"""
    deco_group_id: int | None = None
    bumper_group_id: int | None = None


@router.get("/{channel_id}/deco")
async def get_channel_deco_config(
    channel_id: int,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get deco configuration for a channel.
    
    Args:
        channel_id: Channel ID
        
    Returns:
        Deco configuration with group details
    """
    from ..database.models.deco import DecoGroup
    
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    config = {
        "channel_id": channel_id,
        "deco_group_id": getattr(channel, 'deco_group_id', None),
        "bumper_group_id": getattr(channel, 'bumper_group_id', None),
        "deco_group": None,
        "bumper_group": None,
    }
    
    # Get deco group details
    for field in ['deco_group_id', 'bumper_group_id']:
        group_id = getattr(channel, field, None)
        if group_id:
            stmt = select(DecoGroup).where(DecoGroup.id == group_id)
            result = await db.execute(stmt)
            group = result.scalar_one_or_none()
            if group:
                key = field.replace('_id', '')
                config[key] = {
                    "id": group.id,
                    "name": group.name,
                }
    
    return config


@router.put("/{channel_id}/deco")
async def update_channel_deco_config(
    channel_id: int,
    config: DecoConfigUpdate,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update deco configuration for a channel.
    
    Args:
        channel_id: Channel ID
        config: Deco configuration to update
        
    Returns:
        Updated configuration
    """
    from ..database.models.deco import DecoGroup
    
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Validate deco groups exist
    for field in ['deco_group_id', 'bumper_group_id']:
        group_id = getattr(config, field, None)
        if group_id and group_id > 0:
            stmt = select(DecoGroup).where(DecoGroup.id == group_id)
            result = await db.execute(stmt)
            group = result.scalar_one_or_none()
            if not group:
                raise HTTPException(status_code=400, detail=f"Deco group {group_id} not found")
            if hasattr(channel, field):
                setattr(channel, field, group_id)
        elif group_id == 0:
            if hasattr(channel, field):
                setattr(channel, field, None)
    
    await db.commit()
    await db.refresh(channel)
    
    cache = await get_cache()
    await cache.invalidate_channel(channel_id)
    await request_plex_guide_reload(force=False)
    
    logger.info(f"Updated deco config for channel {channel_id}")
    return await get_channel_deco_config(channel_id, db)


# ============================================================================
# Programming Guide Endpoint
# ============================================================================


@router.get("/{channel_id}/programming")
async def get_channel_programming(
    channel_id: int,
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get programming guide for a channel.
    
    Args:
        channel_id: Channel ID
        hours: Number of hours to include (default 24)
        
    Returns:
        Programming guide with scheduled items
    """
    from datetime import datetime, timedelta
    from ..database.models.playout import Playout, PlayoutItem
    
    stmt = select(Channel).where(Channel.id == channel_id)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Get active playout for this channel
    stmt = select(Playout).where(
        Playout.channel_id == channel_id,
        Playout.is_active == True
    )
    result = await db.execute(stmt)
    playout = result.scalar_one_or_none()
    
    if not playout:
        return {
            "channel_id": channel_id,
            "channel_name": channel.name,
            "channel_number": channel.number,
            "programs": [],
            "message": "No active playout for this channel",
        }
    
    # Get playout items for the next N hours
    now = datetime.utcnow()
    end_time = now + timedelta(hours=hours)
    
    stmt = select(PlayoutItem).where(
        PlayoutItem.playout_id == playout.id,
        PlayoutItem.start_time >= now,
        PlayoutItem.start_time <= end_time
    ).order_by(PlayoutItem.start_time)
    
    result = await db.execute(stmt)
    items = result.scalars().all()
    
    programs = [
        {
            "id": item.id,
            "title": item.title,
            "episode_title": item.episode_title,
            "start_time": item.start_time.isoformat(),
            "finish_time": item.finish_time.isoformat(),
            "duration_seconds": (item.finish_time - item.start_time).total_seconds(),
            "filler_kind": item.filler_kind,
            "custom_title": item.custom_title,
        }
        for item in items
    ]
    
    return {
        "channel_id": channel_id,
        "channel_name": channel.name,
        "channel_number": channel.number,
        "playout_id": playout.id,
        "hours": hours,
        "program_count": len(programs),
        "programs": programs,
    }


@router.get("/{channel_number}/schedule")
async def get_channel_schedule(
    channel_number: str,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get schedule for a channel by number (supports decimal e.g. "1984.1").

    Returns programmes from TimelineBuilder for EPG consistency.
    """
    from ..api.timeline_builder import TimelineBuilder, PlaybackAnchor
    from ..api.title_resolver import TitleResolver
    from ..scheduling import ScheduleParser

    stmt = select(Channel).where(Channel.number == channel_number, Channel.enabled == True)
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    playback_pos = None
    stmt = select(ChannelPlaybackPosition).where(ChannelPlaybackPosition.channel_id == channel.id)
    result = await db.execute(stmt)
    playback_pos = result.scalar_one_or_none()

    playout_items: list[dict[str, Any]] = []
    schedule_file = ScheduleParser.find_schedule_file(channel_number)
    if schedule_file:
        from ..api.iptv import _run_schedule_engine_sync
        try:
            playout_items = await asyncio.to_thread(
                _run_schedule_engine_sync, channel.id, schedule_file
            )
        except Exception as e:
            logger.warning(f"Schedule file load failed: {e}")

    if not playout_items:
        stmt = select(Playout).where(
            Playout.channel_id == channel.id,
            Playout.is_active == True,
        )
        result = await db.execute(stmt)
        playout = result.scalar_one_or_none()
        if playout:
            items_stmt = select(PlayoutItem, MediaItem).outerjoin(
                MediaItem, PlayoutItem.media_item_id == MediaItem.id
            ).where(PlayoutItem.playout_id == playout.id).order_by(PlayoutItem.start_time)
            items_result = await db.execute(items_stmt)
            for pi, mi in items_result.all():
                if mi:
                    playout_items.append({
                        "media_item": mi,
                        "custom_title": pi.title or pi.custom_title,
                    })

    if not playout_items:
        return {
            "channel_id": channel.id,
            "channel_number": channel_number,
            "channel_name": channel.name,
            "programmes": [],
            "message": "No schedule items for this channel",
        }

    now = datetime.utcnow()
    anchor = PlaybackAnchor(
        playout_start_time=playback_pos.playout_start_time or now if playback_pos else now,
        last_item_index=playback_pos.last_item_index if playback_pos else 0,
        current_item_start_time=getattr(playback_pos, "current_item_start_time", None) if playback_pos else None,
        elapsed_seconds_in_item=getattr(playback_pos, "elapsed_seconds_in_item", 0) or 0 if playback_pos else 0,
    )
    builder = TimelineBuilder()
    programmes_raw = builder.build(playout_items, anchor, now=now, max_programmes=hours * 4)

    resolver = TitleResolver()
    programmes = []
    for p in programmes_raw:
        try:
            title = resolver.resolve_title(p.playout_item, p.media_item, channel)
        except Exception:
            title = p.title or "Unknown"
        programmes.append({
            "start": p.start_time.isoformat(),
            "stop": p.stop_time.isoformat(),
            "title": title,
        })

    return {
        "channel_id": channel.id,
        "channel_number": channel_number,
        "channel_name": channel.name,
        "programmes": programmes,
    }
