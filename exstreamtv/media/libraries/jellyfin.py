"""
Jellyfin and Emby media server library integration.

Connects to Jellyfin/Emby to discover and stream media.
Since Emby is the fork origin of Jellyfin, they share similar APIs.
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


class JellyfinLibrary(BaseLibrary):
    """
    Jellyfin Media Server library integration.

    Features:
    - Library discovery via Jellyfin API
    - Media metadata sync
    - Streaming URL generation
    - Artwork retrieval
    """

    def __init__(
        self,
        library_id: int,
        name: str,
        server_url: str,
        api_key: str,
        jellyfin_library_id: str,
        jellyfin_library_name: str = "",
    ):
        """
        Initialize JellyfinLibrary.

        Args:
            library_id: Unique library identifier.
            name: Display name for the library.
            server_url: Jellyfin server URL.
            api_key: API key for authentication.
            jellyfin_library_id: Jellyfin library ID (GUID).
            jellyfin_library_name: Jellyfin library display name.
        """
        super().__init__(library_id, name, LibraryType.JELLYFIN)
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.jellyfin_library_id = jellyfin_library_id
        self.jellyfin_library_name = jellyfin_library_name
        self._session: Optional[aiohttp.ClientSession] = None
        self._user_id: Optional[str] = None
        self._server_name: Optional[str] = None

    @property
    def headers(self) -> Dict[str, str]:
        """Get HTTP headers for Jellyfin API requests."""
        return {
            "X-Emby-Token": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def connect(self) -> bool:
        """Connect to the Jellyfin server."""
        try:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

            # Get server info
            url = f"{self.server_url}/System/Info"
            async with self._session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to connect to Jellyfin: HTTP {response.status}")
                    return False

                data = await response.json()
                self._server_name = data.get("ServerName", "Jellyfin")

            # Get first admin user for API calls
            users_url = f"{self.server_url}/Users"
            async with self._session.get(users_url, headers=self.headers) as response:
                if response.status == 200:
                    users = await response.json()
                    if users:
                        self._user_id = users[0].get("Id")

            logger.info(
                f"Connected to Jellyfin: {self._server_name} "
                f"(Library: {self.jellyfin_library_name})"
            )
            return True

        except aiohttp.ClientError as e:
            logger.error(f"Jellyfin connection error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error connecting to Jellyfin: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Jellyfin server."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.debug(f"Disconnected from Jellyfin: {self.jellyfin_library_name}")

    async def sync(self) -> List[LibraryItem]:
        """
        Synchronize with the Jellyfin library.

        Returns:
            List of LibraryItem objects.
        """
        if not self._session:
            raise RuntimeError("Not connected to Jellyfin")

        logger.info(f"Syncing Jellyfin library: {self.jellyfin_library_name}")

        items: List[LibraryItem] = []

        try:
            # Build query for library items
            params = {
                "ParentId": self.jellyfin_library_id,
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Fields": "Overview,Genres,Studios,People,ProviderIds,MediaSources",
                "EnableTotalRecordCount": "true",
                "StartIndex": "0",
                "Limit": "5000",
            }

            if self._user_id:
                url = f"{self.server_url}/Users/{self._user_id}/Items"
            else:
                url = f"{self.server_url}/Items"

            query = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{query}"

            async with self._session.get(full_url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch Jellyfin library: HTTP {response.status}")
                    return items

                data = await response.json()
                item_list = data.get("Items", [])

                for item_data in item_list:
                    try:
                        item = self._parse_item(item_data)
                        if item:
                            items.append(item)
                            self._items[item.id] = item
                    except Exception as e:
                        logger.debug(f"Error parsing item: {e}")

            self._last_sync = datetime.now()
            logger.info(f"Synced {len(items)} items from Jellyfin: {self.jellyfin_library_name}")

        except Exception as e:
            logger.exception(f"Error syncing Jellyfin library: {e}")

        return items

    def _parse_item(self, item_data: Dict[str, Any]) -> Optional[LibraryItem]:
        """Parse Jellyfin item into LibraryItem."""
        item_type = item_data.get("Type", "")
        item_id = item_data.get("Id", "")

        if item_type == "Movie":
            return self._parse_movie(item_data)
        elif item_type == "Episode":
            return self._parse_episode(item_data)

        return None

    def _parse_movie(self, item_data: Dict[str, Any]) -> LibraryItem:
        """Parse movie data into LibraryItem."""
        item_id = item_data.get("Id", "")
        title = item_data.get("Name", "Untitled")

        # Get duration
        duration = timedelta(0)
        runtime_ticks = item_data.get("RunTimeTicks", 0)
        if runtime_ticks:
            duration = timedelta(microseconds=runtime_ticks // 10)

        # Get provider IDs
        provider_ids = item_data.get("ProviderIds", {})

        return LibraryItem(
            id=f"jellyfin_{item_id}",
            library_id=self.library_id,
            media_type=MediaType.MOVIE,
            title=title,
            sort_title=item_data.get("SortName", title).lower(),
            duration=duration,
            year=item_data.get("ProductionYear"),
            studio=self._get_first_studio(item_data),
            genres=item_data.get("Genres", []),
            actors=self._parse_actors(item_data),
            poster_path=self._get_image_url(item_id, "Primary"),
            fanart_path=self._get_image_url(item_id, "Backdrop"),
            tmdb_id=provider_ids.get("Tmdb"),
            tvdb_id=provider_ids.get("Tvdb"),
            imdb_id=provider_ids.get("Imdb"),
            added_at=self._parse_date(item_data.get("DateCreated")),
            updated_at=datetime.now(),
        )

    def _parse_episode(self, item_data: Dict[str, Any]) -> LibraryItem:
        """Parse episode data into LibraryItem."""
        item_id = item_data.get("Id", "")
        title = item_data.get("Name", "Untitled")

        # Get duration
        duration = timedelta(0)
        runtime_ticks = item_data.get("RunTimeTicks", 0)
        if runtime_ticks:
            duration = timedelta(microseconds=runtime_ticks // 10)

        show_title = item_data.get("SeriesName", "Unknown Show")
        season_number = item_data.get("ParentIndexNumber")
        episode_number = item_data.get("IndexNumber")

        # Sort title for ordering
        sort_title = f"{show_title} {season_number or 0:02d}{episode_number or 0:03d}"

        return LibraryItem(
            id=f"jellyfin_{item_id}",
            library_id=self.library_id,
            media_type=MediaType.EPISODE,
            title=title,
            sort_title=sort_title.lower(),
            duration=duration,
            year=item_data.get("ProductionYear"),
            show_title=show_title,
            season_number=season_number,
            episode_number=episode_number,
            poster_path=self._get_image_url(item_id, "Primary"),
            fanart_path=self._get_image_url(item_data.get("SeriesId", item_id), "Backdrop"),
            added_at=self._parse_date(item_data.get("DateCreated")),
            updated_at=datetime.now(),
        )

    def _get_first_studio(self, item_data: Dict[str, Any]) -> Optional[str]:
        """Get first studio from item data."""
        studios = item_data.get("Studios", [])
        if studios:
            if isinstance(studios[0], dict):
                return studios[0].get("Name")
            return str(studios[0])
        return None

    def _parse_actors(self, item_data: Dict[str, Any]) -> List[str]:
        """Parse actors from People data."""
        actors = []
        for person in item_data.get("People", []):
            if person.get("Type") == "Actor":
                actors.append(person.get("Name", ""))
        return [a for a in actors if a][:10]  # Limit to 10 actors

    def _get_image_url(self, item_id: str, image_type: str) -> str:
        """Get image URL for an item."""
        return f"{self.server_url}/Items/{item_id}/Images/{image_type}"

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None
        try:
            # Handle various date formats
            date_str = date_str.split(".")[0].replace("Z", "")
            return datetime.fromisoformat(date_str)
        except ValueError:
            return None

    async def get_item(self, item_id: str) -> Optional[LibraryItem]:
        """Get a specific item by ID."""
        return self._items.get(item_id)

    async def get_stream_url(self, item_id: str) -> Optional[str]:
        """
        Get streaming URL for an item.

        Returns the direct stream URL for the media file.
        """
        # Extract Jellyfin item ID
        jellyfin_id = item_id.replace("jellyfin_", "")

        # Use universal streaming endpoint
        params = {
            "Static": "true",
            "api_key": self.api_key,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())

        return f"{self.server_url}/Videos/{jellyfin_id}/stream?{query}"

    async def get_transcode_url(
        self,
        item_id: str,
        container: str = "ts",
        video_codec: str = "h264",
        audio_codec: str = "aac",
        bitrate: int = 8000000,
    ) -> Optional[str]:
        """
        Get transcoded stream URL.

        Args:
            item_id: Library item ID.
            container: Output container format.
            video_codec: Target video codec.
            audio_codec: Target audio codec.
            bitrate: Target bitrate in bps.

        Returns:
            Transcode URL or None.
        """
        jellyfin_id = item_id.replace("jellyfin_", "")

        params = {
            "DeviceId": "exstreamtv",
            "Container": container,
            "VideoCodec": video_codec,
            "AudioCodec": audio_codec,
            "VideoBitrate": str(bitrate),
            "AudioBitrate": "128000",
            "TranscodingMaxAudioChannels": "2",
            "RequireAvc": "false",
            "SegmentContainer": "ts",
            "MinSegments": "2",
            "api_key": self.api_key,
        }

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.server_url}/Videos/{jellyfin_id}/master.m3u8?{query}"

    @classmethod
    async def discover_libraries(
        cls, server_url: str, api_key: str
    ) -> List[Dict[str, Any]]:
        """
        Discover available libraries on a Jellyfin server.

        Args:
            server_url: Jellyfin server URL.
            api_key: API key.

        Returns:
            List of library info dicts.
        """
        libraries = []

        try:
            headers = {
                "X-Emby-Token": api_key,
                "Accept": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                # First get users to find admin user
                users_url = f"{server_url.rstrip('/')}/Users"
                async with session.get(users_url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to get Jellyfin users: HTTP {response.status}")
                        return libraries

                    users = await response.json()
                    if not users:
                        return libraries

                    user_id = users[0].get("Id")

                # Get library folders
                url = f"{server_url.rstrip('/')}/Users/{user_id}/Views"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to discover Jellyfin libraries: HTTP {response.status}")
                        return libraries

                    data = await response.json()
                    items = data.get("Items", [])

                    for item in items:
                        libraries.append({
                            "id": item.get("Id"),
                            "name": item.get("Name"),
                            "type": item.get("CollectionType", "unknown"),
                            "server_id": item.get("ServerId"),
                        })

        except Exception as e:
            logger.exception(f"Error discovering Jellyfin libraries: {e}")

        return libraries


class EmbyLibrary(BaseLibrary):
    """
    Emby Media Server library integration.

    Emby is the fork origin of Jellyfin, so the API is very similar.
    This class wraps JellyfinLibrary with Emby-specific adjustments.
    """

    def __init__(
        self,
        library_id: int,
        name: str,
        server_url: str,
        api_key: str,
        emby_library_id: str,
        emby_library_name: str = "",
    ):
        """
        Initialize EmbyLibrary.

        Args:
            library_id: Unique library identifier.
            name: Display name for the library.
            server_url: Emby server URL.
            api_key: API key for authentication.
            emby_library_id: Emby library ID (GUID).
            emby_library_name: Emby library display name.
        """
        super().__init__(library_id, name, LibraryType.EMBY)
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.emby_library_id = emby_library_id
        self.emby_library_name = emby_library_name
        self._session: Optional[aiohttp.ClientSession] = None
        self._user_id: Optional[str] = None
        self._server_name: Optional[str] = None

    @property
    def headers(self) -> Dict[str, str]:
        """Get HTTP headers for Emby API requests."""
        return {
            "X-Emby-Token": self.api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Emby-Client": "EXStreamTV",
            "X-Emby-Client-Version": "1.0.0",
            "X-Emby-Device-Name": "EXStreamTV Server",
            "X-Emby-Device-Id": "exstreamtv-server",
        }

    async def connect(self) -> bool:
        """Connect to the Emby server."""
        try:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

            # Get server info
            url = f"{self.server_url}/System/Info/Public"
            async with self._session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to connect to Emby: HTTP {response.status}")
                    return False

                data = await response.json()
                self._server_name = data.get("ServerName", "Emby")

            # Get first user for API calls
            users_url = f"{self.server_url}/Users"
            async with self._session.get(users_url, headers=self.headers) as response:
                if response.status == 200:
                    users = await response.json()
                    if users:
                        self._user_id = users[0].get("Id")

            logger.info(
                f"Connected to Emby: {self._server_name} "
                f"(Library: {self.emby_library_name})"
            )
            return True

        except aiohttp.ClientError as e:
            logger.error(f"Emby connection error: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error connecting to Emby: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the Emby server."""
        if self._session:
            await self._session.close()
            self._session = None
        logger.debug(f"Disconnected from Emby: {self.emby_library_name}")

    async def sync(self) -> List[LibraryItem]:
        """
        Synchronize with the Emby library.

        Returns:
            List of LibraryItem objects.
        """
        if not self._session:
            raise RuntimeError("Not connected to Emby")

        logger.info(f"Syncing Emby library: {self.emby_library_name}")

        items: List[LibraryItem] = []

        try:
            # Build query for library items
            params = {
                "ParentId": self.emby_library_id,
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Episode",
                "Fields": "Overview,Genres,Studios,People,ProviderIds,MediaSources",
                "EnableTotalRecordCount": "true",
                "StartIndex": "0",
                "Limit": "5000",
            }

            if self._user_id:
                url = f"{self.server_url}/Users/{self._user_id}/Items"
            else:
                url = f"{self.server_url}/Items"

            query = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{query}"

            async with self._session.get(full_url, headers=self.headers) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch Emby library: HTTP {response.status}")
                    return items

                data = await response.json()
                item_list = data.get("Items", [])

                for item_data in item_list:
                    try:
                        item = self._parse_item(item_data)
                        if item:
                            items.append(item)
                            self._items[item.id] = item
                    except Exception as e:
                        logger.debug(f"Error parsing item: {e}")

            self._last_sync = datetime.now()
            logger.info(f"Synced {len(items)} items from Emby: {self.emby_library_name}")

        except Exception as e:
            logger.exception(f"Error syncing Emby library: {e}")

        return items

    def _parse_item(self, item_data: Dict[str, Any]) -> Optional[LibraryItem]:
        """Parse Emby item into LibraryItem."""
        item_type = item_data.get("Type", "")
        item_id = item_data.get("Id", "")

        if item_type == "Movie":
            return self._parse_movie(item_data)
        elif item_type == "Episode":
            return self._parse_episode(item_data)

        return None

    def _parse_movie(self, item_data: Dict[str, Any]) -> LibraryItem:
        """Parse movie data into LibraryItem."""
        item_id = item_data.get("Id", "")
        title = item_data.get("Name", "Untitled")

        # Get duration
        duration = timedelta(0)
        runtime_ticks = item_data.get("RunTimeTicks", 0)
        if runtime_ticks:
            duration = timedelta(microseconds=runtime_ticks // 10)

        # Get provider IDs
        provider_ids = item_data.get("ProviderIds", {})

        return LibraryItem(
            id=f"emby_{item_id}",
            library_id=self.library_id,
            media_type=MediaType.MOVIE,
            title=title,
            sort_title=item_data.get("SortName", title).lower(),
            duration=duration,
            year=item_data.get("ProductionYear"),
            studio=self._get_first_studio(item_data),
            genres=item_data.get("Genres", []),
            actors=self._parse_actors(item_data),
            poster_path=self._get_image_url(item_id, "Primary"),
            fanart_path=self._get_image_url(item_id, "Backdrop"),
            tmdb_id=provider_ids.get("Tmdb"),
            tvdb_id=provider_ids.get("Tvdb"),
            imdb_id=provider_ids.get("Imdb"),
            added_at=self._parse_date(item_data.get("DateCreated")),
            updated_at=datetime.now(),
        )

    def _parse_episode(self, item_data: Dict[str, Any]) -> LibraryItem:
        """Parse episode data into LibraryItem."""
        item_id = item_data.get("Id", "")
        title = item_data.get("Name", "Untitled")

        # Get duration
        duration = timedelta(0)
        runtime_ticks = item_data.get("RunTimeTicks", 0)
        if runtime_ticks:
            duration = timedelta(microseconds=runtime_ticks // 10)

        show_title = item_data.get("SeriesName", "Unknown Show")
        season_number = item_data.get("ParentIndexNumber")
        episode_number = item_data.get("IndexNumber")

        sort_title = f"{show_title} {season_number or 0:02d}{episode_number or 0:03d}"

        return LibraryItem(
            id=f"emby_{item_id}",
            library_id=self.library_id,
            media_type=MediaType.EPISODE,
            title=title,
            sort_title=sort_title.lower(),
            duration=duration,
            year=item_data.get("ProductionYear"),
            show_title=show_title,
            season_number=season_number,
            episode_number=episode_number,
            poster_path=self._get_image_url(item_id, "Primary"),
            fanart_path=self._get_image_url(item_data.get("SeriesId", item_id), "Backdrop"),
            added_at=self._parse_date(item_data.get("DateCreated")),
            updated_at=datetime.now(),
        )

    def _get_first_studio(self, item_data: Dict[str, Any]) -> Optional[str]:
        """Get first studio from item data."""
        studios = item_data.get("Studios", [])
        if studios:
            if isinstance(studios[0], dict):
                return studios[0].get("Name")
            return str(studios[0])
        return None

    def _parse_actors(self, item_data: Dict[str, Any]) -> List[str]:
        """Parse actors from People data."""
        actors = []
        for person in item_data.get("People", []):
            if person.get("Type") == "Actor":
                actors.append(person.get("Name", ""))
        return [a for a in actors if a][:10]

    def _get_image_url(self, item_id: str, image_type: str) -> str:
        """Get image URL for an item."""
        return f"{self.server_url}/Items/{item_id}/Images/{image_type}?api_key={self.api_key}"

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None
        try:
            date_str = date_str.split(".")[0].replace("Z", "")
            return datetime.fromisoformat(date_str)
        except ValueError:
            return None

    async def get_item(self, item_id: str) -> Optional[LibraryItem]:
        """Get a specific item by ID."""
        return self._items.get(item_id)

    async def get_stream_url(self, item_id: str) -> Optional[str]:
        """Get streaming URL for an item."""
        emby_id = item_id.replace("emby_", "")

        params = {
            "Static": "true",
            "api_key": self.api_key,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())

        return f"{self.server_url}/Videos/{emby_id}/stream?{query}"

    @classmethod
    async def discover_libraries(
        cls, server_url: str, api_key: str
    ) -> List[Dict[str, Any]]:
        """
        Discover available libraries on an Emby server.

        Args:
            server_url: Emby server URL.
            api_key: API key.

        Returns:
            List of library info dicts.
        """
        libraries = []

        try:
            headers = {
                "X-Emby-Token": api_key,
                "Accept": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                # Get users first
                users_url = f"{server_url.rstrip('/')}/Users"
                async with session.get(users_url, headers=headers) as response:
                    if response.status != 200:
                        return libraries

                    users = await response.json()
                    if not users:
                        return libraries

                    user_id = users[0].get("Id")

                # Get library folders
                url = f"{server_url.rstrip('/')}/Users/{user_id}/Views"
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        return libraries

                    data = await response.json()
                    items = data.get("Items", [])

                    for item in items:
                        libraries.append({
                            "id": item.get("Id"),
                            "name": item.get("Name"),
                            "type": item.get("CollectionType", "unknown"),
                            "server_id": item.get("ServerId"),
                        })

        except Exception as e:
            logger.exception(f"Error discovering Emby libraries: {e}")

        return libraries
