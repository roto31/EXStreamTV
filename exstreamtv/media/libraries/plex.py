"""
Plex Media Server library integration.

Connects to Plex to discover and stream media.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp

from exstreamtv.media.libraries.base import (
    BaseLibrary,
    LibraryItem,
    LibraryType,
    MediaType,
)

logger = logging.getLogger(__name__)


class PlexLibrary(BaseLibrary):
    """
    Plex Media Server library integration.

    Features:
    - Library discovery via Plex API
    - Media metadata sync
    - Streaming URL generation
    - Artwork retrieval
    """

    def __init__(
        self,
        library_id: int,
        name: str,
        server_url: str,
        token: str,
        plex_library_key: str,
        plex_library_name: str = "",
    ):
        """
        Initialize PlexLibrary.

        Args:
            library_id: Unique library identifier.
            name: Display name for the library.
            server_url: Plex server URL (e.g., http://localhost:32400).
            token: X-Plex-Token for authentication.
            plex_library_key: Plex library section key.
            plex_library_name: Plex library section name.
        """
        super().__init__(library_id, name, LibraryType.PLEX)
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.plex_library_key = plex_library_key
        self.plex_library_name = plex_library_name
        self._session: Optional[aiohttp.ClientSession] = None
        self._library_type: Optional[str] = None  # "movie", "show"

    @property
    def headers(self) -> Dict[str, str]:
        """Get HTTP headers for Plex API requests."""
        return {
            "X-Plex-Token": self.token,
            "Accept": "application/json",
            "X-Plex-Client-Identifier": "exstreamtv",
            "X-Plex-Product": "EXStreamTV",
            "X-Plex-Version": "1.0.0",
            "X-Plex-Device": "Server",
            "X-Plex-Platform": "Python",
        }

    async def connect(self) -> bool:
        """Connect to the Plex server."""
        try:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

            # Test connection and get library info
            url = f"{self.server_url}/library/sections/{self.plex_library_key}"
            async with self._session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to connect to Plex: HTTP {response.status}")
                    return False

                data = await response.json()
                media_container = data.get("MediaContainer", {})
                directories = media_container.get("Directory", [])

                if directories:
                    directory = directories[0] if isinstance(directories, list) else directories
                    self._library_type = directory.get("type", "movie")
                    self.plex_library_name = directory.get("title", self.plex_library_name)

            logger.info(
                f"Connected to Plex library: {self.plex_library_name} "
                f"({self._library_type})"
            )
            return True

        except aiohttp.ClientError as e:
            logger.error(f"Plex connection error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error connecting to Plex: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Plex server."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.debug(f"Disconnected from Plex: {self.plex_library_name}")

    async def sync(self) -> List[LibraryItem]:
        """
        Synchronize with the Plex library.

        Returns:
            List of LibraryItem objects.
        """
        if not self._session:
            raise RuntimeError("Not connected to Plex")

        logger.info(f"Syncing Plex library: {self.plex_library_name}")

        items: List[LibraryItem] = []

        try:
            # Get all items from library
            url = f"{self.server_url}/library/sections/{self.plex_library_key}/all"
            async with self._session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch Plex library: HTTP {response.status}")
                    return items

                data = await response.json()
                metadata_list = data.get("MediaContainer", {}).get("Metadata", [])

                if self._library_type == "show":
                    # For TV libraries, fetch episodes
                    items = await self._sync_shows(metadata_list)
                else:
                    # For movie libraries
                    items = await self._sync_movies(metadata_list)

            self._last_sync = datetime.now()
            logger.info(f"Synced {len(items)} items from Plex: {self.plex_library_name}")

        except Exception as e:
            logger.exception(f"Error syncing Plex library: {e}")

        return items

    async def _sync_movies(self, metadata_list: List[Dict[str, Any]]) -> List[LibraryItem]:
        """Sync movies from metadata list."""
        items = []

        for metadata in metadata_list:
            try:
                item = self._parse_movie(metadata)
                items.append(item)
                self._items[item.id] = item
            except Exception as e:
                logger.warning(f"Error parsing movie: {e}")

        return items

    async def _sync_shows(self, shows: List[Dict[str, Any]]) -> List[LibraryItem]:
        """Sync TV shows and episodes."""
        items = []

        for show in shows:
            try:
                show_key = show.get("ratingKey")
                show_title = show.get("title", "Unknown Show")

                # Create show item
                show_item = LibraryItem(
                    id=f"plex_{show_key}",
                    library_id=self.library_id,
                    media_type=MediaType.SHOW,
                    title=show_title,
                    sort_title=show.get("titleSort", show_title).lower(),
                    year=show.get("year"),
                    studio=show.get("studio"),
                    genres=self._parse_genres(show),
                    poster_path=self._get_image_url(show.get("thumb")),
                    fanart_path=self._get_image_url(show.get("art")),
                    tmdb_id=self._get_guid_id(show, "tmdb"),
                    tvdb_id=self._get_guid_id(show, "tvdb"),
                    imdb_id=self._get_guid_id(show, "imdb"),
                    added_at=self._parse_timestamp(show.get("addedAt")),
                    updated_at=self._parse_timestamp(show.get("updatedAt")),
                )
                items.append(show_item)
                self._items[show_item.id] = show_item

                # Fetch episodes for this show
                episodes = await self._fetch_show_episodes(show_key, show_title)
                items.extend(episodes)

            except Exception as e:
                logger.warning(f"Error parsing show: {e}")

        return items

    async def _fetch_show_episodes(
        self, show_key: str, show_title: str
    ) -> List[LibraryItem]:
        """Fetch all episodes for a show."""
        episodes = []

        if not self._session:
            return episodes

        try:
            # Get all episodes for the show
            url = f"{self.server_url}/library/metadata/{show_key}/allLeaves"
            async with self._session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    logger.warning(f"Failed to fetch episodes for show {show_key}")
                    return episodes

                data = await response.json()
                episode_list = data.get("MediaContainer", {}).get("Metadata", [])

                for ep in episode_list:
                    try:
                        item = self._parse_episode(ep, show_title)
                        episodes.append(item)
                        self._items[item.id] = item
                    except Exception as e:
                        logger.debug(f"Error parsing episode: {e}")

        except Exception as e:
            logger.warning(f"Error fetching episodes: {e}")

        return episodes

    def _parse_movie(self, metadata: Dict[str, Any]) -> LibraryItem:
        """Parse movie metadata into LibraryItem."""
        rating_key = metadata.get("ratingKey", "")
        title = metadata.get("title", "Untitled")

        # Get duration from Media
        duration = timedelta(0)
        media = metadata.get("Media", [])
        if media:
            duration_ms = media[0].get("duration", 0)
            duration = timedelta(milliseconds=duration_ms)

        return LibraryItem(
            id=f"plex_{rating_key}",
            library_id=self.library_id,
            media_type=MediaType.MOVIE,
            title=title,
            sort_title=metadata.get("titleSort", title).lower(),
            duration=duration,
            year=metadata.get("year"),
            studio=metadata.get("studio"),
            genres=self._parse_genres(metadata),
            actors=self._parse_actors(metadata),
            poster_path=self._get_image_url(metadata.get("thumb")),
            fanart_path=self._get_image_url(metadata.get("art")),
            tmdb_id=self._get_guid_id(metadata, "tmdb"),
            tvdb_id=self._get_guid_id(metadata, "tvdb"),
            imdb_id=self._get_guid_id(metadata, "imdb"),
            added_at=self._parse_timestamp(metadata.get("addedAt")),
            updated_at=self._parse_timestamp(metadata.get("updatedAt")),
        )

    def _parse_episode(self, metadata: Dict[str, Any], show_title: str) -> LibraryItem:
        """Parse episode metadata into LibraryItem."""
        rating_key = metadata.get("ratingKey", "")
        title = metadata.get("title", "Untitled")

        # Get duration from Media
        duration = timedelta(0)
        media = metadata.get("Media", [])
        if media:
            duration_ms = media[0].get("duration", 0)
            duration = timedelta(milliseconds=duration_ms)

        return LibraryItem(
            id=f"plex_{rating_key}",
            library_id=self.library_id,
            media_type=MediaType.EPISODE,
            title=title,
            sort_title=f"{show_title} {metadata.get('parentIndex', 0):02d}{metadata.get('index', 0):03d}",
            duration=duration,
            year=metadata.get("year"),
            show_title=show_title,
            season_number=metadata.get("parentIndex"),
            episode_number=metadata.get("index"),
            poster_path=self._get_image_url(metadata.get("thumb")),
            fanart_path=self._get_image_url(metadata.get("art")),
            added_at=self._parse_timestamp(metadata.get("addedAt")),
            updated_at=self._parse_timestamp(metadata.get("updatedAt")),
        )

    def _parse_genres(self, metadata: Dict[str, Any]) -> List[str]:
        """Parse genres from metadata."""
        genres = []
        for genre in metadata.get("Genre", []):
            if isinstance(genre, dict):
                genres.append(genre.get("tag", ""))
            else:
                genres.append(str(genre))
        return [g for g in genres if g]

    def _parse_actors(self, metadata: Dict[str, Any]) -> List[str]:
        """Parse actors from metadata."""
        actors = []
        for role in metadata.get("Role", []):
            if isinstance(role, dict):
                actors.append(role.get("tag", ""))
        return [a for a in actors if a]

    def _get_image_url(self, path: Optional[str]) -> Optional[str]:
        """Get full image URL with token."""
        if not path:
            return None
        return f"{self.server_url}{path}?X-Plex-Token={self.token}"

    def _get_guid_id(self, metadata: Dict[str, Any], source: str) -> Optional[str]:
        """Extract external ID from GUID."""
        guids = metadata.get("Guid", [])
        for guid in guids:
            if isinstance(guid, dict):
                guid_id = guid.get("id", "")
                if guid_id.startswith(f"{source}://"):
                    return guid_id.replace(f"{source}://", "")
        return None

    def _parse_timestamp(self, timestamp: Optional[int]) -> Optional[datetime]:
        """Parse Unix timestamp to datetime."""
        if timestamp:
            return datetime.fromtimestamp(timestamp)
        return None

    async def get_item(self, item_id: str) -> Optional[LibraryItem]:
        """Get a specific item by ID."""
        return self._items.get(item_id)

    async def get_stream_url(self, item_id: str) -> Optional[str]:
        """
        Get streaming URL for an item.

        Returns the direct stream URL for the media file.
        """
        if not self._session:
            return None

        # Extract rating key from ID
        rating_key = item_id.replace("plex_", "")

        try:
            # Get media info to find the best part
            url = f"{self.server_url}/library/metadata/{rating_key}"
            async with self._session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                metadata = data.get("MediaContainer", {}).get("Metadata", [])

                if not metadata:
                    return None

                media = metadata[0].get("Media", [])
                if not media:
                    return None

                parts = media[0].get("Part", [])
                if not parts:
                    return None

                part_key = parts[0].get("key", "")
                if part_key:
                    return f"{self.server_url}{part_key}?X-Plex-Token={self.token}"

        except Exception as e:
            logger.warning(f"Error getting stream URL: {e}")

        return None

    async def get_transcode_url(
        self,
        item_id: str,
        quality: str = "1080p",
        bitrate: int = 8000,
    ) -> Optional[str]:
        """
        Get transcoded stream URL.

        Args:
            item_id: Library item ID.
            quality: Target quality.
            bitrate: Target bitrate in kbps.

        Returns:
            Transcode URL or None.
        """
        rating_key = item_id.replace("plex_", "")

        params = {
            "path": f"/library/metadata/{rating_key}",
            "mediaIndex": "0",
            "partIndex": "0",
            "protocol": "hls",
            "fastSeek": "1",
            "directPlay": "0",
            "directStream": "0",
            "videoQuality": "100",
            "maxVideoBitrate": str(bitrate),
            "subtitleSize": "100",
            "audioBoost": "100",
            "X-Plex-Token": self.token,
        }

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.server_url}/video/:/transcode/universal/start.m3u8?{query}"

    @classmethod
    async def discover_libraries(
        cls, server_url: str, token: str
    ) -> List[Dict[str, Any]]:
        """
        Discover available libraries on a Plex server.

        Args:
            server_url: Plex server URL.
            token: X-Plex-Token.

        Returns:
            List of library info dicts.
        """
        libraries = []

        try:
            headers = {
                "X-Plex-Token": token,
                "Accept": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                url = f"{server_url.rstrip('/')}/library/sections"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to discover Plex libraries: HTTP {response.status}")
                        return libraries

                    data = await response.json()
                    directories = data.get("MediaContainer", {}).get("Directory", [])

                    for directory in directories:
                        libraries.append({
                            "key": directory.get("key"),
                            "title": directory.get("title"),
                            "type": directory.get("type"),
                            "agent": directory.get("agent"),
                            "scanner": directory.get("scanner"),
                            "language": directory.get("language"),
                        })

        except Exception as e:
            logger.exception(f"Error discovering Plex libraries: {e}")

        return libraries
