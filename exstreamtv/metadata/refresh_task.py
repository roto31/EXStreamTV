"""Background task for refreshing metadata for existing media items"""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..database import MediaItem, get_db
from ..streaming.stream_manager import StreamManager
from .enricher import MetadataEnricher
from .extractor import extract_metadata

logger = logging.getLogger(__name__)


class MetadataRefreshTask:
    """Background task to refresh metadata for existing media items"""

    def __init__(
        self,
        enricher: MetadataEnricher | None = None,
        stream_manager: StreamManager | None = None,
        refresh_interval_hours: int = 24,
        batch_size: int = 10,
    ):
        """
        Initialize metadata refresh task.

        Args:
            enricher: MetadataEnricher instance
            stream_manager: StreamManager instance
            refresh_interval_hours: Hours between refreshes for each item
            batch_size: Number of items to process per batch
        """
        self.enricher = enricher
        self.stream_manager = stream_manager or StreamManager()
        self.refresh_interval_hours = refresh_interval_hours
        self.batch_size = batch_size
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self):
        """Start the background refresh task"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info("Started metadata refresh background task")

    def stop(self):
        """Stop the background refresh task"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Stopped metadata refresh background task")

    async def _refresh_loop(self):
        """Main refresh loop"""
        while self._running:
            try:
                await self.refresh_metadata_batch()
                # Wait 1 hour before next batch
                await asyncio.sleep(3600.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in metadata refresh loop: {e}")
                await asyncio.sleep(3600.0)  # Wait before retrying

    async def refresh_metadata_batch(self):
        """Refresh metadata for a batch of media items"""
        db = next(get_db())
        try:
            # Find items that need refreshing (missing metadata or stale)
            cutoff_time = datetime.utcnow() - timedelta(hours=self.refresh_interval_hours)

            # Get items missing key metadata fields
            items_to_refresh = (
                db.query(MediaItem)
                .filter((MediaItem.series_title.is_(None)) | (MediaItem.updated_at < cutoff_time))
                .limit(self.batch_size)
                .all()
            )

            if not items_to_refresh:
                logger.debug("No media items need metadata refresh")
                return

            logger.info(f"Refreshing metadata for {len(items_to_refresh)} media items")

            for media_item in items_to_refresh:
                if not self._running:
                    break

                try:
                    await self.refresh_media_item_metadata(media_item, db)
                except Exception as e:
                    logger.exception(
                        f"Error refreshing metadata for media item {media_item.id}: {e}"
                    )

            db.commit()

        except Exception as e:
            logger.exception(f"Error in metadata refresh batch: {e}")
            db.rollback()
        finally:
            db.close()

    async def refresh_media_item_metadata(self, media_item: MediaItem, db: Session):
        """
        Refresh metadata for a single media item.

        Args:
            media_item: MediaItem instance
            db: Database session
        """
        # Detect source
        source = self.stream_manager.detect_source(media_item.url)

        # Get video info if available
        video_info = None
        try:
            video_info = await self.stream_manager.get_media_info(media_item.url, source=source)
        except Exception as e:
            logger.debug(f"Could not get media info for {media_item.url}: {e}")

        # Extract metadata
        extracted = extract_metadata(media_item.url, source, video_info)

        # Enrich metadata if enricher is available
        if self.enricher:
            try:
                enriched = await self.enricher.enrich_media_item(media_item)
                # Merge enriched data
                for key, value in enriched.items():
                    if value and (key not in extracted or not extracted[key]):
                        extracted[key] = value
            except Exception as e:
                logger.warning(f"Error enriching metadata for {media_item.id}: {e}")

        # Update media item with extracted metadata
        if extracted.get("series_title"):
            media_item.series_title = extracted["series_title"]
        if extracted.get("episode_title"):
            media_item.episode_title = extracted["episode_title"]
        if extracted.get("season_number"):
            media_item.season_number = extracted["season_number"]
        if extracted.get("episode_number"):
            media_item.episode_number = extracted["episode_number"]
        if extracted.get("episode_air_date"):
            media_item.episode_air_date = extracted["episode_air_date"]
        if extracted.get("content_rating"):
            media_item.content_rating = extracted["content_rating"]

        # Update JSON fields
        import json

        if extracted.get("genres"):
            media_item.genres = (
                json.dumps(extracted["genres"])
                if isinstance(extracted["genres"], list)
                else extracted["genres"]
            )
        if extracted.get("actors"):
            media_item.actors = (
                json.dumps(extracted["actors"])
                if isinstance(extracted["actors"], list)
                else extracted["actors"]
            )
        if extracted.get("directors"):
            media_item.directors = (
                json.dumps(extracted["directors"])
                if isinstance(extracted["directors"], list)
                else extracted["directors"]
            )
        if extracted.get("guids"):
            media_item.guids = (
                json.dumps(extracted["guids"])
                if isinstance(extracted["guids"], dict)
                else extracted["guids"]
            )

        # Update timestamp
        media_item.updated_at = datetime.utcnow()

        logger.debug(f"Refreshed metadata for media item {media_item.id}: {media_item.title}")
