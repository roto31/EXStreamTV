#!/usr/bin/env python3
"""
Fix library_id for Plex media items.

This script maps MediaItem.plex_library_section_id to PlexLibrary.plex_library_key
and updates MediaItem.library_id accordingly.

Run: python3 scripts/fix_library_ids.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exstreamtv.database import get_sync_session
from exstreamtv.database.models import MediaItem
from exstreamtv.database.models.library import PlexLibrary


def main():
    print("=" * 60)
    print("Plex Library ID Fix Script")
    print("=" * 60)
    
    session = get_sync_session()
    
    try:
        # Get all PlexLibrary records
        plex_libraries = session.query(PlexLibrary).all()
        print(f"\nFound {len(plex_libraries)} Plex libraries:")
        
        # Build mapping: plex_library_key (as int) -> PlexLibrary.id
        key_to_id = {}
        for lib in plex_libraries:
            try:
                key = int(lib.plex_library_key)
                key_to_id[key] = lib.id
                print(f"  - Library ID {lib.id}: section_key={lib.plex_library_key} -> '{lib.plex_library_name}'")
            except (ValueError, TypeError):
                print(f"  ! Could not parse plex_library_key for library {lib.id}: {lib.plex_library_key}")
        
        print(f"\nKey to ID mapping: {key_to_id}")
        
        # Check current state
        total_plex = session.query(MediaItem).filter(MediaItem.source == "plex").count()
        null_library_id = session.query(MediaItem).filter(
            MediaItem.source == "plex",
            MediaItem.library_id == None
        ).count()
        
        print(f"\nCurrent state:")
        print(f"  - Total Plex media items: {total_plex}")
        print(f"  - Items with NULL library_id: {null_library_id}")
        
        # Query items that can be fixed
        items = session.query(MediaItem).filter(
            MediaItem.source == "plex",
            MediaItem.library_id == None,
            MediaItem.plex_library_section_id != None
        ).all()
        
        print(f"  - Items with plex_library_section_id that can be fixed: {len(items)}")
        
        if len(items) == 0:
            # Check if plex_library_section_id is populated
            section_ids = session.query(MediaItem.plex_library_section_id).filter(
                MediaItem.source == "plex"
            ).distinct().all()
            section_ids = [s[0] for s in section_ids]
            print(f"\n  Available plex_library_section_id values in DB: {section_ids}")
            
            if all(s is None for s in section_ids):
                print("\n  WARNING: All plex_library_section_id values are NULL!")
                print("  This means media items were imported without section info.")
                print("  You may need to re-scan your Plex libraries.")
                return
        
        # Update each item
        total_updated = 0
        section_counts = {}
        
        for item in items:
            section_id = item.plex_library_section_id
            if section_id in key_to_id:
                item.library_id = key_to_id[section_id]
                total_updated += 1
                section_counts[section_id] = section_counts.get(section_id, 0) + 1
        
        print(f"\nUpdating {total_updated} items...")
        for section_id, count in section_counts.items():
            lib_id = key_to_id.get(section_id)
            print(f"  - Section {section_id} -> library_id {lib_id}: {count} items")
        
        session.commit()
        
        print(f"\n✅ Fix complete: updated {total_updated} media items")
        
        # Verify
        remaining_null = session.query(MediaItem).filter(
            MediaItem.source == "plex",
            MediaItem.library_id == None
        ).count()
        print(f"\nVerification: {remaining_null} items still have NULL library_id")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()
