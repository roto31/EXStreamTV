"""
Media Sources API Endpoints

API for managing Plex, Jellyfin, Emby, and local media sources.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.database import get_db, PlexLibrary, JellyfinLibrary, EmbyLibrary, LocalLibrary, MediaItem
from exstreamtv.media_sources import PlexMediaSource, JellyfinMediaSource, EmbyMediaSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media-sources", tags=["Media Sources"])

# ============================================================================
# Request/Response Models
# ============================================================================

class MediaSourceBase(BaseModel):
    """Base model for media source configuration."""
    name: str = Field(..., description="Display name for the source")
    server_url: str = Field(..., description="Server URL")

class PlexSourceConfig(MediaSourceBase):
    """Plex media source configuration."""
    token: str = Field(..., description="Plex authentication token")

class JellyfinSourceConfig(MediaSourceBase):
    """Jellyfin media source configuration."""
    api_key: str = Field(..., description="Jellyfin API key")
    user_id: str | None = Field(None, description="User ID (optional)")

class EmbySourceConfig(MediaSourceBase):
    """Emby media source configuration."""
    api_key: str = Field(..., description="Emby API key")
    user_id: str | None = Field(None, description="User ID (optional)")

class LibrarySelection(BaseModel):
    """Library selection for scanning."""
    library_ids: list[str] = Field(..., description="Library IDs to scan")

class ConnectionTestRequest(BaseModel):
    """Request to test a media source connection."""
    source_type: str = Field(..., description="Source type: plex, jellyfin, emby")
    server_url: str = Field(..., description="Server URL")
    token: str | None = Field(None, description="Auth token (Plex)")
    api_key: str | None = Field(None, description="API key (Jellyfin/Emby)")

class ConnectionTestResponse(BaseModel):
    """Response from connection test."""
    success: bool
    message: str
    server_name: str | None = None
    server_version: str | None = None
    libraries: list[dict[str, Any]] = []

class MediaSourceResponse(BaseModel):
    """Response model for media source."""
    id: int
    name: str
    source_type: str
    server_url: str
    is_enabled: bool
    last_scan: datetime | None = None
    item_count: int = 0
    library_count: int = 0

class ScanResultResponse(BaseModel):
    """Response from library scan."""
    success: bool
    message: str
    items_found: int = 0
    items_imported: int = 0

# ============================================================================
# Connection Testing
# ============================================================================

@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_media_source_connection(
    request: ConnectionTestRequest,
) -> ConnectionTestResponse:
    """Test connection to a media source.
    
    Tests connectivity and authentication before saving the source.
    """
    source_type = request.source_type.lower()
    
    try:
        if source_type == "plex":
            if not request.token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plex token is required",
                )
            source = PlexMediaSource(
                name="Test",
                server_url=request.server_url,
                token=request.token,
            )
        elif source_type == "jellyfin":
            if not request.api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Jellyfin API key is required",
                )
            source = JellyfinMediaSource(
                name="Test",
                server_url=request.server_url,
                api_key=request.api_key,
            )
        elif source_type == "emby":
            if not request.api_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Emby API key is required",
                )
            source = EmbyMediaSource(
                name="Test",
                server_url=request.server_url,
                api_key=request.api_key,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown source type: {source_type}",
            )
        
        # Test connection
        success, message = await source.test_connection()
        
        if success:
            # Get libraries
            libraries = await source.get_libraries()
            library_data = [
                {
                    "id": lib.id,
                    "name": lib.name,
                    "type": lib.type,
                }
                for lib in libraries
            ]
            
            source_dict = source.to_dict()
            return ConnectionTestResponse(
                success=True,
                message=message,
                server_name=source_dict.get("server_name"),
                server_version=source_dict.get("server_version"),
                libraries=library_data,
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message=message,
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Connection test failed: {e}")
        return ConnectionTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )

# ============================================================================
# Plex Sources
# ============================================================================

@router.get("/plex", response_model=list[MediaSourceResponse])
async def list_plex_sources(
    db: AsyncSession = Depends(get_db),
) -> list[MediaSourceResponse]:
    """List all configured Plex sources."""
    result = await db.execute(select(PlexLibrary))
    libraries = result.scalars().all()
    
    # Group by server
    servers: dict[str, dict] = {}
    for lib in libraries:
        key = lib.server_url
        if key not in servers:
            servers[key] = {
                "id": lib.id,
                "name": lib.name.split(" - ")[0] if " - " in lib.name else lib.name,
                "source_type": "plex",
                "server_url": lib.server_url,
                "is_enabled": True,
                "last_scan": lib.last_scan,
                "item_count": 0,
                "library_count": 0,
            }
        servers[key]["item_count"] += lib.item_count
        servers[key]["library_count"] += 1
        if lib.last_scan and (not servers[key]["last_scan"] or lib.last_scan > servers[key]["last_scan"]):
            servers[key]["last_scan"] = lib.last_scan
    
    return [MediaSourceResponse(**s) for s in servers.values()]

@router.get("/plex/libraries")
async def list_plex_libraries(
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List all individual Plex libraries (for filtering)."""
    result = await db.execute(select(PlexLibrary).order_by(PlexLibrary.name))
    libraries = result.scalars().all()
    
    return [
        {
            "id": lib.id,
            "name": lib.name,
            "plex_library_key": lib.plex_library_key,
            "plex_library_name": lib.plex_library_name,
            "library_type": lib.library_type,
            "item_count": lib.item_count,
            "last_scan": lib.last_scan,
            "is_enabled": lib.is_enabled,
        }
        for lib in libraries
    ]

