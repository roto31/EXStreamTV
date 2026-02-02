# StreamTV Migration - Quick Start Guide

**Last Updated**: 2026-01-26  
**Source**: `/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db` (9.2 MB)  
**Target**: `/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db`

## What Will Be Migrated

| Item | Count | Notes |
|------|-------|-------|
| **Channels** | 14 | Full ErsatzTV-compatible settings |
| **Media Items** | 5,471 | 91.5% Archive.org, 6.2% YouTube, 2.3% Plex |
| **Collections** | 196 | Will become playlists in EXStreamTV |
| **Playlists** | 18 | Native playlists |
| **Total Playlists** | 214 | Combined collections + playlists |
| **Collection Items** | 4,697 | Items within collections |
| **Playlist Items** | 4,147 | Items within playlists |
| **Total Items** | 8,844 | All playlist/collection items |
| **Playouts** | 14 | Auto-generated for each channel |

**Estimated Time**: 15-25 minutes

## Quick Migration (3 Steps)

### 1. Backup Databases

```bash
# Backup StreamTV
cp "/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db" \
   "/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db.backup"

# Backup EXStreamTV (if exists)
cp "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db" \
   "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db.backup" 2>/dev/null || true
```

### 2. Run Migration

```bash
cd "/Users/roto1231/Documents/XCode Projects/EXStreamTV"

python3 -c "
import asyncio
from exstreamtv.importers.streamtv_importer_custom import StreamTVCustomImporter
from exstreamtv.database.connection import get_async_session

async def migrate():
    importer = StreamTVCustomImporter(
        '/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db',
        dry_run=False
    )
    async with get_async_session() as session:
        stats = await importer.migrate_all(session)
    print(f'✓ Migrated {stats.channels} channels, {stats.media_items} media items')
    print(f'✓ Created {stats.playlists + stats.collections} playlists with {stats.playlist_items + stats.collection_items} items')
    print(f'✓ Errors: {stats.errors}, Warnings: {stats.warnings}')

asyncio.run(migrate())
"
```

### 3. Verify Results

```bash
sqlite3 "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db" "
SELECT 'channels' as table_name, COUNT(*) as count FROM channels
UNION ALL SELECT 'media_items', COUNT(*) FROM media_items
UNION ALL SELECT 'playlists', COUNT(*) FROM playlists
UNION ALL SELECT 'playlist_items', COUNT(*) FROM playlist_items
UNION ALL SELECT 'playouts', COUNT(*) FROM playouts;
"
```

**Expected Results**:
```
channels|14
media_items|5471
playlists|214
playlist_items|8844
playouts|14
```

## Detailed Documentation

- **Complete Plan**: [`.cursor/plans/streamtv_migration_plan_*.plan.md`](.cursor/plans/)
- **Schema Mapping**: [`docs/StreamTV_Schema_Mapping.md`](docs/StreamTV_Schema_Mapping.md)
- **Custom Importer**: [`exstreamtv/importers/streamtv_importer_custom.py`](exstreamtv/importers/streamtv_importer_custom.py)

## Key Features

✅ **Metadata Extraction**: Automatically extracts Archive.org, YouTube, and Plex metadata from JSON  
✅ **ID Management**: Collections use +10000 offset to avoid ID collisions with playlists  
✅ **Denormalization**: Playlist items include cached media metadata for performance  
✅ **UUID Generation**: Auto-generates unique_id for all channels  
✅ **Default Playouts**: Creates continuous flood playouts for all channels  

## Troubleshooting

**Problem**: "No such table" error  
**Solution**: Verify source database path is correct

**Problem**: Duplicate key error  
**Solution**: Delete existing EXStreamTV database and re-run migration

**Problem**: Missing media items  
**Solution**: Check foreign key constraints in source database

## Rollback

If migration fails:

```bash
# Restore EXStreamTV backup
rm "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db"
cp "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db.backup" \
   "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db"
```

## Post-Migration

1. **Start EXStreamTV**: `python -m exstreamtv`
2. **Access Web UI**: http://localhost:8411
3. **Test Channels**: Verify 2-3 channels play correctly
4. **Check Playlists**: Confirm all 214 playlists are visible
5. **Optimize Database**: Run `VACUUM` and `ANALYZE` in SQLite
