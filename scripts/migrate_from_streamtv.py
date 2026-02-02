#!/usr/bin/env python3
"""
StreamTV to EXStreamTV Migration Script

Migrates an existing StreamTV installation to EXStreamTV.
Preserves all data, configurations, and channels.

Supports:
- Database migration with source-specific metadata preservation
- YouTube and Archive.org source metadata
- Channel and playlist configurations
- Schedule migration

Usage:
    python migrate_from_streamtv.py --source /path/to/streamtv
    python migrate_from_streamtv.py --source /path/to/streamtv --dry-run
    python migrate_from_streamtv.py --source /path/to/streamtv/streamtv.db --db-only
"""

import argparse
import asyncio
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def log(message: str, level: str = "INFO") -> None:
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": " ", "WARN": "!", "ERROR": "X", "OK": "✓"}.get(level, " ")
    print(f"[{timestamp}] {prefix} {message}")


def migrate_database(source_db: Path, target_db: Path) -> dict:
    """
    Migrate database from StreamTV to EXStreamTV.
    
    Returns:
        Migration statistics.
    """
    stats = {
        "channels": 0,
        "playlists": 0,
        "playlist_items": 0,
        "schedules": 0,
    }
    
    if not source_db.exists():
        log(f"Source database not found: {source_db}")
        return stats
    
    # Copy database file
    shutil.copy2(source_db, target_db)
    log(f"Copied database to {target_db}")
    
    # Connect and count records
    conn = sqlite3.connect(target_db)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM channels")
        stats["channels"] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("SELECT COUNT(*) FROM playlists")
        stats["playlists"] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("SELECT COUNT(*) FROM playlist_items")
        stats["playlist_items"] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("SELECT COUNT(*) FROM schedules")
        stats["schedules"] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        pass
    
    conn.close()
    return stats


def migrate_config(source_config: Path, target_config: Path) -> bool:
    """
    Migrate configuration file.
    
    Returns:
        True if successful.
    """
    if not source_config.exists():
        log(f"Source config not found: {source_config}")
        return False
    
    shutil.copy2(source_config, target_config)
    log(f"Copied config to {target_config}")
    return True


def migrate_data(source_data: Path, target_data: Path) -> dict:
    """
    Migrate data directory (cookies, logs, etc.).
    
    Returns:
        Migration statistics.
    """
    stats = {"files": 0, "dirs": 0}
    
    if not source_data.exists():
        log(f"Source data directory not found: {source_data}")
        return stats
    
    target_data.mkdir(parents=True, exist_ok=True)
    
    for item in source_data.iterdir():
        if item.is_file():
            shutil.copy2(item, target_data / item.name)
            stats["files"] += 1
        elif item.is_dir():
            shutil.copytree(item, target_data / item.name, dirs_exist_ok=True)
            stats["dirs"] += 1
    
    log(f"Copied data directory: {stats['files']} files, {stats['dirs']} dirs")
    return stats


async def run_database_migration(source_db: Path, dry_run: bool) -> dict:
    """Run database migration using StreamTVCustomImporter."""
    try:
        # Use custom importer for StreamTV-specific schema
        from exstreamtv.importers.streamtv_importer_custom import StreamTVCustomImporter
        
        # Enable detailed logging
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='[%(asctime)s] %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        importer = StreamTVCustomImporter(source_db, dry_run=dry_run)
        
        # Validate first
        log("Validating source database...")
        validation = importer.validate()
        
        if not validation["is_valid"]:
            log("Validation failed:", "ERROR")
            for error in validation["errors"]:
                log(f"  {error}", "ERROR")
            if validation["warnings"]:
                log("Warnings:")
                for warning in validation["warnings"]:
                    log(f"  {warning}", "WARN")
            return {"success": False, "errors": validation["errors"]}
        
        log("Source database validated", "OK")
        log("")
        log("Source contents:")
        log(f"  Channels: {validation['counts'].get('channels', 0)}")
        log(f"  Media items: {validation['counts'].get('media_items', 0)}")
        log(f"  Collections: {validation['counts'].get('collections', 0)}")
        log(f"  Playlists: {validation['counts'].get('playlists', 0)}")
        log(f"  Collection items: {validation['counts'].get('collection_items', 0)}")
        log(f"  Playlist items: {validation['counts'].get('playlist_items', 0)}")
        total_playlists = validation['counts'].get('collections', 0) + validation['counts'].get('playlists', 0)
        total_items = validation['counts'].get('collection_items', 0) + validation['counts'].get('playlist_items', 0)
        log(f"  Total playlists (after merge): {total_playlists}")
        log(f"  Total playlist items: {total_items}")
        log("")
        
        if validation["warnings"]:
            log("Warnings detected:")
            for warning in validation["warnings"]:
                log(f"  {warning}", "WARN")
            log("")
        
        if dry_run:
            log("DRY RUN complete - no changes made", "OK")
            return {"success": True, "dry_run": True, "counts": validation["counts"]}
        
        # Run migration with database session
        log("Starting migration...")
        log("This may take several minutes for large databases...")
        log("")
        
        from exstreamtv.database.connection import get_async_session
        
        async with get_async_session() as session:
            try:
                stats = await importer.migrate_all(session)
                
                # Log detailed statistics
                log("")
                log("Migration statistics:")
                log(f"  Channels migrated: {stats.channels}")
                log(f"  Media items migrated: {stats.media_items}")
                log(f"  Collections → Playlists: {stats.collections}")
                log(f"  Playlists migrated: {stats.playlists}")
                log(f"  Total playlists created: {stats.collections + stats.playlists}")
                log(f"  Collection items migrated: {stats.collection_items}")
                log(f"  Playlist items migrated: {stats.playlist_items}")
                log(f"  Total playlist items: {stats.collection_items + stats.playlist_items}")
                log(f"  Default playouts created: {stats.playouts_created}")
                log("")
                log(f"  Archive.org metadata extracted: {stats.archive_org_extracted}")
                log(f"  YouTube metadata extracted: {stats.youtube_extracted}")
                log(f"  Plex metadata extracted: {stats.plex_extracted}")
                log("")
                
                if stats.errors > 0:
                    log(f"  Errors encountered: {stats.errors}", "WARN")
                if stats.warnings > 0:
                    log(f"  Warnings: {stats.warnings}", "WARN")
                
                if stats.errors == 0:
                    log("Migration completed successfully!", "OK")
                else:
                    log("Migration completed with errors - review logs above", "WARN")
                
                return {"success": True, "stats": stats.to_dict()}
                
            except Exception as e:
                log(f"Migration error: {e}", "ERROR")
                import traceback
                log(f"Traceback:", "ERROR")
                for line in traceback.format_exc().splitlines():
                    log(f"  {line}", "ERROR")
                await session.rollback()
                return {"success": False, "error": str(e)}
        
    except ImportError as e:
        log(f"Database module not available: {e}", "ERROR")
        log("Make sure exstreamtv package is installed", "ERROR")
        return {"success": False, "fallback": False, "error": str(e)}


