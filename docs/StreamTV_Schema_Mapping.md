# StreamTV to EXStreamTV Schema Mapping Documentation

**Date**: 2026-01-26  
**Source Database**: `/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db`  
**Database Size**: 9.2 MB  
**Total Records**: 14,315 (5,471 media + 4,697 collection items + 4,147 playlist items)

## Executive Summary

StreamTV uses a schema that is **very close** to EXStreamTV's target schema, with some key differences:

1. **Collections vs Playlists**: StreamTV has BOTH concepts (EXStreamTV treats them similarly)
2. **Embedded Metadata**: Source-specific data stored in JSON `meta_data` field
3. **Rich Channel Configuration**: Comprehensive channel settings already present
4. **Empty Schedules**: No schedule data (can be generated post-migration)

## Media Source Breakdown

| Source | Count | Percentage | Notes |
|--------|-------|------------|-------|
| **Archive.org** | 5,004 | 91.5% | Primary content source, rich metadata in JSON |
| **YouTube** | 338 | 6.2% | Video IDs in source_id field |
| **Plex** | 128 | 2.3% | Local media library integration |
| **PBS** | 1 | <0.1% | Single test item |
| **TOTAL** | 5,471 | 100% | |

## Table-by-Table Schema Mapping

### 1. Channels Table

**StreamTV Schema** (28 columns):
```sql
CREATE TABLE channels (
    id INTEGER PRIMARY KEY,
    number VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    group VARCHAR,
    enabled BOOLEAN,
    logo_path VARCHAR,
    created_at DATETIME,
    updated_at DATETIME,
    playout_mode TEXT DEFAULT 'continuous',
    ffmpeg_profile_id INTEGER,
    watermark_id INTEGER,
    streaming_mode TEXT DEFAULT 'transport_stream_hybrid',
    transcode_mode TEXT DEFAULT 'on_demand',
    subtitle_mode TEXT DEFAULT 'none',
    preferred_audio_language_code TEXT,
    preferred_audio_title TEXT,
    preferred_subtitle_language_code TEXT,
    stream_selector_mode TEXT DEFAULT 'default',
    stream_selector TEXT,
    music_video_credits_mode TEXT DEFAULT 'none',
    music_video_credits_template TEXT,
    song_video_mode TEXT DEFAULT 'default',
    idle_behavior TEXT DEFAULT 'stop_on_disconnect',
    playout_source TEXT DEFAULT 'generated',
    mirror_source_channel_id INTEGER,
    playout_offset INTEGER,
    show_in_epg INTEGER DEFAULT 1,
    is_yaml_source INTEGER DEFAULT 0,
    transcode_profile TEXT
);
```

**EXStreamTV Target** ([`exstreamtv/database/models/channel.py`](exstreamtv/database/models/channel.py)):
```python
class Channel(Base):
    id: Mapped[int]
    unique_id: Mapped[str | None]  # ⚠️ NOT IN STREAMTV - must generate
    number: Mapped[str]
    name: Mapped[str]
    sort_number: Mapped[float | None]  # ⚠️ NOT IN STREAMTV - optional
    categories: Mapped[str | None]  # ⚠️ NOT IN STREAMTV - optional
    group: Mapped[str | None]
    enabled: Mapped[bool]
    logo_url: Mapped[str | None]  # ⚠️ StreamTV uses logo_path
    logo_path: Mapped[str | None]  # ✅ MATCH
    playout_mode: Mapped[str]
    streaming_mode: Mapped[str]
    ffmpeg_profile_id: Mapped[int | None]
    fallback_filler_id: Mapped[int | None]  # ⚠️ NOT IN STREAMTV
    watermark_id: Mapped[int | None]
    transcode_mode: Mapped[str | None]
    subtitle_mode: Mapped[str | None]
    preferred_audio_language_code: Mapped[str | None]
    preferred_audio_title: Mapped[str | None]
    preferred_subtitle_language_code: Mapped[str | None]
    stream_selector_mode: Mapped[str | None]
    stream_selector: Mapped[str | None]
    music_video_credits_mode: Mapped[str | None]
    music_video_credits_template: Mapped[str | None]
    song_video_mode: Mapped[str | None]
    idle_behavior: Mapped[str | None]
    playout_source: Mapped[str | None]
    mirror_source_channel_id: Mapped[int | None]
    playout_offset: Mapped[int | None]
    show_in_epg: Mapped[bool]
    # ... additional ErsatzTV compatibility fields
```

