#!/usr/bin/env python3
"""
Fix Media Item Library Associations

This script fixes the missing library_id associations in media_items,
which is preventing URL resolution from working properly.

The issue is that media_items have source='plex' and source_id like 
'/library/metadata/123' but no library_id set, so the Plex resolver
can't find the server URL and token.

Solution: Since all Plex content comes from the same server, we can:
1. Set library_id = 1 (first Plex library) for all plex items
2. Or use the plex_library_section_id to match to the correct library
"""

import sqlite3
import sys
from pathlib import Path


def get_db_path() -> Path:
    """Find the database path."""
    # Try common locations
    paths = [
        Path("/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db"),
        Path("exstreamtv.db"),
        Path("../exstreamtv.db"),
    ]
    
    for p in paths:
        if p.exists():
            return p
    
    raise FileNotFoundError("Database not found")


def fix_library_associations(db_path: Path, dry_run: bool = True) -> dict:
    """
    Fix library_id for media items.
    
    Args:
        db_path: Path to database
        dry_run: If True, don't actually update, just report
        
    Returns:
        Statistics about the fix
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {
        "total_media_items": 0,
        "items_without_library_id": 0,
        "plex_items_fixed": 0,
        "plex_libraries": [],
    }
    
    # Get total counts
    cursor.execute("SELECT COUNT(*) FROM media_items")
    stats["total_media_items"] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM media_items WHERE library_id IS NULL")
    stats["items_without_library_id"] = cursor.fetchone()[0]
    
    # Get Plex libraries
    cursor.execute("""
        SELECT id, name, server_url, plex_library_key 
        FROM plex_libraries
    """)
    plex_libs = cursor.fetchall()
    stats["plex_libraries"] = [{"id": r[0], "name": r[1], "key": r[3]} for r in plex_libs]
    
    print(f"Total media items: {stats['total_media_items']}")
    print(f"Items without library_id: {stats['items_without_library_id']}")
    print(f"Plex libraries: {len(plex_libs)}")
    
    if not plex_libs:
        print("ERROR: No Plex libraries found!")
        conn.close()
        return stats
    
    # Since we can't determine which library each item belongs to without
    # the section ID, we'll use a default approach:
    # Set library_id = 1 for all Plex items (assumes single Plex server)
    default_library_id = 1
    default_lib_info = plex_libs[0] if plex_libs else None
    
    if default_lib_info:
        print(f"\nWill use library ID {default_library_id}: {default_lib_info[1]}")
        print(f"  Server URL: {default_lib_info[2]}")
    
    # Count Plex items that need fixing
    cursor.execute("""
        SELECT COUNT(*) FROM media_items 
        WHERE source = 'plex' AND library_id IS NULL
    """)
    plex_items_count = cursor.fetchone()[0]
    print(f"\nPlex items needing fix: {plex_items_count}")
    
    if dry_run:
        print("\n[DRY RUN] No changes made. Run with --apply to fix.")
    else:
        print("\nApplying fix...")
        
        # Update all Plex items to use the first library
        cursor.execute("""
            UPDATE media_items 
            SET library_id = ?
            WHERE source = 'plex' AND library_id IS NULL
        """, (default_library_id,))
        
        stats["plex_items_fixed"] = cursor.rowcount
        conn.commit()
        
        print(f"Fixed {stats['plex_items_fixed']} Plex items")
    
    conn.close()
    return stats


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix media item library associations")
    parser.add_argument("--apply", action="store_true", help="Actually apply the fix")
    parser.add_argument("--db", type=str, help="Path to database")
    
    args = parser.parse_args()
    
    try:
        db_path = Path(args.db) if args.db else get_db_path()
        print(f"Using database: {db_path}")
        
        dry_run = not args.apply
        stats = fix_library_associations(db_path, dry_run=dry_run)
        
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"Total items: {stats['total_media_items']}")
        print(f"Items without library_id: {stats['items_without_library_id']}")
        print(f"Items fixed: {stats.get('plex_items_fixed', 0)}")
        
        if dry_run:
            print("\nTo apply fix, run: python fix_media_library_association.py --apply")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
