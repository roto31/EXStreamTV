#!/usr/bin/env python3
"""
Fix Empty Playouts for StreamTV Imported Channels

This script populates playout_items for channels that have empty playouts
but have matching playlists with content. This fixes channels imported from
StreamTV that weren't properly linked to their media content.

Usage:
    python scripts/fix_empty_playouts.py [--dry-run]
    
Options:
    --dry-run    Show what would be updated without making changes
"""

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    """Get the EXStreamTV database path."""
    locations = [
        Path("exstreamtv.db"),
        Path("/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db"),
    ]
    
    for path in locations:
        if path.exists():
            return path
    
    raise FileNotFoundError("Could not find exstreamtv.db")


def find_matching_playlist(cursor, channel_name: str) -> tuple[int, str, int] | None:
    """
    Find a playlist that matches the channel name.
    
    Returns:
        Tuple of (playlist_id, playlist_name, item_count) or None
    """
    # Try exact match first
    cursor.execute("""
        SELECT p.id, p.name, COUNT(pi.id) as item_count
        FROM playlists p
        LEFT JOIN playlist_items pi ON p.id = pi.playlist_id
        WHERE p.name = ?
        GROUP BY p.id
        HAVING item_count > 0
    """, (channel_name,))
    result = cursor.fetchone()
    if result:
        return result
    
    # Try LIKE match (channel name might be part of playlist name)
    cursor.execute("""
        SELECT p.id, p.name, COUNT(pi.id) as item_count
        FROM playlists p
        LEFT JOIN playlist_items pi ON p.id = pi.playlist_id
        WHERE p.name LIKE ?
        GROUP BY p.id
        HAVING item_count > 0
        ORDER BY item_count DESC
        LIMIT 1
    """, (f"%{channel_name}%",))
    result = cursor.fetchone()
    if result:
        return result
    
    # Try matching key words from channel name
    keywords = channel_name.split()
    for keyword in keywords:
        if len(keyword) > 3:  # Skip short words
            cursor.execute("""
                SELECT p.id, p.name, COUNT(pi.id) as item_count
                FROM playlists p
                LEFT JOIN playlist_items pi ON p.id = pi.playlist_id
                WHERE p.name LIKE ?
                GROUP BY p.id
                HAVING item_count > 0
                ORDER BY item_count DESC
                LIMIT 1
            """, (f"%{keyword}%",))
            result = cursor.fetchone()
            if result and result[2] > 10:  # Require at least 10 items
                return result
    
    return None


def fix_empty_playouts(db_path: Path, dry_run: bool = False) -> dict:
    """
    Fix channels with empty playouts by linking them to matching playlists.
    
    Args:
        db_path: Path to the database
        dry_run: If True, don't actually make changes
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "channels_checked": 0,
        "channels_with_empty_playouts": 0,
        "channels_fixed": 0,
        "playout_items_created": 0,
        "channels_no_match": [],
        "errors": 0,
    }
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Find channels with empty playouts (playout exists but no playout_items)
        cursor.execute("""
            SELECT 
                c.id as channel_id, 
                c.number, 
                c.name,
                p.id as playout_id
            FROM channels c
            JOIN playouts p ON c.id = p.channel_id
            WHERE p.is_active = 1
              AND (SELECT COUNT(*) FROM playout_items WHERE playout_id = p.id) = 0
            ORDER BY c.number
        """)
        
        empty_channels = cursor.fetchall()
        stats["channels_with_empty_playouts"] = len(empty_channels)
        
        if not empty_channels:
            logger.info("No channels with empty playouts found")
            return stats
        
        logger.info(f"Found {len(empty_channels)} channels with empty playouts")
        
        now = datetime.utcnow()
        
        for channel in empty_channels:
            stats["channels_checked"] += 1
            channel_id = channel["channel_id"]
            channel_number = channel["number"]
            channel_name = channel["name"]
            playout_id = channel["playout_id"]
            
            # Find matching playlist
            match = find_matching_playlist(cursor, channel_name)
            
            if not match:
                logger.warning(f"No matching playlist found for channel {channel_number}: {channel_name}")
                stats["channels_no_match"].append(f"{channel_number}: {channel_name}")
                continue
            
            playlist_id, playlist_name, item_count = match
            logger.info(f"Channel {channel_number} ({channel_name}) -> Playlist '{playlist_name}' ({item_count} items)")
            
            if dry_run:
                logger.info(f"  [DRY RUN] Would create {item_count} playout items")
                stats["channels_fixed"] += 1
                stats["playout_items_created"] += item_count
                continue
            
            # Get playlist items with media info
            cursor.execute("""
                SELECT 
                    pi.id, pi.media_item_id, pi.position, pi.title, pi.duration_seconds,
                    m.duration as media_duration, m.title as media_title
                FROM playlist_items pi
                LEFT JOIN media_items m ON pi.media_item_id = m.id
                WHERE pi.playlist_id = ?
                ORDER BY pi.position
            """, (playlist_id,))
            
            playlist_items = cursor.fetchall()
            
            # Create playout items
            current_time = now
            items_created = 0
            
            for pi in playlist_items:
                media_id = pi["media_item_id"]
                title = pi["media_title"] or pi["title"] or f"Item {pi['id']}"
                
                # Get duration (prefer media_items.duration, fallback to playlist_items.duration_seconds)
                duration = pi["media_duration"] or pi["duration_seconds"] or 1800  # Default 30 min
                
                finish_time = current_time + timedelta(seconds=duration)
                
                cursor.execute("""
                    INSERT INTO playout_items (
                        playout_id, media_item_id, source_url,
                        start_time, finish_time, title,
                        created_at, updated_at
                    ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?)
                """, (
                    playout_id, media_id,
                    current_time.isoformat(), finish_time.isoformat(),
                    title[:500],
                    now.isoformat(), now.isoformat()
                ))
                
                current_time = finish_time
                items_created += 1
            
            stats["channels_fixed"] += 1
            stats["playout_items_created"] += items_created
            logger.info(f"  Created {items_created} playout items for channel {channel_number}")
        
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
    print("EMPTY PLAYOUT FIX SUMMARY")
    print("=" * 60)
    print(f"Channels with empty playouts: {stats['channels_with_empty_playouts']}")
    print(f"Channels fixed: {stats['channels_fixed']}")
    print(f"Playout items created: {stats['playout_items_created']}")
    
    if stats["channels_no_match"]:
        print(f"\nChannels with no matching playlist ({len(stats['channels_no_match'])}):")
        for name in stats["channels_no_match"][:10]:
            print(f"  - {name}")
        if len(stats["channels_no_match"]) > 10:
            print(f"  ... and {len(stats['channels_no_match']) - 10} more")
    
    if dry_run:
        print(f"\n[DRY RUN] Would have fixed {stats['channels_fixed']} channels")
    else:
        print(f"\nSuccessfully fixed {stats['channels_fixed']} channels")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Fix empty playouts for StreamTV imported channels"
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
        
        stats = fix_empty_playouts(db_path, dry_run=args.dry_run)
        print_summary(stats, args.dry_run)
        
        if stats["errors"] > 0:
            sys.exit(1)
        
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