def main() -> int:
    """Main migration entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate StreamTV installation to EXStreamTV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --source /path/to/streamtv
  %(prog)s --source /path/to/streamtv --dry-run
  %(prog)s --source /path/to/streamtv/streamtv.db --db-only

The migration preserves:
  - All channels with unique IDs
  - Playlists and media items
  - YouTube source metadata (video IDs, channel info, tags)
  - Archive.org source metadata (identifiers, collections)
  - Schedules and configurations
        """
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to StreamTV installation directory or database file",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("."),
        help="Path to EXStreamTV installation directory (default: current)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="Only migrate database (skip config and data files)",
    )
    
    args = parser.parse_args()
    source = args.source.resolve()
    target = args.target.resolve()
    
    log("=" * 60)
    log("StreamTV to EXStreamTV Migration")
    log("=" * 60)
    log(f"Source: {source}")
    log(f"Target: {target}")
    log(f"Mode: {'DRY RUN' if args.dry_run else 'DB ONLY' if args.db_only else 'FULL MIGRATION'}")
    log("")
    
    # Determine source paths
    if source.is_file() and source.suffix == ".db":
        source_db = source
        source_dir = source.parent
    elif source.is_dir():
        source_db = source / "streamtv.db"
        source_dir = source
    else:
        log(f"ERROR: Source not found: {source}", "ERROR")
        return 1
    
    source_config = source_dir / "config.yaml"
    source_data = source_dir / "data"
    
    log("Checking source files...")
    log(f"  Database: {'Found' if source_db.exists() else 'Not found'}")
    if not args.db_only:
        log(f"  Config: {'Found' if source_config.exists() else 'Not found'}")
        log(f"  Data: {'Found' if source_data.exists() else 'Not found'}")
    log("")
    
    if not source_db.exists():
        log(f"ERROR: Database not found: {source_db}", "ERROR")
        return 1
    
    # Step 1: Migrate database
    log("")
    log("=" * 60)
    log("Step 1: Database Migration")
    log("=" * 60)
    log("")
    
    db_result = asyncio.run(run_database_migration(source_db, args.dry_run))
    
    if db_result.get("success"):
        if args.dry_run:
            log("")
            log("=" * 60)
            log("DRY RUN COMPLETE", "OK")
            log("=" * 60)
            log("")
            log("Validation passed. Migration ready to proceed.")
            log("Remove --dry-run flag to perform actual migration.")
        else:
            stats = db_result.get("stats", {})
            if stats.get("errors", 0) > 0:
                log("")
                log("=" * 60)
                log("MIGRATION COMPLETED WITH ERRORS", "WARN")
                log("=" * 60)
                log("")
                log(f"Total errors: {stats.get('errors', 0)}")
                log(f"Total warnings: {stats.get('warnings', 0)}")
                log("")
                log("Review the error log above for details.")
                log("Some items may not have been migrated.")
            else:
                log("")
                log("=" * 60)
                log("DATABASE MIGRATION SUCCESSFUL", "OK")
                log("=" * 60)
    else:
        log("")
        log("=" * 60)
        log("DATABASE MIGRATION FAILED", "ERROR")
        log("=" * 60)
        log("")
        error_msg = db_result.get("error", "Unknown error")
        log(f"Error: {error_msg}")
        log("")
        log("Troubleshooting steps:")
        log("  1. Check that the source database exists and is readable")
        log("  2. Verify EXStreamTV dependencies are installed (pip install -e .)")
        log("  3. Review error messages above")
        log("  4. Check logs/migration_*.log for detailed error traces")
        log("")
        return 1
    
    if args.dry_run or args.db_only:
        log("")
        if args.dry_run:
            log("DRY RUN complete. Remove --dry-run flag to perform actual migration.")
        else:
            log("Database-only migration complete.")
        return 0
    
    log("")
    
    # Step 2: Migrate config
    if source_config.exists():
        log("Step 2: Migrating configuration...")
        migrate_config(source_config, target / "config.yaml")
    
    # Step 3: Migrate data
    if source_data.exists():
        log("Step 3: Migrating data directory...")
        migrate_data(source_data, target / "data")
    
    log("")
    log("=" * 60)
    log("Migration complete!", "OK")
    log("=" * 60)
    log("")
    log("Next steps:")
    log("  1. Review config.yaml and update any paths")
    log("  2. Run: python -m exstreamtv")
    log("  3. Access WebUI at http://localhost:8411")
    log("  4. Verify channels and playback")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