**Field Mapping**:
```python
CHANNEL_MAPPING = {
    # Direct mappings (same name, same type)
    "id": "id",
    "number": "number",
    "name": "name",
    "group": "group",
    "enabled": "enabled",
    "logo_path": "logo_path",
    "playout_mode": "playout_mode",
    "ffmpeg_profile_id": "ffmpeg_profile_id",
    "watermark_id": "watermark_id",
    "streaming_mode": "streaming_mode",
    "transcode_mode": "transcode_mode",
    "subtitle_mode": "subtitle_mode",
    "preferred_audio_language_code": "preferred_audio_language_code",
    "preferred_audio_title": "preferred_audio_title",
    "preferred_subtitle_language_code": "preferred_subtitle_language_code",
    "stream_selector_mode": "stream_selector_mode",
    "stream_selector": "stream_selector",
    "music_video_credits_mode": "music_video_credits_mode",
    "music_video_credits_template": "music_video_credits_template",
    "song_video_mode": "song_video_mode",
    "idle_behavior": "idle_behavior",
    "playout_source": "playout_source",
    "mirror_source_channel_id": "mirror_source_channel_id",
    "playout_offset": "playout_offset",
    "show_in_epg": "show_in_epg",
    "is_yaml_source": "is_yaml_source",
    
    # Special handling required
    "unique_id": lambda row: str(uuid.uuid4()),  # Generate UUID
}
```

**Migration Notes**:
- ✅ **98% compatible** - almost perfect match!
- ⚠️ Generate `unique_id` (UUID) for each channel
- ⚠️ `logo_path` is local path, may need to verify accessibility
- ✅ All ErsatzTV-compatible fields present

---

### 2. Media Items Table

**StreamTV Schema** (20 columns):
```sql
CREATE TABLE media_items (
    id INTEGER PRIMARY KEY,
    source VARCHAR(11) NOT NULL,      -- 'YOUTUBE', 'ARCHIVE_ORG', 'PLEX', 'PBS'
    source_id VARCHAR NOT NULL,        -- External ID (video_id, identifier, etc.)
    url VARCHAR NOT NULL,              -- Playback URL
    title VARCHAR NOT NULL,
    description TEXT,
    duration INTEGER,                  -- Duration in seconds
    thumbnail VARCHAR,
    uploader VARCHAR,
    upload_date VARCHAR,
    view_count INTEGER,
    meta_data TEXT,                    -- ⚠️ JSON with source-specific metadata
    created_at DATETIME,
    updated_at DATETIME,
    series_title VARCHAR,
    episode_title VARCHAR,
    season_number INTEGER,
    episode_number INTEGER,
    episode_air_date VARCHAR,
    genres TEXT                        -- ⚠️ JSON array
);
```

