"""Efficient M3U playlist importer following iptv-org standards"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from ..database.models import Channel, MediaItem, Playlist, PlaylistItem, PlayoutMode, StreamSource
from ..database.session import SessionLocal, init_db

logger = logging.getLogger(__name__)

@dataclass
class M3UEntry:
    """Represents a single M3U playlist entry with all metadata"""

    duration: int | None = None  # -1 for live streams
    tvg_id: str | None = None
    tvg_name: str | None = None
    tvg_logo: str | None = None
    tvg_chno: str | None = None
    tvg_shift: str | None = None  # Timezone shift
    group_title: str | None = None
    radio: bool = False
    url: str | None = None
    title: str | None = None
    extra_attrs: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "duration": self.duration,
            "tvg_id": self.tvg_id,
            "tvg_name": self.tvg_name,
            "tvg_logo": self.tvg_logo,
            "tvg_chno": self.tvg_chno,
            "tvg_shift": self.tvg_shift,
            "group_title": self.group_title,
            "radio": self.radio,
            "url": self.url,
            "title": self.title,
            "extra_attrs": self.extra_attrs,
        }

class M3UParser:
    """Efficient M3U parser with streaming support for large files"""

    # Compiled regex patterns for performance
    EXTINF_PATTERN = re.compile(r"#EXTINF:(-?\d+)")
    ATTR_PATTERN = re.compile(r'(\w+(?:-\w+)*)="([^"]*)"')
    TITLE_PATTERN = re.compile(r",\s*(.+?)(?:\s*$|\s*#)")
    URL_PATTERN = re.compile(r"^(https?|rtmp|rtsp|udp|tcp)://", re.IGNORECASE)

    @staticmethod
    def parse_extinf_line(line: str) -> M3UEntry:
        """
        Parse #EXTINF line efficiently using compiled regex

        Format: #EXTINF:-1 tvg-id="..." tvg-name="..." tvg-logo="..." group-title="..." ,Channel Name
        """
        entry = M3UEntry()

        # Extract duration (first number after #EXTINF:)
        duration_match = M3UParser.EXTINF_PATTERN.match(line)
        if duration_match:
            duration = int(duration_match.group(1))
            entry.duration = duration if duration > 0 else None

        # Extract all attributes in one pass
        attrs = M3UParser.ATTR_PATTERN.findall(line)

        for key, value in attrs:
            key_lower = key.lower()
            if key_lower == "tvg-id":
                entry.tvg_id = value
            elif key_lower == "tvg-name":
                entry.tvg_name = value
            elif key_lower == "tvg-logo":
                entry.tvg_logo = value
            elif key_lower == "tvg-chno":
                entry.tvg_chno = value
            elif key_lower == "tvg-shift":
                entry.tvg_shift = value
            elif key_lower == "group-title":
                entry.group_title = value
            elif key_lower == "radio":
                entry.radio = value.lower() == "true"
            else:
                entry.extra_attrs[key] = value

        # Extract title (after comma)
        title_match = M3UParser.TITLE_PATTERN.search(line)
        if title_match:
            entry.title = title_match.group(1).strip()

        return entry

    @staticmethod
    async def parse_file(m3u_path_or_url: str, chunk_size: int = 8192) -> list[M3UEntry]:
        """
        Parse M3U file efficiently (supports both local files and URLs)

        Args:
            m3u_path_or_url: Path to local file or URL
            chunk_size: Chunk size for streaming reads

        Returns:
            List of M3UEntry objects
        """

        entries = []
        parsed = urlparse(m3u_path_or_url)
        is_url = parsed.scheme in ("http", "https")

        if is_url:
            logger.info(f"Fetching M3U from URL: {m3u_path_or_url}")
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                async with client.stream("GET", m3u_path_or_url) as response:
                    response.raise_for_status()

                    # Stream parse line-by-line
                    buffer = ""
                    current_entry = None
                    async for chunk in response.aiter_bytes(chunk_size):
                        buffer += chunk.decode("utf-8", errors="replace")

                        # Process complete lines
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()

                            if not line or (
                                line.startswith("#") and not line.startswith("#EXTINF")
                            ):
                                continue

                            if line.startswith("#EXTINF"):
                                current_entry = M3UParser.parse_extinf_line(line)
                            elif current_entry and M3UParser.URL_PATTERN.match(line):
                                current_entry.url = line
                                if not current_entry.url.startswith(("http://", "https://")):
                                    current_entry.url = urljoin(m3u_path_or_url, current_entry.url)
                                entries.append(current_entry)
                                current_entry = None
        else:
            # Local file - stream read for large files
            m3u_path = Path(m3u_path_or_url)
            if not m3u_path.exists():
                raise FileNotFoundError(f"M3U file not found: {m3u_path_or_url}")

            logger.info(f"Reading M3U from file: {m3u_path_or_url}")
            current_entry = None

            with open(m3u_path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()

                    if not line or (line.startswith("#") and not line.startswith("#EXTINF")):
                        continue

                    if line.startswith("#EXTINF"):
                        current_entry = M3UParser.parse_extinf_line(line)
                    elif current_entry and M3UParser.URL_PATTERN.match(line):
                        current_entry.url = line
                        entries.append(current_entry)
                        current_entry = None

        logger.info(f"Parsed {len(entries)} entries from M3U file")
        return entries

class M3UImporter:
    """Efficient M3U importer with bulk operations"""

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self.created_channels = []
        self._channel_cache: dict[str, Channel] = {}
        self._media_cache: dict[str, MediaItem] = {}

    def _get_or_create_channel(
        self, entry: M3UEntry, channel_number: str, auto_number: bool = False
    ) -> tuple[Channel, bool]:
        """
        Get existing channel or create new one (with caching)

        Returns:
            Tuple of (Channel, is_new)
        """
        # Check cache first
        if channel_number in self._channel_cache:
            channel = self._channel_cache[channel_number]
            # Update fields
            channel.name = entry.tvg_name or entry.title or entry.tvg_id or channel.name
            if entry.group_title:
                channel.group = entry.group_title
            if entry.tvg_logo:
                channel.logo_path = entry.tvg_logo
            return channel, False

        # Check database
        existing = self.db.query(Channel).filter(Channel.number == channel_number).first()
        if existing:
            self._channel_cache[channel_number] = existing
            # Update fields
            existing.name = entry.tvg_name or entry.title or entry.tvg_id or existing.name
            if entry.group_title:
                existing.group = entry.group_title
            if entry.tvg_logo:
                existing.logo_path = entry.tvg_logo
            return existing, False

        # Handle auto-numbering
        if auto_number:
            base_num = int(channel_number) if channel_number.isdigit() else 1000
            for i in range(1, 10000):
                candidate = str(base_num + i)
                if not self.db.query(Channel).filter(Channel.number == candidate).first():
                    channel_number = candidate
                    break

        # Create new channel
        channel_name = entry.tvg_name or entry.title or entry.tvg_id or f"Channel {channel_number}"

        channel = Channel(
            number=channel_number,
            name=channel_name,
            group=entry.group_title,
            enabled=True,
            logo_path=entry.tvg_logo,
            playout_mode=PlayoutMode.CONTINUOUS.value,
            is_yaml_source=False,
        )

        self.db.add(channel)
        self._channel_cache[channel_number] = channel
        return channel, True

    def _get_or_create_media_item(
        self, entry: M3UEntry, channel: Channel
    ) -> tuple[MediaItem, bool]:
        """
        Get existing media item or create new one (with caching)

        Returns:
            Tuple of (MediaItem, is_new)
        """
        # Check cache
        if entry.url in self._media_cache:
            return self._media_cache[entry.url], False

        # Check database
        existing = self.db.query(MediaItem).filter(MediaItem.url == entry.url).first()
        if existing:
            self._media_cache[entry.url] = existing
            return existing, False

        # Determine source type
        source = StreamSource.YOUTUBE  # Default
        url_lower = entry.url.lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower:
            source = StreamSource.YOUTUBE
        elif "archive.org" in url_lower:
            source = StreamSource.ARCHIVE_ORG
        elif entry.url.startswith("plex://"):
            source = StreamSource.PLEX

        # Extract source ID
        source_id = entry.tvg_id or entry.url

        # Create metadata JSON for EPG
        metadata = {
            "m3u_source": True,
            "tvg_id": entry.tvg_id,
            "tvg_name": entry.tvg_name,
            "tvg_logo": entry.tvg_logo,
            "tvg_chno": entry.tvg_chno,
            "tvg_shift": entry.tvg_shift,
            "group_title": entry.group_title,
            "is_live": True,
            "radio": entry.radio,
            **entry.extra_attrs,
        }

        media_item = MediaItem(
            source=source,
            source_id=source_id,
            url=entry.url,
            title=entry.tvg_name or entry.title or channel.name,
            description="Live stream from M3U playlist",
            duration=None,  # Live streams
            thumbnail=entry.tvg_logo,
            meta_data=json.dumps(metadata, ensure_ascii=False),
        )

        self.db.add(media_item)
        self._media_cache[entry.url] = media_item
        return media_item, True

    async def parse_and_preview(self, m3u_path_or_url: str) -> list[dict[str, Any]]:
        """
        Parse M3U file and return preview data (no database writes)

        Args:
            m3u_path_or_url: Path to M3U file or URL

        Returns:
            List of channel preview dictionaries
        """
        entries = await M3UParser.parse_file(m3u_path_or_url)

        if not entries:
            return []

        preview_list = []
        current_number = 1000

        for entry in entries:
            # Determine channel number
            if entry.tvg_chno:
                channel_number = entry.tvg_chno
            else:
                channel_number = str(current_number)
                current_number += 1

            preview_list.append(
                {
                    "channel_number": channel_number,
                    "name": entry.tvg_name
                    or entry.title
                    or entry.tvg_id
                    or f"Channel {channel_number}",
                    "group": entry.group_title,
                    "logo": entry.tvg_logo,
                    "tvg_id": entry.tvg_id,
                    "url": entry.url,
                    "title": entry.title,
                    "radio": entry.radio,
                    "extra_attrs": entry.extra_attrs,
                }
            )

        return preview_list

    async def import_selected(
        self,
        m3u_path_or_url: str,
        selected_indices: list[int],
        channel_number_start: int = 1000,
        auto_assign_numbers: bool = True,
        create_playlists: bool = True,
        batch_size: int = 100,
    ) -> list[Channel]:
        """
        Import selected channels from M3U file with efficient batch processing

        Args:
            m3u_path_or_url: Path to M3U file or URL
            selected_indices: List of indices of entries to import
            channel_number_start: Starting channel number
            auto_assign_numbers: Auto-increment on conflicts
            create_playlists: Create playlists for channels
            batch_size: Batch size for database commits

        Returns:
            List of created Channel objects
        """
        init_db()

        # Parse M3U file
        entries = await M3UParser.parse_file(m3u_path_or_url)

        if not entries:
            logger.warning("No entries found in M3U file")
            return []

        # Filter to selected entries
        selected_entries = [entries[i] for i in selected_indices if 0 <= i < len(entries)]

        if not selected_entries:
            logger.warning("No valid entries selected for import")
            return []

        logger.info(f"Importing {len(selected_entries)} channels from M3U file...")

        imported_channels = []
        current_number = channel_number_start
        channels_to_create = []
        media_items_to_create = []
        playlist_items_to_create = []

        for idx, entry in enumerate(selected_entries):
            try:
                # Determine channel number
                if entry.tvg_chno:
                    channel_number = entry.tvg_chno
                else:
                    channel_number = str(current_number)
                    current_number += 1

                # Get or create channel
                channel, is_new_channel = self._get_or_create_channel(
                    entry, channel_number, auto_number=auto_assign_numbers
                )

                if is_new_channel:
                    channels_to_create.append(channel)
                    imported_channels.append(channel)

                # Get or create media item
                media_item, is_new_media = self._get_or_create_media_item(entry, channel)

                if is_new_media:
                    media_items_to_create.append(media_item)

                # Create playlist if requested
                if create_playlists:
                    # Check if playlist exists
                    playlist = (
                        self.db.query(Playlist)
                        .filter(
                            Playlist.name == f"{channel.name} - Live Stream",
                            Playlist.channel_id == channel.id,
                        )
                        .first()
                    )

                    if not playlist:
                        playlist = Playlist(
                            name=f"{channel.name} - Live Stream",
                            description=f"Live stream playlist for {channel.name}",
                            channel_id=channel.id,
                        )
                        self.db.add(playlist)
                        self.db.flush()  # Flush to get ID

                    # Check if playlist item exists
                    existing_item = (
                        self.db.query(PlaylistItem)
                        .filter(
                            PlaylistItem.playlist_id == playlist.id,
                            PlaylistItem.media_item_id == media_item.id,
                        )
                        .first()
                    )

                    if not existing_item:
                        playlist_item = PlaylistItem(
                            playlist_id=playlist.id, media_item_id=media_item.id, order=0
                        )
                        playlist_items_to_create.append(playlist_item)

                # Batch commit for performance
                if (idx + 1) % batch_size == 0:
                    self.db.commit()
                    logger.debug(f"Committed batch {idx + 1}/{len(selected_entries)}")

            except Exception as e:
                logger.error(f"Error importing entry {idx + 1}: {e}", exc_info=True)
                continue

        # Final commit
        try:
            self.db.commit()
            logger.info(f"✓ Created {len(channels_to_create)} new channels")
            logger.info(f"✓ Created {len(media_items_to_create)} new media items")
            logger.info(f"✓ Created {len(playlist_items_to_create)} playlist items")
        except Exception as e:
            logger.error(f"Error committing final batch: {e}", exc_info=True)
            self.db.rollback()
            raise

        logger.info(f"\n{'=' * 60}")
        logger.info("M3U Import complete!")
        logger.info(f"  Created/Updated: {len(imported_channels)} channels")
        logger.info(f"  Total entries processed: {len(selected_entries)}")
        logger.info(f"{'=' * 60}")

        return imported_channels

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()

async def import_channels_from_m3u(
    m3u_path_or_url: str,
    channel_number_start: int = 1000,
    auto_assign_numbers: bool = True,
    create_playlists: bool = True,
) -> list[Channel]:
    """
    Convenience function to import channels from M3U file

    Args:
        m3u_path_or_url: Path to M3U file or URL
        channel_number_start: Starting channel number
        auto_assign_numbers: Auto-increment channel numbers
        create_playlists: Create playlists for channels

    Returns:
        List of imported Channel objects
    """
    importer = M3UImporter()
    try:
        # Import all entries (no selection)
        entries = await M3UParser.parse_file(m3u_path_or_url)
        selected_indices = list(range(len(entries)))
        return await importer.import_selected(
            m3u_path_or_url,
            selected_indices,
            channel_number_start=channel_number_start,
            auto_assign_numbers=auto_assign_numbers,
            create_playlists=create_playlists,
        )
    finally:
        importer.close()
