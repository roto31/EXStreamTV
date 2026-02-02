"""
StreamTV Custom Database Importer

Handles migration from StreamTV with its specific schema:
- Collections + Playlists → EXStreamTV Playlists
- Embedded metadata extraction (Archive.org, YouTube, Plex)
- ID offsetting to prevent collisions
- Denormalized playlist item fields
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from exstreamtv.importers.schema_mapper import (
    convert_datetime,
    generate_unique_id,
    parse_json_field,
)

logger = logging.getLogger(__name__)

# ID offset for collections to avoid collision with playlists
COLLECTION_ID_OFFSET = 10000


@dataclass
class StreamTVCustomMigrationStats:
    """Statistics for StreamTV custom migration progress."""
    
    channels: int = 0
    media_items: int = 0
    playlists: int = 0  # StreamTV playlists
    collections: int = 0  # StreamTV collections (migrated as playlists)
    playlist_items: int = 0
    collection_items: int = 0
    playouts_created: int = 0
    
    # Source-specific metadata
    archive_org_extracted: int = 0
    youtube_extracted: int = 0
    plex_extracted: int = 0
    
    # Issues
    errors: int = 0
    warnings: int = 0
    
    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "channels": self.channels,
            "media_items": self.media_items,
            "playlists": self.playlists,
            "collections": self.collections,
            "total_playlists": self.playlists + self.collections,
            "playlist_items": self.playlist_items,
            "collection_items": self.collection_items,
            "total_playlist_items": self.playlist_items + self.collection_items,
            "playouts_created": self.playouts_created,
            "archive_org_extracted": self.archive_org_extracted,
            "youtube_extracted": self.youtube_extracted,
            "plex_extracted": self.plex_extracted,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class StreamTVCustomImporter:
    """
    Import StreamTV database into EXStreamTV.
    
    Handles StreamTV-specific schema with:
    - Both collections and playlists tables
    - Embedded source metadata in JSON
    - Channel configuration already ErsatzTV-compatible
    """
    
    def __init__(
        self,
        source_db_path: str | Path,
        dry_run: bool = False,
    ):
        """
        Initialize the importer.
        
        Args:
            source_db_path: Path to StreamTV SQLite database
            dry_run: If True, validate but don't actually import
        """
        self.source_db_path = Path(source_db_path)
        self.dry_run = dry_run
        self.stats = StreamTVCustomMigrationStats()
        
        # ID mappings (source ID -> EXStreamTV ID)
        self.id_maps: dict[str, dict[int, int]] = {
            "channels": {},
            "media_items": {},
            "playlists": {},
            "collections": {},  # Mapped to playlist IDs with offset
        }
        
        self._source_conn: sqlite3.Connection | None = None
        self._media_cache: dict[int, Any] = {}
    
    def validate(self) -> dict[str, Any]:
        """
        Validate source StreamTV database.
        
        Returns:
            Validation result dictionary
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "counts": {},
        }
        
        if not self.source_db_path.exists():
            result["is_valid"] = False
            result["errors"].append(f"Database not found: {self.source_db_path}")
            return result
        
        try:
            conn = sqlite3.connect(str(self.source_db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check for StreamTV tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            
            expected_tables = [
                "channels",
                "media_items",
                "playlists",
                "collections",
                "playlist_items",
                "collection_items",
            ]
            
            for table in expected_tables:
                if table in existing_tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        result["counts"][table] = count
                    except sqlite3.Error:
                        result["counts"][table] = 0
                else:
                    result["warnings"].append(f"Table '{table}' not found")
                    result["counts"][table] = 0
            
            conn.close()
            
        except sqlite3.Error as e:
            result["is_valid"] = False
            result["errors"].append(f"SQLite error: {e}")
        
        return result
    
    def _connect_source(self) -> sqlite3.Connection:
        """Connect to source database."""
        if self._source_conn is None:
            self._source_conn = sqlite3.connect(str(self.source_db_path))
            self._source_conn.row_factory = sqlite3.Row
        return self._source_conn
    
    def _close_source(self) -> None:
        """Close source database connection."""
        if self._source_conn:
            self._source_conn.close()
            self._source_conn = None
    
    def _get_source_rows(self, table: str) -> list[dict[str, Any]]:
        """Get all rows from a source table."""
        conn = self._connect_source()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.warning(f"Error reading {table}: {e}")
            return []
    
    async def _build_media_cache(self, session: Any) -> dict[int, Any]:
        """Build cache of media items for denormalization."""
        from exstreamtv.database.models import MediaItem
        
        stmt = select(MediaItem)
        result = await session.execute(stmt)
        media_items = result.scalars().all()
        
        cache = {}
        for media in media_items:
            # Use StreamTV source ID for lookup
            for source_id, target_id in self.id_maps["media_items"].items():
                if target_id == media.id:
                    cache[source_id] = media
                    break
        
        return cache
    
    async def migrate_all(self, session: Any) -> StreamTVCustomMigrationStats:
        """
        Run full migration.
        
        Args:
            session: SQLAlchemy async session
            
        Returns:
            Migration statistics
        """
        logger.info(f"Starting StreamTV custom migration from {self.source_db_path}")
        
        if self.dry_run:
            logger.info("DRY RUN - No changes will be made")
        
        try:
            # Order matters - migrate in dependency order
            await self.migrate_channels(session)
            await self.migrate_media_items_with_metadata(session)
            await self.migrate_collections_as_playlists(session)
            await self.migrate_playlists(session)
            
            # Build media cache for denormalization
            self._media_cache = await self._build_media_cache(session)
            
            await self.migrate_collection_items(session)
            await self.migrate_playlist_items(session)
            await self.create_default_playouts(session)
            
            if not self.dry_run:
                await session.commit()
            
            logger.info(f"Migration complete: {self.stats.to_dict()}")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            self.stats.errors += 1
            raise
        finally:
            self._close_source()
        
        return self.stats
    
    async def migrate_channels(self, session: Any) -> int:
        """Migrate StreamTV channels."""
        from exstreamtv.database.models import Channel
        
        rows = self._get_source_rows("channels")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("id")
                
                channel = Channel(
                    name=row.get("name", f"Channel {source_id}"),
                    number=str(row.get("number", source_id)),
                    unique_id=generate_unique_id(),  # Generate new UUID
                    group=row.get("group"),
                    enabled=row.get("enabled", True),
                    logo_path=row.get("logo_path"),
                    playout_mode=row.get("playout_mode", "continuous"),
                    streaming_mode=row.get("streaming_mode", "transport_stream_hybrid"),
                    ffmpeg_profile_id=row.get("ffmpeg_profile_id"),
                    watermark_id=row.get("watermark_id"),
                    transcode_mode=row.get("transcode_mode"),
                    subtitle_mode=row.get("subtitle_mode"),
                    preferred_audio_language_code=row.get("preferred_audio_language_code"),
                    preferred_audio_title=row.get("preferred_audio_title"),
                    preferred_subtitle_language_code=row.get("preferred_subtitle_language_code"),
                    stream_selector_mode=row.get("stream_selector_mode"),
                    stream_selector=row.get("stream_selector"),
                    music_video_credits_mode=row.get("music_video_credits_mode"),
                    music_video_credits_template=row.get("music_video_credits_template"),
                    song_video_mode=row.get("song_video_mode"),
                    idle_behavior=row.get("idle_behavior"),
                    playout_source=row.get("playout_source"),
                    mirror_source_channel_id=row.get("mirror_source_channel_id"),
                    playout_offset=row.get("playout_offset"),
                    show_in_epg=row.get("show_in_epg", True),
                    is_yaml_source=row.get("is_yaml_source", False),
                )
                
                if not self.dry_run:
                    session.add(channel)
                    await session.flush()
                    self.id_maps["channels"][source_id] = channel.id
                else:
                    self.id_maps["channels"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating channel {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.channels = count
        logger.info(f"Migrated {count} channels")
        return count
    
    async def migrate_media_items_with_metadata(self, session: Any) -> int:
        """Migrate StreamTV media items with embedded metadata extraction."""
        from exstreamtv.database.models import MediaItem
        
        rows = self._get_source_rows("media_items")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("id")
                source_type = row.get("source", "").upper()
                
                # FIX: Detect source from URL if source field is empty/unknown
                # This ensures Archive.org items are properly identified for streaming
                detected_source = self._detect_source_from_url(row.get("url", ""), source_type)
                
                # Base fields
                media_item = MediaItem(
                    title=row.get("title", f"Item {source_id}"),
                    source=detected_source,
                    source_id=row.get("source_id"),
                    url=row.get("url"),
                    duration=row.get("duration"),
                    description=row.get("description"),
                    plot=row.get("description"),  # Alias
                    thumbnail=row.get("thumbnail"),
                    uploader=row.get("uploader"),
                    upload_date=row.get("upload_date"),
                    view_count=row.get("view_count"),
                    meta_data=row.get("meta_data"),
                    show_title=row.get("series_title"),
                    season_number=row.get("season_number"),
                    episode_number=row.get("episode_number"),
                    genres=row.get("genres"),
                    library_source=source_type.lower(),
                    media_type=self._infer_media_type(row),
                    is_available=True,
                    episode_count=1,
                )
                
                # Extract source-specific metadata from JSON
                meta_json = row.get("meta_data")
                if meta_json:
                    try:
                        if source_type == "ARCHIVE_ORG":
                            self._extract_archive_org_metadata(media_item, meta_json)
                            self.stats.archive_org_extracted += 1
                        elif source_type == "YOUTUBE":
                            self._extract_youtube_metadata(media_item, meta_json)
                            self.stats.youtube_extracted += 1
                        elif source_type == "PLEX":
                            self._extract_plex_metadata(media_item, meta_json)
                            self.stats.plex_extracted += 1
                    except Exception as e:
                        logger.warning(f"Error extracting metadata for {source_id}: {e}")
                        self.stats.warnings += 1
                
                if not self.dry_run:
                    session.add(media_item)
                    await session.flush()
                    self.id_maps["media_items"][source_id] = media_item.id
                else:
                    self.id_maps["media_items"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating media item {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.media_items = count
        logger.info(f"Migrated {count} media items")
        return count
    
    def _infer_media_type(self, row: dict[str, Any]) -> str:
        """Infer media type from row data."""
        if row.get("episode_number") or row.get("series_title"):
            return "episode"
        return "movie"
    
    def _detect_source_from_url(self, url: str, existing_source: str) -> str:
        """
        Detect media source from URL patterns.
        
        This is critical for proper streaming - Archive.org items need
        special handling (headers, timeouts) that only happens if the
        source is correctly identified.
        
        Args:
            url: The media URL
            existing_source: The source field from the original database
            
        Returns:
            Detected source type (lowercase)
        """
        url_lower = (url or "").lower()
        existing_lower = (existing_source or "").lower()
        
        # If already set correctly, use it
        if existing_lower in ("archive_org", "youtube", "plex", "jellyfin", "local"):
            return existing_lower
        
        # Detect from URL patterns
        if "archive.org" in url_lower:
            logger.debug(f"Detected Archive.org source from URL: {url[:80]}...")
            return "archive_org"
        elif "youtube.com" in url_lower or "youtu.be" in url_lower or "googlevideo.com" in url_lower:
            logger.debug(f"Detected YouTube source from URL: {url[:80]}...")
            return "youtube"
        elif ":32400" in url_lower or "/library/metadata/" in url_lower:
            logger.debug(f"Detected Plex source from URL: {url[:80]}...")
            return "plex"
        elif ":8096" in url_lower or "jellyfin" in url_lower:
            logger.debug(f"Detected Jellyfin source from URL: {url[:80]}...")
            return "jellyfin"
        elif url_lower.startswith("/") or url_lower.startswith("file://"):
            return "local"
        
        # Fallback to existing or unknown
        return existing_lower if existing_lower else "unknown"
    
    def _extract_archive_org_metadata(self, media_item: Any, meta_json: str) -> None:
        """Extract Archive.org metadata from JSON."""
        try:
            meta = json.loads(meta_json)
            
            media_item.archive_org_identifier = meta.get("identifier")
            media_item.archive_org_creator = meta.get("creator")
            media_item.year = meta.get("year")
            
            # Collection (may be list or string)
            collection = meta.get("collection")
            if isinstance(collection, list):
                media_item.archive_org_collection = json.dumps(collection)
            else:
                media_item.archive_org_collection = collection
            
            # Subject/tags
            subject = meta.get("subject")
            if isinstance(subject, list):
                media_item.archive_org_subject = json.dumps(subject)
            else:
                media_item.archive_org_subject = subject
            
            # Video file info
            video_files = meta.get("video_files", [])
            if video_files:
                media_item.archive_org_filename = video_files[0].get("name")
            
            # Override duration if present
            if meta.get("runtime"):
                media_item.duration = meta.get("runtime")
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in Archive.org metadata: {e}")
    
    def _extract_youtube_metadata(self, media_item: Any, meta_json: str) -> None:
        """Extract YouTube metadata from JSON."""
        try:
            meta = json.loads(meta_json)
            
            media_item.youtube_video_id = media_item.source_id  # Already in source_id
            media_item.youtube_channel_id = meta.get("channel_id")
            media_item.youtube_channel_name = meta.get("channel") or meta.get("uploader")
            media_item.youtube_category = meta.get("category")
            media_item.youtube_like_count = meta.get("like_count")
            
            # Tags
            tags = meta.get("tags", [])
            if isinstance(tags, list):
                media_item.youtube_tags = json.dumps(tags)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in YouTube metadata: {e}")
    
    def _extract_plex_metadata(self, media_item: Any, meta_json: str) -> None:
        """Extract Plex metadata from JSON."""
        try:
            meta = json.loads(meta_json)
            
            media_item.plex_rating_key = meta.get("rating_key") or media_item.source_id
            media_item.plex_guid = meta.get("guid")
            media_item.plex_library_section_id = meta.get("library_section_id")
            media_item.plex_library_section_title = meta.get("library_section_title")
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in Plex metadata: {e}")
    
    async def migrate_collections_as_playlists(self, session: Any) -> int:
        """Migrate StreamTV collections as EXStreamTV playlists with ID offset."""
        from exstreamtv.database.models import Playlist
        
        rows = self._get_source_rows("collections")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("id")
                
                playlist = Playlist(
                    name=row.get("name", f"Collection {source_id}"),
                    description=row.get("description"),
                    collection_type=row.get("collection_type", "static"),
                    search_query=row.get("search_query"),
                    source_type="mixed",
                    is_enabled=True,
                    shuffle=False,
                    loop=True,
                )
                
                if not self.dry_run:
                    session.add(playlist)
                    await session.flush()
                    # Store with offset to distinguish from playlists
                    self.id_maps["collections"][source_id] = playlist.id
                else:
                    self.id_maps["collections"][source_id] = source_id + COLLECTION_ID_OFFSET
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating collection {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.collections = count
        logger.info(f"Migrated {count} collections as playlists")
        return count
    
    async def migrate_playlists(self, session: Any) -> int:
        """Migrate StreamTV playlists (separate from collections)."""
        from exstreamtv.database.models import Playlist
        
        rows = self._get_source_rows("playlists")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("id")
                
                playlist = Playlist(
                    name=row.get("name", f"Playlist {source_id}"),
                    description=row.get("description"),
                    collection_type="static",
                    source_type="mixed",
                    is_enabled=True,
                    shuffle=False,
                    loop=True,
                )
                
                if not self.dry_run:
                    session.add(playlist)
                    await session.flush()
                    self.id_maps["playlists"][source_id] = playlist.id
                else:
                    self.id_maps["playlists"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating playlist {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.playlists = count
        logger.info(f"Migrated {count} playlists")
        return count
    
    async def migrate_collection_items(self, session: Any) -> int:
        """Migrate collection items to playlist items."""
        from exstreamtv.database.models import PlaylistItem
        
        rows = self._get_source_rows("collection_items")
        count = 0
        
        for row in rows:
            try:
                source_collection_id = row.get("collection_id")
                source_media_id = row.get("media_item_id")
                
                # Get mapped IDs
                playlist_id = self.id_maps["collections"].get(source_collection_id)
                media_id = self.id_maps["media_items"].get(source_media_id)
                
                if not playlist_id or not media_id:
                    self.stats.warnings += 1
                    continue
                
                # Get media item for denormalization
                media = self._media_cache.get(source_media_id)
                if not media:
                    self.stats.warnings += 1
                    continue
                
                item = PlaylistItem(
                    playlist_id=playlist_id,
                    media_item_id=media_id,
                    position=row.get("order", 0),
                    title=media.title,
                    duration_seconds=media.duration,
                    thumbnail_url=media.thumbnail,
                    is_enabled=True,
                )
                
                if not self.dry_run:
                    session.add(item)
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating collection item {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.collection_items = count
        logger.info(f"Migrated {count} collection items")
        return count
    
    async def migrate_playlist_items(self, session: Any) -> int:
        """Migrate playlist items."""
        from exstreamtv.database.models import PlaylistItem
        
        rows = self._get_source_rows("playlist_items")
        count = 0
        
        for row in rows:
            try:
                source_playlist_id = row.get("playlist_id")
                source_media_id = row.get("media_item_id")
                
                # Get mapped IDs
                playlist_id = self.id_maps["playlists"].get(source_playlist_id)
                media_id = self.id_maps["media_items"].get(source_media_id)
                
                if not playlist_id or not media_id:
                    self.stats.warnings += 1
                    continue
                
                # Get media item for denormalization
                media = self._media_cache.get(source_media_id)
                if not media:
                    self.stats.warnings += 1
                    continue
                
                item = PlaylistItem(
                    playlist_id=playlist_id,
                    media_item_id=media_id,
                    position=row.get("order", 0),
                    title=media.title,
                    duration_seconds=media.duration,
                    thumbnail_url=media.thumbnail,
                    is_enabled=True,
                )
                
                if not self.dry_run:
                    session.add(item)
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating playlist item {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.playlist_items = count
        logger.info(f"Migrated {count} playlist items")
        return count
    
    async def create_default_playouts(self, session: Any) -> int:
        """Create default playouts for channels that don't have schedules."""
        from exstreamtv.database.models import Playout
        
        count = 0
        
        for source_channel_id, channel_id in self.id_maps["channels"].items():
            try:
                playout = Playout(
                    channel_id=channel_id,
                    playout_type="continuous",
                    schedule_kind="flood",
                    is_active=True,
                )
                
                if not self.dry_run:
                    session.add(playout)
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error creating playout for channel {channel_id}: {e}")
                self.stats.errors += 1
        
        self.stats.playouts_created = count
        logger.info(f"Created {count} default playouts")
        return count
    
    def get_id_map(self, entity_type: str) -> dict[int, int]:
        """Get ID mapping for an entity type."""
        return self.id_maps.get(entity_type, {})
