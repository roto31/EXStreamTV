"""Import channels and all requirements from YAML files"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from ..database.models import (
    Channel,
    Collection,
    CollectionItem,
    MediaItem,
    Playlist,
    PlaylistItem,
    StreamSource,
)
from ..database.session import SessionLocal, init_db
from ..streaming import StreamManager
from ..validation import ValidationError, YAMLValidator

logger = logging.getLogger(__name__)


class ChannelImporter:
    """Import channels and all requirements from YAML configuration"""

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self.stream_manager = StreamManager()
        self.created_channels = []
        self.created_collections = {}
        self.created_media = {}

    def parse_duration(self, duration_str: str) -> int | None:
        """Parse ISO 8601 duration (PT3M44S) to seconds"""
        if not duration_str:
            return None

        try:
            # Remove PT prefix
            duration_str = duration_str.replace("PT", "")

            total_seconds = 0

            # Parse hours
            hours_match = re.search(r"(\d+)H", duration_str)
            if hours_match:
                total_seconds += int(hours_match.group(1)) * 3600

            # Parse minutes
            minutes_match = re.search(r"(\d+)M", duration_str)
            if minutes_match:
                total_seconds += int(minutes_match.group(1)) * 60

            # Parse seconds
            seconds_match = re.search(r"(\d+)S", duration_str)
            if seconds_match:
                total_seconds += int(seconds_match.group(1))

            return total_seconds if total_seconds > 0 else None
        except Exception as e:
            logger.warning(f"Could not parse duration '{duration_str}': {e}")
            return None

    async def get_or_create_media_item(self, stream_data: dict[str, Any]) -> MediaItem:
        """Get existing media item or create new one"""
        url = stream_data.get("url")
        if not url:
            raise ValueError("Stream data missing 'url' field")

        # Check if media item already exists
        existing = self.db.query(MediaItem).filter(MediaItem.url == url).first()
        if existing:
            return existing

        # Determine source
        source_str = stream_data.get("source", "").lower()
        if source_str == "plex" or "plex://" in url:
            source = StreamSource.PLEX
        elif "youtube" in source_str or "youtu.be" in url or "youtube.com" in url:
            source = StreamSource.YOUTUBE
        elif "archive" in source_str or "archive.org" in url:
            source = StreamSource.ARCHIVE_ORG
        else:
            source = StreamSource.YOUTUBE  # Default

        # Extract source ID
        source_id = ""
        if source == StreamSource.PLEX:
            # Extract rating key from Plex URL
            plex_rating_key = stream_data.get("plex_rating_key")
            if plex_rating_key:
                source_id = str(plex_rating_key)
            else:
                # Try to extract from URL
                match = re.search(r"/library/metadata/(\d+)", url)
                source_id = match.group(1) if match else url

        # For Plex sources, fetch full metadata from Plex API
        # Use 'title' field first, then 'id', then 'collection' as fallback
        # 'collection' is for grouping, not for individual item titles
        title = (
            stream_data.get("title")
            or stream_data.get("id")
            or stream_data.get("collection", "Untitled")
        )
        description = stream_data.get("notes", "")
        duration = self.parse_duration(stream_data.get("runtime"))
        thumbnail = None
        uploader = stream_data.get("uploader")
        upload_date = stream_data.get("upload_date")

        if source == StreamSource.PLEX and self.stream_manager and self.stream_manager.plex_adapter:
            try:
                plex_info = await self.stream_manager.plex_adapter.get_media_info(url)
                if plex_info:
                    # Use Plex metadata if available
                    if plex_info.get("title"):
                        title = plex_info["title"]
                    if plex_info.get("summary"):
                        description = plex_info["summary"]
                    if plex_info.get("duration"):
                        duration = plex_info["duration"]

                    # Format thumbnail URL - make it absolute if it's a relative path
                    if plex_info.get("thumb"):
                        thumb_path = plex_info["thumb"]
                        if thumb_path.startswith("/"):
                            # Relative path - make it absolute using Plex base URL
                            if self.stream_manager.plex_adapter.base_url:
                                thumbnail = f"{self.stream_manager.plex_adapter.base_url}{thumb_path}?X-Plex-Token={self.stream_manager.plex_adapter.token or ''}"
                            else:
                                thumbnail = thumb_path
                        elif thumb_path.startswith("http"):
                            # Already absolute
                            thumbnail = thumb_path
                        # Relative path without leading slash
                        elif self.stream_manager.plex_adapter.base_url:
                            thumbnail = f"{self.stream_manager.plex_adapter.base_url}/{thumb_path}?X-Plex-Token={self.stream_manager.plex_adapter.token or ''}"
                        else:
                            thumbnail = thumb_path

                    logger.debug(f"  Fetched Plex metadata for {title[:50]}")
            except Exception as e:
                logger.warning(f"  Could not fetch Plex metadata for {url}: {e}. Using YAML data.")

        # Fallback to YAML data if Plex metadata fetch failed
        if not title or title == "Untitled":
            title = stream_data.get("id", "Media Item")

        # Parse duration from YAML if not set from Plex
        if not duration:
            duration = self.parse_duration(stream_data.get("runtime"))

        # Extract source ID for non-Plex sources
        if source == StreamSource.YOUTUBE:
            match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
            if match:
                source_id = match.group(1)
        elif source == StreamSource.ARCHIVE_ORG:
            match = re.search(r"archive\.org\/details\/([^\/\?]+)", url)
            if match:
                source_id = match.group(1)

        # For Archive.org items, fetch enhanced metadata and store in meta_data
        meta_data_json = None
        if (
            source == StreamSource.ARCHIVE_ORG
            and self.stream_manager
            and self.stream_manager.archive_org_adapter
            and source_id
        ):
            try:
                # Fetch enhanced metadata using get_item_info (includes subject, year, language, publisher, contributor, etc.)
                item_info = await self.stream_manager.archive_org_adapter.get_item_info(source_id)

                # Store enhanced metadata in meta_data JSON field
                # This metadata will be used by XMLTV EPG generation
                import json

                meta_data_json = json.dumps(item_info, ensure_ascii=False)

                # Also update basic fields from enhanced metadata if not already set
                if not title or title == "Untitled":
                    title = item_info.get("title", title)
                if not description:
                    description = item_info.get("description", "")
                if not uploader and item_info.get("creator"):
                    uploader = item_info.get("creator")
                if not upload_date and item_info.get("date"):
                    upload_date = str(item_info.get("date", ""))
                if not duration and item_info.get("runtime"):
                    duration = item_info.get("runtime")

                logger.debug(f"  Fetched enhanced metadata for Archive.org item: {source_id}")
            except Exception as e:
                logger.warning(
                    f"  Could not fetch enhanced metadata for Archive.org item {source_id}: {e}"
                )
                # Continue without enhanced metadata - basic fields will be used

        # Create media item
        media_item = MediaItem(
            source=source,
            source_id=source_id or url,
            url=url,
            title=title,
            description=description,
            duration=duration,
            thumbnail=thumbnail,
            uploader=uploader if uploader else stream_data.get("network"),
            upload_date=upload_date
            if upload_date
            else (
                str(stream_data.get("broadcast_date", ""))
                if stream_data.get("broadcast_date")
                else None
            ),
            meta_data=meta_data_json,
        )

        self.db.add(media_item)
        self.db.commit()
        self.db.refresh(media_item)

        logger.info(f"  ✓ Created media item: {title[:50]}")
        return media_item

    def get_or_create_collection(self, collection_name: str) -> Collection:
        """Get existing collection or create new one"""
        if collection_name in self.created_collections:
            return self.created_collections[collection_name]

        # Check if collection already exists
        existing = self.db.query(Collection).filter(Collection.name == collection_name).first()
        if existing:
            self.created_collections[collection_name] = existing
            return existing

        # Create new collection
        collection = Collection(name=collection_name, description=f"Collection: {collection_name}")
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)

        self.created_collections[collection_name] = collection
        logger.info(f"  ✓ Created collection: {collection_name}")
        return collection

    def add_media_to_collection(
        self, collection: Collection, media_item: MediaItem, order: int = 0
    ):
        """Add media item to collection"""
        # Check if already in collection
        existing = (
            self.db.query(CollectionItem)
            .filter(
                CollectionItem.collection_id == collection.id,
                CollectionItem.media_item_id == media_item.id,
            )
            .first()
        )

        if existing:
            return

        collection_item = CollectionItem(
            collection_id=collection.id, media_item_id=media_item.id, order=order
        )
        self.db.add(collection_item)
        self.db.commit()

    async def import_channel_from_config(self, channel_config: dict[str, Any]) -> Channel:
        """Import a single channel from configuration"""
        channel_number = str(channel_config.get("number", ""))
        channel_name = channel_config.get("name", f"Channel {channel_number}")

        if not channel_number:
            raise ValueError("Channel config missing 'number' field")

        # Check if channel already exists
        existing = self.db.query(Channel).filter(Channel.number == channel_number).first()
        if existing:
            logger.info(f"Channel {channel_number} already exists, updating...")
            existing.name = channel_name
            existing.group = channel_config.get("group")
            existing.description = channel_config.get("description")
            existing.enabled = channel_config.get("enabled", True)
            self.db.commit()
            self.db.refresh(existing)
            channel = existing
        else:
            # Create new channel
            channel = Channel(
                number=channel_number,
                name=channel_name,
                group=channel_config.get("group"),
                enabled=channel_config.get("enabled", True),
                is_yaml_source=True,
                transcode_profile=channel_config.get("transcode_profile"),
            )
            self.db.add(channel)
            self.db.commit()
            self.db.refresh(channel)

            logger.info(f"✓ Created channel: {channel_number} - {channel_name}")
            self.created_channels.append(channel)

        # Import media items and collections
        streams = channel_config.get("streams", [])
        if streams:
            logger.info(f"  Importing {len(streams)} media items...")

            # Group streams by collection
            collection_map = {}
            for i, stream_data in enumerate(streams):
                collection_name = stream_data.get("collection")
                if collection_name:
                    if collection_name not in collection_map:
                        collection_map[collection_name] = []
                    collection_map[collection_name].append((i, stream_data))

            # Create collections and add media
            for collection_name, stream_list in collection_map.items():
                collection = self.get_or_create_collection(collection_name)

                for order, stream_data in stream_list:
                    try:
                        media_item = await self.get_or_create_media_item(stream_data)
                        self.add_media_to_collection(collection, media_item, order)
                    except Exception as e:
                        logger.exception(f"  ✗ Error importing media item: {e}")
                        continue

            # Create or update main playlist for channel
            playlist_name = f"{channel_name} - Main Playlist"
            existing_playlist = (
                self.db.query(Playlist)
                .filter(Playlist.name == playlist_name, Playlist.channel_id == channel.id)
                .first()
            )

            if existing_playlist:
                # Clear existing playlist items
                self.db.query(PlaylistItem).filter(
                    PlaylistItem.playlist_id == existing_playlist.id
                ).delete()
                self.db.commit()
                playlist = existing_playlist
                logger.info(f"  Updating existing playlist...")
            else:
                playlist = Playlist(
                    name=playlist_name,
                    description=f"Main playlist for {channel_name}",
                    channel_id=channel.id,
                )
                self.db.add(playlist)
                self.db.commit()
                self.db.refresh(playlist)

            # Add all media items to playlist in order
            all_media = []
            for stream_data in streams:
                try:
                    media_item = await self.get_or_create_media_item(stream_data)
                    all_media.append(media_item)
                except Exception as e:
                    logger.exception(f"  ✗ Error adding to playlist: {e}")
                    continue

            for order, media_item in enumerate(all_media):
                playlist_item = PlaylistItem(
                    playlist_id=playlist.id, media_item_id=media_item.id, order=order
                )
                self.db.add(playlist_item)

            self.db.commit()
            logger.info(f"  ✓ {'Updated' if existing_playlist else 'Created'} playlist with {len(all_media)} items")

        return channel

    async def import_from_yaml(self, yaml_path: Path, validate: bool = True) -> list[Channel]:
        """
        Import channels from YAML file

        Args:
            yaml_path: Path to YAML file
            validate: Whether to validate against JSON schema (default: True)

        Returns:
            List of imported Channel objects
        """
        if not yaml_path.exists():
            raise FileNotFoundError(f"YAML file not found: {yaml_path}")

        # Validate YAML file against schema if requested
        if validate:
            try:
                validator = YAMLValidator()
                result = validator.validate_channel_file(yaml_path)
                if not result.get("valid", False):
                    raise ValidationError(f"Validation failed: {result.get('errors', [])}")
                logger.info(f"✓ Validated {yaml_path.name} before import")
            except ValidationError as e:
                logger.exception(f"Validation error: {e.message}")
                raise
            except Exception as e:
                logger.warning(f"Validation skipped due to error: {e}")
                # Continue with import even if validation fails (non-blocking)

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        # Initialize database
        init_db()

        channels_config = data.get("channels", [])
        if not channels_config:
            raise ValueError("YAML file must contain a 'channels' list")

        logger.info(f"Importing {len(channels_config)} channels from {yaml_path.name}...")

        imported_channels = []
        for channel_config in channels_config:
            try:
                channel = await self.import_channel_from_config(channel_config)
                imported_channels.append(channel)
            except Exception as e:
                logger.exception(f"Error importing channel: {e}")
                continue

        logger.info(f"\n{'=' * 60}")
        logger.info("Import complete!")
        logger.info(f"  Created/Updated: {len(imported_channels)} channels")
        logger.info(f"  Created: {len(self.created_collections)} collections")
        logger.info(f"{'=' * 60}")

        return imported_channels

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()


async def import_channels_from_yaml(yaml_path: Path, validate: bool = True) -> list[Channel]:
    """
    Convenience function to import channels from YAML file

    Args:
        yaml_path: Path to YAML file
        validate: Whether to validate against JSON schema (default: True)

    Returns:
        List of imported Channel objects
    """
    importer = ChannelImporter()
    try:
        return await importer.import_from_yaml(yaml_path, validate=validate)
    finally:
        importer.close()