**EXStreamTV Target** ([`exstreamtv/database/models/media.py`](exstreamtv/database/models/media.py)):
```python
class MediaItem(Base):
    id: Mapped[int]
    media_type: Mapped[str]  # ⚠️ NOT IN STREAMTV - infer from source
    source: Mapped[str]  # ✅ MATCH (lowercase in EXStreamTV)
    source_id: Mapped[str | None]
    url: Mapped[str | None]
    library_source: Mapped[str]  # ⚠️ NOT IN STREAMTV - default 'local'
    library_id: Mapped[int | None]
    external_id: Mapped[str | None]  # ⚠️ NOT IN STREAMTV
    title: Mapped[str]
    sort_title: Mapped[str | None]
    original_title: Mapped[str | None]
    description: Mapped[str | None]  # ✅ MATCH
    plot: Mapped[str | None]  # ⚠️ Alias for description
    duration: Mapped[int | None]  # ✅ MATCH
    thumbnail: Mapped[str | None]  # ✅ MATCH
    uploader: Mapped[str | None]  # ✅ MATCH
    upload_date: Mapped[str | None]  # ✅ MATCH
    view_count: Mapped[int | None]  # ✅ MATCH
    meta_data: Mapped[str | None]  # ✅ MATCH (JSON)
    show_title: Mapped[str | None]  # ⚠️ StreamTV: series_title
    season_number: Mapped[int | None]  # ✅ MATCH
    episode_number: Mapped[int | None]  # ✅ MATCH
    episode_count: Mapped[int]  # ⚠️ NOT IN STREAMTV - default 1
    year: Mapped[int | None]  # ⚠️ NOT IN STREAMTV - extract from meta_data
    release_date: Mapped[datetime | None]
    genres: Mapped[str | None]  # ✅ MATCH (JSON)
    
    # Source-specific fields (extract from meta_data JSON)
    youtube_video_id: Mapped[str | None]
    youtube_channel_id: Mapped[str | None]
    youtube_channel_name: Mapped[str | None]
    youtube_tags: Mapped[str | None]
    youtube_category: Mapped[str | None]
    
    archive_org_identifier: Mapped[str | None]
    archive_org_filename: Mapped[str | None]
    archive_org_creator: Mapped[str | None]
    archive_org_collection: Mapped[str | None]
    archive_org_subject: Mapped[str | None]
    
    plex_rating_key: Mapped[str | None]
    plex_guid: Mapped[str | None]
```

**Field Mapping**:
```python
MEDIA_ITEM_MAPPING = {
    # Direct mappings
    "id": "id",
    "source": lambda s: s.lower(),  # Convert 'YOUTUBE' -> 'youtube'
    "source_id": "source_id",
    "url": "url",
    "title": "title",
    "description": "description",
    "duration": "duration",
    "thumbnail": "thumbnail",
    "uploader": "uploader",
    "upload_date": "upload_date",
    "view_count": "view_count",
    "meta_data": "meta_data",
    "genres": "genres",
    
    # Renamed fields
    "series_title": "show_title",
    "episode_title": "episode_title",  # Store in meta or custom field
    "season_number": "season_number",
    "episode_number": "episode_number",
    
    # Generated/inferred fields
    "media_type": lambda row: infer_media_type(row),
    "library_source": lambda row: row["source"].lower(),
    "episode_count": lambda: 1,
    "is_available": lambda: True,
    
    # Extract from meta_data JSON
    "year": lambda row: extract_year_from_metadata(row),
}

def infer_media_type(row):
    """Infer media type from source and metadata."""
    if row.get("episode_number"):
        return "episode"
    if row.get("series_title"):
        return "episode"
    return "movie"  # Default for Archive.org content
```

**Archive.org Metadata Extraction**:
```python
def extract_archive_org_metadata(media_item, meta_json):
    """Extract Archive.org fields from meta_data JSON."""
    meta = json.loads(meta_json)
    
    return {
        "archive_org_identifier": meta.get("identifier"),
        "archive_org_filename": meta.get("video_files", [{}])[0].get("name"),
        "archive_org_creator": meta.get("creator"),
        "archive_org_collection": json.dumps(meta.get("collection", [])),
        "archive_org_subject": json.dumps(meta.get("subject", [])),
        "year": meta.get("year"),
        "duration": meta.get("runtime"),  # Override if present
    }
```

**YouTube Metadata Extraction**:
```python
def extract_youtube_metadata(media_item, meta_json):
    """Extract YouTube fields from meta_data JSON."""
    meta = json.loads(meta_json) if meta_json else {}
    
    return {
        "youtube_video_id": media_item.source_id,  # Already in source_id
        "youtube_channel_id": meta.get("channel_id"),
        "youtube_channel_name": meta.get("channel"),
        "youtube_tags": json.dumps(meta.get("tags", [])),
        "youtube_category": meta.get("category"),
        "youtube_like_count": meta.get("like_count"),
    }
```

**Migration Notes**:
- ✅ **80% compatible** - good structural match
- ⚠️ Must parse `meta_data` JSON to extract source-specific fields
- ⚠️ 5,004 Archive.org items need metadata extraction
- ⚠️ 338 YouTube items need metadata extraction
- ✅ Genres already in JSON format

---

### 3. Collections Table

