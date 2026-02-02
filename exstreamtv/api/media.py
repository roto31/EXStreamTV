"""Media API endpoints - Async version"""

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import MediaItemCreate, MediaItemResponse
from ..config import get_config
from ..database import get_db
from ..database.models import MediaItem, StreamSource

logger = logging.getLogger(__name__)

class PlexRatingKeyRequest(BaseModel):
    rating_key: str

class PaginatedMediaResponse(BaseModel):
    """Paginated response for media items."""
    items: list[dict[str, Any]]
    total: int
    skip: int
    limit: int
    has_more: bool

router = APIRouter(prefix="/media", tags=["Media"])

def media_to_response(media: MediaItem) -> dict[str, Any]:
    """Convert MediaItem model to response dictionary."""
    return {
        "id": media.id,
        "source": media.source if isinstance(media.source, str) else (media.source.value if hasattr(media.source, "value") else str(media.source)),
        "source_id": media.source_id,
        "external_id": getattr(media, "external_id", None),
        "library_id": getattr(media, "library_id", None),
        "url": media.url,
        "title": media.title,
        "description": media.description,
        "duration": media.duration,
        "thumbnail": media.thumbnail,
        "poster_path": getattr(media, "poster_path", None),
        "art_url": getattr(media, "art_url", None),
        "uploader": getattr(media, "uploader", None),
        "upload_date": getattr(media, "upload_date", None),
        "view_count": getattr(media, "view_count", None),
        "meta_data": getattr(media, "meta_data", None),
        "created_at": media.created_at,
        "updated_at": media.updated_at,
        # Metadata fields for filtering
        "media_type": getattr(media, "media_type", None),
        "year": getattr(media, "year", None),
        "content_rating": getattr(media, "content_rating", None),
        "genres": getattr(media, "genres", None),
        "studio": getattr(media, "studio", None),
        # TV show fields
        "show_title": getattr(media, "show_title", None),
        "season_number": getattr(media, "season_number", None),
        "episode_number": getattr(media, "episode_number", None),
        # Additional metadata
        "added_date": getattr(media, "added_date", None),
        "originally_available": getattr(media, "originally_available", None),
        "rating": getattr(media, "rating", None),
    }

