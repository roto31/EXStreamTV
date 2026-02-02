"""Playlists API endpoints - Async version"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..api.schemas import PlaylistCreate, PlaylistResponse
from ..database import get_db
from ..database.models import MediaItem, Playlist, PlaylistItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playlists", tags=["Playlists"])


def playlist_to_response(playlist: Playlist) -> dict[str, Any]:
    """Convert Playlist model to response dictionary."""
    items = []
    for item in getattr(playlist, "items", []) or []:
        item_data = {
            "id": item.id,
            "media_item_id": item.media_item_id,
            "order": item.order,
            "media_item": None,
        }
        if hasattr(item, "media_item") and item.media_item:
            item_data["media_item"] = {
                "id": item.media_item.id,
                "title": item.media_item.title,
                "source": item.media_item.source,
                "url": item.media_item.url,
            }
        items.append(item_data)
    
    return {
        "id": playlist.id,
        "name": playlist.name,
        "description": playlist.description,
        "channel_id": getattr(playlist, "channel_id", None),
        "created_at": playlist.created_at,
        "updated_at": playlist.updated_at,
        "items": items,
    }


@router.get("")
async def get_all_playlists(
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Get all playlists.

    Args:
        db: Database session

    Returns:
        list: List of all playlists
    """
    stmt = select(Playlist).options(
        selectinload(Playlist.items)
    ).order_by(Playlist.name)
    
    result = await db.execute(stmt)
    playlists = result.scalars().all()
    
    return [playlist_to_response(p) for p in playlists]


