#!/usr/bin/env python3
"""
Fix Archive.org Media Item Sources

This script updates media items that have Archive.org URLs but are missing
the proper source='archive_org' designation. This is critical for streaming
because Archive.org items need special handling (headers, timeouts).

Usage:
    python scripts/fix_archive_org_sources.py [--dry-run]
    
Options:
    --dry-run    Show what would be updated without making changes
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Get the EXStreamTV database path."""
    # Check common locations
    locations = [
        Path("exstreamtv.db"),
        Path("/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db"),
        Path.home() / ".exstreamtv" / "exstreamtv.db",
    ]
    
    for path in locations:
        if path.exists():
            return path
    
    raise FileNotFoundError("Could not find exstreamtv.db")


def fix_archive_org_sources(db_path: Path, dry_run: bool = False) -> dict:
    """
    Fix media items with Archive.org URLs that have missing/wrong source field.
    
    Args:
        db_path: Path to the database
        dry_run: If True, don't actually make changes
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "total_media_items": 0,
        "archive_org_by_url": 0,
        "youtube_by_url": 0,
        "plex_by_url": 0,
        "already_correct": 0,
        "updated": 0,
        "errors": 0,
    }
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM media_items")
        stats["total_media_items"] = cursor.fetchone()[0]
        
        # Find Archive.org items with missing/wrong source
        cursor.execute("""
            SELECT id, title, url, source 
            FROM media_items 
            WHERE url LIKE '%archive.org%' 
              AND (source IS NULL OR source = '' OR source NOT IN ('archive_org', 'ARCHIVE_ORG'))
        """)
        archive_org_items = cursor.fetchall()
        stats["archive_org_by_url"] = len(archive_org_items)
        
        logger.info(f"Found {len(archive_org_items)} Archive.org items needing source fix")
        
        # Fix Archive.org items
        if archive_org_items and not dry_run:
            cursor.execute("""
                UPDATE media_items 
                SET source = 'archive_org'
                WHERE url LIKE '%archive.org%' 
                  AND (source IS NULL OR source = '' OR source NOT IN ('archive_org', 'ARCHIVE_ORG'))
            """)
            stats["updated"] += cursor.rowcount
            logger.info(f"Updated {cursor.rowcount} Archive.org items")
        elif archive_org_items:
            logger.info(f"[DRY RUN] Would update {len(archive_org_items)} Archive.org items")
            for item in archive_org_items[:5]:
                logger.info(f"  - {item['title'][:50]}... (current source: {item['source']})")
            if len(archive_org_items) > 5:
                logger.info(f"  ... and {len(archive_org_items) - 5} more")
        
        # Find YouTube items with missing/wrong source
        cursor.execute("""
            SELECT id, title, url, source 
            FROM media_items 
            WHERE (url LIKE '%youtube.com%' OR url LIKE '%youtu.be%' OR url LIKE '%googlevideo.com%')
              AND (source IS NULL OR source = '' OR source NOT IN ('youtube', 'YOUTUBE'))
        """)
        youtube_items = cursor.fetchall()
        stats["youtube_by_url"] = len(youtube_items)
        
        if youtube_items and not dry_run:
            cursor.execute("""
                UPDATE media_items 
                SET source = 'youtube'
                WHERE (url LIKE '%youtube.com%' OR url LIKE '%youtu.be%' OR url LIKE '%googlevideo.com%')
                  AND (source IS NULL OR source = '' OR source NOT IN ('youtube', 'YOUTUBE'))
            """)
            stats["updated"] += cursor.rowcount
            logger.info(f"Updated {cursor.rowcount} YouTube items")
        elif youtube_items:
            logger.info(f"[DRY RUN] Would update {len(youtube_items)} YouTube items")
        
        # Find Plex items with missing/wrong source
        cursor.execute("""
            SELECT id, title, url, source 
            FROM media_items 
            WHERE (url LIKE '%:32400%' OR url LIKE '%/library/metadata/%')
              AND (source IS NULL OR source = '' OR source NOT IN ('plex', 'PLEX'))
        """)
        plex_items = cursor.fetchall()
        stats["plex_by_url"] = len(plex_items)
        
        if plex_items and not dry_run:
            cursor.execute("""
                UPDATE media_items 
                SET source = 'plex'
                WHERE (url LIKE '%:32400%' OR url LIKE '%/library/metadata/%')
                  AND (source IS NULL OR source = '' OR source NOT IN ('plex', 'PLEX'))
            """)
            stats["updated"] += cursor.rowcount
            logger.info(f"Updated {cursor.rowcount} Plex items")
        elif plex_items:
            logger.info(f"[DRY RUN] Would update {len(plex_items)} Plex items")
        
        # Also fix items with archive_org_identifier but wrong source
        cursor.execute("""
            SELECT id, title, source, archive_org_identifier
            FROM media_items 
            WHERE archive_org_identifier IS NOT NULL 
              AND archive_org_identifier != ''
              AND (source IS NULL OR source = '' OR source NOT IN ('archive_org', 'ARCHIVE_ORG'))
        """)
        archive_by_field = cursor.fetchall()
        
        if archive_by_field and not dry_run:
            cursor.execute("""
                UPDATE media_items 
                SET source = 'archive_org'
                WHERE archive_org_identifier IS NOT NULL 
                  AND archive_org_identifier != ''
                  AND (source IS NULL OR source = '' OR source NOT IN ('archive_org', 'ARCHIVE_ORG'))
            """)
            stats["updated"] += cursor.rowcount
            logger.info(f"Updated {cursor.rowcount} items with archive_org_identifier")
        elif archive_by_field:
            logger.info(f"[DRY RUN] Would update {len(archive_by_field)} items with archive_org_identifier")
        
        # Count already correct items
        cursor.execute("""
            SELECT COUNT(*) FROM media_items 
            WHERE source = 'archive_org' 
               OR (url LIKE '%archive.org%' AND source = 'archive_org')
        """)
        stats["already_correct"] = cursor.fetchone()[0]
        
        if not dry_run:
            conn.commit()
            logger.info("Database changes committed")
        else:
            logger.info("[DRY RUN] No changes made")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        stats["errors"] += 1
        conn.rollback()
        raise
    finally:
        conn.close()
    
    return stats


def print_summary(stats: dict, dry_run: bool) -> None:
    """Print summary of the fix operation."""
    print("\n" + "=" * 60)
    print("ARCHIVE.ORG SOURCE FIX SUMMARY")
    print("=" * 60)
    print(f"Total media items in database: {stats['total_media_items']}")
    print(f"Archive.org items by URL: {stats['archive_org_by_url']}")
    print(f"YouTube items by URL: {stats['youtube_by_url']}")
    print(f"Plex items by URL: {stats['plex_by_url']}")
    print(f"Already correctly labeled: {stats['already_correct']}")
    if dry_run:
        print(f"\n[DRY RUN] Would update: {stats['archive_org_by_url'] + stats['youtube_by_url'] + stats['plex_by_url']} items")
    else:
        print(f"\nActually updated: {stats['updated']} items")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Fix Archive.org media item sources in EXStreamTV database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to exstreamtv.db (auto-detected if not specified)"
    )
    
    args = parser.parse_args()
    
    try:
        db_path = args.db_path or get_db_path()
        logger.info(f"Using database: {db_path}")
        
        if args.dry_run:
            logger.info("Running in DRY RUN mode - no changes will be made")
        
        stats = fix_archive_org_sources(db_path, dry_run=args.dry_run)
        print_summary(stats, args.dry_run)
        
        if stats["errors"] > 0:
            sys.exit(1)
        
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
