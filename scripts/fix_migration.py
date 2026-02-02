#!/usr/bin/env python3
"""
Fix Migration Issues and Re-import Media

This script:
1. Updates Plex library URLs to match current config
2. Clears incomplete media imports
3. Re-runs full media and schedule migration
4. Validates the results
"""

import asyncio
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def log(message: str, level: str = "INFO") -> None:
    """Print timestamped log message."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = {"INFO": "  ", "WARN": " !", "ERROR": " X", "OK": " ✓"}.get(level, "  ")
    print(f"[{timestamp}]{prefix} {message}")


def update_plex_urls(db_path: Path, new_url: str) -> None:
    """Update all Plex library URLs to match current config."""
    log(f"Updating Plex library URLs to: {new_url}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Update plex_libraries table
    cursor.execute("""
        UPDATE plex_libraries
        SET server_url = ?
        WHERE server_url != ?
    """, (new_url, new_url))
    
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    
    log(f"Updated {updated} Plex library URLs", "OK")


def clear_incomplete_data(db_path: Path) -> None:
    """
    Clear incomplete migration data to allow clean re-import.
    Keeps channels but clears media items and playout items.
    """
    log("Clearing incomplete migration data...")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get counts before deletion
    cursor.execute("SELECT COUNT(*) FROM media_items")
    media_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM playout_items")
    playout_count = cursor.fetchone()[0]
    
    log(f"Found {media_count} media items and {playout_count} playout items")
    
    # Clear playout items
    cursor.execute("DELETE FROM playout_items")
    log(f"Deleted {cursor.rowcount} playout items")
    
    # Clear playouts (need to rebuild ID mapping)
    cursor.execute("DELETE FROM playouts")
    log(f"Deleted {cursor.rowcount} playouts")
    
    # Clear program schedules
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='program_schedules'")
    if cursor.fetchone():
        cursor.execute("DELETE FROM program_schedule_items WHERE 1=1")
        log(f"Deleted {cursor.rowcount} schedule items")
        cursor.execute("DELETE FROM program_schedules WHERE 1=1")
        log(f"Deleted {cursor.rowcount} schedules")
    
    # Clear media items (will be re-imported)
    cursor.execute("DELETE FROM media_items")
    log(f"Deleted {cursor.rowcount} media items")
    
    # Clear collection items if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collection_items'")
    if cursor.fetchone():
        cursor.execute("DELETE FROM collection_items WHERE 1=1")
        deleted = cursor.rowcount
        if deleted > 0:
            log(f"Deleted {deleted} collection items")
    
    conn.commit()
    conn.close()
    
    log("Data cleared successfully", "OK")


async def run_migration(source_db: Path, target_db: Path) -> bool:
    """Run the full migration with proper media import."""
    from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
    from exstreamtv.database.connection import get_async_session
    import sqlite3
    
    log("Starting media and schedule re-import...")
    
    try:
        importer = ErsatzTVImporter(source_db, dry_run=False)
        
        # Pre-populate channel ID mapping from existing channels
        log("Pre-populating channel ID mappings...")
        conn_source = sqlite3.connect(str(source_db))
        conn_target = sqlite3.connect(str(target_db))
        
        cursor_source = conn_source.cursor()
        cursor_target = conn_target.cursor()
        
        # Get channel mappings: ErsatzTV ID -> EXStreamTV ID (match by number)
        cursor_source.execute("SELECT Id, Number FROM Channel")
        source_channels = {row[1]: row[0] for row in cursor_source.fetchall()}  # number -> id
        
        cursor_target.execute("SELECT id, number FROM channels")
        target_channels = {row[1]: row[0] for row in cursor_target.fetchall()}  # number -> id
        
        # Build ID map
        for number, source_id in source_channels.items():
            if number in target_channels:
                importer.id_maps["channels"][source_id] = target_channels[number]
        
        conn_source.close()
        conn_target.close()
        
        log(f"Mapped {len(importer.id_maps['channels'])} channels", "OK")
        
        async with get_async_session() as session:
            # Import program schedules first (playouts reference these)
            log("Step 1: Importing program schedules...")
            schedule_count = await importer.migrate_schedules(session)
            log(f"Imported {schedule_count} schedules", "OK")
            
            # Import playouts (needed for playout items)
            log("Step 2: Importing playouts...")
            playout_count = await importer.migrate_playouts(session)
            log(f"Imported {playout_count} playouts", "OK")
            
            # Import media items (critical for playout items)
            log("Step 3: Importing media items...")
            media_count = await importer.migrate_media_items(session)
            log(f"Imported {media_count} media items", "OK")
            
            # Import collections
            log("Step 4: Importing collections...")
            collection_count = await importer.migrate_collections(session)
            log(f"Imported {collection_count} collections", "OK")
            
            # Import playout items (now that everything exists)
            log("Step 5: Importing playout items...")
            playout_item_count = await importer.migrate_playout_items(session)
            log(f"Imported {playout_item_count} playout items", "OK")
            
            # Commit all changes
            await session.commit()
        
        # Validate results
        conn = sqlite3.connect(str(target_db))
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM media_items")
        final_media = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM playout_items")
        final_playout = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT c.number, c.name, COUNT(pi.id) as items
            FROM channels c
            LEFT JOIN playouts p ON p.channel_id = c.id
            LEFT JOIN playout_items pi ON pi.playout_id = p.id
            GROUP BY c.id
            HAVING items = 0
            ORDER BY c.number
        """)
        empty_channels = cursor.fetchall()
        
        conn.close()
        
        log("")
        log("=" * 60)
        log("Migration Complete!", "OK")
        log("=" * 60)
        log(f"Media items: {final_media}")
        log(f"Playout items: {final_playout}")
        
        if empty_channels:
            log("")
            log(f"Channels still without content: {len(empty_channels)}", "WARN")
            for ch_num, ch_name, _ in empty_channels[:5]:
                log(f"  - Channel {ch_num}: {ch_name}", "WARN")
            if len(empty_channels) > 5:
                log(f"  ... and {len(empty_channels) - 5} more", "WARN")
        else:
            log("")
            log("All channels now have schedule content!", "OK")
        
        return len(empty_channels) == 0
        
    except Exception as e:
        log(f"Migration failed: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def main() -> int:
    """Main entry point."""
    import yaml
    
    # Paths
    workspace = Path(__file__).parent.parent
    config_path = workspace / "config.yaml"
    target_db = workspace / "exstreamtv.db"
    source_db = Path.home() / "Library/Application Support/ersatztv/ersatztv.sqlite3"
    
    if not target_db.exists():
        log(f"Target database not found: {target_db}", "ERROR")
        return 1
    
    if not source_db.exists():
        log(f"Source database not found: {source_db}", "ERROR")
        return 1
    
    log("=" * 60)
    log("ErsatzTV Migration Fix")
    log("=" * 60)
    log(f"Source: {source_db}")
    log(f"Target: {target_db}")
    log("")
    
    # Read Plex URL from config
    plex_url = None
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
            plex_url = config.get("libraries", {}).get("plex", {}).get("url")
            if not plex_url:
                plex_url = config.get("plex", {}).get("url")
    
    if not plex_url:
        log("Could not find Plex URL in config.yaml", "ERROR")
        log("Please configure plex.url or libraries.plex.url", "ERROR")
        return 1
    
    log(f"Plex server URL: {plex_url}")
    log("")
    
    # Step 1: Update Plex URLs
    update_plex_urls(target_db, plex_url)
    log("")
    
    # Step 2: Clear incomplete data
    clear_incomplete_data(target_db)
    log("")
    
    # Step 3: Re-run migration
    success = asyncio.run(run_migration(source_db, target_db))
    
    if success:
        log("")
        log("Migration fix completed successfully!", "OK")
        log("Please restart EXStreamTV to see the changes.")
        return 0
    else:
        log("")
        log("Migration completed with warnings", "WARN")
        log("Some channels may still need manual configuration.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
