"""
Migration API - Import settings and channels from ErsatzTV and StreamTV

Supports:
- ErsatzTV SQLite database imports
- ErsatzTV JSON config imports
- StreamTV database imports
- Dry-run validation
- Progress tracking
"""

import asyncio
import json
import logging
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..database.connection import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Migration"])


# ============================================================================
# Response Models
# ============================================================================

class MigrationSource(BaseModel):
    """Available migration source."""
    id: str
    name: str
    description: str
    supported_formats: list[str]
    icon: str


class ValidationResult(BaseModel):
    """Validation result for a migration source."""
    is_valid: bool
    source_type: str
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MigrationProgress(BaseModel):
    """Migration progress status."""
    status: str  # pending, running, completed, failed
    current_step: str
    total_steps: int
    current_step_number: int
    items_processed: int
    items_total: int
    errors: list[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class MigrationResult(BaseModel):
    """Result of a migration operation."""
    success: bool
    source_type: str
    stats: dict[str, int]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    duration_seconds: float


# Global progress tracking
_migration_progress: dict[str, MigrationProgress] = {}


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/sources", response_model=list[MigrationSource])
async def get_migration_sources() -> list[MigrationSource]:
    """Get list of available migration sources."""
    return [
        MigrationSource(
            id="ersatztv",
            name="ErsatzTV",
            description="Import channels, schedules, filler presets, decos, and FFmpeg profiles from ErsatzTV",
            supported_formats=["SQLite Database (.db)", "JSON Config Files"],
            icon="📺"
        ),
        MigrationSource(
            id="streamtv",
            name="StreamTV",
            description="Import channels, playlists, and media items from StreamTV",
            supported_formats=["SQLite Database (.db)"],
            icon="📡"
        ),
    ]


@router.post("/validate/ersatztv", response_model=ValidationResult)
async def validate_ersatztv_source(
    db_file: Optional[UploadFile] = File(None),
    db_path: Optional[str] = Form(None),
    json_files: Optional[list[UploadFile]] = File(None),
) -> ValidationResult:
    """
    Validate an ErsatzTV source before migration.
    
    Accepts either:
    - A SQLite database file upload
    - A path to an existing database
    - JSON config files (channels.json, program-schedules.json, etc.)
    """
    if db_file:
        # Handle uploaded database file
        return await _validate_ersatztv_db_upload(db_file)
    elif db_path:
        # Handle path to existing database
        return await _validate_ersatztv_db_path(db_path)
    elif json_files:
        # Handle JSON config files
        return await _validate_ersatztv_json(json_files)
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide either a database file, database path, or JSON config files"
        )


@router.post("/validate/streamtv", response_model=ValidationResult)
async def validate_streamtv_source(
    db_file: Optional[UploadFile] = File(None),
    db_path: Optional[str] = Form(None),
) -> ValidationResult:
    """Validate a StreamTV source before migration."""
    if db_file:
        return await _validate_streamtv_db_upload(db_file)
    elif db_path:
        return await _validate_streamtv_db_path(db_path)
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide either a database file or database path"
        )


@router.post("/import/ersatztv", response_model=MigrationResult)
async def import_ersatztv(
    background_tasks: BackgroundTasks,
    db_file: Optional[UploadFile] = File(None),
    db_path: Optional[str] = Form(None),
    json_files: Optional[list[UploadFile]] = File(None),
    dry_run: bool = Form(False),
) -> MigrationResult:
    """
    Import data from ErsatzTV.
    
    Imports:
    - Channels with all settings
    - FFmpeg profiles
    - Resolutions
    - Watermarks
    - Filler presets
    - Decos
    - Program schedules and items
    - Blocks and block items
    - Templates
    - Playouts and playout items
    """
    start_time = datetime.now()
    
    try:
        if db_file:
            result = await _import_ersatztv_db_upload(db_file, dry_run)
        elif db_path:
            result = await _import_ersatztv_db_path(db_path, dry_run)
        elif json_files:
            result = await _import_ersatztv_json(json_files, dry_run)
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide either a database file, database path, or JSON config files"
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        result.duration_seconds = duration
        return result
        
    except Exception as e:
        logger.error(f"ErsatzTV import failed: {e}", exc_info=True)
        duration = (datetime.now() - start_time).total_seconds()
        return MigrationResult(
            success=False,
            source_type="ersatztv",
            stats={},
            errors=[str(e)],
            duration_seconds=duration
        )


