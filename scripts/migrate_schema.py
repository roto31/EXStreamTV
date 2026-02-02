#!/usr/bin/env python3
"""
Database Schema Migration Script

Adds missing columns to database tables to match SQLAlchemy models.
This script is idempotent - it only adds columns that don't exist.

Usage:
    python scripts/migrate_schema.py
    python scripts/migrate_schema.py --dry-run
    python scripts/migrate_schema.py --db-path /path/to/exstreamtv.db
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def log(message: str, level: str = "INFO") -> None:
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": " ", "WARN": "!", "ERROR": "X", "OK": "✓", "SKIP": "-"}.get(level, " ")
    print(f"[{timestamp}] {prefix} {message}")


def get_existing_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    """Get set of existing column names for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def add_column_if_missing(
    cursor: sqlite3.Cursor,
    table_name: str,
    column_name: str,
    column_type: str,
    existing_columns: set[str],
    dry_run: bool = False,
) -> bool:
    """Add a column if it doesn't exist. Returns True if column was added."""
    if column_name in existing_columns:
        return False
    
    sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
    
    if dry_run:
        log(f"Would add: {table_name}.{column_name} ({column_type})", "INFO")
    else:
        cursor.execute(sql)
        log(f"Added: {table_name}.{column_name}", "OK")
    
    return True