@router.get("/count")
async def get_media_count(
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get total count of media items.

    Args:
        source: Optional source filter
        db: Database session

    Returns:
        dict: Total count and breakdown by source
    """
    # Total count
    stmt = select(func.count(MediaItem.id))
    if source:
        stmt = stmt.where(MediaItem.source == source)
    result = await db.execute(stmt)
    total = result.scalar() or 0
    
    # Count by source
    sources_stmt = select(
        MediaItem.source,
        func.count(MediaItem.id).label("count")
    ).group_by(MediaItem.source)
    sources_result = await db.execute(sources_stmt)
    by_source = {str(row[0]): row[1] for row in sources_result.all()}
    
    return {
        "total": total,
        "by_source": by_source,
    }

@router.get("")
async def get_all_media(
    source: str | None = None,
    library_id: int | None = None,
    media_type: str | None = None,
    year: int | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    duration_min: int | None = None,
    duration_max: int | None = None,
    content_rating: str | None = None,
    genre: str | None = None,
    search: str | None = None,
    sort_by: str = "title",
    sort_order: str = "asc",
    skip: int = 0,
    limit: int = 100,
    paginated: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]] | PaginatedMediaResponse:
    """Get all media items with filtering.

    Supports comprehensive filtering compatible with Plex API patterns.
    Reference: https://developer.plex.tv/pms/

    Args:
        source: Source filter (plex, youtube, archive_org, jellyfin, emby, local)
        library_id: Library ID filter (for media server items)
        media_type: Type filter (movie, episode, track, other_video)
        year: Exact year filter
        year_min: Minimum year (inclusive)
        year_max: Maximum year (inclusive)
        duration_min: Minimum duration in seconds
        duration_max: Maximum duration in seconds
        content_rating: Content rating filter (TV-MA, PG-13, etc.)
        genre: Genre filter (partial match)
        search: Search term for title/description
        sort_by: Sort field (title, year, duration, created_at)
        sort_order: Sort order (asc, desc)
        skip: Number of items to skip
        limit: Maximum number of items to return (max 1000)
        paginated: If true, return paginated response with total count
        db: Database session

    Returns:
        list or PaginatedMediaResponse: List of media items
    """
    from sqlalchemy import desc, asc, or_
    
    # Cap limit at 1000 for performance
    limit = min(limit, 1000)
    
    # Build base query with filters
    base_stmt = select(MediaItem)
    conditions = []
    
    # Source filter
    if source:
        conditions.append(MediaItem.source == source)
    
    # Library filter
    if library_id:
        conditions.append(MediaItem.library_id == library_id)
    
    # Media type filter
    if media_type:
        conditions.append(MediaItem.media_type == media_type)
    
    # Year filters
    if year:
        conditions.append(MediaItem.year == year)
    if year_min:
        conditions.append(MediaItem.year >= year_min)
    if year_max:
        conditions.append(MediaItem.year <= year_max)
    
    # Duration filters (in seconds)
    if duration_min:
        conditions.append(MediaItem.duration >= duration_min)
    if duration_max:
        conditions.append(MediaItem.duration <= duration_max)
    
    # Content rating filter
    if content_rating:
        conditions.append(MediaItem.content_rating == content_rating)
    
    # Genre filter (partial match in JSON array)
    if genre:
        conditions.append(MediaItem.genres.ilike(f"%{genre}%"))
    
    # Search filter
    if search:
        search_term = f"%{search}%"
        conditions.append(or_(
            MediaItem.title.ilike(search_term),
            MediaItem.description.ilike(search_term),
            MediaItem.show_title.ilike(search_term),
        ))
    
    # Apply all conditions
    if conditions:
        base_stmt = base_stmt.where(*conditions)
    
    # Sorting with proper NULL handling
    from sqlalchemy import nullslast, nullsfirst
    
    sort_column = {
        "title": MediaItem.title,
        "year": MediaItem.year,
        "duration": MediaItem.duration,
        "created_at": MediaItem.created_at,
        "added_date": MediaItem.added_date,
    }.get(sort_by, MediaItem.title)
    
    # Put NULLs at the end regardless of sort direction
    if sort_order == "desc":
        base_stmt = base_stmt.order_by(nullslast(desc(sort_column)))
    else:
        base_stmt = base_stmt.order_by(nullslast(asc(sort_column)))
    
    # Get total count if paginated
    total = 0
    if paginated:
        count_stmt = select(func.count(MediaItem.id))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
        count_result = await db.execute(count_stmt)
        total = count_result.scalar() or 0
    
    # Get items
    stmt = base_stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    media_items = result.scalars().all()
    
    items = [media_to_response(m) for m in media_items]
    
    if paginated:
        return PaginatedMediaResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            has_more=(skip + len(items)) < total,
        )
    
    return items

@router.get("/filters")
async def get_available_filters(
    source: str | None = None,
    library_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get available filter options based on current media.
    
    Returns distinct values for filtering dropdowns.
    Similar to Plex API filter endpoints.
    
    Args:
        source: Optional source filter
        library_id: Optional library filter
        db: Database session
        
    Returns:
        Dictionary of available filter options
    """
    from sqlalchemy import distinct
    
    conditions = []
    if source:
        conditions.append(MediaItem.source == source)
    if library_id:
        conditions.append(MediaItem.library_id == library_id)
    
    # Get distinct years
    years_stmt = select(distinct(MediaItem.year)).where(
        MediaItem.year.isnot(None)
    )
    if conditions:
        years_stmt = years_stmt.where(*conditions)
    years_result = await db.execute(years_stmt.order_by(MediaItem.year.desc()))
    years = [y[0] for y in years_result.all() if y[0]]
    
    # Get distinct media types
    types_stmt = select(distinct(MediaItem.media_type))
    if conditions:
        types_stmt = types_stmt.where(*conditions)
    types_result = await db.execute(types_stmt)
    types = [t[0] for t in types_result.all() if t[0]]
    
    # Get distinct content ratings
    ratings_stmt = select(distinct(MediaItem.content_rating)).where(
        MediaItem.content_rating.isnot(None)
    )
    if conditions:
        ratings_stmt = ratings_stmt.where(*conditions)
    ratings_result = await db.execute(ratings_stmt)
    ratings = [r[0] for r in ratings_result.all() if r[0]]
    
    # Get distinct sources
    sources_stmt = select(distinct(MediaItem.source))
    sources_result = await db.execute(sources_stmt)
    sources = [s[0] for s in sources_result.all() if s[0]]
    
    # Duration ranges (predefined buckets)
    duration_ranges = [
        {"label": "Under 5 min", "min": 0, "max": 300},
        {"label": "5-15 min", "min": 300, "max": 900},
        {"label": "15-30 min", "min": 900, "max": 1800},
        {"label": "30-60 min", "min": 1800, "max": 3600},
        {"label": "1-2 hours", "min": 3600, "max": 7200},
        {"label": "Over 2 hours", "min": 7200, "max": None},
    ]
    
    # Year ranges (decades)
    year_ranges = []
    if years:
        min_year = min(years)
        max_year = max(years)
        decade_start = (min_year // 10) * 10
        while decade_start <= max_year:
            year_ranges.append({
                "label": f"{decade_start}s",
                "min": decade_start,
                "max": decade_start + 9,
            })
            decade_start += 10
    
    return {
        "years": years[:50],  # Limit for performance
        "year_ranges": year_ranges,
        "media_types": types,
        "content_ratings": sorted(ratings),
        "sources": sources,
        "duration_ranges": duration_ranges,
    }

@router.get("/shows")
async def get_tv_shows(
    library_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get TV shows grouped with episode counts.
    
    Groups episodes by show_title and returns show-level data.
    
    Args:
        library_id: Optional library ID filter
        skip: Number of shows to skip
        limit: Maximum shows to return
        db: Database session
        
    Returns:
        List of shows with episode counts and metadata
    """
    from sqlalchemy import distinct
    
    # Get distinct shows with episode counts
    base_query = select(
        MediaItem.show_title,
        func.count(MediaItem.id).label("episode_count"),
        func.min(MediaItem.thumbnail).label("thumbnail"),
        func.min(MediaItem.year).label("year"),
        func.min(MediaItem.library_id).label("library_id"),
        func.sum(MediaItem.duration).label("total_duration"),
    ).where(
        MediaItem.media_type == "episode",
        MediaItem.show_title.isnot(None),
    ).group_by(MediaItem.show_title)
    
    if library_id:
        base_query = base_query.where(MediaItem.library_id == library_id)
    
    # Get total count
    count_query = select(func.count(distinct(MediaItem.show_title))).where(
        MediaItem.media_type == "episode",
        MediaItem.show_title.isnot(None),
    )
    if library_id:
        count_query = count_query.where(MediaItem.library_id == library_id)
    
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get shows with pagination
    query = base_query.order_by(MediaItem.show_title).offset(skip).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    shows = []
    for row in rows:
        shows.append({
            "show_title": row.show_title,
            "episode_count": row.episode_count,
            "thumbnail": row.thumbnail,
            "year": row.year,
            "library_id": row.library_id,
            "total_duration": row.total_duration,
        })
    
    return {
        "shows": shows,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": (skip + len(shows)) < total,
    }

@router.get("/shows/{show_title}/episodes")
async def get_show_episodes(
    show_title: str,
    library_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get all episodes for a specific TV show, grouped by season.
    
    Args:
        show_title: The show title to get episodes for
        library_id: Optional library ID filter
        db: Database session
        
    Returns:
        Show info with seasons and episodes
    """
    # URL decode the show title
    from urllib.parse import unquote
    show_title = unquote(show_title)
    
    # Get all episodes for this show
    stmt = select(MediaItem).where(
        MediaItem.media_type == "episode",
        MediaItem.show_title == show_title,
    ).order_by(MediaItem.season_number, MediaItem.episode_number)
    
    if library_id:
        stmt = stmt.where(MediaItem.library_id == library_id)
    
    result = await db.execute(stmt)
    episodes = result.scalars().all()
    
    if not episodes:
        return {"show_title": show_title, "seasons": [], "episode_count": 0}
    
    # Group by season
    seasons: dict[int, list] = {}
    show_thumbnail = None
    show_year = None
    
    for ep in episodes:
        season_num = ep.season_number or 0
        if season_num not in seasons:
            seasons[season_num] = []
        
        seasons[season_num].append({
            "id": ep.id,
            "title": ep.title,
            "episode_number": ep.episode_number,
            "season_number": season_num,
            "duration": ep.duration,
            "thumbnail": ep.thumbnail,
            "description": ep.description,
            "year": ep.year,
        })
        
        # Get show-level data from first episode
        if not show_thumbnail and ep.thumbnail:
            show_thumbnail = ep.thumbnail
        if not show_year and ep.year:
            show_year = ep.year
    
    # Convert to list format
    seasons_list = [
        {
            "season_number": num,
            "episode_count": len(eps),
            "episodes": eps,
        }
        for num, eps in sorted(seasons.items())
    ]
    
    return {
        "show_title": show_title,
        "thumbnail": show_thumbnail,
        "year": show_year,
        "episode_count": len(episodes),
        "season_count": len(seasons),
        "seasons": seasons_list,
    }

@router.get("/search")
async def search_media(
    q: str,
    source: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
) -> list[dict[str, Any]]:
    """Search media items by title.
    
    Args:
        q: Search query
        source: Optional source filter
        limit: Maximum results
        db: Database session
        
    Returns:
        List of matching media items
    """
    stmt = select(MediaItem).where(
        MediaItem.title.ilike(f"%{q}%")
    )
    
    if source:
        stmt = stmt.where(MediaItem.source == source)
    
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    media_items = result.scalars().all()
    
    return [media_to_response(m) for m in media_items]

@router.get("/{media_id}")
async def get_media(
    media_id: int, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Get media item by ID.

    Args:
        media_id: Media item ID
        db: Database session

    Returns:
        MediaItemResponse: Media item details

    Raises:
        HTTPException: If media item not found
    """
    stmt = select(MediaItem).where(MediaItem.id == media_id)
    result = await db.execute(stmt)
    media_item = result.scalar_one_or_none()
    
    if not media_item:
        raise HTTPException(status_code=404, detail="Media item not found")
    
    return media_to_response(media_item)

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_media(
    media: MediaItemCreate, 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Add a new media item from URL.

    Args:
        media: Media item creation data
        db: Database session

    Returns:
        MediaItemResponse: Created media item

    Raises:
        HTTPException: If source is unsupported or creation fails
    """
    # Check if URL already exists
    stmt = select(MediaItem).where(MediaItem.url == media.url)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        return media_to_response(existing)

    try:
        # Detect source from URL
        source = StreamSource.LOCAL.value  # Default
        url_lower = media.url.lower()
        
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            source = StreamSource.YOUTUBE.value
        elif "archive.org" in url_lower:
            source = StreamSource.ARCHIVE_ORG.value
        elif "plex://" in url_lower:
            source = StreamSource.PLEX.value
        
        # Extract source ID
        source_id = media.url
        
        # Create media item
        db_media = MediaItem(
            source=source,
            source_id=source_id,
            url=media.url,
            title=media.title,
            description=media.description,
            duration=media.duration,
            thumbnail=media.thumbnail,
        )

        db.add(db_media)
        await db.commit()
        await db.refresh(db_media)
        
        logger.info(f"Created media item: {db_media.title}")
        return media_to_response(db_media)
        
    except Exception as e:
        logger.exception(f"Error adding media: {e}")
        raise HTTPException(status_code=400, detail=f"Error adding media: {e!s}")

@router.post("/plex/from-rating-key", status_code=status.HTTP_201_CREATED)
async def create_media_from_plex_rating_key(
    request: PlexRatingKeyRequest = Body(...), 
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """Create a MediaItem from a Plex rating key.

    Args:
        request: Plex rating key request
        db: Database session

    Returns:
        MediaItemResponse: Created media item

    Raises:
        HTTPException: If Plex not configured or media not found
    """
    config = get_config()
    rating_key = request.rating_key

    if not config.plex.enabled or not config.plex.base_url:
        raise HTTPException(status_code=400, detail="Plex not configured")

    # Check if MediaItem already exists for this rating key
    stmt = select(MediaItem).where(
        MediaItem.source == StreamSource.PLEX.value,
        MediaItem.source_id == rating_key
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        return media_to_response(existing)

    try:
        # Create Plex URL
        plex_base = config.plex.base_url.replace('http://', '').replace('https://', '')
        plex_url = f"plex://{plex_base}/library/metadata/{rating_key}"

        # Create media item
        db_media = MediaItem(
            source=StreamSource.PLEX.value,
            source_id=rating_key,
            url=plex_url,
            title=f"Plex Media {rating_key}",
            description="",
            duration=None,
            thumbnail=None,
        )

        db.add(db_media)
        await db.commit()
        await db.refresh(db_media)
        
        logger.info(f"Created Plex media item: {rating_key}")
        return media_to_response(db_media)
        
    except Exception as e:
        logger.exception(f"Error creating media from Plex: {e}")
        raise HTTPException(status_code=400, detail=f"Error creating media from Plex: {e!s}")

@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    media_id: int, 
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a media item.

    Args:
        media_id: Media item ID
        db: Database session

    Raises:
        HTTPException: If media item not found
    """
    stmt = select(MediaItem).where(MediaItem.id == media_id)
    result = await db.execute(stmt)
    media_item = result.scalar_one_or_none()
    
    if not media_item:
        raise HTTPException(status_code=404, detail="Media item not found")

    await db.delete(media_item)
    await db.commit()
    
    logger.info(f"Deleted media item: {media_id}")