@router.post("/import/streamtv", response_model=MigrationResult)
async def import_streamtv(
    background_tasks: BackgroundTasks,
    db_file: Optional[UploadFile] = File(None),
    db_path: Optional[str] = Form(None),
    dry_run: bool = Form(False),
) -> MigrationResult:
    """Import data from StreamTV."""
    start_time = datetime.now()
    
    try:
        if db_file:
            result = await _import_streamtv_db_upload(db_file, dry_run)
        elif db_path:
            result = await _import_streamtv_db_path(db_path, dry_run)
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide either a database file or database path"
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        result.duration_seconds = duration
        return result
        
    except Exception as e:
        logger.error(f"StreamTV import failed: {e}", exc_info=True)
        duration = (datetime.now() - start_time).total_seconds()
        return MigrationResult(
            success=False,
            source_type="streamtv",
            stats={},
            errors=[str(e)],
            duration_seconds=duration
        )


@router.get("/progress/{migration_id}", response_model=MigrationProgress)
async def get_migration_progress(migration_id: str) -> MigrationProgress:
    """Get progress of an ongoing migration."""
    if migration_id not in _migration_progress:
        raise HTTPException(status_code=404, detail="Migration not found")
    return _migration_progress[migration_id]


@router.get("/detect")
async def detect_sources() -> dict[str, Any]:
    """
    Detect available migration sources on the system.
    
    Searches common locations for ErsatzTV and StreamTV databases.
    """
    detected = {
        "ersatztv": [],
        "streamtv": [],
    }
    
    home = Path.home()
    
    # ErsatzTV common locations - check both .db and .sqlite3 extensions
    ersatztv_paths = [
        # macOS Application Support (primary location)
        home / "Library" / "Application Support" / "ersatztv" / "ersatztv.sqlite3",
        home / "Library" / "Application Support" / "ersatztv" / "ersatztv.db",
        home / "Library" / "Application Support" / "ersatztv",  # JSON config directory
        # Linux locations
        home / ".config" / "ersatztv" / "ersatztv.sqlite3",
        home / ".config" / "ersatztv" / "ersatztv.db",
        home / ".local" / "share" / "ersatztv" / "ersatztv.sqlite3",
        Path("/var/lib/ersatztv/ersatztv.sqlite3"),
        Path("/var/lib/ersatztv/ersatztv.db"),
        # Docker/custom locations
        home / ".dizquetv" / "ersatztv.db",
        home / ".dizquetv" / "ersatztv.sqlite3",
        home / "ersatztv" / "ersatztv.db",
        home / "ersatztv" / "ersatztv.sqlite3",
        home / "ersatztv" / "config",  # JSON config directory
    ]
    
    seen_paths = set()  # Avoid duplicates
    
    for path in ersatztv_paths:
        if path.exists() and str(path) not in seen_paths:
            seen_paths.add(str(path))
            if path.is_file() and path.suffix in (".db", ".sqlite3"):
                size = path.stat().st_size / 1024 / 1024
                detected["ersatztv"].append({
                    "path": str(path),
                    "type": "database",
                    "size_mb": round(size, 2),
                })
            elif path.is_dir():
                # Check for JSON config files
                json_files = list(path.glob("*.json"))
                if json_files:
                    detected["ersatztv"].append({
                        "path": str(path),
                        "type": "json_config",
                        "files": [f.name for f in json_files],
                    })
    
    # StreamTV common locations
    streamtv_paths = [
        home / "streamtv.db",
        home / ".streamtv" / "streamtv.db",
        Path("./streamtv.db"),
    ]
    
    for path in streamtv_paths:
        if path.exists() and path.is_file():
            size = path.stat().st_size / 1024 / 1024
            detected["streamtv"].append({
                "path": str(path),
                "type": "database",
                "size_mb": round(size, 2),
            })
    
    return detected


# ============================================================================
# Internal Helper Functions
# ============================================================================