**StreamTV Schema** (7 columns):
```sql
CREATE TABLE collections (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    collection_type TEXT DEFAULT 'manual',  -- 'manual', 'smart', 'static'
    search_query TEXT                       -- For smart collections
);
```

**EXStreamTV Target** ([`exstreamtv/database/models/playlist.py`](exstreamtv/database/models/playlist.py)):
```python
class Playlist(Base):  # Collections map to Playlists in EXStreamTV
    id: Mapped[int]
    name: Mapped[str]
    description: Mapped[str | None]
    group_id: Mapped[int | None]  # ⚠️ NOT IN STREAMTV
    source_type: Mapped[str]  # ⚠️ NOT IN STREAMTV - default 'mixed'
    source_url: Mapped[str | None]
    thumbnail_url: Mapped[str | None]
    is_enabled: Mapped[bool]  # ⚠️ NOT IN STREAMTV - default True
    shuffle: Mapped[bool]  # ⚠️ NOT IN STREAMTV - default False
    loop: Mapped[bool]  # ⚠️ NOT IN STREAMTV - default True
    collection_type: Mapped[str]  # ✅ MATCH
    search_query: Mapped[str | None]  # ✅ MATCH
```

**Field Mapping**:
```python
COLLECTION_MAPPING = {
    # Direct mappings
    "id": lambda row: row["id"] + 10000,  # Offset to avoid collision with playlists
    "name": "name",
    "description": "description",
    "collection_type": "collection_type",
    "search_query": "search_query",
    
    # Default values
    "source_type": lambda: "mixed",
    "is_enabled": lambda: True,
    "shuffle": lambda: False,
    "loop": lambda: True,
}
```

**Migration Strategy**:
- ✅ **Collections → Playlists**: Treat StreamTV collections as EXStreamTV playlists
- ⚠️ Use ID offset (add 10000) to avoid conflicts with StreamTV playlists
- ⚠️ StreamTV has **196 collections** + **18 playlists** = **214 total playlists** in EXStreamTV

---

### 4. Collection Items Table

**StreamTV Schema** (5 columns):
```sql
CREATE TABLE collection_items (
    id INTEGER PRIMARY KEY,
    collection_id INTEGER NOT NULL,
    media_item_id INTEGER NOT NULL,
    order INTEGER,
    created_at DATETIME
);
```

**EXStreamTV Target**:
```python
class PlaylistItem(Base):
    id: Mapped[int]
    playlist_id: Mapped[int]  # ⚠️ StreamTV: collection_id
    media_item_id: Mapped[int | None]
    source_url: Mapped[str | None]  # ⚠️ NOT IN STREAMTV
    title: Mapped[str]  # ⚠️ NOT IN STREAMTV - get from media_item
    duration_seconds: Mapped[int | None]  # ⚠️ NOT IN STREAMTV - get from media_item
    thumbnail_url: Mapped[str | None]  # ⚠️ NOT IN STREAMTV - get from media_item
    position: Mapped[int]  # ⚠️ StreamTV: order
    in_point_seconds: Mapped[int | None]
    out_point_seconds: Mapped[int | None]
    is_enabled: Mapped[bool]  # ⚠️ NOT IN STREAMTV - default True
```

**Field Mapping**:
```python
COLLECTION_ITEM_MAPPING = {
    "playlist_id": lambda row: row["collection_id"] + 10000,  # Match offset
    "media_item_id": "media_item_id",
    "position": "order",
    "is_enabled": lambda: True,
    
    # Denormalize from media_items table (for performance)
    "title": lambda row, media_cache: media_cache[row["media_item_id"]].title,
    "duration_seconds": lambda row, media_cache: media_cache[row["media_item_id"]].duration,
    "thumbnail_url": lambda row, media_cache: media_cache[row["media_item_id"]].thumbnail,
}
```

**Migration Notes**:
- ⚠️ **4,697 collection items** to migrate
- ⚠️ Must join with media_items to populate denormalized fields
- ⚠️ Apply ID offset to collection_id → playlist_id

---

### 5. Playlists Table

**StreamTV Schema** (6 columns):
```sql
CREATE TABLE playlists (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    channel_id INTEGER,  # ⚠️ Association with channel
    created_at DATETIME,
    updated_at DATETIME
);
```

