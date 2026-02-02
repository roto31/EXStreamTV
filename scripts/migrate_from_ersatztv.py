#!/usr/bin/env python3
"""
ErsatzTV to EXStreamTV Migration Script

Comprehensive migration from ErsatzTV to EXStreamTV with full entity support.
Supports importing:
- FFmpeg profiles
- Channels with unique_id and categories
- Channel watermarks
- Decos (watermarks, graphics, filler, dead air)
- Program schedules and items (including marathon mode)
- Blocks and block items
- Filler presets
- Templates
- Playouts

Usage:
    python migrate_from_ersatztv.py --source /path/to/ersatztv.db
    python migrate_from_ersatztv.py --source /path/to/ersatztv.db --dry-run
    python migrate_from_ersatztv.py --source /path/to/ersatztv.db --validate-only
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def log(message: str, level: str = "INFO") -> None:
    """Print timestamped log message with level."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": " ", "WARN": "!", "ERROR": "X", "OK": "✓"}.get(level, " ")
    print(f"[{timestamp}] {prefix} {message}")


def connect_ersatztv_db(db_path: Path) -> Optional[sqlite3.Connection]:
    """
    Connect to ErsatzTV SQLite database.
    
    ErsatzTV uses SQLite for its database.
    """
    if not db_path.exists():
        log(f"Database not found: {db_path}")
        return None
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_ersatztv_channels(conn: sqlite3.Connection) -> list[dict]:
    """Get all channels from ErsatzTV."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                Id, Number, Name, "Group", 
                StreamingMode, UniqueId,
                FFmpegProfileId, FallbackFillerId, WatermarkId
            FROM Channel
            ORDER BY Number
        """)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        log(f"Error reading channels: {e}")
        return []


def get_ersatztv_playouts(conn: sqlite3.Connection) -> list[dict]:
    """Get all playouts from ErsatzTV."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                Id, ChannelId, ProgramScheduleId
            FROM Playout
        """)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        log(f"Error reading playouts: {e}")
        return []


def get_ersatztv_schedules(conn: sqlite3.Connection) -> list[dict]:
    """Get all program schedules from ErsatzTV."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                Id, Name, 
                KeepMultiPartEpisodesTogether,
                TreatCollectionsAsShows,
                ShuffleScheduleItems,
                RandomStartPoint
            FROM ProgramSchedule
        """)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        log(f"Error reading schedules: {e}")
        return []


def get_ersatztv_filler_presets(conn: sqlite3.Connection) -> list[dict]:
    """Get all filler presets from ErsatzTV."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                Id, Name, FillerKind, FillerMode,
                Duration, Count, PadToNearestMinute,
                AllowWatermarks, MediaCollectionId
            FROM FillerPreset
        """)
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        log(f"Error reading filler presets: {e}")
        return []