@router.post("/plex", response_model=MediaSourceResponse)
async def add_plex_source(
    config: PlexSourceConfig,
    db: AsyncSession = Depends(get_db),
) -> MediaSourceResponse:
    """Add a new Plex media source and scan its libraries."""
    # Test connection first
    source = PlexMediaSource(
        name=config.name,
        server_url=config.server_url,
        token=config.token,
    )
    
    success, message = await source.test_connection()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection failed: {message}",
        )
    
    # Get libraries
    libraries = await source.get_libraries()
    
    # Save each library to database
    total_items = 0
    for lib in libraries:
        plex_lib = PlexLibrary(
            name=f"{config.name} - {lib.name}",
            server_url=config.server_url,
            token=config.token,
            plex_library_key=lib.id,
            plex_library_name=lib.name,
            library_type=lib.type,
            is_enabled=True,
            item_count=lib.item_count,
        )
        db.add(plex_lib)
    
    await db.commit()
    
    return MediaSourceResponse(
        id=1,  # Will be actual ID after commit
        name=config.name,
        source_type="plex",
        server_url=config.server_url,
        is_enabled=True,
        item_count=total_items,
        library_count=len(libraries),
    )

@router.post("/plex/{source_id}/scan", response_model=ScanResultResponse)
async def scan_plex_source(
    source_id: int,
    libraries: LibrarySelection | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScanResultResponse:
    """Scan a Plex source and import media items."""
    # Get the Plex library configuration
    result = await db.execute(
        select(PlexLibrary).where(PlexLibrary.id == source_id)
    )
    plex_lib = result.scalar_one_or_none()
    
    if not plex_lib:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plex source not found",
        )
    
    # Create source client
    source = PlexMediaSource(
        name=plex_lib.name,
        server_url=plex_lib.server_url,
        token=plex_lib.token,
    )
    
    if not await source.connect():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Plex: {source.error_message}",
        )
    
    # Determine which libraries to scan
    # If specific library IDs provided, use those; otherwise scan just this library
    if libraries and libraries.library_ids:
        lib_ids = libraries.library_ids
    else:
        # Use the specific library's plex_library_key, not all server libraries
        lib_ids = [plex_lib.plex_library_key]
    
    # Scan libraries
    items_found = 0
    items_imported = 0
    
    for lib_id in lib_ids:
        items = await source.scan_library(lib_id)
        items_found += len(items)
        
        # Import items to database
        for item in items:
            # Check if item already exists
            existing = await db.execute(
                select(MediaItem).where(
                    MediaItem.source == "plex",
                    MediaItem.external_id == item.id,
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            # Create new media item
            media_item = MediaItem(
                title=item.title,
                media_type=item.type,
                duration=item.duration_ms // 1000 if item.duration_ms else 0,
                source="plex",
                source_id=item.id,
                external_id=item.id,
                url=item.file_path,
                year=item.year,
                description=item.summary,
                thumbnail=item.thumbnail_url,
                show_title=item.show_title,
                season_number=item.season_number,
                episode_number=item.episode_number,
                library_id=plex_lib.id,  # Track which library this came from
                library_source="plex",
            )
            db.add(media_item)
            items_imported += 1
    
    # Update last scan time and item count
    plex_lib.last_scan = datetime.now()
    plex_lib.item_count = items_found
    await db.commit()
    
    lib_name = plex_lib.plex_library_name or plex_lib.name
    return ScanResultResponse(
        success=True,
        message=f"Scanned library: {lib_name}",
        items_found=items_found,
        items_imported=items_imported,
    )

# ============================================================================
# Jellyfin Sources
# ============================================================================

@router.get("/jellyfin", response_model=list[MediaSourceResponse])
async def list_jellyfin_sources(
    db: AsyncSession = Depends(get_db),
) -> list[MediaSourceResponse]:
    """List all configured Jellyfin sources."""
    result = await db.execute(select(JellyfinLibrary))
    libraries = result.scalars().all()
    
    servers: dict[str, dict] = {}
    for lib in libraries:
        key = lib.server_url
        if key not in servers:
            servers[key] = {
                "id": lib.id,
                "name": lib.name.split(" - ")[0] if " - " in lib.name else lib.name,
                "source_type": "jellyfin",
                "server_url": lib.server_url,
                "is_enabled": True,
                "last_scan": lib.last_scan,
                "item_count": 0,
                "library_count": 0,
            }
        servers[key]["item_count"] += lib.item_count
        servers[key]["library_count"] += 1
    
    return [MediaSourceResponse(**s) for s in servers.values()]

@router.post("/jellyfin", response_model=MediaSourceResponse)
async def add_jellyfin_source(
    config: JellyfinSourceConfig,
    db: AsyncSession = Depends(get_db),
) -> MediaSourceResponse:
    """Add a new Jellyfin media source."""
    source = JellyfinMediaSource(
        name=config.name,
        server_url=config.server_url,
        api_key=config.api_key,
        user_id=config.user_id,
    )
    
    success, message = await source.test_connection()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection failed: {message}",
        )
    
    libraries = await source.get_libraries()
    
    for lib in libraries:
        jf_lib = JellyfinLibrary(
            name=f"{config.name} - {lib.name}",
            server_url=config.server_url,
            api_key=config.api_key,
            jellyfin_library_id=lib.id,
            jellyfin_library_name=lib.name,
            library_type=lib.type,
            is_enabled=True,
        )
        db.add(jf_lib)
    
    await db.commit()
    
    return MediaSourceResponse(
        id=1,
        name=config.name,
        source_type="jellyfin",
        server_url=config.server_url,
        is_enabled=True,
        library_count=len(libraries),
    )

@router.post("/jellyfin/{source_id}/scan", response_model=ScanResultResponse)
async def scan_jellyfin_source(
    source_id: int,
    libraries: LibrarySelection | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScanResultResponse:
    """Scan a Jellyfin source and import media items."""
    result = await db.execute(
        select(JellyfinLibrary).where(JellyfinLibrary.id == source_id)
    )
    jf_lib = result.scalar_one_or_none()
    
    if not jf_lib:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Jellyfin source not found",
        )
    
    source = JellyfinMediaSource(
        name=jf_lib.name,
        server_url=jf_lib.server_url,
        api_key=jf_lib.api_key,
    )
    
    if not await source.connect():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Jellyfin: {source.error_message}",
        )
    
    if libraries and libraries.library_ids:
        lib_ids = libraries.library_ids
    else:
        all_libs = await source.get_libraries()
        lib_ids = [lib.id for lib in all_libs]
    
    items_found = 0
    items_imported = 0
    
    for lib_id in lib_ids:
        items = await source.scan_library(lib_id)
        items_found += len(items)
        
        for item in items:
            existing = await db.execute(
                select(MediaItem).where(
                    MediaItem.source == "jellyfin",
                    MediaItem.external_id == item.id,
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            media_item = MediaItem(
                title=item.title,
                media_type=item.type,
                duration=item.duration_ms // 1000 if item.duration_ms else 0,
                source="jellyfin",
                source_id=item.id,
                external_id=item.id,
                url=item.file_path,
                year=item.year,
                description=item.summary,
                thumbnail=item.thumbnail_url,
                show_title=item.show_title,
                season_number=item.season_number,
                episode_number=item.episode_number,
            )
            db.add(media_item)
            items_imported += 1
    
    jf_lib.last_scan = datetime.now()
    jf_lib.item_count = items_found
    await db.commit()
    
    return ScanResultResponse(
        success=True,
        message=f"Scanned {len(lib_ids)} libraries",
        items_found=items_found,
        items_imported=items_imported,
    )

# ============================================================================
# Emby Sources
# ============================================================================

@router.get("/emby", response_model=list[MediaSourceResponse])
async def list_emby_sources(
    db: AsyncSession = Depends(get_db),
) -> list[MediaSourceResponse]:
    """List all configured Emby sources."""
    result = await db.execute(select(EmbyLibrary))
    libraries = result.scalars().all()
    
    servers: dict[str, dict] = {}
    for lib in libraries:
        key = lib.server_url
        if key not in servers:
            servers[key] = {
                "id": lib.id,
                "name": lib.name.split(" - ")[0] if " - " in lib.name else lib.name,
                "source_type": "emby",
                "server_url": lib.server_url,
                "is_enabled": True,
                "last_scan": lib.last_scan,
                "item_count": 0,
                "library_count": 0,
            }
        servers[key]["item_count"] += lib.item_count
        servers[key]["library_count"] += 1
    
    return [MediaSourceResponse(**s) for s in servers.values()]

@router.post("/emby", response_model=MediaSourceResponse)
async def add_emby_source(
    config: EmbySourceConfig,
    db: AsyncSession = Depends(get_db),
) -> MediaSourceResponse:
    """Add a new Emby media source."""
    source = EmbyMediaSource(
        name=config.name,
        server_url=config.server_url,
        api_key=config.api_key,
        user_id=config.user_id,
    )
    
    success, message = await source.test_connection()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Connection failed: {message}",
        )
    
    libraries = await source.get_libraries()
    
    for lib in libraries:
        emby_lib = EmbyLibrary(
            name=f"{config.name} - {lib.name}",
            server_url=config.server_url,
            api_key=config.api_key,
            emby_library_id=lib.id,
            emby_library_name=lib.name,
            library_type=lib.type,
            is_enabled=True,
        )
        db.add(emby_lib)
    
    await db.commit()
    
    return MediaSourceResponse(
        id=1,
        name=config.name,
        source_type="emby",
        server_url=config.server_url,
        is_enabled=True,
        library_count=len(libraries),
    )

@router.post("/emby/{source_id}/scan", response_model=ScanResultResponse)
async def scan_emby_source(
    source_id: int,
    libraries: LibrarySelection | None = None,
    db: AsyncSession = Depends(get_db),
) -> ScanResultResponse:
    """Scan an Emby source and import media items."""
    result = await db.execute(
        select(EmbyLibrary).where(EmbyLibrary.id == source_id)
    )
    emby_lib = result.scalar_one_or_none()
    
    if not emby_lib:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Emby source not found",
        )
    
    source = EmbyMediaSource(
        name=emby_lib.name,
        server_url=emby_lib.server_url,
        api_key=emby_lib.api_key,
    )
    
    if not await source.connect():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to Emby: {source.error_message}",
        )
    
    if libraries and libraries.library_ids:
        lib_ids = libraries.library_ids
    else:
        all_libs = await source.get_libraries()
        lib_ids = [lib.id for lib in all_libs]
    
    items_found = 0
    items_imported = 0
    
    for lib_id in lib_ids:
        items = await source.scan_library(lib_id)
        items_found += len(items)
        
        for item in items:
            existing = await db.execute(
                select(MediaItem).where(
                    MediaItem.source == "emby",
                    MediaItem.external_id == item.id,
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            media_item = MediaItem(
                title=item.title,
                media_type=item.type,
                duration=item.duration_ms // 1000 if item.duration_ms else 0,
                source="emby",
                source_id=item.id,
                external_id=item.id,
                url=item.file_path,
                year=item.year,
                description=item.summary,
                thumbnail=item.thumbnail_url,
                show_title=item.show_title,
                season_number=item.season_number,
                episode_number=item.episode_number,
            )
            db.add(media_item)
            items_imported += 1
    
    emby_lib.last_scan = datetime.now()
    emby_lib.item_count = items_found
    await db.commit()
    
    return ScanResultResponse(
        success=True,
        message=f"Scanned {len(lib_ids)} libraries",
        items_found=items_found,
        items_imported=items_imported,
    )

# ============================================================================
# Summary / All Sources
# ============================================================================

@router.get("/summary")
async def get_media_sources_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a summary of all configured media sources."""
    plex_result = await db.execute(select(PlexLibrary))
    plex_libs = plex_result.scalars().all()
    
    jellyfin_result = await db.execute(select(JellyfinLibrary))
    jellyfin_libs = jellyfin_result.scalars().all()
    
    emby_result = await db.execute(select(EmbyLibrary))
    emby_libs = emby_result.scalars().all()
    
    local_result = await db.execute(select(LocalLibrary))
    local_libs = local_result.scalars().all()
    
    return {
        "plex": {
            "count": len(set(lib.server_url for lib in plex_libs)),
            "library_count": len(plex_libs),
            "total_items": sum(lib.item_count for lib in plex_libs),
        },
        "jellyfin": {
            "count": len(set(lib.server_url for lib in jellyfin_libs)),
            "library_count": len(jellyfin_libs),
            "total_items": sum(lib.item_count for lib in jellyfin_libs),
        },
        "emby": {
            "count": len(set(lib.server_url for lib in emby_libs)),
            "library_count": len(emby_libs),
            "total_items": sum(lib.item_count for lib in emby_libs),
        },
        "local": {
            "count": len(local_libs),
            "total_items": sum(lib.item_count for lib in local_libs),
        },
    }