**EXStreamTV Target**: Same as Collections (Playlist model)

**Field Mapping**:
```python
PLAYLIST_MAPPING = {
    # Direct mappings (no ID offset for playlists)
    "id": "id",
    "name": "name",
    "description": "description",
    
    # Defaults
    "source_type": lambda: "mixed",
    "collection_type": lambda: "static",
    "is_enabled": lambda: True,
    "shuffle": lambda: False,
    "loop": lambda: True,
}
```

**Migration Notes**:
- ✅ **18 playlists** to migrate
- ⚠️ `channel_id` association not in EXStreamTV Playlist model (handle separately)

---

### 6. Playlist Items Table

**StreamTV Schema** (6 columns):
```sql
CREATE TABLE playlist_items (
    id INTEGER PRIMARY KEY,
    playlist_id INTEGER NOT NULL,
    media_item_id INTEGER NOT NULL,
    order INTEGER,
    start_time DATETIME,  # ⚠️ Scheduled start time (optional)
    created_at DATETIME
);
```

**EXStreamTV Target**: Same as CollectionItem (PlaylistItem model)

**Field Mapping**:
```python
PLAYLIST_ITEM_MAPPING = {
    # Direct mappings (no ID offset)
    "playlist_id": "playlist_id",
    "media_item_id": "media_item_id",
    "position": "order",
    "is_enabled": lambda: True,
    
    # Denormalize from media_items
    "title": lambda row, media_cache: media_cache[row["media_item_id"]].title,
    "duration_seconds": lambda row, media_cache: media_cache[row["media_item_id"]].duration,
    "thumbnail_url": lambda row, media_cache: media_cache[row["media_item_id"]].thumbnail,
}
```

**Migration Notes**:
- ✅ **4,147 playlist items** to migrate
- ⚠️ `start_time` field not used in EXStreamTV PlaylistItem (can store in playout timeline)

---

### 7. Schedules Table

**StreamTV Schema** (15 columns):
```sql
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    playlist_id INTEGER,
    collection_id INTEGER,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    repeat BOOLEAN,
    created_at DATETIME,
    updated_at DATETIME,
    name TEXT NOT NULL DEFAULT '',
    keep_multi_part_episodes_together BOOLEAN NOT NULL DEFAULT 0,
    treat_collections_as_shows BOOLEAN NOT NULL DEFAULT 0,
    shuffle_schedule_items BOOLEAN NOT NULL DEFAULT 0,
    random_start_point BOOLEAN NOT NULL DEFAULT 0,
    is_yaml_source BOOLEAN NOT NULL DEFAULT 0
);
```

**EXStreamTV Target** ([`exstreamtv/database/models/schedule.py`](exstreamtv/database/models/schedule.py)):
```python
class ProgramSchedule(Base):
    id: Mapped[int]
    name: Mapped[str]
    keep_multi_part_episodes: Mapped[bool]  # ⚠️ StreamTV: keep_multi_part_episodes_together
    treat_collections_as_shows: Mapped[bool]
    shuffle_schedule_items: Mapped[bool]
    random_start_point: Mapped[bool]
    fixed_start_time_behavior: Mapped[str]  # ⚠️ NOT IN STREAMTV - default 'fill'
```

**Migration Notes**:
- ⚠️ **0 schedules** in StreamTV database (can skip or create defaults)
- ⚠️ StreamTV schedules include channel/playlist association (EXStreamTV uses Playout)
- ⚠️ If migrating: create corresponding Playout records

---

### 8. Schedule Items Table