def migrate_channels(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to channels table."""
    cols = get_existing_columns(cursor, "channels")
    count = 0
    
    columns = [
        ("unique_id", "VARCHAR(36)"),
        ("sort_number", "REAL"),
        ("categories", "TEXT"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "channels", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_blocks(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to blocks table."""
    cols = get_existing_columns(cursor, "blocks")
    count = 0
    
    columns = [
        ("minutes", "INTEGER"),
        ("stop_scheduling", "BOOLEAN DEFAULT 0"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "blocks", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_filler_presets(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to filler_presets table."""
    cols = get_existing_columns(cursor, "filler_presets")
    count = 0
    
    columns = [
        ("filler_kind", "VARCHAR(20)"),
        ("expression", "TEXT"),
        ("allow_watermarks", "BOOLEAN DEFAULT 1"),
        ("collection_id", "INTEGER"),
        ("smart_collection_id", "INTEGER"),
        ("multi_collection_id", "INTEGER"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "filler_presets", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_program_schedules(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to program_schedules table."""
    cols = get_existing_columns(cursor, "program_schedules")
    count = 0
    
    columns = [
        ("fixed_start_time_behavior", "VARCHAR(20) DEFAULT 'fill'"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "program_schedules", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_playlists(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to playlists table."""
    cols = get_existing_columns(cursor, "playlists")
    count = 0
    
    columns = [
        ("collection_type", "VARCHAR(20) DEFAULT 'static'"),
        ("search_query", "TEXT"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "playlists", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_playouts(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to playouts table."""
    cols = get_existing_columns(cursor, "playouts")
    count = 0
    
    columns = [
        ("deco_id", "INTEGER"),
        ("schedule_kind", "VARCHAR(20) DEFAULT 'flood'"),
        ("schedule_file", "TEXT"),
        ("seed", "INTEGER"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "playouts", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_block_items(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to block_items table."""
    cols = get_existing_columns(cursor, "block_items")
    count = 0
    
    columns = [
        ("multi_collection_id", "INTEGER"),
        ("smart_collection_id", "INTEGER"),
        ("search_query", "TEXT"),
        ("search_title", "VARCHAR(500)"),
        ("disable_watermarks", "BOOLEAN DEFAULT 0"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "block_items", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_program_schedule_items(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to program_schedule_items table."""
    cols = get_existing_columns(cursor, "program_schedule_items")
    count = 0
    
    columns = [
        ("multi_collection_id", "INTEGER"),
        ("smart_collection_id", "INTEGER"),
        ("search_query", "TEXT"),
        ("search_title", "VARCHAR(500)"),
        ("marathon_batch_size", "INTEGER"),
        ("marathon_group_by", "VARCHAR(20)"),
        ("preferred_audio_language_code", "VARCHAR(10)"),
        ("preferred_audio_title", "VARCHAR(255)"),
        ("preferred_subtitle_language_code", "VARCHAR(10)"),
        ("subtitle_mode", "VARCHAR(20)"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "program_schedule_items", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_decos(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to decos table."""
    cols = get_existing_columns(cursor, "decos")
    count = 0
    
    columns = [
        ("watermark_mode", "VARCHAR(20) DEFAULT 'inherit'"),
        ("watermark_id", "INTEGER"),
        ("graphics_elements_mode", "VARCHAR(20) DEFAULT 'inherit'"),
        ("break_content_mode", "VARCHAR(20) DEFAULT 'inherit'"),
        ("default_filler_mode", "VARCHAR(20) DEFAULT 'inherit'"),
        ("default_filler_collection_id", "INTEGER"),
        ("default_filler_trim_to_fit", "BOOLEAN DEFAULT 0"),
        ("dead_air_fallback_mode", "VARCHAR(20) DEFAULT 'inherit'"),
        ("dead_air_fallback_collection_id", "INTEGER"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "decos", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def migrate_ffmpeg_profiles(cursor: sqlite3.Cursor, dry_run: bool) -> int:
    """Add missing columns to ffmpeg_profiles table."""
    cols = get_existing_columns(cursor, "ffmpeg_profiles")
    count = 0
    
    columns = [
        ("video_format", "VARCHAR(20) DEFAULT 'h264'"),
        ("video_profile", "VARCHAR(20)"),
        ("allow_b_frames", "BOOLEAN DEFAULT 1"),
        ("bit_depth", "VARCHAR(10) DEFAULT '8bit'"),
        ("audio_format", "VARCHAR(20) DEFAULT 'aac'"),
        ("audio_buffer_size", "VARCHAR(20) DEFAULT '384k'"),
        ("scaling_behavior", "VARCHAR(30) DEFAULT 'scale_and_pad'"),
        ("tonemap_algorithm", "VARCHAR(30)"),
        ("normalize_loudness_mode", "VARCHAR(20) DEFAULT 'off'"),
        ("target_loudness", "REAL"),
        ("vaapi_driver", "VARCHAR(50)"),
        ("vaapi_device", "VARCHAR(100)"),
        ("qsv_extra_hardware_frames", "INTEGER"),
        ("normalize_framerate", "BOOLEAN DEFAULT 1"),
        ("deinterlace_video", "BOOLEAN"),
        ("gop_size", "INTEGER"),
        ("global_watermark_id", "INTEGER"),
    ]
    
    for col_name, col_type in columns:
        if add_column_if_missing(cursor, "ffmpeg_profiles", col_name, col_type, cols, dry_run):
            count += 1
    
    return count


def run_migration(db_path: str, dry_run: bool = False) -> dict[str, int]:
    """Run all migrations and return count of columns added per table."""
    log("=" * 60)
    log("EXStreamTV Database Schema Migration")
    log("=" * 60)
    log(f"Database: {db_path}")
    log(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    log("")
    
    if not Path(db_path).exists():
        log(f"Database not found: {db_path}", "ERROR")
        return {}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    results = {}
    
    # Run all migrations
    migrations = [
        ("channels", migrate_channels),
        ("blocks", migrate_blocks),
        ("filler_presets", migrate_filler_presets),
        ("program_schedules", migrate_program_schedules),
        ("playlists", migrate_playlists),
        ("playouts", migrate_playouts),
        ("block_items", migrate_block_items),
        ("program_schedule_items", migrate_program_schedule_items),
        ("decos", migrate_decos),
        ("ffmpeg_profiles", migrate_ffmpeg_profiles),
    ]
    
    for table_name, migrate_func in migrations:
        try:
            count = migrate_func(cursor, dry_run)
            results[table_name] = count
            if count == 0:
                log(f"{table_name}: No changes needed", "SKIP")
        except sqlite3.OperationalError as e:
            log(f"{table_name}: Error - {e}", "ERROR")
            results[table_name] = -1
    
    if not dry_run:
        conn.commit()
        log("")
        log("Changes committed to database", "OK")
    
    conn.close()
    
    # Summary
    log("")
    log("=" * 60)
    log("Migration Summary")
    log("=" * 60)
    
    total_added = sum(v for v in results.values() if v > 0)
    tables_modified = sum(1 for v in results.values() if v > 0)
    
    log(f"Tables checked: {len(results)}")
    log(f"Tables modified: {tables_modified}")
    log(f"Columns added: {total_added}")
    
    if dry_run and total_added > 0:
        log("")
        log("This was a dry run. Run without --dry-run to apply changes.")
    
    return results


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate EXStreamTV database schema to match models"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="exstreamtv.db",
        help="Path to database file (default: exstreamtv.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes",
    )
    
    args = parser.parse_args()
    
    results = run_migration(args.db_path, args.dry_run)
    
    # Return non-zero if any errors occurred
    if any(v < 0 for v in results.values()):
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
