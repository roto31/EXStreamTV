"""Channel importer v2 - With REQUIRED metadata extraction and optional AI enhancement"""

import logging
import re
from datetime import datetime
from typing import Any

from ..database.models_v2 import MediaItem, StreamSource
from ..database.session import SessionLocal
from ..metadata.ai_enhancer_v2 import AIMetadataEnhancerV2
from ..metadata.api_key_manager_v2 import APIKeyManagerV2
from ..metadata.engine_v2 import MetadataEngineV2
from ..streaming.stream_manager_v2 import StreamManagerV2

logger = logging.getLogger(__name__)


class ChannelImporterV2:
    """Channel importer v2 - With REQUIRED metadata extraction during import"""

    def __init__(self, db_session=None):
        """
        Initialize channel importer v2

        Args:
            db_session: Optional database session
        """
        self.db = db_session or SessionLocal()
        self.stream_manager = StreamManagerV2()
        self.metadata_engine = MetadataEngineV2(self.stream_manager)

        # Initialize AI enhancer if enabled
        self.ai_enhancer = None
        if self.metadata_engine and hasattr(self.metadata_engine, "enabled"):
            try:
                api_key_manager = APIKeyManagerV2()
                self.ai_enhancer = AIMetadataEnhancerV2(api_key_manager)
            except Exception as e:
                logger.warning(f"AI enhancer not available: {e}")

        self.created_channels = []
        self.created_collections = {}
        self.created_media = {}

    def parse_duration(self, duration_str: str) -> int | None:
        """Parse ISO 8601 duration (PT3M44S) to seconds"""
        if not duration_str:
            return None

        try:
            duration_str = duration_str.replace("PT", "")
            total_seconds = 0

            hours_match = re.search(r"(\d+)H", duration_str)
            if hours_match:
                total_seconds += int(hours_match.group(1)) * 3600

            minutes_match = re.search(r"(\d+)M", duration_str)
            if minutes_match:
                total_seconds += int(minutes_match.group(1)) * 60

            seconds_match = re.search(r"(\d+)S", duration_str)
            if seconds_match:
                total_seconds += int(seconds_match.group(1))

            return total_seconds if total_seconds > 0 else None
        except Exception as e:
            logger.warning(f"Could not parse duration '{duration_str}': {e}")
            return None

    async def get_or_create_media_item(self, stream_data: dict[str, Any]) -> MediaItem:
        """
        Get existing media item or create new one with REQUIRED metadata extraction

        CRITICAL: This method REQUIRES metadata extraction during import.
        Metadata extraction is not optional - it's a core part of the import process.

        Args:
            stream_data: Stream data from YAML

        Returns:
            MediaItem with all metadata fields populated

        Raises:
            ValueError: If URL is missing or metadata extraction fails
            RuntimeError: If metadata extraction fails
        """
        url = stream_data.get("url")
        if not url:
            raise ValueError("Stream data missing 'url' field")

        # Check if media item already exists
        existing = self.db.query(MediaItem).filter(MediaItem.url == url).first()
        if existing:
            # Optionally update metadata if it's incomplete
            if not existing.title or not existing.description:
                logger.info(f"Updating incomplete metadata for existing item: {url[:100]}")
                try:
                    metadata = await self.metadata_engine.extract_metadata(url)
                    self._update_media_item_from_metadata(existing, metadata)
                    self.db.commit()
                except Exception as e:
                    logger.warning(f"Failed to update metadata for existing item: {e}")

            return existing

        # Determine source
        source = self.stream_manager.detect_source(url)

        # REQUIRED: Extract metadata during import
        logger.info(f"Extracting metadata (REQUIRED) for: {url[:100]}...")
        try:
            metadata = await self.metadata_engine.extract_metadata(url, source)
        except Exception as e:
            logger.exception(f"Metadata extraction failed (REQUIRED): {e}")
            raise RuntimeError(f"Failed to extract metadata during import: {e}") from e

        # Optional: AI enhancement if enabled
        if self.ai_enhancer and self.ai_enhancer.enabled:
            try:
                logger.debug("Applying AI enhancement to metadata...")
                enhanced_metadata = await self.ai_enhancer.enhance_metadata(metadata, source.value)

                # Merge enhanced fields
                if enhanced_metadata.get("ai_enhanced_title"):
                    metadata["ai_enhanced_title"] = enhanced_metadata["ai_enhanced_title"]
                if enhanced_metadata.get("ai_enhanced_description"):
                    metadata["ai_enhanced_description"] = enhanced_metadata[
                        "ai_enhanced_description"
                    ]
                if enhanced_metadata.get("epg_data"):
                    metadata["epg_data"] = enhanced_metadata["epg_data"]

                metadata["ai_enhanced_at"] = enhanced_metadata.get("ai_enhanced_at")
                metadata["ai_model_used"] = enhanced_metadata.get("ai_model_used")
            except Exception as e:
                logger.warning(f"AI enhancement failed (non-critical): {e}")
                # Continue without AI enhancement

        # Create MediaItem from extracted metadata
        source_id = self._extract_source_id(url, metadata, source)

        # Parse upload_date if it's a string
        upload_date = None
        if metadata.get("upload_date"):
            upload_date_str = metadata.get("upload_date")
            if isinstance(upload_date_str, str):
                try:
                    from dateutil import parser

                    upload_date = parser.parse(upload_date_str)
                except Exception:
                    pass

        import json

        # Use AI-enhanced title if available, otherwise use raw title
        title = metadata.get("ai_enhanced_title") or metadata.get("title", "")
        if not title:
            # Fallback to YAML data
            title = stream_data.get("title") or stream_data.get("id", "Untitled")

        # Use AI-enhanced description if available
        description = metadata.get("ai_enhanced_description") or metadata.get("description", "")
        if not description:
            description = stream_data.get("notes", "")

        # Build source_config
        source_config = {}
        if source == StreamSource.ARCHIVE_ORG:
            source_config = {
                "preferred_format": metadata.get("preferred_format", "h264"),
                "file_selection": metadata.get("file_selection", "best_quality"),
            }
        elif source == StreamSource.YOUTUBE:
            source_config = {
                "format": metadata.get("format", "bestvideo+bestaudio/best"),
                "prefer_avc": metadata.get("prefer_avc", True),
            }

        # Create new MediaItem with all metadata fields
        new_item = MediaItem(
            source=source,
            source_id=source_id,
            url=url,
            title=title,
            description=description,
            duration=metadata.get("duration")
            or metadata.get("runtime")
            or self.parse_duration(stream_data.get("runtime")),
            thumbnail=metadata.get("thumbnail"),
            uploader=metadata.get("uploader") or metadata.get("creator"),
            upload_date=upload_date,
            view_count=metadata.get("view_count"),
            # Archive.org specific
            archive_org_identifier=metadata.get("identifier")
            if source == StreamSource.ARCHIVE_ORG
            else None,
            archive_org_filename=metadata.get("filename")
            if source == StreamSource.ARCHIVE_ORG
            else None,
            archive_org_creator=metadata.get("creator")
            if source == StreamSource.ARCHIVE_ORG
            else None,
            archive_org_collection=metadata.get("collection")
            if source == StreamSource.ARCHIVE_ORG
            else None,
            archive_org_subject=json.dumps(metadata.get("subject", []))
            if source == StreamSource.ARCHIVE_ORG and metadata.get("subject")
            else None,
            archive_org_broadcast_date=metadata.get("broadcast_date")
            if source == StreamSource.ARCHIVE_ORG
            else None,
            # YouTube specific
            youtube_video_id=metadata.get("video_id") if source == StreamSource.YOUTUBE else None,
            youtube_channel_id=metadata.get("channel_id")
            if source == StreamSource.YOUTUBE
            else None,
            youtube_channel_title=metadata.get("channel_title")
            if source == StreamSource.YOUTUBE
            else None,
            youtube_tags=json.dumps(metadata.get("tags", []))
            if source == StreamSource.YOUTUBE and metadata.get("tags")
            else None,
            youtube_category=metadata.get("category") if source == StreamSource.YOUTUBE else None,
            youtube_like_count=metadata.get("like_count")
            if source == StreamSource.YOUTUBE
            else None,
            youtube_comment_count=metadata.get("comment_count")
            if source == StreamSource.YOUTUBE
            else None,
            # Plex specific
            plex_rating_key=metadata.get("rating_key") if source == StreamSource.PLEX else None,
            plex_guid=metadata.get("guid") if source == StreamSource.PLEX else None,
            plex_library_section_id=metadata.get("library_section_id")
            if source == StreamSource.PLEX
            else None,
            # AI-enhanced fields
            ai_enhanced_title=metadata.get("ai_enhanced_title"),
            ai_enhanced_description=metadata.get("ai_enhanced_description"),
            ai_enhanced_at=metadata.get("ai_enhanced_at"),
            ai_model_used=metadata.get("ai_model_used"),
            # Source config
            source_config=json.dumps(source_config) if source_config else None,
        )

        self.db.add(new_item)
        self.db.flush()

        logger.info(f"Created media item with metadata: {title[:50]} (source: {source.value})")

        return new_item

    def _extract_source_id(self, url: str, metadata: dict[str, Any], source: StreamSource) -> str:
        """Extract source ID from URL or metadata"""
        if source == StreamSource.YOUTUBE:
            return metadata.get("video_id") or (
                self.stream_manager.youtube_adapter.extract_video_id(url)
                if self.stream_manager.youtube_adapter
                else url
            )
        elif source == StreamSource.ARCHIVE_ORG:
            return metadata.get("identifier") or (
                self.stream_manager.archive_org_adapter.extract_identifier(url)
                if self.stream_manager.archive_org_adapter
                else url
            )
        elif source == StreamSource.PLEX:
            return metadata.get("rating_key") or (
                self.stream_manager.plex_adapter.extract_rating_key(url)
                if self.stream_manager.plex_adapter
                else url
            )
        return url

    def _update_media_item_from_metadata(self, media_item: MediaItem, metadata: dict[str, Any]):
        """Update existing MediaItem with new metadata"""
        import json

        # Update core fields
        if metadata.get("title"):
            media_item.title = metadata.get("title")
        if metadata.get("description"):
            media_item.description = metadata.get("description")
        if metadata.get("duration") or metadata.get("runtime"):
            media_item.duration = metadata.get("duration") or metadata.get("runtime")
        if metadata.get("thumbnail"):
            media_item.thumbnail = metadata.get("thumbnail")
        if metadata.get("uploader") or metadata.get("creator"):
            media_item.uploader = metadata.get("uploader") or metadata.get("creator")

        # Update source-specific fields based on source
        source = StreamSource(metadata.get("source", "youtube"))

        if source == StreamSource.ARCHIVE_ORG:
            if metadata.get("identifier"):
                media_item.archive_org_identifier = metadata.get("identifier")
            if metadata.get("filename"):
                media_item.archive_org_filename = metadata.get("filename")
            if metadata.get("creator"):
                media_item.archive_org_creator = metadata.get("creator")
            if metadata.get("collection"):
                media_item.archive_org_collection = metadata.get("collection")
            if metadata.get("subject"):
                media_item.archive_org_subject = json.dumps(metadata.get("subject"))

        elif source == StreamSource.YOUTUBE:
            if metadata.get("video_id"):
                media_item.youtube_video_id = metadata.get("video_id")
            if metadata.get("channel_id"):
                media_item.youtube_channel_id = metadata.get("channel_id")
            if metadata.get("channel_title"):
                media_item.youtube_channel_title = metadata.get("channel_title")
            if metadata.get("tags"):
                media_item.youtube_tags = json.dumps(metadata.get("tags"))
            if metadata.get("category"):
                media_item.youtube_category = metadata.get("category")
            if metadata.get("like_count"):
                media_item.youtube_like_count = metadata.get("like_count")
            if metadata.get("comment_count"):
                media_item.youtube_comment_count = metadata.get("comment_count")

        elif source == StreamSource.PLEX:
            if metadata.get("rating_key"):
                media_item.plex_rating_key = metadata.get("rating_key")
            if metadata.get("guid"):
                media_item.plex_guid = metadata.get("guid")
            if metadata.get("library_section_id"):
                media_item.plex_library_section_id = metadata.get("library_section_id")

        media_item.updated_at = datetime.utcnow()

    # Additional methods for collection/playlist creation would go here
    # (similar to original channel_importer.py but using v2 models)