**StreamTV Schema** (38 columns - very comprehensive!):
```sql
CREATE TABLE schedule_items (
    id INTEGER PRIMARY KEY,
    schedule_id INTEGER NOT NULL,
    index INTEGER NOT NULL,
    start_type VARCHAR(7) NOT NULL,
    start_time DATETIME,
    fixed_start_time_behavior VARCHAR(17),
    collection_type VARCHAR(16) NOT NULL,
    collection_id INTEGER,
    media_item_id INTEGER,
    playlist_id INTEGER,
    search_title VARCHAR,
    search_query VARCHAR,
    playback_order VARCHAR(13) NOT NULL,
    playout_mode VARCHAR(8) NOT NULL,
    multiple_mode VARCHAR(8),
    multiple_count INTEGER,
    playout_duration_hours INTEGER NOT NULL,
    playout_duration_minutes INTEGER NOT NULL,
    fill_with_group_mode VARCHAR,
    tail_mode VARCHAR,
    discard_to_fill_attempts INTEGER,
    custom_title VARCHAR,
    guide_mode VARCHAR(6) NOT NULL,
    pre_roll_filler_id INTEGER,
    mid_roll_filler_id INTEGER,
    post_roll_filler_id INTEGER,
    tail_filler_id INTEGER,
    fallback_filler_id INTEGER,
    watermark_id INTEGER,
    preferred_audio_language VARCHAR,
    preferred_audio_title VARCHAR,
    preferred_subtitle_language VARCHAR,
    subtitle_mode VARCHAR,
    created_at DATETIME,
    updated_at DATETIME,
    tail_filler_collection_id INTEGER,
    plex_show_key TEXT,
    plex_season_key TEXT,
    plex_artist_key TEXT
);
```

**EXStreamTV Target**: Maps to `ProgramScheduleItem` model

**Migration Notes**:
- ⚠️ **0 schedule items** in StreamTV (can skip)
- ✅ Schema is ErsatzTV-compatible (StreamTV borrowed from ErsatzTV)

---

## Migration Implementation Strategy

### Phase 1: Create Custom StreamTV Importer

Create `exstreamtv/importers/streamtv_importer_custom.py`:

```python
class StreamTVCustomImporter(StreamTVImporter):
    """
    Custom StreamTV importer that handles:
    - Collections + Playlists → Playlists
    - Embedded metadata extraction
    - ID offsetting for collections
    """
    
    async def migrate_all(self, session):
        # 1. Channels (14 records)
        await self.migrate_channels(session)
        
        # 2. Media Items (5,471 records) with metadata extraction
        await self.migrate_media_items_with_metadata(session)
        
        # 3. Collections → Playlists (196 records, ID offset +10000)
        await self.migrate_collections_as_playlists(session)
        
        # 4. Playlists → Playlists (18 records, no offset)
        await self.migrate_playlists(session)
        
        # 5. Collection Items → Playlist Items (4,697 records)
        await self.migrate_collection_items(session)
        
        # 6. Playlist Items → Playlist Items (4,147 records)
        await self.migrate_playlist_items(session)
        
        # 7. Create default playouts for channels (if needed)
        await self.create_default_playouts(session)
        
        await session.commit()
```

### Phase 2: Metadata Extraction Functions

```python
async def migrate_media_items_with_metadata(self, session):
    """Migrate media items and extract embedded metadata."""
    rows = self._get_source_rows("media_items")
    
    for row in rows:
        # Base media item
        media_item = MediaItem(
            title=row["title"],
            source=row["source"].lower(),
            source_id=row["source_id"],
            url=row["url"],
            duration=row["duration"],
            # ... other fields
        )
        
        # Extract source-specific metadata
        meta_json = row.get("meta_data")
        if meta_json and row["source"] == "ARCHIVE_ORG":
            metadata = extract_archive_org_metadata(row, meta_json)
            for key, value in metadata.items():
                setattr(media_item, key, value)
        elif meta_json and row["source"] == "YOUTUBE":
            metadata = extract_youtube_metadata(row, meta_json)
            for key, value in metadata.items():
                setattr(media_item, key, value)
        
        session.add(media_item)
        await session.flush()
        self.id_maps["media_items"][row["id"]] = media_item.id
```

### Phase 3: Collections ID Offsetting

```python
async def migrate_collections_as_playlists(self, session):
    """Migrate collections as playlists with ID offset."""
    ID_OFFSET = 10000
    
    rows = self._get_source_rows("collections")
    
    for row in rows:
        playlist = Playlist(
            name=row["name"],
            description=row["description"],
            collection_type=row.get("collection_type", "static"),
            search_query=row.get("search_query"),
            source_type="mixed",
            is_enabled=True,
        )
        
        session.add(playlist)
        await session.flush()
        
        # Map with offset
        self.id_maps["collections"][row["id"]] = playlist.id
```