@router.get("/{playlist_id}")
async def get_playlist(
    playlist_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get playlist by ID.

    Args:
        playlist_id: Playlist ID
        db: Database session

    Returns:
        PlaylistResponse: Playlist details

    Raises:
        HTTPException: If playlist not found
    """
    stmt = select(Playlist).where(Playlist.id == playlist_id).options(
        selectinload(Playlist.items)
    )
    result = await db.execute(stmt)
    playlist = result.scalar_one_or_none()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return playlist_to_response(playlist)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_playlist(
    playlist: PlaylistCreate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a new playlist.

    Args:
        playlist: Playlist creation data
        db: Database session

    Returns:
        PlaylistResponse: Created playlist
    """
    db_playlist = Playlist(**playlist.model_dump())
    db.add(db_playlist)
    await db.commit()
    await db.refresh(db_playlist)
    
    logger.info(f"Created playlist: {db_playlist.name}")
    return playlist_to_response(db_playlist)


@router.put("/{playlist_id}")
async def update_playlist(
    playlist_id: int,
    name: str | None = None,
    description: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Update a playlist.
    
    Args:
        playlist_id: Playlist ID
        name: New name (optional)
        description: New description (optional)
        db: Database session
        
    Returns:
        Updated playlist
    """
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    result = await db.execute(stmt)
    playlist = result.scalar_one_or_none()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    if name is not None:
        playlist.name = name
    if description is not None:
        playlist.description = description
    
    await db.commit()
    await db.refresh(playlist)
    
    logger.info(f"Updated playlist: {playlist.name}")
    return playlist_to_response(playlist)


@router.post("/{playlist_id}/items/{media_id}", status_code=status.HTTP_201_CREATED)
async def add_item_to_playlist(
    playlist_id: int, 
    media_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Add media item to playlist.

    Args:
        playlist_id: Playlist ID
        media_id: Media item ID
        db: Database session

    Returns:
        dict[str, str]: Success message

    Raises:
        HTTPException: If playlist or media item not found
    """
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    result = await db.execute(stmt)
    playlist = result.scalar_one_or_none()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    stmt = select(MediaItem).where(MediaItem.id == media_id)
    result = await db.execute(stmt)
    media_item = result.scalar_one_or_none()
    
    if not media_item:
        raise HTTPException(status_code=404, detail="Media item not found")

    # Check if already in playlist
    stmt = select(PlaylistItem).where(
        PlaylistItem.playlist_id == playlist_id,
        PlaylistItem.media_item_id == media_id
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Item already in playlist")

    # Get max order
    stmt = select(func.count(PlaylistItem.id)).where(
        PlaylistItem.playlist_id == playlist_id
    )
    result = await db.execute(stmt)
    max_order = result.scalar() or 0

    playlist_item = PlaylistItem(
        playlist_id=playlist_id, 
        media_item_id=media_id, 
        order=max_order
    )
    db.add(playlist_item)
    await db.commit()
    
    logger.info(f"Added media {media_id} to playlist {playlist_id}")
    return {"message": "Item added to playlist"}


@router.delete("/{playlist_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item_from_playlist(
    playlist_id: int, 
    item_id: int, 
    db: AsyncSession = Depends(get_db)
) -> None:
    """Remove item from playlist.

    Args:
        playlist_id: Playlist ID
        item_id: Item ID to remove
        db: Database session

    Raises:
        HTTPException: If item not found in playlist
    """
    stmt = select(PlaylistItem).where(
        PlaylistItem.id == item_id,
        PlaylistItem.playlist_id == playlist_id
    )
    result = await db.execute(stmt)
    playlist_item = result.scalar_one_or_none()
    
    if not playlist_item:
        raise HTTPException(status_code=404, detail="Item not found in playlist")

    order = playlist_item.order
    
    await db.delete(playlist_item)
    
    # Reorder remaining items
    stmt = select(PlaylistItem).where(
        PlaylistItem.playlist_id == playlist_id,
        PlaylistItem.order > order
    )
    result = await db.execute(stmt)
    remaining = result.scalars().all()
    
    for item in remaining:
        item.order -= 1
    
    await db.commit()
    
    logger.info(f"Removed item {item_id} from playlist {playlist_id}")


@router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_playlist(
    playlist_id: int, 
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a playlist.

    Args:
        playlist_id: Playlist ID
        db: Database session

    Raises:
        HTTPException: If playlist not found
    """
    stmt = select(Playlist).where(Playlist.id == playlist_id)
    result = await db.execute(stmt)
    playlist = result.scalar_one_or_none()
    
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    await db.delete(playlist)
    await db.commit()
    
    logger.info(f"Deleted playlist: {playlist_id}")


@router.post("/{playlist_id}/items/{item_id}/move")
async def move_playlist_item(
    playlist_id: int,
    item_id: int,
    direction: str,
    db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Move a playlist item up or down.
    
    Args:
        playlist_id: Playlist ID
        item_id: Item ID to move
        direction: 'up' or 'down'
        db: Database session
        
    Returns:
        Success message
    """
    stmt = select(PlaylistItem).where(
        PlaylistItem.id == item_id,
        PlaylistItem.playlist_id == playlist_id
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in playlist")
    
    if direction == "up":
        if item.order == 0:
            raise HTTPException(status_code=400, detail="Item is already at the top")
        
        stmt = select(PlaylistItem).where(
            PlaylistItem.playlist_id == playlist_id,
            PlaylistItem.order == item.order - 1
        )
        result = await db.execute(stmt)
        other_item = result.scalar_one_or_none()
        
        if other_item:
            other_item.order = item.order
            item.order -= 1
            
    elif direction == "down":
        stmt = select(func.max(PlaylistItem.order)).where(
            PlaylistItem.playlist_id == playlist_id
        )
        result = await db.execute(stmt)
        max_order = result.scalar() or 0
        
        if item.order >= max_order:
            raise HTTPException(status_code=400, detail="Item is already at the bottom")
        
        stmt = select(PlaylistItem).where(
            PlaylistItem.playlist_id == playlist_id,
            PlaylistItem.order == item.order + 1
        )
        result = await db.execute(stmt)
        other_item = result.scalar_one_or_none()
        
        if other_item:
            other_item.order = item.order
            item.order += 1
    else:
        raise HTTPException(status_code=400, detail="Direction must be 'up' or 'down'")
    
    await db.commit()
    
    return {"message": f"Item moved {direction}"}
