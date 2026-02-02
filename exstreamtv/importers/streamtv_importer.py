"""
StreamTV Database Importer

Migration from StreamTV SQLite database to EXStreamTV.
Handles StreamTV-specific tables and source metadata.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from exstreamtv.importers.schema_mapper import (
    convert_datetime,
    generate_unique_id,
    parse_json_field,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamTVMigrationStats:
    """Statistics for StreamTV migration progress."""
    
    channels: int = 0
    playlists: int = 0
    playlist_items: int = 0
    media_items: int = 0
    youtube_sources: int = 0
    archive_sources: int = 0
    local_sources: int = 0
    schedules: int = 0
    errors: int = 0
    warnings: int = 0
    
    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "channels": self.channels,
            "playlists": self.playlists,
            "playlist_items": self.playlist_items,
            "media_items": self.media_items,
            "youtube_sources": self.youtube_sources,
            "archive_sources": self.archive_sources,
            "local_sources": self.local_sources,
            "schedules": self.schedules,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class StreamTVImporter:
    """
    Import StreamTV database into EXStreamTV.
    
    StreamTV uses a different schema with source-specific metadata
    for YouTube and Archive.org content.
    """
    
    # StreamTV table mapping
    STREAMTV_TABLES = [
        "channels",
        "playlists",
        "playlist_items",
        "media_items",
        "youtube_videos",
        "archive_org_items",
        "schedules",
    ]
    
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
        self.stats = StreamTVMigrationStats()
        
        # ID mappings (source ID -> EXStreamTV ID)
        self.id_maps: dict[str, dict[int, int]] = {
            "channels": {},
            "playlists": {},
            "media_items": {},
            "schedules": {},
        }
        
        self._source_conn: sqlite3.Connection | None = None
    
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
            
            for table in self.STREAMTV_TABLES:
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
    
    async def migrate_all(self, session: Any) -> StreamTVMigrationStats:
        """
        Run full migration.
        
        Args:
            session: SQLAlchemy async session
            
        Returns:
            Migration statistics
        """
        logger.info(f"Starting StreamTV migration from {self.source_db_path}")
        
        if self.dry_run:
            logger.info("DRY RUN - No changes will be made")
        
        try:
            # Order matters - migrate in dependency order
            await self.migrate_channels(session)
            await self.migrate_playlists(session)
            await self.migrate_media_items(session)
            await self.migrate_youtube_sources(session)
            await self.migrate_archive_sources(session)
            await self.migrate_schedules(session)
            
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
                    unique_id=row.get("unique_id") or generate_unique_id(),
                    group=row.get("group", "StreamTV Import"),
                    categories=row.get("categories"),
                    enabled=row.get("enabled", True),
                    streaming_mode="transport_stream_hybrid",
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
    
    async def migrate_playlists(self, session: Any) -> int:
        """Migrate StreamTV playlists."""
        from exstreamtv.database.models import Playlist, PlaylistItem
        
        # Migrate playlists
        playlist_rows = self._get_source_rows("playlists")
        playlist_count = 0
        
        for row in playlist_rows:
            try:
                source_id = row.get("id")
                
                playlist = Playlist(
                    name=row.get("name", f"Playlist {source_id}"),
                    description=row.get("description"),
                )
                
                if not self.dry_run:
                    session.add(playlist)
                    await session.flush()
                    self.id_maps["playlists"][source_id] = playlist.id
                else:
                    self.id_maps["playlists"][source_id] = source_id
                
                playlist_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating playlist {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.playlists = playlist_count
        
        # Migrate playlist items
        item_rows = self._get_source_rows("playlist_items")
        item_count = 0
        
        for row in item_rows:
            try:
                source_playlist_id = row.get("playlist_id")
                playlist_id = self.id_maps["playlists"].get(source_playlist_id)
                
                if not playlist_id:
                    continue
                
                item = PlaylistItem(
                    playlist_id=playlist_id,
                    position=row.get("position", 0),
                    media_item_id=row.get("media_item_id"),
                )
                
                if not self.dry_run:
                    session.add(item)
                
                item_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating playlist item {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.playlist_items = item_count
        logger.info(f"Migrated {playlist_count} playlists with {item_count} items")
        return playlist_count
    
    async def migrate_media_items(self, session: Any) -> int:
        """Migrate StreamTV media items."""
        from exstreamtv.database.models import MediaItem
        
        rows = self._get_source_rows("media_items")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("id")
                
                # FIX: Detect source from URL if not explicitly set
                detected_source = self._detect_source_from_url(
                    row.get("url", ""), 
                    row.get("source", "")
                )
                
                media_item = MediaItem(
                    title=row.get("title", f"Item {source_id}"),
                    source=detected_source,
                    source_id=row.get("source_id"),
                    url=row.get("url"),
                    duration=row.get("duration"),
                    description=row.get("description"),
                    thumbnail=row.get("thumbnail"),
                    media_type=row.get("media_type", "other_video"),
                    year=row.get("year"),
                    genres=row.get("genres"),
                    is_available=True,
                )
                
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
    
    async def migrate_youtube_sources(self, session: Any) -> int:
        """Migrate YouTube-specific metadata."""
        from sqlalchemy import update
        from exstreamtv.database.models import MediaItem
        
        rows = self._get_source_rows("youtube_videos")
        count = 0
        
        for row in rows:
            try:
                media_item_id = row.get("media_item_id")
                exstream_id = self.id_maps["media_items"].get(media_item_id)
                
                if not exstream_id or self.dry_run:
                    count += 1
                    continue
                
                # Update media item with YouTube-specific fields
                stmt = (
                    update(MediaItem)
                    .where(MediaItem.id == exstream_id)
                    .values(
                        youtube_video_id=row.get("video_id"),
                        youtube_channel_id=row.get("channel_id"),
                        youtube_channel_name=row.get("channel_name"),
                        youtube_tags=row.get("tags"),
                        youtube_category=row.get("category"),
                        youtube_like_count=row.get("like_count"),
                        source="youtube",
                    )
                )
                await session.execute(stmt)
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating YouTube source: {e}")
                self.stats.errors += 1
        
        self.stats.youtube_sources = count
        logger.info(f"Migrated {count} YouTube sources")
        return count
    
    async def migrate_archive_sources(self, session: Any) -> int:
        """Migrate Archive.org-specific metadata."""
        from sqlalchemy import update
        from exstreamtv.database.models import MediaItem
        
        rows = self._get_source_rows("archive_org_items")
        count = 0
        
        for row in rows:
            try:
                media_item_id = row.get("media_item_id")
                exstream_id = self.id_maps["media_items"].get(media_item_id)
                
                if not exstream_id or self.dry_run:
                    count += 1
                    continue
                
                # Update media item with Archive.org-specific fields
                stmt = (
                    update(MediaItem)
                    .where(MediaItem.id == exstream_id)
                    .values(
                        archive_org_identifier=row.get("identifier"),
                        archive_org_filename=row.get("filename"),
                        archive_org_creator=row.get("creator"),
                        archive_org_collection=row.get("collection"),
                        archive_org_subject=row.get("subject"),
                        source="archive_org",
                    )
                )
                await session.execute(stmt)
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Archive.org source: {e}")
                self.stats.errors += 1
        
        self.stats.archive_sources = count
        logger.info(f"Migrated {count} Archive.org sources")
        return count
    
    async def migrate_schedules(self, session: Any) -> int:
        """Migrate StreamTV schedules."""
        from exstreamtv.database.models import ProgramSchedule
        
        rows = self._get_source_rows("schedules")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("id")
                
                schedule = ProgramSchedule(
                    name=row.get("name", f"Schedule {source_id}"),
                    keep_multi_part_episodes=True,
                    shuffle_schedule_items=row.get("shuffle", False),
                    random_start_point=row.get("random_start", False),
                )
                
                if not self.dry_run:
                    session.add(schedule)
                    await session.flush()
                    self.id_maps["schedules"][source_id] = schedule.id
                else:
                    self.id_maps["schedules"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating schedule {row.get('id')}: {e}")
                self.stats.errors += 1
        
        self.stats.schedules = count
        logger.info(f"Migrated {count} schedules")
        return count
    
    def get_id_map(self, entity_type: str) -> dict[int, int]:
        """Get ID mapping for an entity type."""
        return self.id_maps.get(entity_type, {})
    
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
        
        # Fallback to existing or local
        return existing_lower if existing_lower else "local"
