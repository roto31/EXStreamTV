"""
ErsatzTV Database Importer

Comprehensive migration from ErsatzTV SQLite database to EXStreamTV.
Migrates all entities with full schema compatibility including:
- Plex libraries and connections
- Media items (movies, episodes, shows)
- Media files and versions
- Collections and playlists
- Channels, schedules, playouts
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from exstreamtv.importers.enum_maps import (
    convert_audio_format,
    convert_collection_type,
    convert_deco_mode,
    convert_fixed_start_time_behavior,
    convert_hardware_acceleration,
    convert_playback_mode,
    convert_playback_order,
    convert_scaling_behavior,
    convert_streaming_mode,
    convert_video_format,
    convert_watermark_location,
)
from exstreamtv.importers.schema_mapper import (
    BLOCK_FIELD_MAP,
    BLOCK_ITEM_FIELD_MAP,
    CHANNEL_FIELD_MAP,
    DECO_FIELD_MAP,
    FFMPEG_PROFILE_FIELD_MAP,
    FILLER_PRESET_FIELD_MAP,
    PLAYOUT_FIELD_MAP,
    PROGRAM_SCHEDULE_FIELD_MAP,
    PROGRAM_SCHEDULE_ITEM_FIELD_MAP,
    WATERMARK_FIELD_MAP,
    convert_datetime,
    generate_unique_id,
    map_row,
)
from exstreamtv.importers.validators import ErsatzTVValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    """Statistics for migration progress."""
    
    ffmpeg_profiles: int = 0
    resolutions: int = 0
    plex_libraries: int = 0
    media_items: int = 0
    media_files: int = 0
    channels: int = 0
    watermarks: int = 0
    collections: int = 0
    collection_items: int = 0
    playouts: int = 0
    playout_items: int = 0
    schedules: int = 0
    schedule_items: int = 0
    blocks: int = 0
    block_items: int = 0
    filler_presets: int = 0
    decos: int = 0
    templates: int = 0
    errors: int = 0
    warnings: int = 0
    
    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "ffmpeg_profiles": self.ffmpeg_profiles,
            "resolutions": self.resolutions,
            "plex_libraries": self.plex_libraries,
            "media_items": self.media_items,
            "media_files": self.media_files,
            "channels": self.channels,
            "watermarks": self.watermarks,
            "collections": self.collections,
            "collection_items": self.collection_items,
            "playouts": self.playouts,
            "playout_items": self.playout_items,
            "schedules": self.schedules,
            "schedule_items": self.schedule_items,
            "blocks": self.blocks,
            "block_items": self.block_items,
            "filler_presets": self.filler_presets,
            "decos": self.decos,
            "templates": self.templates,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ErsatzTVImporter:
    """
    Import ErsatzTV database into EXStreamTV.
    
    Handles all entity types with proper foreign key resolution.
    """
    
    def __init__(
        self,
        source_db_path: str | Path,
        dry_run: bool = False,
    ):
        """
        Initialize the importer.
        
        Args:
            source_db_path: Path to ErsatzTV SQLite database
            dry_run: If True, validate but don't actually import
        """
        self.source_db_path = Path(source_db_path)
        self.dry_run = dry_run
        self.stats = MigrationStats()
        
        # ID mappings (source ID -> EXStreamTV ID)
        self.id_maps: dict[str, dict[int, int]] = {
            "ffmpeg_profiles": {},
            "channels": {},
            "watermarks": {},
            "schedules": {},
            "filler_presets": {},
            "blocks": {},
            "decos": {},
            "templates": {},
            "collections": {},
            "playouts": {},
            "plex_libraries": {},
            "media_items": {},
        }
        
        self._source_conn: sqlite3.Connection | None = None
        self._plex_secrets: dict[str, Any] | None = None
    
    def validate(self) -> ValidationResult:
        """
        Validate source database before migration.
        
        Returns:
            ValidationResult with all checks
        """
        validator = ErsatzTVValidator(self.source_db_path)
        return validator.validate_source()
    
    async def build_media_mapping_from_plex_keys(self, session: Any) -> int:
        """
        Build media_items id_map by matching ErsatzTV MediaItem IDs to 
        EXStreamTV MediaItems via Plex keys.
        
        This allows re-importing PlayoutItems with correct media references
        even when EXStreamTV media items were imported/synced separately.
        
        Returns:
            Number of mappings created
        """
        from exstreamtv.database.models import MediaItem
        from sqlalchemy import select
        
        conn = self._connect_source()
        cursor = conn.cursor()
        
        # Get ErsatzTV MediaItem ID -> Plex Key mapping
        ersatz_mapping = {}
        
        # Movies
        try:
            cursor.execute("""
                SELECT mi.Id, pm.Key 
                FROM MediaItem mi 
                JOIN PlexMovie pm ON mi.Id = pm.Id
            """)
            for row in cursor.fetchall():
                ersatz_mapping[row[0]] = row[1]
        except sqlite3.Error as e:
            logger.warning(f"Error reading PlexMovie keys: {e}")
        
        # Episodes
        try:
            cursor.execute("""
                SELECT mi.Id, pe.Key 
                FROM MediaItem mi 
                JOIN PlexEpisode pe ON mi.Id = pe.Id
            """)
            for row in cursor.fetchall():
                ersatz_mapping[row[0]] = row[1]
        except sqlite3.Error as e:
            logger.warning(f"Error reading PlexEpisode keys: {e}")
        
        logger.info(f"Found {len(ersatz_mapping)} ErsatzTV media items with Plex keys")
        
        # Get EXStreamTV Plex Key -> MediaItem ID mapping
        stmt = select(MediaItem).where(MediaItem.source == "plex")
        result = await session.execute(stmt)
        exstream_items = result.scalars().all()
        
        exstream_mapping = {}
        for item in exstream_items:
            if item.source_id:
                exstream_mapping[item.source_id] = item.id
        
        logger.info(f"Found {len(exstream_mapping)} EXStreamTV media items with Plex source_id")
        
        # Build the id_map: ErsatzTV MediaItem ID -> EXStreamTV MediaItem ID
        mapped_count = 0
        for ersatz_id, plex_key in ersatz_mapping.items():
            if plex_key in exstream_mapping:
                self.id_maps["media_items"][ersatz_id] = exstream_mapping[plex_key]
                mapped_count += 1
        
        logger.info(f"Created {mapped_count} media item mappings via Plex keys")
        return mapped_count
    
    async def repair_playout_items(self, session: Any) -> dict[str, int]:
        """
        Repair broken PlayoutItems by:
        1. Building media mapping from Plex keys
        2. Deleting broken PlayoutItems (no media_item_id)
        3. Re-importing PlayoutItems from ErsatzTV with correct mapping
        
        Returns:
            Statistics dict with counts
        """
        from exstreamtv.database.models import Playout, PlayoutItem
        from sqlalchemy import delete, select
        
        stats = {
            "mappings_created": 0,
            "items_deleted": 0,
            "items_imported": 0,
            "items_skipped": 0,
            "errors": 0
        }
        
        # Step 1: Build media mapping
        stats["mappings_created"] = await self.build_media_mapping_from_plex_keys(session)
        
        # Step 2: Build playout mapping (ErsatzTV Playout ID -> EXStreamTV Playout ID)
        # Match by channel number
        from exstreamtv.database.models import Channel
        from sqlalchemy.orm import selectinload
        
        ersatz_playouts = self._get_source_rows("Playout")
        ersatz_channels = {row["Id"]: row for row in self._get_source_rows("Channel")}
        
        # Use selectinload to eagerly load channel relationship (avoid lazy load in async)
        stmt = select(Playout).options(selectinload(Playout.channel))
        result = await session.execute(stmt)
        exstream_playouts = result.scalars().all()
        
        # Build channel number -> EXStreamTV playout mapping
        channel_to_playout = {}
        for playout in exstream_playouts:
            if playout.channel:
                channel_to_playout[playout.channel.number] = playout.id
        
        # Build ErsatzTV Playout ID -> EXStreamTV Playout ID
        for ersatz_playout in ersatz_playouts:
            ersatz_channel = ersatz_channels.get(ersatz_playout.get("ChannelId"))
            if ersatz_channel:
                channel_num = str(ersatz_channel.get("Number"))
                if channel_num in channel_to_playout:
                    self.id_maps["playouts"][ersatz_playout["Id"]] = channel_to_playout[channel_num]
        
        logger.info(f"Mapped {len(self.id_maps['playouts'])} playouts by channel number")
        
        # Step 3: Delete broken PlayoutItems
        if not self.dry_run:
            delete_stmt = delete(PlayoutItem).where(
                PlayoutItem.media_item_id.is_(None),
                PlayoutItem.source_url.is_(None)
            )
            result = await session.execute(delete_stmt)
            stats["items_deleted"] = result.rowcount
            logger.info(f"Deleted {stats['items_deleted']} broken PlayoutItems")
        
        # Step 4: Re-import PlayoutItems from ErsatzTV
        stats["items_imported"] = await self.migrate_playout_items(session)
        
        if not self.dry_run:
            await session.commit()
        
        return stats
    
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
    
    def _load_plex_secrets(self) -> dict[str, Any]:
        """
        Load Plex authentication secrets from plex-secrets.json.
        
        ErsatzTV stores Plex auth tokens in a JSON file alongside the database.
        
        Returns:
            Dictionary with structure:
            {
                "ClientIdentifier": "...",
                "UserAuthTokens": {"email": "token"},
                "ServerAuthTokens": {"client_id": "token"}
            }
        """
        if self._plex_secrets is not None:
            return self._plex_secrets
        
        secrets_path = self.source_db_path.parent / "plex-secrets.json"
        
        if not secrets_path.exists():
            logger.warning(f"Plex secrets file not found: {secrets_path}")
            self._plex_secrets = {}
            return self._plex_secrets
        
        try:
            with open(secrets_path, "r") as f:
                self._plex_secrets = json.load(f)
            logger.info(f"Loaded Plex secrets from {secrets_path}")
            return self._plex_secrets
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading Plex secrets: {e}")
            self._plex_secrets = {}
            return self._plex_secrets
    
    def _get_plex_token(self, client_identifier: str) -> str | None:
        """
        Get Plex auth token for a specific server.
        
        Args:
            client_identifier: Plex server's client identifier
            
        Returns:
            Auth token string or None if not found
        """
        secrets = self._load_plex_secrets()
        server_tokens = secrets.get("ServerAuthTokens", {})
        return server_tokens.get(client_identifier)
    
    async def migrate_all(self, session: Any) -> MigrationStats:
        """
        Run full migration.
        
        Executes all migration steps in correct dependency order:
        1. FFmpeg Profiles (no dependencies)
        2. Resolutions (no dependencies)
        3. Watermarks (no dependencies)
        4. Plex Libraries (no dependencies, needs plex-secrets.json)
        5. Media Items (depends on Plex Libraries)
        6. Media Files (depends on Media Items)
        7. Collections -> Playlists (depends on Media Items for item mapping)
        8. Channels (depends on FFmpegProfiles, Watermarks)
        9. Filler Presets (depends on Collections)
        10. Decos (depends on Watermarks, FillerPresets)
        11. Program Schedules + Schedule Items (depends on Collections, FillerPresets)
        12. Blocks + Block Items (depends on Collections)
        13. Templates
        14. Playouts (depends on Channels, Schedules, Templates, Decos)
        15. PlayoutItems (depends on Playouts, MediaItems)
        
        Args:
            session: SQLAlchemy async session
            
        Returns:
            Migration statistics
        """
        logger.info(f"Starting ErsatzTV migration from {self.source_db_path}")
        
        if self.dry_run:
            logger.info("DRY RUN - No changes will be made")
        
        try:
            # Order matters - migrate in dependency order
            # Step 1: FFmpeg Profiles (no dependencies)
            await self.migrate_ffmpeg_profiles(session)
            
            # Step 2: Resolutions (no dependencies)
            await self.migrate_resolutions(session)
            
            # Step 3: Watermarks (no dependencies)
            await self.migrate_watermarks(session)
            
            # Step 4: Plex Libraries (no dependencies, reads plex-secrets.json)
            await self.migrate_plex_libraries(session)
            
            # Step 5: Media Items (depends on Plex Libraries for library_id mapping)
            await self.migrate_media_items(session)
            
            # Step 6: Media Files (depends on Media Items)
            await self.migrate_media_files(session)
            
            # Step 7: Collections -> Playlists (depends on Media Items for item mapping)
            await self.migrate_collections(session)
            
            # Step 8: Channels (depends on FFmpegProfiles, Watermarks)
            await self.migrate_channels(session)
            
            # Step 9: Filler Presets (depends on Collections)
            await self.migrate_filler_presets(session)
            
            # Step 10: Decos (depends on Watermarks, FillerPresets)
            await self.migrate_decos(session)
            
            # Step 11: Program Schedules + Schedule Items (depends on Collections, FillerPresets)
            await self.migrate_schedules(session)
            
            # Step 12: Blocks + Block Items (depends on Collections)
            await self.migrate_blocks(session)
            
            # Step 13: Templates
            await self.migrate_templates(session)
            
            # Step 14: Playouts (depends on Channels, Schedules, Templates, Decos)
            await self.migrate_playouts(session)
            
            # Step 15: PlayoutItems (depends on Playouts, MediaItems)
            await self.migrate_playout_items(session)
            
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
    
    async def migrate_ffmpeg_profiles(self, session: Any) -> int:
        """Migrate FFmpeg profiles."""
        from exstreamtv.database.models import FFmpegProfile
        
        rows = self._get_source_rows("FFmpegProfile")
        count = 0
        
        for row in rows:
            try:
                mapped = map_row(row, FFMPEG_PROFILE_FIELD_MAP)
                source_id = row.get("Id")
                
                # Create profile
                profile = FFmpegProfile(
                    name=mapped.get("name", f"Profile {source_id}"),
                    hardware_acceleration=mapped.get("hardware_acceleration", "none"),
                    video_format=mapped.get("video_format", "h264"),
                    audio_format=mapped.get("audio_format", "aac"),
                    video_bitrate=mapped.get("video_bitrate", "4000k"),
                    audio_bitrate=mapped.get("audio_bitrate", "128k"),
                    scaling_behavior=mapped.get("scaling_behavior", "scale_and_pad"),
                    normalize_framerate=mapped.get("normalize_framerate", True),
                    normalize_audio=True,
                    is_enabled=True,
                )
                
                if not self.dry_run:
                    session.add(profile)
                    await session.flush()
                    self.id_maps["ffmpeg_profiles"][source_id] = profile.id
                else:
                    self.id_maps["ffmpeg_profiles"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating FFmpegProfile {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.ffmpeg_profiles = count
        logger.info(f"Migrated {count} FFmpeg profiles")
        return count
    
    async def migrate_watermarks(self, session: Any) -> int:
        """Migrate channel watermarks."""
        from exstreamtv.database.models import ChannelWatermark
        
        rows = self._get_source_rows("ChannelWatermark")
        count = 0
        
        for row in rows:
            try:
                mapped = map_row(row, WATERMARK_FIELD_MAP)
                source_id = row.get("Id")
                
                watermark = ChannelWatermark(
                    name=mapped.get("name", f"Watermark {source_id}"),
                    image_path=mapped.get("image_path"),
                    image=mapped.get("image"),
                    mode=mapped.get("mode", "permanent"),
                    location=mapped.get("location", "bottom_right"),
                    size=mapped.get("size", "medium"),
                    width_percent=mapped.get("width_percent", 10),
                    opacity=mapped.get("opacity", 100),
                )
                
                if not self.dry_run:
                    session.add(watermark)
                    await session.flush()
                    self.id_maps["watermarks"][source_id] = watermark.id
                else:
                    self.id_maps["watermarks"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Watermark {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.watermarks = count
        logger.info(f"Migrated {count} watermarks")
        return count
    
    async def migrate_channels(self, session: Any) -> int:
        """Migrate channels."""
        from exstreamtv.database.models import Channel
        
        rows = self._get_source_rows("Channel")
        count = 0
        
        for row in rows:
            try:
                mapped = map_row(row, CHANNEL_FIELD_MAP)
                source_id = row.get("Id")
                
                # Map foreign keys
                ffmpeg_profile_id = None
                source_profile_id = row.get("FFmpegProfileId")
                if source_profile_id and source_profile_id in self.id_maps["ffmpeg_profiles"]:
                    ffmpeg_profile_id = self.id_maps["ffmpeg_profiles"][source_profile_id]
                
                watermark_id = None
                source_watermark_id = row.get("WatermarkId")
                if source_watermark_id and source_watermark_id in self.id_maps["watermarks"]:
                    watermark_id = self.id_maps["watermarks"][source_watermark_id]
                
                channel = Channel(
                    name=mapped.get("name", f"Channel {source_id}"),
                    number=str(mapped.get("number", source_id)),
                    unique_id=mapped.get("unique_id") or generate_unique_id(),
                    group=mapped.get("group", "Imported"),
                    streaming_mode=mapped.get("streaming_mode", "transport_stream_hybrid"),
                    ffmpeg_profile_id=ffmpeg_profile_id,
                    watermark_id=watermark_id,
                    enabled=True,
                )
                
                if not self.dry_run:
                    session.add(channel)
                    await session.flush()
                    self.id_maps["channels"][source_id] = channel.id
                else:
                    self.id_maps["channels"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Channel {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.channels = count
        logger.info(f"Migrated {count} channels")
        return count
    
    async def migrate_filler_presets(self, session: Any) -> int:
        """Migrate filler presets with collection mapping."""
        from exstreamtv.database.models import FillerPreset
        
        rows = self._get_source_rows("FillerPreset")
        count = 0
        
        for row in rows:
            try:
                mapped = map_row(row, FILLER_PRESET_FIELD_MAP)
                source_id = row.get("Id")
                
                # Map MediaCollectionId from ErsatzTV to collection_id (playlist)
                collection_id = None
                source_collection_id = row.get("MediaCollectionId")
                if source_collection_id and source_collection_id in self.id_maps["collections"]:
                    collection_id = self.id_maps["collections"][source_collection_id]
                
                preset = FillerPreset(
                    name=mapped.get("name", f"Filler {source_id}"),
                    filler_mode=mapped.get("filler_mode", "duration"),
                    filler_kind=mapped.get("filler_kind"),
                    playback_order=mapped.get("playback_order", "shuffled"),
                    allow_watermarks=mapped.get("allow_watermarks", True),
                    count=mapped.get("count"),
                    duration_seconds=mapped.get("duration_seconds"),
                    collection_id=collection_id,  # Mapped from MediaCollectionId
                )
                
                if not self.dry_run:
                    session.add(preset)
                    await session.flush()
                    self.id_maps["filler_presets"][source_id] = preset.id
                else:
                    self.id_maps["filler_presets"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating FillerPreset {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.filler_presets = count
        logger.info(f"Migrated {count} filler presets")
        return count
    
    async def migrate_decos(self, session: Any) -> int:
        """Migrate deco configurations."""
        from exstreamtv.database.models import Deco
        
        rows = self._get_source_rows("Deco")
        count = 0
        
        for row in rows:
            try:
                mapped = map_row(row, DECO_FIELD_MAP)
                source_id = row.get("Id")
                
                # Map watermark foreign key
                watermark_id = None
                source_watermark_id = row.get("WatermarkId")
                if source_watermark_id and source_watermark_id in self.id_maps["watermarks"]:
                    watermark_id = self.id_maps["watermarks"][source_watermark_id]
                
                deco = Deco(
                    name=mapped.get("name", f"Deco {source_id}"),
                    watermark_mode=mapped.get("watermark_mode", "inherit"),
                    watermark_id=watermark_id,
                    graphics_elements_mode=mapped.get("graphics_elements_mode", "inherit"),
                    break_content_mode=mapped.get("break_content_mode", "inherit"),
                    default_filler_mode=mapped.get("default_filler_mode", "inherit"),
                    dead_air_fallback_mode=mapped.get("dead_air_fallback_mode", "inherit"),
                )
                
                if not self.dry_run:
                    session.add(deco)
                    await session.flush()
                    self.id_maps["decos"][source_id] = deco.id
                else:
                    self.id_maps["decos"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Deco {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.decos = count
        logger.info(f"Migrated {count} decos")
        return count
    
    async def migrate_schedules(self, session: Any) -> int:
        """Migrate program schedules and items."""
        from exstreamtv.database.models import ProgramSchedule, ProgramScheduleItem
        
        # First, migrate schedules
        schedule_rows = self._get_source_rows("ProgramSchedule")
        schedule_count = 0
        
        for row in schedule_rows:
            try:
                mapped = map_row(row, PROGRAM_SCHEDULE_FIELD_MAP)
                source_id = row.get("Id")
                
                schedule = ProgramSchedule(
                    name=mapped.get("name", f"Schedule {source_id}"),
                    keep_multi_part_episodes=mapped.get("keep_multi_part_episodes", True),
                    treat_collections_as_shows=mapped.get("treat_collections_as_shows", False),
                    shuffle_schedule_items=mapped.get("shuffle_schedule_items", False),
                    random_start_point=mapped.get("random_start_point", False),
                    fixed_start_time_behavior=mapped.get("fixed_start_time_behavior", "fill"),
                )
                
                if not self.dry_run:
                    session.add(schedule)
                    await session.flush()
                    self.id_maps["schedules"][source_id] = schedule.id
                else:
                    self.id_maps["schedules"][source_id] = source_id
                
                schedule_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating ProgramSchedule {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.schedules = schedule_count
        
        # Then, migrate schedule items
        item_rows = self._get_source_rows("ProgramScheduleItem")
        item_count = 0
        skipped_schedule_items = 0
        
        for row in item_rows:
            try:
                mapped = map_row(row, PROGRAM_SCHEDULE_ITEM_FIELD_MAP)
                source_schedule_id = row.get("ProgramScheduleId")
                
                # Map schedule foreign key
                schedule_id = self.id_maps["schedules"].get(source_schedule_id)
                if not schedule_id:
                    continue
                
                # Determine collection reference based on collection type
                collection_type = mapped.get("collection_type", "collection")
                collection_id = None
                multi_collection_id = None
                smart_collection_id = None
                
                # CollectionType 0 = collection -> references CollectionId
                if collection_type == "collection":
                    source_collection_id = row.get("CollectionId")
                    if source_collection_id:
                        collection_id = self.id_maps["collections"].get(source_collection_id)
                    if not collection_id:
                        # No valid collection reference, skip this item
                        skipped_schedule_items += 1
                        continue
                        
                # CollectionType 1, 2 = show/season -> references MediaItemId
                elif collection_type in ("television_show", "television_season"):
                    # These reference media items directly - skip for now
                    # Future: could create a playlist from the show's episodes
                    skipped_schedule_items += 1
                    continue
                    
                # CollectionType 4 = multi_collection -> references MultiCollectionId
                elif collection_type == "multi_collection":
                    multi_collection_id = row.get("MultiCollectionId")
                    if not multi_collection_id:
                        skipped_schedule_items += 1
                        continue
                        
                # CollectionType 5 = smart_collection -> references SmartCollectionId
                elif collection_type == "smart_collection":
                    smart_collection_id = row.get("SmartCollectionId")
                    if not smart_collection_id:
                        skipped_schedule_items += 1
                        continue
                        
                # CollectionType 6 = search -> uses search_query
                elif collection_type == "search":
                    # Search-based items don't need collection_id
                    pass
                else:
                    # Unknown type, skip
                    skipped_schedule_items += 1
                    continue
                
                # Map filler foreign keys
                pre_roll_filler_id = None
                source_pre_roll = row.get("PreRollFillerId")
                if source_pre_roll and source_pre_roll in self.id_maps["filler_presets"]:
                    pre_roll_filler_id = self.id_maps["filler_presets"][source_pre_roll]
                
                item = ProgramScheduleItem(
                    schedule_id=schedule_id,
                    position=mapped.get("position", 1),
                    collection_type=collection_type,
                    collection_id=collection_id,
                    multi_collection_id=multi_collection_id,
                    smart_collection_id=smart_collection_id,
                    search_query=row.get("SearchQuery"),
                    search_title=row.get("SearchTitle"),
                    playback_mode=mapped.get("playback_mode", "flood"),
                    playback_order=mapped.get("playback_order", "chronological"),
                    custom_title=mapped.get("custom_title"),
                    guide_mode=mapped.get("guide_mode", "normal"),
                    pre_roll_filler_id=pre_roll_filler_id,
                )
                
                if not self.dry_run:
                    session.add(item)
                
                item_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating ProgramScheduleItem {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        if skipped_schedule_items > 0:
            logger.warning(f"Skipped {skipped_schedule_items} schedule items (show/season refs or missing collections)")
        
        self.stats.schedule_items = item_count
        logger.info(f"Migrated {schedule_count} schedules with {item_count} items")
        return schedule_count
    
    async def migrate_blocks(self, session: Any) -> int:
        """Migrate blocks and block items."""
        from datetime import time
        from exstreamtv.database.models import Block, BlockItem
        
        # First, migrate blocks
        block_rows = self._get_source_rows("Block")
        block_count = 0
        
        for row in block_rows:
            try:
                mapped = map_row(row, BLOCK_FIELD_MAP)
                source_id = row.get("Id")
                
                # Parse start time
                start_time_str = row.get("StartTime", "00:00:00")
                if isinstance(start_time_str, str):
                    parts = start_time_str.split(":")
                    start_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
                else:
                    start_time = time(0, 0, 0)
                
                block = Block(
                    name=mapped.get("name", f"Block {source_id}"),
                    start_time=start_time,
                    duration_minutes=mapped.get("duration_minutes", 60),
                    days_of_week=mapped.get("days_of_week", 127),
                    stop_scheduling=mapped.get("stop_scheduling", False),
                )
                
                if not self.dry_run:
                    session.add(block)
                    await session.flush()
                    self.id_maps["blocks"][source_id] = block.id
                else:
                    self.id_maps["blocks"][source_id] = source_id
                
                block_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Block {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.blocks = block_count
        
        # Then, migrate block items
        item_rows = self._get_source_rows("BlockItem")
        item_count = 0
        
        for row in item_rows:
            try:
                mapped = map_row(row, BLOCK_ITEM_FIELD_MAP)
                source_block_id = row.get("BlockId")
                
                # Map block foreign key
                block_id = self.id_maps["blocks"].get(source_block_id)
                if not block_id:
                    continue
                
                item = BlockItem(
                    block_id=block_id,
                    position=mapped.get("position", 1),
                    collection_type=mapped.get("collection_type", "collection"),
                    collection_id=mapped.get("collection_id"),
                    playback_order=mapped.get("playback_order", "chronological"),
                    include_in_guide=mapped.get("include_in_guide", True),
                    disable_watermarks=mapped.get("disable_watermarks", False),
                )
                
                if not self.dry_run:
                    session.add(item)
                
                item_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating BlockItem {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.block_items = item_count
        logger.info(f"Migrated {block_count} blocks with {item_count} items")
        return block_count
    
    async def migrate_templates(self, session: Any) -> int:
        """Migrate templates."""
        from exstreamtv.database.models import Template
        
        rows = self._get_source_rows("Template")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("Id")
                
                template = Template(
                    name=row.get("Name", f"Template {source_id}"),
                )
                
                if not self.dry_run:
                    session.add(template)
                    await session.flush()
                    self.id_maps["templates"][source_id] = template.id
                else:
                    self.id_maps["templates"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Template {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.templates = count
        logger.info(f"Migrated {count} templates")
        return count
    
    async def migrate_playouts(self, session: Any) -> int:
        """Migrate playouts."""
        from exstreamtv.database.models import Playout
        
        rows = self._get_source_rows("Playout")
        count = 0
        
        for row in rows:
            try:
                mapped = map_row(row, PLAYOUT_FIELD_MAP)
                source_id = row.get("Id")
                
                # Map foreign keys
                channel_id = self.id_maps["channels"].get(row.get("ChannelId"))
                if not channel_id:
                    logger.warning(f"Skipping playout {source_id}: channel not found")
                    continue
                
                schedule_id = None
                source_schedule_id = row.get("ProgramScheduleId")
                if source_schedule_id and source_schedule_id in self.id_maps["schedules"]:
                    schedule_id = self.id_maps["schedules"][source_schedule_id]
                
                template_id = None
                source_template_id = row.get("TemplateId")
                if source_template_id and source_template_id in self.id_maps["templates"]:
                    template_id = self.id_maps["templates"][source_template_id]
                
                deco_id = None
                source_deco_id = row.get("DecoId")
                if source_deco_id and source_deco_id in self.id_maps["decos"]:
                    deco_id = self.id_maps["decos"][source_deco_id]
                
                playout = Playout(
                    channel_id=channel_id,
                    program_schedule_id=schedule_id,
                    template_id=template_id,
                    deco_id=deco_id,
                    schedule_kind=mapped.get("schedule_kind", "flood"),
                    schedule_file=mapped.get("schedule_file"),
                    seed=mapped.get("seed"),
                    is_active=True,
                )
                
                if not self.dry_run:
                    session.add(playout)
                    await session.flush()
                    self.id_maps["playouts"][source_id] = playout.id
                else:
                    self.id_maps["playouts"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Playout {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.playouts = count
        logger.info(f"Migrated {count} playouts")
        return count
    
    async def migrate_resolutions(self, session: Any) -> int:
        """Migrate resolution presets."""
        from exstreamtv.database.models import Resolution
        
        rows = self._get_source_rows("Resolution")
        count = 0
        
        for row in rows:
            try:
                source_id = row.get("Id")
                
                resolution = Resolution(
                    name=row.get("Name", f"Resolution {source_id}"),
                    width=row.get("Width", 1920),
                    height=row.get("Height", 1080),
                    is_preset=row.get("IsPreset", False),
                )
                
                if not self.dry_run:
                    session.add(resolution)
                    await session.flush()
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Resolution {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.resolutions = count
        logger.info(f"Migrated {count} resolutions")
        return count
    
    async def migrate_plex_libraries(self, session: Any) -> int:
        """
        Migrate Plex media sources and libraries.
        
        Combines data from:
        - PlexMediaSource: Server name, client identifier
        - PlexConnection: Server URL (active connection)
        - Library: Library name and type
        - plex-secrets.json: Auth tokens
        
        Target: plex_libraries table
        """
        from exstreamtv.database.models import PlexLibrary
        
        conn = self._connect_source()
        cursor = conn.cursor()
        count = 0
        
        # Get all Plex media sources with their active connections
        try:
            cursor.execute("""
                SELECT 
                    pms.Id as MediaSourceId,
                    pms.ClientIdentifier,
                    pms.ServerName,
                    pc.Uri as ServerUrl,
                    l.Id as LibraryId,
                    l.Name as LibraryName,
                    l.MediaKind,
                    pl.Key as PlexLibraryKey
                FROM PlexMediaSource pms
                JOIN PlexConnection pc ON pc.PlexMediaSourceId = pms.Id AND pc.IsActive = 1
                JOIN PlexLibrary pl ON 1=1
                JOIN Library l ON l.Id = pl.Id AND l.MediaSourceId = pms.Id
                ORDER BY pms.Id, l.Id
            """)
            rows = cursor.fetchall()
        except sqlite3.Error as e:
            logger.warning(f"Error querying Plex libraries: {e}")
            return 0
        
        # Map MediaKind to library_type
        media_kind_map = {
            1: "movie",
            2: "show",
            3: "music_video",
            4: "other_video",
            5: "music",
            6: "image",
        }
        
        for row in rows:
            try:
                row_dict = dict(row)
                client_id = row_dict.get("ClientIdentifier")
                server_url = row_dict.get("ServerUrl")
                library_name = row_dict.get("LibraryName")
                library_key = row_dict.get("PlexLibraryKey")
                media_kind = row_dict.get("MediaKind", 1)
                
                # Get auth token for this server
                token = self._get_plex_token(client_id)
                if not token:
                    logger.warning(f"No auth token found for Plex server {client_id}")
                    self.stats.warnings += 1
                    # Use placeholder - user will need to re-authenticate
                    token = "TOKEN_REQUIRED"
                
                # Determine library type
                library_type = media_kind_map.get(media_kind, "movie")
                
                plex_library = PlexLibrary(
                    name=f"{row_dict.get('ServerName', 'Plex')} - {library_name}",
                    server_url=server_url,
                    token=token,
                    plex_library_key=str(library_key),
                    plex_library_name=library_name,
                    library_type=library_type,
                    is_enabled=True,
                    item_count=0,  # Will be updated after media import
                )
                
                if not self.dry_run:
                    session.add(plex_library)
                    await session.flush()
                    # Map using composite of MediaSourceId + LibraryId
                    source_lib_id = row_dict.get("LibraryId")
                    self.id_maps["plex_libraries"][source_lib_id] = plex_library.id
                else:
                    source_lib_id = row_dict.get("LibraryId")
                    self.id_maps["plex_libraries"][source_lib_id] = source_lib_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Plex library: {e}")
                self.stats.errors += 1
        
        self.stats.plex_libraries = count
        logger.info(f"Migrated {count} Plex libraries")
        return count
    
    async def migrate_media_items(self, session: Any) -> int:
        """
        Migrate media items from ErsatzTV to EXStreamTV.
        
        Imports:
        - PlexMovie -> MediaItem (source="plex", media_type="movie")
        - PlexEpisode -> MediaItem (source="plex", media_type="episode")
        - Includes Plex Key as external_id for API access
        
        This is critical for:
        - Collection items to reference actual content
        - Playout items to have valid media references
        - Streaming to work with correct file paths
        """
        from exstreamtv.database.models import MediaItem
        
        conn = self._connect_source()
        cursor = conn.cursor()
        count = 0
        
        # Migrate Plex Movies
        try:
            cursor.execute("""
                SELECT 
                    m.Id,
                    pm.Key as PlexKey,
                    mm.Title,
                    mm.Year,
                    mm.ContentRating,
                    mm.Plot as Description,
                    mm.Tagline,
                    l.Id as LibraryId,
                    mi.LibraryPathId
                FROM PlexMovie pm
                JOIN Movie m ON pm.Id = m.Id
                JOIN MovieMetadata mm ON m.Id = mm.MovieId
                JOIN MediaItem mi ON m.Id = mi.Id
                JOIN LibraryPath lp ON mi.LibraryPathId = lp.Id
                JOIN Library l ON lp.LibraryId = l.Id
            """)
            movie_rows = cursor.fetchall()
        except sqlite3.Error as e:
            logger.warning(f"Error querying Plex movies: {e}")
            movie_rows = []
        
        for row in movie_rows:
            try:
                row_dict = dict(row)
                source_id = row_dict.get("Id")
                library_id = row_dict.get("LibraryId")
                
                # Map library to EXStreamTV plex_library
                mapped_library_id = self.id_maps["plex_libraries"].get(library_id)
                
                media_item = MediaItem(
                    media_type="movie",
                    source="plex",
                    source_id=row_dict.get("PlexKey"),
                    external_id=row_dict.get("PlexKey"),
                    library_source="plex",
                    library_id=mapped_library_id,
                    title=row_dict.get("Title", f"Movie {source_id}"),
                    year=row_dict.get("Year"),
                    description=row_dict.get("Description"),
                    content_rating=row_dict.get("ContentRating"),
                )
                
                if not self.dry_run:
                    session.add(media_item)
                    await session.flush()
                    self.id_maps["media_items"][source_id] = media_item.id
                else:
                    self.id_maps["media_items"][source_id] = source_id
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating movie {row_dict.get('Id')}: {e}")
                self.stats.errors += 1
        
        logger.info(f"Migrated {count} movies")
        
        # Migrate Plex Episodes
        episode_count = 0
        try:
            cursor.execute("""
                SELECT 
                    e.Id,
                    pe.Key as PlexKey,
                    em.Title,
                    em.EpisodeNumber,
                    em.Plot as Description,
                    s.SeasonNumber,
                    shm.Title as ShowTitle,
                    l.Id as LibraryId,
                    mi.LibraryPathId
                FROM PlexEpisode pe
                JOIN Episode e ON pe.Id = e.Id
                JOIN EpisodeMetadata em ON e.Id = em.EpisodeId
                JOIN Season s ON e.SeasonId = s.Id
                JOIN ShowMetadata shm ON s.ShowId = shm.ShowId
                JOIN MediaItem mi ON e.Id = mi.Id
                JOIN LibraryPath lp ON mi.LibraryPathId = lp.Id
                JOIN Library l ON lp.LibraryId = l.Id
            """)
            episode_rows = cursor.fetchall()
        except sqlite3.Error as e:
            logger.warning(f"Error querying Plex episodes: {e}")
            episode_rows = []
        
        for row in episode_rows:
            try:
                row_dict = dict(row)
                source_id = row_dict.get("Id")
                library_id = row_dict.get("LibraryId")
                
                mapped_library_id = self.id_maps["plex_libraries"].get(library_id)
                
                # Build episode title: "Show - S01E02 - Episode Title"
                show_title = row_dict.get("ShowTitle", "")
                season_num = row_dict.get("SeasonNumber", 0)
                episode_num = row_dict.get("EpisodeNumber", 0)
                episode_title = row_dict.get("Title", "")
                full_title = f"{show_title} - S{season_num:02d}E{episode_num:02d}"
                if episode_title:
                    full_title += f" - {episode_title}"
                
                media_item = MediaItem(
                    media_type="episode",
                    source="plex",
                    source_id=row_dict.get("PlexKey"),
                    external_id=row_dict.get("PlexKey"),
                    library_source="plex",
                    library_id=mapped_library_id,
                    title=full_title,
                    description=row_dict.get("Description"),
                    episode_number=episode_num,
                    season_number=season_num,
                    show_title=show_title,
                )
                
                if not self.dry_run:
                    session.add(media_item)
                    await session.flush()
                    self.id_maps["media_items"][source_id] = media_item.id
                else:
                    self.id_maps["media_items"][source_id] = source_id
                
                episode_count += 1
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating episode {row_dict.get('Id')}: {e}")
                self.stats.errors += 1
        
        logger.info(f"Migrated {episode_count} episodes")
        
        self.stats.media_items = count
        logger.info(f"Migrated {count} total media items")
        return count
    
    async def migrate_media_files(self, session: Any) -> int:
        """
        Migrate media file paths and versions.
        
        Links MediaItem to actual file locations for streaming.
        
        Source: MediaVersion, MediaFile
        Target: media_files table
        """
        from exstreamtv.database.models import MediaFile
        
        conn = self._connect_source()
        cursor = conn.cursor()
        count = 0
        
        # Get media files with their associated media items
        try:
            cursor.execute("""
                SELECT 
                    mf.Id as FileId,
                    mf.Path,
                    mv.Id as VersionId,
                    mv.Duration,
                    mv.Width,
                    mv.Height,
                    COALESCE(mv.MovieId, mv.EpisodeId, mv.MusicVideoId, mv.OtherVideoId) as MediaItemId
                FROM MediaFile mf
                JOIN MediaVersion mv ON mf.MediaVersionId = mv.Id
                WHERE mf.Path IS NOT NULL AND mf.Path != ''
            """)
            rows = cursor.fetchall()
        except sqlite3.Error as e:
            logger.warning(f"Error querying media files: {e}")
            return 0
        
        for row in rows:
            try:
                row_dict = dict(row)
                source_media_id = row_dict.get("MediaItemId")
                
                # Map to EXStreamTV media_item_id
                mapped_media_id = self.id_maps["media_items"].get(source_media_id)
                
                if not mapped_media_id:
                    # Media item wasn't imported, skip file
                    continue
                
                # Parse duration (stored as TimeSpan string like "01:30:45.123")
                duration_str = row_dict.get("Duration", "00:00:00")
                duration_seconds = 0
                if duration_str:
                    try:
                        parts = duration_str.split(":")
                        if len(parts) >= 3:
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            # Handle seconds with possible decimal
                            seconds = float(parts[2].split(".")[0])
                            duration_seconds = hours * 3600 + minutes * 60 + int(seconds)
                    except (ValueError, IndexError):
                        pass
                
                media_file = MediaFile(
                    media_item_id=mapped_media_id,
                    path=row_dict.get("Path"),
                    size_bytes=0,  # ErsatzTV doesn't store file size
                    is_accessible=True,
                )
                
                if not self.dry_run:
                    session.add(media_file)
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating media file: {e}")
                self.stats.errors += 1
        
        self.stats.media_files = count
        logger.info(f"Migrated {count} media files")
        return count
    
    async def migrate_collections(self, session: Any) -> int:
        """
        Migrate ErsatzTV collections to EXStreamTV playlists.
        
        This is critical for filler presets and schedule items
        which reference collections by ID.
        """
        from exstreamtv.database.models import Playlist, PlaylistItem
        
        # Migrate Collection table
        collection_rows = self._get_source_rows("Collection")
        collection_count = 0
        
        for row in collection_rows:
            try:
                source_id = row.get("Id")
                
                # Map ErsatzTV collection type to playlist
                playlist = Playlist(
                    name=row.get("Name", f"Collection {source_id}"),
                    description=row.get("Description"),
                )
                
                if not self.dry_run:
                    session.add(playlist)
                    await session.flush()
                    self.id_maps["collections"][source_id] = playlist.id
                else:
                    self.id_maps["collections"][source_id] = source_id
                
                collection_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating Collection {row.get('Id')}: {e}")
                self.stats.errors += 1
        
        self.stats.collections = collection_count
        
        # Migrate CollectionItems
        # First, build a lookup of media item titles from the source database
        conn = self._connect_source()
        cursor = conn.cursor()
        media_titles: dict[int, str] = {}
        
        try:
            # Get movie titles
            cursor.execute("""
                SELECT m.Id, mm.Title 
                FROM Movie m 
                JOIN MovieMetadata mm ON m.Id = mm.MovieId
            """)
            for row_data in cursor.fetchall():
                media_titles[row_data[0]] = row_data[1]
            
            # Get episode titles
            cursor.execute("""
                SELECT e.Id, 
                       COALESCE(em.Title, '') || ' - S' || printf('%02d', s.SeasonNumber) || 'E' || printf('%02d', em.EpisodeNumber) as Title
                FROM Episode e
                JOIN EpisodeMetadata em ON e.Id = em.EpisodeId
                JOIN Season s ON e.SeasonId = s.Id
            """)
            for row_data in cursor.fetchall():
                media_titles[row_data[0]] = row_data[1]
        except sqlite3.Error as e:
            logger.warning(f"Error fetching media titles: {e}")
        
        item_rows = self._get_source_rows("CollectionItem")
        item_count = 0
        skipped_items = 0
        
        for row in item_rows:
            try:
                source_collection_id = row.get("CollectionId")
                playlist_id = self.id_maps["collections"].get(source_collection_id)
                
                if not playlist_id:
                    continue
                
                # Map MediaItemId from ErsatzTV to EXStreamTV media_item_id
                source_media_id = row.get("MediaItemId")
                mapped_media_id = self.id_maps["media_items"].get(source_media_id)
                
                if not mapped_media_id:
                    # Media item wasn't imported - skip but count for reporting
                    skipped_items += 1
                    continue
                
                # Get title from lookup, fallback to generic title
                title = media_titles.get(source_media_id, f"Item {source_media_id}")
                
                item = PlaylistItem(
                    playlist_id=playlist_id,
                    media_item_id=mapped_media_id,
                    title=title,
                    position=row.get("Index", 0),
                )
                
                if not self.dry_run:
                    session.add(item)
                
                item_count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating CollectionItem: {e}")
                self.stats.errors += 1
        
        self.stats.collection_items = item_count
        if skipped_items > 0:
            logger.warning(f"Skipped {skipped_items} collection items with unmapped media")
        logger.info(f"Migrated {collection_count} collections with {item_count} items")
        return collection_count
    
    async def migrate_playout_items(self, session: Any) -> int:
        """
        Migrate ErsatzTV playout items (scheduled content timeline).
        
        This preserves the actual scheduled content that appears on channels.
        Only imports items that can be linked to existing media items.
        """
        from datetime import timedelta
        from exstreamtv.database.models import PlayoutItem
        
        rows = self._get_source_rows("PlayoutItem")
        count = 0
        skipped_no_playout = 0
        skipped_no_media = 0
        mapped_with_media = 0
        
        for row in rows:
            try:
                source_playout_id = row.get("PlayoutId")
                playout_id = self.id_maps["playouts"].get(source_playout_id)
                
                if not playout_id:
                    skipped_no_playout += 1
                    continue
                
                # Parse dates (model uses start_time and finish_time)
                start_time = convert_datetime(row.get("Start"))
                finish_time = convert_datetime(row.get("Finish"))
                
                if not start_time or not finish_time:
                    logger.warning(f"Skipping PlayoutItem: missing start/finish time")
                    continue
                
                # Convert in/out points to timedelta (model uses Interval type)
                # ErsatzTV stores these as TimeSpan strings (HH:MM:SS.fff) or seconds
                in_point = None
                out_point = None
                in_point_val = row.get("InPoint")
                out_point_val = row.get("OutPoint")
                
                def parse_timespan(val):
                    """Parse TimeSpan string or numeric seconds to timedelta."""
                    if val is None:
                        return None
                    if isinstance(val, (int, float)):
                        return timedelta(seconds=float(val))
                    if isinstance(val, str):
                        # Parse HH:MM:SS.fff format
                        try:
                            parts = val.split(":")
                            if len(parts) >= 3:
                                hours = int(parts[0])
                                minutes = int(parts[1])
                                # Handle seconds with optional decimal
                                sec_parts = parts[2].split(".")
                                seconds = int(sec_parts[0])
                                microseconds = int(sec_parts[1]) if len(sec_parts) > 1 else 0
                                return timedelta(hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)
                            elif len(parts) == 2:
                                minutes = int(parts[0])
                                seconds = int(parts[1])
                                return timedelta(minutes=minutes, seconds=seconds)
                        except (ValueError, IndexError):
                            pass
                        # Try as float seconds
                        try:
                            return timedelta(seconds=float(val))
                        except ValueError:
                            pass
                    return None
                
                in_point = parse_timespan(in_point_val)
                out_point = parse_timespan(out_point_val)
                
                # Map MediaItemId from ErsatzTV to EXStreamTV
                source_media_id = row.get("MediaItemId")
                mapped_media_id = self.id_maps["media_items"].get(source_media_id) if source_media_id else None
                
                # Skip items without valid media mapping - don't create broken items
                if not mapped_media_id:
                    skipped_no_media += 1
                    continue
                
                mapped_with_media += 1
                
                # Get title - required field, use custom title or generate from metadata
                title = row.get("CustomTitle") or row.get("Title") or f"Item {row.get('Id', 'Unknown')}"
                
                item = PlayoutItem(
                    playout_id=playout_id,
                    media_item_id=mapped_media_id,
                    start_time=start_time,
                    finish_time=finish_time,
                    in_point=in_point,
                    out_point=out_point,
                    title=title,
                    guide_group=row.get("GuideGroup"),
                    custom_title=row.get("CustomTitle"),
                    filler_kind=row.get("FillerKind"),
                )
                
                if not self.dry_run:
                    session.add(item)
                
                count += 1
                
            except Exception as e:
                logger.warning(f"Error migrating PlayoutItem: {e}")
                self.stats.errors += 1
        
        if skipped_no_playout > 0:
            logger.warning(f"Skipped {skipped_no_playout} playout items (playout not found)")
        if skipped_no_media > 0:
            logger.warning(f"Skipped {skipped_no_media} playout items (media not mapped)")
        
        self.stats.playout_items = count
        logger.info(f"Migrated {count} playout items (with media: {mapped_with_media})")
        return count
    
    def get_id_map(self, entity_type: str) -> dict[int, int]:
        """Get ID mapping for an entity type."""
        return self.id_maps.get(entity_type, {})
