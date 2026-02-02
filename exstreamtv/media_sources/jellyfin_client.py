"""
Jellyfin Media Source Integration

Connects to Jellyfin Media Server to scan and import media libraries.
"""

import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from exstreamtv.media_sources.base import (
    MediaLibrary,
    MediaSource,
    MediaSourceItem,
    MediaSourceStatus,
)

logger = logging.getLogger(__name__)


class JellyfinMediaSource(MediaSource):
    """Jellyfin Media Server integration.
    
    Connects to a Jellyfin server using an API key to:
    - List available libraries
    - Scan and import media items
    - Get streaming URLs for playback
    
    Authentication:
        Uses Jellyfin API keys. Get your API key from:
        Dashboard > API Keys > Add API Key
    """
    
    source_type = "jellyfin"
    
    def __init__(
        self,
        name: str,
        server_url: str,
        api_key: str,
        user_id: str | None = None,
        timeout: int = 30,
    ):
        """Initialize Jellyfin media source.
        
        Args:
            name: Display name for this source
            server_url: Jellyfin server URL (e.g., http://192.168.1.100:8096)
            api_key: Jellyfin API key
            user_id: User ID for user-specific content (optional)
            timeout: Request timeout in seconds
        """
        super().__init__(name, server_url)
        self.api_key = api_key
        self.user_id = user_id
        self.timeout = timeout
        self._server_name: str | None = None
        self._server_version: str | None = None
        self._server_id: str | None = None
        
    @property
    def headers(self) -> dict[str, str]:
        """Get authentication headers for Jellyfin API."""
        return {
            "X-Emby-Token": self.api_key,  # Jellyfin uses X-Emby-Token for compatibility
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    
    async def _request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """Make a request to the Jellyfin API."""
        url = urljoin(self.server_url + "/", endpoint.lstrip("/"))
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json_data,
                )
                
                if response.status_code == 401:
                    self._error_message = "Authentication failed. Invalid API key."
                    self.status = MediaSourceStatus.ERROR
                    return None
                    
                if response.status_code == 404:
                    self._error_message = f"Endpoint not found: {endpoint}"
                    return None
                    
                response.raise_for_status()
                
                if response.content:
                    return response.json()
                return {}
                
        except httpx.TimeoutException:
            self._error_message = f"Connection timeout to {self.server_url}"
            self.status = MediaSourceStatus.ERROR
            logger.error(self._error_message)
            return None
        except httpx.ConnectError:
            self._error_message = f"Cannot connect to {self.server_url}"
            self.status = MediaSourceStatus.ERROR
            logger.error(self._error_message)
            return None
        except Exception as e:
            self._error_message = f"Request error: {str(e)}"
            self.status = MediaSourceStatus.ERROR
            logger.exception(f"Jellyfin API error: {e}")
            return None
    
    async def connect(self) -> bool:
        """Connect to the Jellyfin server and verify authentication."""
        self.status = MediaSourceStatus.CONNECTING
        self._error_message = None
        
        # Get server info
        result = await self._request("/System/Info/Public")
        if not result or not isinstance(result, dict):
            return False
        
        self._server_name = result.get("ServerName", "Jellyfin Server")
        self._server_version = result.get("Version")
        self._server_id = result.get("Id")
        
        # If no user_id specified, get first admin user
        if not self.user_id:
            users = await self._request("/Users")
            if users and isinstance(users, list) and len(users) > 0:
                # Find admin user or use first
                for user in users:
                    if user.get("Policy", {}).get("IsAdministrator"):
                        self.user_id = user.get("Id")
                        break
                if not self.user_id:
                    self.user_id = users[0].get("Id")
        
        self.status = MediaSourceStatus.CONNECTED
        logger.info(f"Connected to Jellyfin: {self._server_name} v{self._server_version}")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from the Jellyfin server."""
        self.status = MediaSourceStatus.DISCONNECTED
        self._libraries.clear()
        logger.info(f"Disconnected from Jellyfin: {self.name}")
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test the connection to the Jellyfin server."""
        if await self.connect():
            return True, f"Connected to {self._server_name} (v{self._server_version})"
        return False, self._error_message or "Connection failed"
    
    async def get_libraries(self) -> list[MediaLibrary]:
        """Get available libraries from Jellyfin."""
        if not self.is_connected:
            await self.connect()
        
        if not self.user_id:
            self._error_message = "No user ID available"
            return []
        
        result = await self._request(f"/Users/{self.user_id}/Views")
        if not result or not isinstance(result, dict):
            return []
        
        libraries = []
        items = result.get("Items", [])
        
        for item in items:
            collection_type = item.get("CollectionType", "")
            lib_type = {
                "movies": "movie",
                "tvshows": "show",
                "music": "music",
                "photos": "photo",
                "books": "book",
            }.get(collection_type, "other")
            
            library = MediaLibrary(
                id=item.get("Id", ""),
                name=item.get("Name", "Unknown"),
                type=lib_type,
                is_enabled=True,
                metadata={
                    "collection_type": collection_type,
                    "etag": item.get("Etag"),
                },
            )
            libraries.append(library)
        
        self._libraries = libraries
        logger.info(f"Found {len(libraries)} Jellyfin libraries")
        return libraries
    
    async def scan_library(self, library_id: str) -> list[MediaSourceItem]:
        """Scan a Jellyfin library and return all items."""
        self.status = MediaSourceStatus.SCANNING
        items = []
        
        if not self.user_id:
            self.status = MediaSourceStatus.CONNECTED
            return []
        
        # Get all items in the library
        result = await self._request(
            f"/Users/{self.user_id}/Items",
            params={
                "ParentId": library_id,
                "Recursive": True,
                "IncludeItemTypes": "Movie,Episode,Audio",
                "Fields": "Path,Overview,Genres,Studios,People,MediaStreams,ProviderIds",
                "StartIndex": 0,
                "Limit": 10000,  # Adjust as needed
            },
        )
        
        if not result or not isinstance(result, dict):
            self.status = MediaSourceStatus.CONNECTED
            return []
        
        item_list = result.get("Items", [])
        
        for item_data in item_list:
            item = self._parse_item(item_data, library_id)
            if item:
                items.append(item)
        
        # Update library item count
        for lib in self._libraries:
            if lib.id == library_id:
                lib.item_count = len(items)
                lib.last_scan = datetime.now()
                break
        
        self.status = MediaSourceStatus.CONNECTED
        logger.info(f"Scanned Jellyfin library: {len(items)} items")
        return items
    
    def _parse_item(
        self,
        item_data: dict[str, Any],
        library_id: str,
    ) -> MediaSourceItem | None:
        """Parse Jellyfin item into MediaSourceItem."""
        try:
            jellyfin_type = item_data.get("Type", "")
            item_id = item_data.get("Id", "")
            
            # Map Jellyfin types
            item_type = {
                "Movie": "movie",
                "Episode": "episode",
                "Audio": "track",
                "Series": "show",
                "Season": "season",
                "MusicAlbum": "album",
                "MusicArtist": "artist",
            }.get(jellyfin_type, "other")
            
            # Skip container types
            if item_type in ("show", "season", "artist", "album"):
                return None
            
            # Get duration in ms (Jellyfin uses ticks: 1 tick = 100 nanoseconds)
            run_time_ticks = item_data.get("RunTimeTicks", 0)
            duration_ms = run_time_ticks // 10000 if run_time_ticks else 0
            
            # Build image URLs
            thumbnail_url = None
            art_url = None
            if item_id:
                thumbnail_url = f"{self.server_url}/Items/{item_id}/Images/Primary?api_key={self.api_key}"
                if item_data.get("BackdropImageTags"):
                    art_url = f"{self.server_url}/Items/{item_id}/Images/Backdrop?api_key={self.api_key}"
            
            # Get genres
            genres = item_data.get("Genres", [])
            
            # Get people (actors, directors)
            people = item_data.get("People", [])
            actors = [p.get("Name") for p in people if p.get("Type") == "Actor"]
            directors = [p.get("Name") for p in people if p.get("Type") == "Director"]
            
            # Episode-specific fields
            show_title = item_data.get("SeriesName")
            season_number = item_data.get("ParentIndexNumber")
            episode_number = item_data.get("IndexNumber")
            
            # Get file path
            file_path = item_data.get("Path")
            
            return MediaSourceItem(
                id=item_id,
                title=item_data.get("Name", "Unknown"),
                type=item_type,
                duration_ms=duration_ms,
                year=item_data.get("ProductionYear"),
                show_title=show_title,
                season_number=season_number,
                episode_number=episode_number,
                file_path=file_path,
                thumbnail_url=thumbnail_url,
                art_url=art_url,
                summary=item_data.get("Overview"),
                genres=genres,
                actors=actors[:10],
                directors=directors,
                studio=next(iter(item_data.get("Studios", [])), {}).get("Name"),
                content_rating=item_data.get("OfficialRating"),
                rating=item_data.get("CommunityRating"),
                source_type="jellyfin",
                source_id=self.name,
                library_id=library_id,
                raw_metadata={
                    "provider_ids": item_data.get("ProviderIds", {}),
                    "date_created": item_data.get("DateCreated"),
                    "play_count": item_data.get("UserData", {}).get("PlayCount"),
                },
            )
        except Exception as e:
            logger.warning(f"Error parsing Jellyfin item: {e}")
            return None
    
    async def get_item(self, item_id: str) -> MediaSourceItem | None:
        """Get a specific item by ID."""
        if not self.user_id:
            return None
            
        result = await self._request(
            f"/Users/{self.user_id}/Items/{item_id}",
            params={
                "Fields": "Path,Overview,Genres,Studios,People,MediaStreams,ProviderIds",
            },
        )
        
        if result and isinstance(result, dict):
            return self._parse_item(result, "")
        return None
    
    async def get_stream_url(self, item_id: str) -> str | None:
        """Get the streaming URL for an item."""
        return f"{self.server_url}/Items/{item_id}/Download?api_key={self.api_key}"
    
    async def get_hls_stream_url(
        self,
        item_id: str,
        max_streaming_bitrate: int = 8000000,
    ) -> str | None:
        """Get HLS transcoded stream URL."""
        params = {
            "DeviceId": "exstreamtv",
            "MediaSourceId": item_id,
            "PlaySessionId": f"exstreamtv-{item_id}",
            "api_key": self.api_key,
            "VideoCodec": "h264",
            "AudioCodec": "aac",
            "MaxStreamingBitrate": max_streaming_bitrate,
            "TranscodingMaxAudioChannels": 2,
            "SegmentContainer": "ts",
            "MinSegments": 1,
            "BreakOnNonKeyFrames": True,
        }
        
        base = f"{self.server_url}/Videos/{item_id}/master.m3u8"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}?{query}"
    
    async def get_episodes_for_show(self, show_id: str) -> list[MediaSourceItem]:
        """Get all episodes for a TV show."""
        if not self.user_id:
            return []
        
        result = await self._request(
            f"/Shows/{show_id}/Episodes",
            params={
                "UserId": self.user_id,
                "Fields": "Path,Overview,Genres,MediaStreams",
            },
        )
        
        if not result or not isinstance(result, dict):
            return []
        
        items = []
        for item_data in result.get("Items", []):
            item = self._parse_item(item_data, "")
            if item:
                items.append(item)
        
        return items
    
    async def refresh_library(self, library_id: str) -> bool:
        """Trigger a Jellyfin library refresh."""
        result = await self._request(
            f"/Items/{library_id}/Refresh",
            method="POST",
            json_data={
                "Recursive": True,
                "MetadataRefreshMode": "Default",
                "ImageRefreshMode": "Default",
            },
        )
        return result is not None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base = super().to_dict()
        base.update({
            "server_name": self._server_name,
            "server_version": self._server_version,
            "server_id": self._server_id,
            "user_id": self.user_id,
            "libraries": [
                {
                    "id": lib.id,
                    "name": lib.name,
                    "type": lib.type,
                    "item_count": lib.item_count,
                    "is_enabled": lib.is_enabled,
                    "last_scan": lib.last_scan.isoformat() if lib.last_scan else None,
                }
                for lib in self._libraries
            ],
        })
        return base