async def _validate_ersatztv_db_upload(db_file: UploadFile) -> ValidationResult:
    """Validate an uploaded ErsatzTV database."""
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        content = await db_file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        return await _validate_ersatztv_db_path(tmp_path)
    finally:
        os.unlink(tmp_path)


async def _validate_ersatztv_db_path(db_path: str) -> ValidationResult:
    """Validate an ErsatzTV database at a given path."""
    path = Path(db_path)
    
    if not path.exists():
        return ValidationResult(
            is_valid=False,
            source_type="ersatztv",
            errors=[f"Database file not found: {db_path}"]
        )
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        counts = {}
        warnings = []
        errors = []
        
        # Check for expected tables - ErsatzTV uses singular table names
        expected_tables = [
            ("Channel", "channels"),
            ("FFmpegProfile", "ffmpeg_profiles"),
            ("Resolution", "resolutions"),
            ("ChannelWatermark", "watermarks"),
            ("FillerPreset", "filler_presets"),
            ("Deco", "decos"),
            ("ProgramSchedule", "schedules"),
            ("ProgramScheduleItem", "schedule_items"),
            ("Block", "blocks"),
            ("BlockItem", "block_items"),
            ("Template", "templates"),
            ("Playout", "playouts"),
            ("PlayoutItem", "playout_items"),
        ]
        
        for table_name, display_name in expected_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                counts[display_name] = count
            except sqlite3.OperationalError:
                counts[display_name] = 0
                if table_name in ("Channel", "Playout"):
                    errors.append(f"Required table '{table_name}' not found")
                # Don't warn for optional tables - cleaner output
        
        conn.close()
        
        is_valid = len(errors) == 0 and counts.get("channels", 0) > 0
        
        if counts.get("channels", 0) == 0:
            errors.append("No channels found in database")
        
        return ValidationResult(
            is_valid=is_valid,
            source_type="ersatztv",
            counts=counts,
            warnings=warnings,
            errors=errors
        )
        
    except Exception as e:
        return ValidationResult(
            is_valid=False,
            source_type="ersatztv",
            errors=[f"Failed to read database: {e}"]
        )


async def _validate_ersatztv_json(json_files: list[UploadFile]) -> ValidationResult:
    """Validate ErsatzTV JSON config files."""
    counts = {}
    warnings = []
    errors = []
    
    file_contents = {}
    
    for file in json_files:
        try:
            content = await file.read()
            data = json.loads(content.decode("utf-8"))
            file_contents[file.filename] = data
            
            if file.filename == "channels.json":
                counts["channels"] = len(data) if isinstance(data, list) else 0
            elif file.filename == "program-schedules.json":
                counts["schedules"] = len(data) if isinstance(data, list) else 0
            elif file.filename == "media-sources.json":
                counts["media_sources"] = len(data) if isinstance(data, list) else 0
            elif file.filename == "filler-presets.json":
                counts["filler_presets"] = len(data) if isinstance(data, list) else 0
                
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in {file.filename}: {e}")
        except Exception as e:
            errors.append(f"Error reading {file.filename}: {e}")
    
    if "channels.json" not in [f.filename for f in json_files]:
        warnings.append("channels.json not provided")
    
    is_valid = len(errors) == 0 and counts.get("channels", 0) > 0
    
    return ValidationResult(
        is_valid=is_valid,
        source_type="ersatztv_json",
        counts=counts,
        warnings=warnings,
        errors=errors
    )