### Phase 4: Denormalized Fields

```python
async def migrate_collection_items(self, session):
    """Migrate collection items with denormalized media fields."""
    
    # Pre-load media items for performance
    media_cache = await self._build_media_cache(session)
    
    rows = self._get_source_rows("collection_items")
    
    for row in rows:
        media_id = row["media_item_id"]
        media = media_cache.get(media_id)
        
        if not media:
            self.stats.warnings += 1
            continue
        
        playlist_item = PlaylistItem(
            playlist_id=self.id_maps["collections"][row["collection_id"]],
            media_item_id=self.id_maps["media_items"][media_id],
            position=row.get("order", 0),
            title=media.title,
            duration_seconds=media.duration,
            thumbnail_url=media.thumbnail,
            is_enabled=True,
        )
        
        session.add(playlist_item)
```

## Migration Execution Plan

### Step 1: Pre-Flight Checks
```bash
# Verify source database
ls -lh "/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db"

# Check table counts
sqlite3 "/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db" "
SELECT 'channels', COUNT(*) FROM channels
UNION ALL SELECT 'media_items', COUNT(*) FROM media_items
UNION ALL SELECT 'collections', COUNT(*) FROM collections
UNION ALL SELECT 'playlists', COUNT(*) FROM playlists;"
```

### Step 2: Backup
```bash
# Backup StreamTV
cp "/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db" \
   "/Users/roto1231/Documents/XCode Projects/StreamTV/streamtv.db.backup.$(date +%Y%m%d_%H%M%S)"

# Backup EXStreamTV
cp "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db" \
   "/Users/roto1231/Documents/XCode Projects/EXStreamTV/exstreamtv.db.backup.$(date +%Y%m%d_%H%M%S)"
```

### Step 3: Run Migration
```bash
cd "/Users/roto1231/Documents/XCode Projects/EXStreamTV"

# Dry run first
python scripts/migrate_from_streamtv.py \
    --source "/Users/roto1231/Documents/XCode Projects/StreamTV" \
    --dry-run

# Full migration
python scripts/migrate_from_streamtv.py \
    --source "/Users/roto1231/Documents/XCode Projects/StreamTV"
```

### Step 4: Validation
```bash
# Check row counts
sqlite3 exstreamtv.db "
SELECT 'channels', COUNT(*) FROM channels
UNION ALL SELECT 'media_items', COUNT(*) FROM media_items
UNION ALL SELECT 'playlists', COUNT(*) FROM playlists
UNION ALL SELECT 'playlist_items', COUNT(*) FROM playlist_items;"

# Expected results:
# channels: 14
# media_items: 5,471
# playlists: 214 (196 collections + 18 playlists)
# playlist_items: 8,844 (4,697 + 4,147)
```

## Success Criteria

✅ **14 channels** migrated with all settings preserved  
✅ **5,471 media items** migrated with source-specific metadata extracted  
✅ **214 playlists** created (196 collections + 18 playlists)  
✅ **8,844 playlist items** migrated with proper foreign keys  
✅ **No orphaned records** (all foreign keys resolve)  
✅ **Archive.org metadata** extracted for 5,004 items  
✅ **YouTube metadata** extracted for 338 items  
✅ **All channels playable** (streams resolve correctly)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ID collision (collections vs playlists) | Medium | High | Use +10000 offset for collections |
| Metadata JSON parsing errors | Low | Medium | Try/except with fallback values |
| Missing media_item references | Low | Medium | Check foreign keys, log orphans |
| Large dataset performance | Medium | Low | Use batch inserts, async processing |
| URL expiration (Archive.org/YouTube) | High | Low | URLs refresh on access automatically |

## Post-Migration Tasks

1. **Verify playback**: Test 5-10 random channels
2. **Check metadata**: Inspect Archive.org and YouTube items
3. **Create schedules**: Generate playout schedules for channels
4. **Optimize database**: VACUUM, ANALYZE, REINDEX
5. **Monitor logs**: Watch for URL resolution errors

---

**Document Version**: 1.0  
**Last Updated**: 2026-01-26  
**Author**: EXStreamTV Migration Team
