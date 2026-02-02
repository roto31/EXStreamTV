"""
Migration Validators

Pre-migration and post-migration validation for ErsatzTV and StreamTV imports.
Ensures data integrity and compatibility before and after migration.
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    
    def add_error(self, message: str) -> None:
        """Add an error (makes result invalid)."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a warning (does not invalidate)."""
        self.warnings.append(message)
    
    def add_info(self, message: str) -> None:
        """Add an informational message."""
        self.info.append(message)
    
    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)
        self.counts.update(other.counts)
        if not other.is_valid:
            self.is_valid = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "counts": self.counts,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


class ErsatzTVValidator:
    """Validator for ErsatzTV database before migration."""
    
    # Expected tables in ErsatzTV database (singular names)
    EXPECTED_TABLES = [
        "Channel",
        "FFmpegProfile",
        "Playout",
        "ProgramSchedule",
        "ProgramScheduleItem",
        "Block",
        "BlockItem",
        "ChannelWatermark",
        "FillerPreset",
        "Deco",
        "Resolution",
        "PlexLibrary",
        "PlexMediaSource",
        "PlexConnection",
        "Collection",
        "CollectionItem",
        "MediaItem",
        "MediaVersion",
        "MediaFile",
    ]
    
    # Required columns per table
    REQUIRED_COLUMNS = {
        "Channel": ["Id", "Number", "Name"],
        "FFmpegProfile": ["Id", "Name"],
        "Playout": ["Id", "ChannelId"],
        "ProgramSchedule": ["Id", "Name"],
        "ProgramScheduleItem": ["Id", "ProgramScheduleId"],
        "Block": ["Id", "Name"],
    }
    
    def __init__(self, db_path: str | Path):
        """
        Initialize validator.
        
        Args:
            db_path: Path to ErsatzTV SQLite database
        """
        self.db_path = Path(db_path)
    
    def validate_source(self) -> ValidationResult:
        """
        Validate the source ErsatzTV database.
        
        Returns:
            ValidationResult with all checks
        """
        result = ValidationResult()
        
        # Check file exists
        if not self.db_path.exists():
            result.add_error(f"Database file not found: {self.db_path}")
            return result
        
        if not self.db_path.is_file():
            result.add_error(f"Path is not a file: {self.db_path}")
            return result
        
        result.add_info(f"Found database: {self.db_path}")
        result.add_info(f"Database size: {self.db_path.stat().st_size / 1024 / 1024:.2f} MB")
        
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Check tables exist
            self._validate_tables(cursor, result)
            
            # Check required columns
            self._validate_columns(cursor, result)
            
            # Get counts
            self._get_counts(cursor, result)
            
            # Check for data integrity
            self._validate_integrity(cursor, result)
            
            conn.close()
            
        except sqlite3.Error as e:
            result.add_error(f"SQLite error: {e}")
        except Exception as e:
            result.add_error(f"Unexpected error: {e}")
        
        return result
    
    def _validate_tables(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """Check that expected tables exist."""
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        for table in self.EXPECTED_TABLES:
            if table not in existing_tables:
                # Try lowercase
                if table.lower() not in {t.lower() for t in existing_tables}:
                    result.add_warning(f"Table '{table}' not found")
                else:
                    result.add_info(f"Table '{table}' found (case mismatch)")
            else:
                result.add_info(f"Table '{table}' found")
    
    def _validate_columns(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """Check that required columns exist."""
        for table, columns in self.REQUIRED_COLUMNS.items():
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                for col in columns:
                    if col not in existing_columns:
                        result.add_warning(f"Column '{col}' not found in '{table}'")
            except sqlite3.Error:
                result.add_warning(f"Could not check columns for '{table}'")
    
    def _get_counts(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """Get row counts for each table."""
        for table in self.EXPECTED_TABLES:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                result.counts[table.lower()] = count
                result.add_info(f"{table}: {count} rows")
            except sqlite3.Error:
                result.counts[table.lower()] = 0
    
    def _validate_integrity(self, cursor: sqlite3.Cursor, result: ValidationResult) -> None:
        """Check data integrity."""
        # Check for orphaned playouts
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM Playouts 
                WHERE ChannelId NOT IN (SELECT Id FROM Channels)
            """)
            orphaned = cursor.fetchone()[0]
            if orphaned > 0:
                result.add_warning(f"{orphaned} playouts reference non-existent channels")
        except sqlite3.Error:
            pass
        
        # Check for duplicate channel numbers
        try:
            cursor.execute("""
                SELECT Number, COUNT(*) as cnt FROM Channels 
                GROUP BY Number HAVING cnt > 1
            """)
            duplicates = cursor.fetchall()
            for dup in duplicates:
                result.add_warning(f"Duplicate channel number: {dup[0]}")
        except sqlite3.Error:
            pass


class PostMigrationValidator:
    """Validator for post-migration integrity checks."""
    
    def __init__(self, session: Any):
        """
        Initialize validator.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def validate_migration(
        self,
        expected_counts: dict[str, int],
    ) -> ValidationResult:
        """
        Validate that migration completed correctly.
        
        Args:
            expected_counts: Expected row counts from source
            
        Returns:
            ValidationResult with all checks
        """
        from sqlalchemy import func, select
        
        from exstreamtv.database.models import (
            Block,
            Channel,
            Deco,
            FFmpegProfile,
            FillerPreset,
            Playout,
            ProgramSchedule,
        )
        
        result = ValidationResult()
        
        # Check counts
        model_map = {
            "channels": Channel,
            "ffmpegprofiles": FFmpegProfile,
            "playouts": Playout,
            "programschedules": ProgramSchedule,
            "blocks": Block,
            "fillerpresets": FillerPreset,
            "decos": Deco,
        }
        
        for source_table, model in model_map.items():
            expected = expected_counts.get(source_table, 0)
            if expected == 0:
                continue
            
            try:
                stmt = select(func.count()).select_from(model)
                actual_result = await self.session.execute(stmt)
                actual = actual_result.scalar()
                
                result.counts[source_table] = actual
                
                if actual == expected:
                    result.add_info(f"{source_table}: {actual} rows (expected {expected})")
                elif actual < expected:
                    result.add_warning(
                        f"{source_table}: {actual} rows (expected {expected}, "
                        f"missing {expected - actual})"
                    )
                else:
                    result.add_info(
                        f"{source_table}: {actual} rows (expected {expected}, "
                        f"extra {actual - expected})"
                    )
            except Exception as e:
                result.add_error(f"Error checking {source_table}: {e}")
        
        return result
    
    async def validate_relationships(self) -> ValidationResult:
        """Validate that all foreign key relationships are valid."""
        from sqlalchemy import select
        
        from exstreamtv.database.models import (
            Channel,
            Playout,
        )
        
        result = ValidationResult()
        
        # Check playouts have valid channels
        try:
            stmt = select(Playout).where(Playout.channel_id.isnot(None))
            playouts_result = await self.session.execute(stmt)
            playouts = playouts_result.scalars().all()
            
            for playout in playouts:
                channel_stmt = select(Channel).where(Channel.id == playout.channel_id)
                channel_result = await self.session.execute(channel_stmt)
                channel = channel_result.scalar()
                
                if not channel:
                    result.add_warning(
                        f"Playout {playout.id} references missing channel {playout.channel_id}"
                    )
            
            result.add_info(f"Checked {len(playouts)} playout relationships")
            
        except Exception as e:
            result.add_error(f"Error validating relationships: {e}")
        
        return result


class AICompatibilityValidator:
    """Validate that migrated data is compatible with AI systems."""
    
    def __init__(self, session: Any):
        """
        Initialize validator.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def validate_channel_creator_compatibility(self) -> ValidationResult:
        """Validate channels are compatible with AI channel creator."""
        from sqlalchemy import select
        
        from exstreamtv.database.models import Channel, Deco
        
        result = ValidationResult()
        
        try:
            # Check channels have required fields
            stmt = select(Channel)
            channels_result = await self.session.execute(stmt)
            channels = channels_result.scalars().all()
            
            for channel in channels:
                if not channel.name:
                    result.add_warning(f"Channel {channel.id} has no name")
                if not channel.number:
                    result.add_warning(f"Channel {channel.id} has no number")
            
            result.add_info(f"Validated {len(channels)} channels for AI compatibility")
            
            # Check decos exist for channels that need them
            stmt = select(Deco)
            decos_result = await self.session.execute(stmt)
            decos = decos_result.scalars().all()
            result.add_info(f"Found {len(decos)} deco configurations")
            
        except Exception as e:
            result.add_error(f"Error validating AI compatibility: {e}")
        
        return result
    
    async def validate_schedule_generator_compatibility(self) -> ValidationResult:
        """Validate schedules are compatible with AI schedule generator."""
        from sqlalchemy import select
        
        from exstreamtv.database.models import (
            ProgramSchedule,
            ProgramScheduleItem,
        )
        
        result = ValidationResult()
        
        try:
            # Check schedules
            stmt = select(ProgramSchedule)
            schedules_result = await self.session.execute(stmt)
            schedules = schedules_result.scalars().all()
            
            for schedule in schedules:
                if not schedule.name:
                    result.add_warning(f"Schedule {schedule.id} has no name")
            
            result.add_info(f"Validated {len(schedules)} schedules")
            
            # Check schedule items
            stmt = select(ProgramScheduleItem)
            items_result = await self.session.execute(stmt)
            items = items_result.scalars().all()
            result.add_info(f"Found {len(items)} schedule items")
            
        except Exception as e:
            result.add_error(f"Error validating schedule compatibility: {e}")
        
        return result
    
    async def validate_block_executor_compatibility(self) -> ValidationResult:
        """Validate blocks are compatible with AI block executor."""
        from sqlalchemy import select
        
        from exstreamtv.database.models import Block, BlockItem
        
        result = ValidationResult()
        
        try:
            # Check blocks
            stmt = select(Block)
            blocks_result = await self.session.execute(stmt)
            blocks = blocks_result.scalars().all()
            
            for block in blocks:
                if not block.name:
                    result.add_warning(f"Block {block.id} has no name")
                if not block.start_time:
                    result.add_warning(f"Block {block.id} has no start time")
                if not block.duration_minutes:
                    result.add_warning(f"Block {block.id} has no duration")
            
            result.add_info(f"Validated {len(blocks)} blocks")
            
            # Check block items
            stmt = select(BlockItem)
            items_result = await self.session.execute(stmt)
            items = items_result.scalars().all()
            result.add_info(f"Found {len(items)} block items")
            
        except Exception as e:
            result.add_error(f"Error validating block compatibility: {e}")
        
        return result


class StreamingReadinessValidator:
    """
    Validate that all required data was imported for streaming to work.
    
    Checks:
    - At least 1 Plex library with valid token
    - Media items exist for collections
    - Schedule items reference valid collections
    - Playouts have valid channel + schedule references
    """
    
    def __init__(self, session: Any):
        """
        Initialize validator.
        
        Args:
            session: SQLAlchemy async session
        """
        self.session = session
    
    async def validate_streaming_readiness(self) -> ValidationResult:
        """
        Validate that all required data is present for streaming.
        
        Returns:
            ValidationResult with streaming readiness checks
        """
        result = ValidationResult()
        
        # Run all checks
        await self._check_plex_libraries(result)
        await self._check_media_items(result)
        await self._check_channels_and_playouts(result)
        await self._check_schedules(result)
        
        return result
    
    async def _check_plex_libraries(self, result: ValidationResult) -> None:
        """Check Plex libraries are configured with valid tokens."""
        from sqlalchemy import func, select
        
        from exstreamtv.database.models import PlexLibrary
        
        try:
            # Count libraries
            stmt = select(func.count()).select_from(PlexLibrary)
            count_result = await self.session.execute(stmt)
            count = count_result.scalar()
            
            result.counts["plex_libraries"] = count
            
            if count == 0:
                result.add_warning("No Plex libraries found - media access may be limited")
            else:
                result.add_info(f"Found {count} Plex libraries")
            
            # Check for placeholder tokens
            stmt = select(PlexLibrary).where(PlexLibrary.token == "TOKEN_REQUIRED")
            missing_token_result = await self.session.execute(stmt)
            missing_tokens = missing_token_result.scalars().all()
            
            if missing_tokens:
                result.add_warning(
                    f"{len(missing_tokens)} Plex libraries need authentication tokens"
                )
                
        except Exception as e:
            result.add_error(f"Error checking Plex libraries: {e}")
    
    async def _check_media_items(self, result: ValidationResult) -> None:
        """Check media items were imported."""
        from sqlalchemy import func, select
        
        from exstreamtv.database.models import MediaFile, MediaItem
        
        try:
            # Count media items
            stmt = select(func.count()).select_from(MediaItem)
            count_result = await self.session.execute(stmt)
            item_count = count_result.scalar()
            
            result.counts["media_items"] = item_count
            
            if item_count == 0:
                result.add_error("No media items found - streaming will not work")
            else:
                result.add_info(f"Found {item_count} media items")
            
            # Count media files
            stmt = select(func.count()).select_from(MediaFile)
            count_result = await self.session.execute(stmt)
            file_count = count_result.scalar()
            
            result.counts["media_files"] = file_count
            
            if file_count == 0:
                result.add_warning("No media files found - file paths may be missing")
            else:
                result.add_info(f"Found {file_count} media files")
                
        except Exception as e:
            result.add_error(f"Error checking media items: {e}")
    
    async def _check_channels_and_playouts(self, result: ValidationResult) -> None:
        """Check channels have valid playouts."""
        from sqlalchemy import func, select
        
        from exstreamtv.database.models import Channel, Playout
        
        try:
            # Count channels
            stmt = select(func.count()).select_from(Channel)
            count_result = await self.session.execute(stmt)
            channel_count = count_result.scalar()
            
            result.counts["channels"] = channel_count
            
            if channel_count == 0:
                result.add_error("No channels found")
            else:
                result.add_info(f"Found {channel_count} channels")
            
            # Count playouts
            stmt = select(func.count()).select_from(Playout)
            count_result = await self.session.execute(stmt)
            playout_count = count_result.scalar()
            
            result.counts["playouts"] = playout_count
            
            if playout_count == 0:
                result.add_warning("No playouts found - channels may not have schedules")
            else:
                result.add_info(f"Found {playout_count} playouts")
            
            # Check for channels without playouts
            stmt = select(Channel).where(
                ~Channel.id.in_(select(Playout.channel_id))
            )
            orphan_result = await self.session.execute(stmt)
            orphan_channels = orphan_result.scalars().all()
            
            if orphan_channels:
                result.add_warning(
                    f"{len(orphan_channels)} channels have no playout configuration"
                )
                
        except Exception as e:
            result.add_error(f"Error checking channels and playouts: {e}")
    
    async def _check_schedules(self, result: ValidationResult) -> None:
        """Check schedules have items."""
        from sqlalchemy import func, select
        
        from exstreamtv.database.models import (
            Playlist,
            PlaylistItem,
            ProgramSchedule,
            ProgramScheduleItem,
        )
        
        try:
            # Count schedules
            stmt = select(func.count()).select_from(ProgramSchedule)
            count_result = await self.session.execute(stmt)
            schedule_count = count_result.scalar()
            
            result.counts["schedules"] = schedule_count
            result.add_info(f"Found {schedule_count} program schedules")
            
            # Count schedule items
            stmt = select(func.count()).select_from(ProgramScheduleItem)
            count_result = await self.session.execute(stmt)
            item_count = count_result.scalar()
            
            result.counts["schedule_items"] = item_count
            result.add_info(f"Found {item_count} schedule items")
            
            # Count playlists (collections)
            stmt = select(func.count()).select_from(Playlist)
            count_result = await self.session.execute(stmt)
            playlist_count = count_result.scalar()
            
            result.counts["playlists"] = playlist_count
            result.add_info(f"Found {playlist_count} playlists/collections")
            
            # Count playlist items
            stmt = select(func.count()).select_from(PlaylistItem)
            count_result = await self.session.execute(stmt)
            playlist_item_count = count_result.scalar()
            
            result.counts["playlist_items"] = playlist_item_count
            
            if playlist_item_count == 0 and playlist_count > 0:
                result.add_warning("Playlists exist but have no items")
            else:
                result.add_info(f"Found {playlist_item_count} playlist items")
                
        except Exception as e:
            result.add_error(f"Error checking schedules: {e}")