async def _validate_streamtv_db_upload(db_file: UploadFile) -> ValidationResult:
    """Validate an uploaded StreamTV database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        content = await db_file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        return await _validate_streamtv_db_path(tmp_path)
    finally:
        os.unlink(tmp_path)


async def _validate_streamtv_db_path(db_path: str) -> ValidationResult:
    """Validate a StreamTV database at a given path."""
    path = Path(db_path)
    
    if not path.exists():
        return ValidationResult(
            is_valid=False,
            source_type="streamtv",
            errors=[f"Database file not found: {db_path}"]
        )
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        counts = {}
        warnings = []
        errors = []
        
        expected_tables = [
            ("channels", "channels"),
            ("playlists", "playlists"),
            ("media_items", "media_items"),
            ("collections", "collections"),
        ]
        
        for table_name, display_name in expected_tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                counts[display_name] = count
            except sqlite3.OperationalError:
                counts[display_name] = 0
                if table_name == "channels":
                    errors.append(f"Required table '{table_name}' not found")
        
        conn.close()
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            source_type="streamtv",
            counts=counts,
            warnings=warnings,
            errors=errors
        )
        
    except Exception as e:
        return ValidationResult(
            is_valid=False,
            source_type="streamtv",
            errors=[f"Failed to read database: {e}"]
        )


async def _import_ersatztv_db_upload(db_file: UploadFile, dry_run: bool) -> MigrationResult:
    """Import from an uploaded ErsatzTV database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        content = await db_file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        return await _import_ersatztv_db_path(tmp_path, dry_run)
    finally:
        os.unlink(tmp_path)


async def _import_ersatztv_db_path(db_path: str, dry_run: bool) -> MigrationResult:
    """Import from ErsatzTV database at path."""
    from ..importers.ersatztv_importer import ErsatzTVImporter, MigrationStats
    
    try:
        importer = ErsatzTVImporter(db_path, dry_run=dry_run)
        
        async with get_async_session() as session:
            stats = await importer.migrate_all(session)
        
        return MigrationResult(
            success=stats.errors == 0,
            source_type="ersatztv",
            stats=stats.to_dict(),
            errors=[],
            warnings=[],
            duration_seconds=0
        )
        
    except Exception as e:
        logger.error(f"ErsatzTV import error: {e}", exc_info=True)
        return MigrationResult(
            success=False,
            source_type="ersatztv",
            stats={},
            errors=[str(e)],
            duration_seconds=0
        )


async def _import_ersatztv_json(json_files: list[UploadFile], dry_run: bool) -> MigrationResult:
    """Import from ErsatzTV JSON config files."""
    stats = {
        "channels": 0,
        "schedules": 0,
        "schedule_items": 0,
        "media_sources": 0,
    }
    errors = []
    warnings = []
    
    file_contents = {}
    
    # Parse all JSON files
    for file in json_files:
        try:
            content = await file.read()
            data = json.loads(content.decode("utf-8"))
            file_contents[file.filename] = data
        except Exception as e:
            errors.append(f"Error reading {file.filename}: {e}")
    
    if errors:
        return MigrationResult(
            success=False,
            source_type="ersatztv_json",
            stats=stats,
            errors=errors,
            duration_seconds=0
        )
    
    if dry_run:
        # Just count what would be imported
        if "channels.json" in file_contents:
            stats["channels"] = len(file_contents["channels.json"])
        if "program-schedules.json" in file_contents:
            schedules = file_contents["program-schedules.json"]
            stats["schedules"] = len(schedules)
            stats["schedule_items"] = sum(len(s.get("items", [])) for s in schedules)
        if "media-sources.json" in file_contents:
            stats["media_sources"] = len(file_contents["media-sources.json"])
        
        return MigrationResult(
            success=True,
            source_type="ersatztv_json",
            stats=stats,
            warnings=["Dry run - no changes made"],
            duration_seconds=0
        )
    
    # Actual import
    try:
        async with get_async_session() as session:
            from ..database.models import Channel, ProgramSchedule, ProgramScheduleItem
            
            # Import channels
            if "channels.json" in file_contents:
                for ch_data in file_contents["channels.json"]:
                    channel = Channel(
                        number=int(ch_data.get("number", 0)),
                        name=ch_data.get("name", "Unknown"),
                        group=ch_data.get("group", "General"),
                        is_enabled=not ch_data.get("isHidden", False),
                    )
                    session.add(channel)
                    stats["channels"] += 1
            
            # Import schedules
            if "program-schedules.json" in file_contents:
                for sched_data in file_contents["program-schedules.json"]:
                    schedule = ProgramSchedule(
                        name=sched_data.get("name", "Unknown"),
                    )
                    session.add(schedule)
                    stats["schedules"] += 1
                    
                    # Import schedule items
                    for idx, item_data in enumerate(sched_data.get("items", [])):
                        # Parse time components
                        start_time = item_data.get("startTime", "00:00:00")
                        item = ProgramScheduleItem(
                            program_schedule=schedule,
                            index=idx,
                            start_time=start_time,
                            collection_type=item_data.get("collectionType", "MediaSource"),
                            playback_order=item_data.get("playbackOrder", "InOrder"),
                        )
                        session.add(item)
                        stats["schedule_items"] += 1
            
            await session.commit()
        
        return MigrationResult(
            success=True,
            source_type="ersatztv_json",
            stats=stats,
            duration_seconds=0
        )
        
    except Exception as e:
        logger.error(f"ErsatzTV JSON import error: {e}", exc_info=True)
        return MigrationResult(
            success=False,
            source_type="ersatztv_json",
            stats=stats,
            errors=[str(e)],
            duration_seconds=0
        )


