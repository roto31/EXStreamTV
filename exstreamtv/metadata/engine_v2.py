"""Metadata extraction engine v2 - Unified metadata extraction from all sources with REQUIRED extraction during import"""

import logging
from datetime import datetime
from typing import Any

from ..database.models_v2 import MediaItem, StreamSource
from ..streaming.stream_manager_v2 import StreamManagerV2
from .extractors.archive_org_v2 import ArchiveOrgMetadataExtractorV2
from .extractors.plex_v2 import PlexMetadataExtractorV2
from .extractors.youtube_v2 import YouTubeMetadataExtractorV2

logger = logging.getLogger(__name__)


class MetadataEngineV2:
    """
    Metadata extraction engine v2

    CRITICAL: Metadata extraction from Archive.org and YouTube is REQUIRED during channel import,
    not an optional enrichment step. All metadata must be extracted during the import process.
    """

    def __init__(self, stream_manager: StreamManagerV2 | None = None):
        """
        Initialize metadata engine

        Args:
            stream_manager: Optional stream manager instance (creates new if not provided)
        """
        self.stream_manager = stream_manager or StreamManagerV2()

        # Initialize extractors
        self.archive_org_extractor = ArchiveOrgMetadataExtractorV2(self.stream_manager)
        self.youtube_extractor = YouTubeMetadataExtractorV2(self.stream_manager)
        self.plex_extractor = PlexMetadataExtractorV2(self.stream_manager)

    async def extract_metadata(
        self, url: str, source: StreamSource | None = None, media_item: MediaItem | None = None
    ) -> dict[str, Any]:
        """
        Extract metadata from source (REQUIRED during import)

        This method MUST be called during channel import to extract all available metadata.
        It is not optional - metadata extraction is a core part of the import process.

        Args:
            url: Media URL
            source: Optional source type (auto-detected if not provided)
            media_item: Optional existing media item (for updates)

        Returns:
            Complete metadata dict with all available fields

        Raises:
            ValueError: If URL is invalid or source not supported
            RuntimeError: If extraction fails
        """
        if not url:
            raise ValueError("URL is required for metadata extraction")

        # Detect source if not provided
        if source is None:
            source = self.stream_manager.detect_source(url)

        logger.info(f"Extracting metadata from {source.value} for URL: {url[:100]}...")

        try:
            # Route to appropriate extractor
            if source == StreamSource.ARCHIVE_ORG:
                metadata = await self.archive_org_extractor.extract_all(url)

            elif source == StreamSource.YOUTUBE:
                metadata = await self.youtube_extractor.extract_all(url)

            elif source == StreamSource.PLEX:
                metadata = await self.plex_extractor.extract_all(url)

            else:
                raise ValueError(f"Unsupported source type for metadata extraction: {source}")

            # Add common fields
            metadata["source"] = source.value
            metadata["url"] = url
            metadata["extracted_at"] = datetime.utcnow()

            logger.info(
                f"Successfully extracted metadata from {source.value} ({len(metadata)} fields)"
            )

            return metadata

        except Exception as e:
            logger.exception(f"Failed to extract metadata from {source.value}: {url[:100]}: {e}")
            raise RuntimeError(f"Metadata extraction failed: {e}") from e

    async def extract_and_store_metadata(
        self, url: str, source: StreamSource | None = None, db_session=None
    ) -> MediaItem:
        """
        Extract metadata and store in database (REQUIRED during import)

        This method combines extraction and storage, ensuring metadata is always
        available in the database for EPG generation.

        Args:
            url: Media URL
            source: Optional source type
            db_session: Database session

        Returns:
            MediaItem with all metadata fields populated
        """
        if not db_session:
            raise ValueError("Database session is required")

        # Extract metadata (REQUIRED)
        metadata = await self.extract_metadata(url, source)

        # Create or update MediaItem
        source_id = self._extract_source_id(url, metadata.get("source"))

        # Check if MediaItem already exists
        existing_item = db_session.query(MediaItem).filter(MediaItem.url == url).first()

        if existing_item:
            # Update existing item with new metadata
            self._update_media_item(existing_item, metadata)
            db_session.commit()
            return existing_item
        else:
            # Create new MediaItem
            new_item = self._create_media_item(metadata, source_id)
            db_session.add(new_item)
            db_session.commit()
            db_session.refresh(new_item)
            return new_item

    def _extract_source_id(self, url: str, source_str: str) -> str:
        """Extract source ID from URL"""
        if source_str == StreamSource.YOUTUBE.value:
            video_id = (
                self.stream_manager.youtube_adapter.extract_video_id(url)
                if self.stream_manager.youtube_adapter
                else None
            )
            return video_id or url
        elif source_str == StreamSource.ARCHIVE_ORG.value:
            identifier = (
                self.stream_manager.archive_org_adapter.extract_identifier(url)
                if self.stream_manager.archive_org_adapter
                else None
            )
            return identifier or url
        elif source_str == StreamSource.PLEX.value:
            rating_key = (
                self.stream_manager.plex_adapter.extract_rating_key(url)
                if self.stream_manager.plex_adapter
                else None
            )
            return rating_key or url
        return url

    def _create_media_item(self, metadata: dict[str, Any], source_id: str) -> MediaItem:
        """Create MediaItem from extracted metadata"""
        source = StreamSource(metadata.get("source", "youtube"))

        # Parse upload_date if it's a string
        upload_date = None
        if metadata.get("upload_date"):
            upload_date_str = metadata.get("upload_date")
            if isinstance(upload_date_str, str):
                try:
                    # Try parsing various date formats
                    from dateutil import parser

                    upload_date = parser.parse(upload_date_str)
                except Exception:
                    pass

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

        import json

        return MediaItem(
            source=source,
            source_id=source_id,
            url=metadata.get("url", ""),
            title=metadata.get("title", ""),
            description=metadata.get("description"),
            duration=metadata.get("duration") or metadata.get("runtime"),
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
            # Source config
            source_config=json.dumps(source_config) if source_config else None,
        )

    def _update_media_item(self, media_item: MediaItem, metadata: dict[str, Any]):
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

        # Update source-specific fields
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