def import_to_exstreamtv(
    target_db: Path,
    channels: list[dict],
    playouts: list[dict],
    schedules: list[dict],
    filler_presets: list[dict],
) -> dict:
    """
    Import data into EXStreamTV database.
    
    Returns:
        Import statistics.
    """
    stats = {
        "channels": 0,
        "playouts": 0,
        "schedules": 0,
        "filler_presets": 0,
    }
    
    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()
    
    # Import channels
    for channel in channels:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO channels 
                (id, number, name, "group", streaming_mode, prefer_channel_logo,
                 ffmpeg_profile_id, fallback_filler_id, is_enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
            """, (
                channel.get("Id"),
                channel.get("Number"),
                channel.get("Name"),
                channel.get("Group", "General"),
                channel.get("StreamingMode", "both"),
                channel.get("PreferChannelLogo", 1),
                channel.get("FFmpegProfileId"),
                channel.get("FallbackFillerId"),
            ))
            stats["channels"] += 1
        except sqlite3.Error as e:
            log(f"Error importing channel {channel.get('Number')}: {e}")
    
    # Import schedules
    for schedule in schedules:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO program_schedules
                (id, name, keep_multi_part_episodes, treat_collections_as_shows,
                 shuffle_schedule_items, random_start_point, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                schedule.get("Id"),
                schedule.get("Name"),
                schedule.get("KeepMultiPartEpisodesTogether", 1),
                schedule.get("TreatCollectionsAsShows", 0),
                schedule.get("ShuffleScheduleItems", 0),
                schedule.get("RandomStartPoint", 0),
            ))
            stats["schedules"] += 1
        except sqlite3.Error as e:
            log(f"Error importing schedule {schedule.get('Name')}: {e}")
    
    # Import playouts
    for playout in playouts:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO playouts
                (id, channel_id, program_schedule_id, playout_type, is_active,
                 created_at, updated_at)
                VALUES (?, ?, ?, 'continuous', 1, datetime('now'), datetime('now'))
            """, (
                playout.get("Id"),
                playout.get("ChannelId"),
                playout.get("ProgramScheduleId"),
            ))
            stats["playouts"] += 1
        except sqlite3.Error as e:
            log(f"Error importing playout {playout.get('Id')}: {e}")
    
    # Import filler presets
    for filler in filler_presets:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO filler_presets
                (id, name, filler_mode, duration_seconds, count, playback_order,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'shuffled', datetime('now'), datetime('now'))
            """, (
                filler.get("Id"),
                filler.get("Name"),
                filler.get("FillerMode", "duration"),
                filler.get("Duration"),
                filler.get("Count"),
            ))
            stats["filler_presets"] += 1
        except sqlite3.Error as e:
            log(f"Error importing filler preset {filler.get('Name')}: {e}")
    
    conn.commit()
    conn.close()
    
    return stats


async def run_migration_async(args: argparse.Namespace) -> int:
    """Run migration with async database session."""
    from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
    from exstreamtv.importers.validators import ErsatzTVValidator
    
    source = args.source.resolve()
    
    log("=" * 60)
    log("ErsatzTV to EXStreamTV Migration")
    log("=" * 60)
    log(f"Source: {source}")
    log(f"Mode: {'VALIDATE ONLY' if args.validate_only else 'DRY RUN' if args.dry_run else 'FULL MIGRATION'}")
    log("")
    
    # Step 1: Validate source database
    log("Step 1: Validating source database...")
    validator = ErsatzTVValidator(source)
    validation = validator.validate_source()
    
    if not validation.is_valid:
        log("Validation FAILED:", "ERROR")
        for error in validation.errors:
            log(f"  {error}", "ERROR")
        return 1
    
    log("Validation passed", "OK")
    
    # Show counts
    log("")
    log("Source database contents:")
    for table, count in validation.counts.items():
        if count > 0:
            log(f"  {table}: {count}")
    
    # Show warnings if any
    if validation.warnings:
        log("")
        log("Warnings:")
        for warning in validation.warnings:
            log(f"  {warning}", "WARN")
    
    if args.validate_only:
        log("")
        log("Validation complete. Use --dry-run or remove flags to proceed.")
        return 0
    
    log("")
    
    # Step 2: Create importer
    importer = ErsatzTVImporter(source, dry_run=args.dry_run)
    
    if args.dry_run:
        log("Step 2: DRY RUN - Simulating migration...")
        log("")
        
        # Show what would be migrated
        conn = connect_ersatztv_db(source)
        if conn:
            channels = get_ersatztv_channels(conn)
            log("Channels to import:")
            for ch in channels[:10]:
                log(f"  {ch.get('Number')}: {ch.get('Name')}")
            if len(channels) > 10:
                log(f"  ... and {len(channels) - 10} more")
            conn.close()
        
        log("")
        log("DRY RUN complete. Remove --dry-run flag to perform actual migration.")
        return 0
    
    # Step 3: Run migration with database session
    log("Step 2: Running migration...")
    log("")
    
    try:
        # Import database session factory
        from exstreamtv.database.connection import get_async_session
        
        async with get_async_session() as session:
            stats = await importer.migrate_all(session)
        
        log("")
        log("=" * 60)
        log("Migration Complete!", "OK")
        log("=" * 60)
        log("")
        log("Entities migrated:")
        stats_dict = stats.to_dict()
        for entity, count in stats_dict.items():
            if count > 0 and entity not in ("errors", "warnings"):
                log(f"  {entity}: {count}", "OK")
        
        if stats.errors > 0:
            log("")
            log(f"Errors encountered: {stats.errors}", "WARN")
        
        if stats.warnings > 0:
            log(f"Warnings: {stats.warnings}", "WARN")
        
        log("")
        log("Next steps:")
        log("  1. Review imported channels in the web UI")
        log("  2. Run the media scanner to import libraries")
        log("  3. Verify playout schedules are correct")
        log("  4. Test streaming on a few channels")
        
        return 0 if stats.errors == 0 else 1
        
    except ImportError as e:
        log(f"Database not available: {e}", "ERROR")
        log("")
        log("Running simplified migration (direct SQLite)...")
        
        # Fall back to simple migration
        conn = connect_ersatztv_db(source)
        if conn is None:
            return 1
        
        channels = get_ersatztv_channels(conn)
        playouts = get_ersatztv_playouts(conn)
        schedules = get_ersatztv_schedules(conn)
        filler_presets = get_ersatztv_filler_presets(conn)
        conn.close()
        
        target = args.target.resolve()
        stats = import_to_exstreamtv(target, channels, playouts, schedules, filler_presets)
        
        log("")
        log("Simple migration complete:")
        for key, value in stats.items():
            log(f"  {key}: {value}")
        
        return 0
    except Exception as e:
        log(f"Migration failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Main migration entry point."""
    parser = argparse.ArgumentParser(
        description="Import ErsatzTV data into EXStreamTV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --source /path/to/ersatztv.db
  %(prog)s --source /path/to/ersatztv.db --dry-run
  %(prog)s --source /path/to/ersatztv.db --validate-only
  %(prog)s --source ~/.ersatztv/ersatztv.db --target ./exstreamtv.db

The migration will import:
  - FFmpeg profiles with all encoding settings
  - Channels with unique IDs and categories
  - Watermarks and deco configurations
  - Program schedules and items (including marathon mode)
  - Blocks and block items
  - Filler presets
  - Templates
  - Playouts with schedule references
        """
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to ErsatzTV database file (ersatztv.db)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("./exstreamtv.db"),
        help="Path to EXStreamTV database file (default: ./exstreamtv.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show what would be imported without making changes",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate source database, don't import anything",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show verbose output",
    )
    
    args = parser.parse_args()
    
    # Run async migration
    return asyncio.run(run_migration_async(args))


if __name__ == "__main__":
    sys.exit(main())