async def _import_streamtv_db_upload(db_file: UploadFile, dry_run: bool) -> MigrationResult:
    """Import from an uploaded StreamTV database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        content = await db_file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        return await _import_streamtv_db_path(tmp_path, dry_run)
    finally:
        os.unlink(tmp_path)


async def _import_streamtv_db_path(db_path: str, dry_run: bool) -> MigrationResult:
    """Import from StreamTV database at path."""
    from ..importers.streamtv_importer import StreamTVImporter
    
    try:
        importer = StreamTVImporter(db_path, dry_run=dry_run)
        
        async with get_async_session() as session:
            stats = await importer.migrate_all(session)
        
        return MigrationResult(
            success=stats.get("errors", 0) == 0,
            source_type="streamtv",
            stats=stats,
            errors=[],
            duration_seconds=0
        )
        
    except Exception as e:
        logger.error(f"StreamTV import error: {e}", exc_info=True)
        return MigrationResult(
            success=False,
            source_type="streamtv",
            stats={},
            errors=[str(e)],
            duration_seconds=0
        )


# ============================================================================
# Repair Endpoints
# ============================================================================

class RepairResult(BaseModel):
    """Result of a repair operation."""
    success: bool
    stats: dict[str, int]
    errors: list[str] = Field(default_factory=list)
    message: str


@router.post("/repair/playout-items", response_model=RepairResult)
async def repair_playout_items(
    dry_run: bool = True,
    ersatztv_path: Optional[str] = None,
) -> RepairResult:
    """
    Repair broken PlayoutItems by re-linking to media items via Plex keys.
    
    This operation:
    1. Builds a mapping from ErsatzTV MediaItem IDs to EXStreamTV MediaItem IDs via Plex keys
    2. Deletes broken PlayoutItems (those with no media_item_id)
    3. Re-imports PlayoutItems from ErsatzTV with correct media links
    
    Args:
        dry_run: If True, only validate without making changes
        ersatztv_path: Optional path to ErsatzTV database (defaults to ~/Library/Application Support/ersatztv/ersatztv.sqlite3)
    
    Returns:
        RepairResult with statistics
    """
    from ..importers.ersatztv_importer import ErsatzTVImporter
    
    # Default ErsatzTV database path
    if not ersatztv_path:
        ersatztv_path = os.path.expanduser(
            "~/Library/Application Support/ersatztv/ersatztv.sqlite3"
        )
    
    if not os.path.exists(ersatztv_path):
        return RepairResult(
            success=False,
            stats={},
            errors=[f"ErsatzTV database not found at: {ersatztv_path}"],
            message="ErsatzTV database not found"
        )
    
    try:
        importer = ErsatzTVImporter(ersatztv_path, dry_run=dry_run)
        
        async with get_async_session() as session:
            stats = await importer.repair_playout_items(session)
        
        message = (
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"Created {stats['mappings_created']} media mappings, "
            f"deleted {stats['items_deleted']} broken items, "
            f"imported {stats['items_imported']} new items"
        )
        
        return RepairResult(
            success=stats.get("errors", 0) == 0,
            stats=stats,
            errors=[],
            message=message
        )
        
    except Exception as e:
        logger.error(f"PlayoutItem repair error: {e}", exc_info=True)
        return RepairResult(
            success=False,
            stats={},
            errors=[str(e)],
            message=f"Repair failed: {str(e)}"
        )
