"""
Library API endpoints.

Manages local and remote media libraries.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from exstreamtv.database.connection import get_db, get_sync_session
from exstreamtv.database.models.library import (
    EmbyLibrary,
    JellyfinLibrary,
    LocalLibrary,
    PlexLibrary,
)
from exstreamtv.media.libraries import (
    LibraryManager,
    LibraryType,
)
from exstreamtv.media.libraries.local import LocalLibrary as LocalLibraryImpl
from exstreamtv.media.libraries.plex import PlexLibrary as PlexLibraryImpl
from exstreamtv.media.libraries.jellyfin import (
    JellyfinLibrary as JellyfinLibraryImpl,
    EmbyLibrary as EmbyLibraryImpl,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/libraries", tags=["Libraries"])

# Global library manager instance
_library_manager = LibraryManager()

# Track active scans
_active_scans: Dict[int, Dict[str, Any]] = {}


# ============ Schemas ============


class LibraryTypeEnum(str, Enum):
    """Library type enumeration."""

    LOCAL = "local"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"


class LibraryStatus(str, Enum):
    """Library status."""

    IDLE = "idle"
    SCANNING = "scanning"
    ERROR = "error"
    DISABLED = "disabled"


class LocalLibraryCreate(BaseModel):
    """Create local library request."""

    name: str = Field(..., min_length=1, max_length=255)
    path: str = Field(..., min_length=1)
    library_type: str = Field(default="other")  # "movie", "show", "music", "other"
    recursive: bool = Field(default=True)
    file_extensions: str = Field(
        default=".mp4,.mkv,.avi,.mov,.wmv,.flv,.webm,.m4v,.ts,.m2ts"
    )
    scan_interval_hours: int = Field(default=1, ge=0)


class PlexLibraryCreate(BaseModel):
    """Create Plex library request."""

    name: str = Field(..., min_length=1, max_length=255)
    server_url: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1)
    plex_library_key: str = Field(..., min_length=1)
    plex_library_name: str = Field(default="")
    library_type: str = Field(default="movie")
    scan_interval_hours: int = Field(default=1, ge=0)


class JellyfinLibraryCreate(BaseModel):
    """Create Jellyfin library request."""

    name: str = Field(..., min_length=1, max_length=255)
    server_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    jellyfin_library_id: str = Field(..., min_length=1)
    jellyfin_library_name: str = Field(default="")
    library_type: str = Field(default="movie")
    scan_interval_hours: int = Field(default=1, ge=0)


class EmbyLibraryCreate(BaseModel):
    """Create Emby library request."""

    name: str = Field(..., min_length=1, max_length=255)
    server_url: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    emby_library_id: str = Field(..., min_length=1)
    emby_library_name: str = Field(default="")
    library_type: str = Field(default="movie")
    scan_interval_hours: int = Field(default=1, ge=0)


class LibraryResponse(BaseModel):
    """Library response."""

    id: int
    name: str
    library_type: str
    source_type: str  # "local", "plex", "jellyfin", "emby"
    is_enabled: bool
    last_scan: Optional[datetime] = None
    item_count: int
    status: LibraryStatus = LibraryStatus.IDLE
    path: Optional[str] = None  # For local libraries
    server_url: Optional[str] = None  # For remote libraries

    class Config:
        from_attributes = True


class LibraryStats(BaseModel):
    """Library statistics."""

    total_items: int = 0
    movies: int = 0
    shows: int = 0
    episodes: int = 0
    total_duration_hours: float = 0.0
    last_scanned: Optional[datetime] = None


class ScanProgress(BaseModel):
    """Scan progress information."""

    library_id: int
    status: str
    total_files: int = 0
    scanned_files: int = 0
    new_items: int = 0
    errors: int = 0
    current_file: Optional[str] = None
    percent_complete: float = 0.0
    started_at: Optional[datetime] = None


class DiscoveredLibrary(BaseModel):
    """Discovered library from remote server."""

    key: str
    name: str
    type: str
    agent: Optional[str] = None


# ============ Helper Functions ============


def _get_library_status(library_id: int) -> LibraryStatus:
    """Get current status of a library."""
    if library_id in _active_scans:
        return LibraryStatus.SCANNING
    return LibraryStatus.IDLE


async def _run_library_scan(library_id: int, library_type: str) -> None:
    """Run a library scan in the background."""
    db = None
    try:
        _active_scans[library_id] = {
            "status": "running",
            "started_at": datetime.now(),
            "total_files": 0,
            "scanned_files": 0,
            "new_items": 0,
            "errors": 0,
        }

        # Use a sync session for background task
        db = get_sync_session()

        # Get library from database
        if library_type == "local":
            db_lib = db.query(LocalLibrary).filter(LocalLibrary.id == library_id).first()
            if db_lib:
                library = LocalLibraryImpl(
                    library_id=db_lib.id,
                    name=db_lib.name,
                    path=db_lib.path,
                )

                def progress_callback(progress):
                    _active_scans[library_id].update({
                        "total_files": progress.total_files,
                        "scanned_files": progress.scanned_files,
                        "new_items": progress.new_items,
                        "errors": progress.errors,
                        "current_file": progress.current_file,
                    })

                library._scanner.add_progress_callback(progress_callback)

                await library.connect()
                items = await library.sync()
                await library.disconnect()

                # Update database
                db_lib.item_count = len(items)
                db_lib.last_scan = datetime.utcnow()
                db.commit()

        elif library_type == "plex":
            db_lib = db.query(PlexLibrary).filter(PlexLibrary.id == library_id).first()
            if db_lib:
                library = PlexLibraryImpl(
                    library_id=db_lib.id,
                    name=db_lib.name,
                    server_url=db_lib.server_url,
                    token=db_lib.token,
                    plex_library_key=db_lib.plex_library_key,
                    plex_library_name=db_lib.plex_library_name,
                )

                await library.connect()
                items = await library.sync()
                await library.disconnect()

                db_lib.item_count = len(items)
                db_lib.last_scan = datetime.utcnow()
                db.commit()

        elif library_type == "jellyfin":
            db_lib = db.query(JellyfinLibrary).filter(JellyfinLibrary.id == library_id).first()
            if db_lib:
                library = JellyfinLibraryImpl(
                    library_id=db_lib.id,
                    name=db_lib.name,
                    server_url=db_lib.server_url,
                    api_key=db_lib.api_key,
                    jellyfin_library_id=db_lib.jellyfin_library_id,
                    jellyfin_library_name=db_lib.jellyfin_library_name,
                )

                await library.connect()
                items = await library.sync()
                await library.disconnect()

                db_lib.item_count = len(items)
                db_lib.last_scan = datetime.utcnow()
                db.commit()

        elif library_type == "emby":
            db_lib = db.query(EmbyLibrary).filter(EmbyLibrary.id == library_id).first()
            if db_lib:
                library = EmbyLibraryImpl(
                    library_id=db_lib.id,
                    name=db_lib.name,
                    server_url=db_lib.server_url,
                    api_key=db_lib.api_key,
                    emby_library_id=db_lib.emby_library_id,
                    emby_library_name=db_lib.emby_library_name,
                )

                await library.connect()
                items = await library.sync()
                await library.disconnect()

                db_lib.item_count = len(items)
                db_lib.last_scan = datetime.utcnow()
                db.commit()

        _active_scans[library_id]["status"] = "completed"

    except Exception as e:
        logger.exception(f"Library scan failed: {e}")
        _active_scans[library_id]["status"] = "failed"
        _active_scans[library_id]["error"] = str(e)

    finally:
        # Close database session
        if db:
            db.close()
        # Clean up after a delay
        await asyncio.sleep(60)
        if library_id in _active_scans:
            del _active_scans[library_id]


# ============ Local Library Endpoints ============


@router.get("/local", response_model=List[LibraryResponse])
async def list_local_libraries(db: AsyncSession = Depends(get_db)) -> List[LibraryResponse]:
    """List all local libraries."""
    result = await db.execute(select(LocalLibrary))
    libraries = result.scalars().all()

    return [
        LibraryResponse(
            id=lib.id,
            name=lib.name,
            library_type=lib.library_type,
            source_type="local",
            is_enabled=lib.is_enabled,
            last_scan=lib.last_scan,
            item_count=lib.item_count,
            status=_get_library_status(lib.id),
            path=lib.path,
        )
        for lib in libraries
    ]


@router.post("/local", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_local_library(
    library: LocalLibraryCreate,
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    """Create a new local library."""
    db_library = LocalLibrary(
        name=library.name,
        path=library.path,
        library_type=library.library_type,
        recursive=library.recursive,
        file_extensions=library.file_extensions,
        scan_interval_hours=library.scan_interval_hours,
        is_enabled=True,
        item_count=0,
    )

    db.add(db_library)
    await db.commit()
    await db.refresh(db_library)

    return LibraryResponse(
        id=db_library.id,
        name=db_library.name,
        library_type=db_library.library_type,
        source_type="local",
        is_enabled=db_library.is_enabled,
        last_scan=db_library.last_scan,
        item_count=db_library.item_count,
        status=LibraryStatus.IDLE,
        path=db_library.path,
    )


@router.delete("/local/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_local_library(library_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a local library."""
    result = await db.execute(select(LocalLibrary).where(LocalLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    await db.delete(library)
    await db.commit()


@router.post("/local/{library_id}/scan", response_model=ScanProgress)
async def scan_local_library(
    library_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ScanProgress:
    """Trigger a scan of a local library."""
    result = await db.execute(select(LocalLibrary).where(LocalLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    if library_id in _active_scans:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    background_tasks.add_task(_run_library_scan, library_id, "local")

    return ScanProgress(
        library_id=library_id,
        status="started",
        started_at=datetime.now(),
    )


# ============ Plex Library Endpoints ============


@router.get("/plex", response_model=List[LibraryResponse])
async def list_plex_libraries(db: AsyncSession = Depends(get_db)) -> List[LibraryResponse]:
    """List all Plex libraries."""
    result = await db.execute(select(PlexLibrary))
    libraries = result.scalars().all()

    return [
        LibraryResponse(
            id=lib.id,
            name=lib.name,
            library_type=lib.library_type,
            source_type="plex",
            is_enabled=lib.is_enabled,
            last_scan=lib.last_scan,
            item_count=lib.item_count,
            status=_get_library_status(lib.id),
            server_url=lib.server_url,
        )
        for lib in libraries
    ]


@router.post("/plex", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_plex_library(
    library: PlexLibraryCreate,
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    """Create a new Plex library connection."""
    db_library = PlexLibrary(
        name=library.name,
        server_url=library.server_url,
        token=library.token,
        plex_library_key=library.plex_library_key,
        plex_library_name=library.plex_library_name,
        library_type=library.library_type,
        scan_interval_hours=library.scan_interval_hours,
        is_enabled=True,
        item_count=0,
    )

    db.add(db_library)
    await db.commit()
    await db.refresh(db_library)

    return LibraryResponse(
        id=db_library.id,
        name=db_library.name,
        library_type=db_library.library_type,
        source_type="plex",
        is_enabled=db_library.is_enabled,
        last_scan=db_library.last_scan,
        item_count=db_library.item_count,
        status=LibraryStatus.IDLE,
        server_url=db_library.server_url,
    )


@router.delete("/plex/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plex_library(library_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a Plex library."""
    result = await db.execute(select(PlexLibrary).where(PlexLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    await db.delete(library)
    await db.commit()


@router.post("/plex/{library_id}/scan", response_model=ScanProgress)
async def scan_plex_library(
    library_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ScanProgress:
    """Trigger a sync of a Plex library."""
    library = db.query(PlexLibrary).filter(PlexLibrary.id == library_id).first()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    if library_id in _active_scans:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    background_tasks.add_task(_run_library_scan, library_id, "plex")

    return ScanProgress(
        library_id=library_id,
        status="started",
        started_at=datetime.now(),
    )


@router.post("/plex/discover", response_model=List[DiscoveredLibrary])
async def discover_plex_libraries(
    server_url: str = Query(...),
    token: str = Query(...),
) -> List[DiscoveredLibrary]:
    """Discover available libraries on a Plex server."""
    libraries = await PlexLibraryImpl.discover_libraries(server_url, token)

    return [
        DiscoveredLibrary(
            key=lib.get("key", ""),
            name=lib.get("title", ""),
            type=lib.get("type", ""),
            agent=lib.get("agent"),
        )
        for lib in libraries
    ]


# ============ Jellyfin Library Endpoints ============


@router.get("/jellyfin", response_model=List[LibraryResponse])
async def list_jellyfin_libraries(db: AsyncSession = Depends(get_db)) -> List[LibraryResponse]:
    """List all Jellyfin libraries."""
    result = await db.execute(select(JellyfinLibrary))
    libraries = result.scalars().all()

    return [
        LibraryResponse(
            id=lib.id,
            name=lib.name,
            library_type=lib.library_type,
            source_type="jellyfin",
            is_enabled=lib.is_enabled,
            last_scan=lib.last_scan,
            item_count=lib.item_count,
            status=_get_library_status(lib.id),
            server_url=lib.server_url,
        )
        for lib in libraries
    ]


@router.post("/jellyfin", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_jellyfin_library(
    library: JellyfinLibraryCreate,
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    """Create a new Jellyfin library connection."""
    db_library = JellyfinLibrary(
        name=library.name,
        server_url=library.server_url,
        api_key=library.api_key,
        jellyfin_library_id=library.jellyfin_library_id,
        jellyfin_library_name=library.jellyfin_library_name,
        library_type=library.library_type,
        scan_interval_hours=library.scan_interval_hours,
        is_enabled=True,
        item_count=0,
    )

    db.add(db_library)
    await db.commit()
    await db.refresh(db_library)

    return LibraryResponse(
        id=db_library.id,
        name=db_library.name,
        library_type=db_library.library_type,
        source_type="jellyfin",
        is_enabled=db_library.is_enabled,
        last_scan=db_library.last_scan,
        item_count=db_library.item_count,
        status=LibraryStatus.IDLE,
        server_url=db_library.server_url,
    )


@router.delete("/jellyfin/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jellyfin_library(library_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a Jellyfin library."""
    result = await db.execute(select(JellyfinLibrary).where(JellyfinLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    await db.delete(library)
    await db.commit()


@router.post("/jellyfin/{library_id}/scan", response_model=ScanProgress)
async def scan_jellyfin_library(
    library_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ScanProgress:
    """Trigger a sync of a Jellyfin library."""
    result = await db.execute(select(JellyfinLibrary).where(JellyfinLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    if library_id in _active_scans:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    background_tasks.add_task(_run_library_scan, library_id, "jellyfin")

    return ScanProgress(
        library_id=library_id,
        status="started",
        started_at=datetime.now(),
    )


@router.post("/jellyfin/discover", response_model=List[DiscoveredLibrary])
async def discover_jellyfin_libraries(
    server_url: str = Query(...),
    api_key: str = Query(...),
) -> List[DiscoveredLibrary]:
    """Discover available libraries on a Jellyfin server."""
    libraries = await JellyfinLibraryImpl.discover_libraries(server_url, api_key)

    return [
        DiscoveredLibrary(
            key=lib.get("id", ""),
            name=lib.get("name", ""),
            type=lib.get("type", ""),
        )
        for lib in libraries
    ]


# ============ Emby Library Endpoints ============


@router.get("/emby", response_model=List[LibraryResponse])
async def list_emby_libraries(db: AsyncSession = Depends(get_db)) -> List[LibraryResponse]:
    """List all Emby libraries."""
    result = await db.execute(select(EmbyLibrary))
    libraries = result.scalars().all()

    return [
        LibraryResponse(
            id=lib.id,
            name=lib.name,
            library_type=lib.library_type,
            source_type="emby",
            is_enabled=lib.is_enabled,
            last_scan=lib.last_scan,
            item_count=lib.item_count,
            status=_get_library_status(lib.id),
            server_url=lib.server_url,
        )
        for lib in libraries
    ]


@router.post("/emby", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_emby_library(
    library: EmbyLibraryCreate,
    db: AsyncSession = Depends(get_db),
) -> LibraryResponse:
    """Create a new Emby library connection."""
    db_library = EmbyLibrary(
        name=library.name,
        server_url=library.server_url,
        api_key=library.api_key,
        emby_library_id=library.emby_library_id,
        emby_library_name=library.emby_library_name,
        library_type=library.library_type,
        scan_interval_hours=library.scan_interval_hours,
        is_enabled=True,
        item_count=0,
    )

    db.add(db_library)
    await db.commit()
    await db.refresh(db_library)

    return LibraryResponse(
        id=db_library.id,
        name=db_library.name,
        library_type=db_library.library_type,
        source_type="emby",
        is_enabled=db_library.is_enabled,
        last_scan=db_library.last_scan,
        item_count=db_library.item_count,
        status=LibraryStatus.IDLE,
        server_url=db_library.server_url,
    )


@router.delete("/emby/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_emby_library(library_id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete an Emby library."""
    result = await db.execute(select(EmbyLibrary).where(EmbyLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    await db.delete(library)
    await db.commit()


@router.post("/emby/{library_id}/scan", response_model=ScanProgress)
async def scan_emby_library(
    library_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ScanProgress:
    """Trigger a sync of an Emby library."""
    result = await db.execute(select(EmbyLibrary).where(EmbyLibrary.id == library_id))
    library = result.scalar_one_or_none()
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    if library_id in _active_scans:
        raise HTTPException(status_code=409, detail="Scan already in progress")

    background_tasks.add_task(_run_library_scan, library_id, "emby")

    return ScanProgress(
        library_id=library_id,
        status="started",
        started_at=datetime.now(),
    )


# ============ Aggregate Endpoints ============


@router.get("", response_model=List[LibraryResponse])
async def list_all_libraries(db: AsyncSession = Depends(get_db)) -> List[LibraryResponse]:
    """List all libraries of all types."""
    libraries = []

    # Local libraries
    result = await db.execute(select(LocalLibrary))
    for lib in result.scalars().all():
        libraries.append(
            LibraryResponse(
                id=lib.id,
                name=lib.name,
                library_type=lib.library_type,
                source_type="local",
                is_enabled=lib.is_enabled,
                last_scan=lib.last_scan,
                item_count=lib.item_count,
                status=_get_library_status(lib.id),
                path=lib.path,
            )
        )

    # Plex libraries
    result = await db.execute(select(PlexLibrary))
    for lib in result.scalars().all():
        libraries.append(
            LibraryResponse(
                id=lib.id,
                name=lib.name,
                library_type=lib.library_type,
                source_type="plex",
                is_enabled=lib.is_enabled,
                last_scan=lib.last_scan,
                item_count=lib.item_count,
                status=_get_library_status(lib.id),
                server_url=lib.server_url,
            )
        )

    # Jellyfin libraries
    result = await db.execute(select(JellyfinLibrary))
    for lib in result.scalars().all():
        libraries.append(
            LibraryResponse(
                id=lib.id,
                name=lib.name,
                library_type=lib.library_type,
                source_type="jellyfin",
                is_enabled=lib.is_enabled,
                last_scan=lib.last_scan,
                item_count=lib.item_count,
                status=_get_library_status(lib.id),
                server_url=lib.server_url,
            )
        )

    # Emby libraries
    result = await db.execute(select(EmbyLibrary))
    for lib in result.scalars().all():
        libraries.append(
            LibraryResponse(
                id=lib.id,
                name=lib.name,
                library_type=lib.library_type,
                source_type="emby",
                is_enabled=lib.is_enabled,
                last_scan=lib.last_scan,
                item_count=lib.item_count,
                status=_get_library_status(lib.id),
                server_url=lib.server_url,
            )
        )

    return libraries


@router.get("/stats", response_model=LibraryStats)
async def get_library_stats(db: AsyncSession = Depends(get_db)) -> LibraryStats:
    """Get aggregate statistics for all libraries."""
    total_items = 0
    movies = 0
    shows = 0
    episodes = 0
    latest_scan = None

    result = await db.execute(select(LocalLibrary))
    for lib in result.scalars().all():
        total_items += lib.item_count
        if lib.last_scan and (not latest_scan or lib.last_scan > latest_scan):
            latest_scan = lib.last_scan

    result = await db.execute(select(PlexLibrary))
    for lib in result.scalars().all():
        total_items += lib.item_count
        if lib.library_type == "movie":
            movies += lib.item_count
        elif lib.library_type == "show":
            shows += lib.item_count
        if lib.last_scan and (not latest_scan or lib.last_scan > latest_scan):
            latest_scan = lib.last_scan

    result = await db.execute(select(JellyfinLibrary))
    for lib in result.scalars().all():
        total_items += lib.item_count
        if lib.last_scan and (not latest_scan or lib.last_scan > latest_scan):
            latest_scan = lib.last_scan

    result = await db.execute(select(EmbyLibrary))
    for lib in result.scalars().all():
        total_items += lib.item_count
        if lib.last_scan and (not latest_scan or lib.last_scan > latest_scan):
            latest_scan = lib.last_scan

    return LibraryStats(
        total_items=total_items,
        movies=movies,
        shows=shows,
        episodes=episodes,
        last_scanned=latest_scan,
    )


@router.get("/scan-progress/{library_id}", response_model=ScanProgress)
def get_scan_progress(library_id: int) -> ScanProgress:
    """Get the progress of an active scan."""
    if library_id not in _active_scans:
        raise HTTPException(status_code=404, detail="No active scan for this library")

    scan = _active_scans[library_id]
    total = scan.get("total_files", 0)
    scanned = scan.get("scanned_files", 0)

    return ScanProgress(
        library_id=library_id,
        status=scan.get("status", "unknown"),
        total_files=total,
        scanned_files=scanned,
        new_items=scan.get("new_items", 0),
        errors=scan.get("errors", 0),
        current_file=scan.get("current_file"),
        percent_complete=(scanned / total * 100) if total > 0 else 0,
        started_at=scan.get("started_at"),
    )


@router.post("/scan-all")
async def scan_all_libraries(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger a scan of all enabled libraries."""
    started = []

    result = await db.execute(select(LocalLibrary).where(LocalLibrary.is_enabled == True))
    for lib in result.scalars().all():
        if lib.id not in _active_scans:
            background_tasks.add_task(_run_library_scan, lib.id, "local")
            started.append({"id": lib.id, "type": "local", "name": lib.name})

    result = await db.execute(select(PlexLibrary).where(PlexLibrary.is_enabled == True))
    for lib in result.scalars().all():
        if lib.id not in _active_scans:
            background_tasks.add_task(_run_library_scan, lib.id, "plex")
            started.append({"id": lib.id, "type": "plex", "name": lib.name})

    result = await db.execute(select(JellyfinLibrary).where(JellyfinLibrary.is_enabled == True))
    for lib in result.scalars().all():
        if lib.id not in _active_scans:
            background_tasks.add_task(_run_library_scan, lib.id, "jellyfin")
            started.append({"id": lib.id, "type": "jellyfin", "name": lib.name})

    result = await db.execute(select(EmbyLibrary).where(EmbyLibrary.is_enabled == True))
    for lib in result.scalars().all():
        if lib.id not in _active_scans:
            background_tasks.add_task(_run_library_scan, lib.id, "emby")
            started.append({"id": lib.id, "type": "emby", "name": lib.name})

    return {
        "message": f"Started {len(started)} library scans",
        "libraries": started,
    }
