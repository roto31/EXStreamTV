"""
Plex Media Source Integration

Connects to Plex Media Server to scan and import media libraries.
Uses the Plex API: https://developer.plex.tv/pms/
Reference: python-plexapi https://python-plexapi.readthedocs.io/en/latest/
"""

import asyncio
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


class PlexMediaSource(MediaSource):
    """Plex Media Server integration.
    
    Connects to a Plex server using an authentication token to:
    - List available libraries
    - Scan and import media items
    - Get streaming URLs for playback
    
    Authentication:
        Uses Plex tokens for authentication. Tokens can be obtained from:
        - Plex web app: Account Settings > Authorized Devices > Get Token
        - Via plex.tv OAuth flow
    
    API Reference:
        https://developer.plex.tv/pms/
    """
    
    source_type = "plex"
    
    def __init__(
        self,
        name: str,
        server_url: str,
        token: str,
        timeout: int = 30,
    ):
        """Initialize Plex media source.
        
        Args:
            name: Display name for this source
            server_url: Plex server URL (e.g., http://192.168.1.100:32400)
            token: Plex authentication token
            timeout: Request timeout in seconds
        """
        super().__init__(name, server_url)
        self.token = token
        self.timeout = timeout
        self._server_name: str | None = None
        self._server_version: str | None = None
        self._machine_id: str | None = None
        
    @property
    def headers(self) -> dict[str, str]:
        """Get authentication headers for Plex API."""
        return {
            "X-Plex-Token": self.token,
            "Accept": "application/json",
            "X-Plex-Client-Identifier": "exstreamtv",
            "X-Plex-Product": "EXStreamTV",
            "X-Plex-Version": "2.0.0",
        }
    
    async def _request(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Make a request to the Plex API.
        
        Args:
            endpoint: API endpoint (e.g., /library/sections)
            method: HTTP method
            params: Query parameters
            
        Returns:
            JSON response or None on error
        """
        url = urljoin(self.server_url, endpoint)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                )
                
                if response.status_code == 401:
                    self._error_message = "Authentication failed. Invalid token."
                    self.status = MediaSourceStatus.ERROR
                    return None
                    
                if response.status_code == 404:
                    self._error_message = f"Endpoint not found: {endpoint}"
                    return None
                    
                response.raise_for_status()
                return response.json()
                
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
            logger.exception(f"Plex API error: {e}")
            return None
    
    async def connect(self) -> bool:
        """Connect to the Plex server and verify authentication."""
        self.status = MediaSourceStatus.CONNECTING
        self._error_message = None
        
        # Get server identity
        result = await self._request("/identity")
        if not result:
            return False
        
        media_container = result.get("MediaContainer", {})
        self._machine_id = media_container.get("machineIdentifier")
        self._server_version = media_container.get("version")
        
        # Get server details
        result = await self._request("/")
        if result:
            media_container = result.get("MediaContainer", {})
            self._server_name = media_container.get("friendlyName", "Plex Server")
        
        self.status = MediaSourceStatus.CONNECTED
        logger.info(f"Connected to Plex: {self._server_name} v{self._server_version}")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from the Plex server."""
        self.status = MediaSourceStatus.DISCONNECTED
        self._libraries.clear()
        logger.info(f"Disconnected from Plex: {self.name}")
    
    async def test_connection(self) -> tuple[bool, str]:
        """Test the connection to the Plex server."""
        if await self.connect():
            return True, f"Connected to {self._server_name} (v{self._server_version})"
        return False, self._error_message or "Connection failed"
    
    async def get_libraries(self) -> list[MediaLibrary]:
        """Get available libraries from Plex.
        
        Plex API: GET /library/sections
        """
        if not self.is_connected:
            await self.connect()
            
        result = await self._request("/library/sections")
        if not result:
            return []
        
        libraries = []
        media_container = result.get("MediaContainer", {})
        directories = media_container.get("Directory", [])
        
        for directory in directories:
            # Map Plex library types
            plex_type = directory.get("type", "")
            lib_type = {
                "movie": "movie",
                "show": "show",
                "artist": "music",
                "photo": "photo",
            }.get(plex_type, "other")
            
            library = MediaLibrary(
                id=str(directory.get("key")),
                name=directory.get("title", "Unknown"),
                type=lib_type,
                is_enabled=True,
                metadata={
                    "plex_type": plex_type,
                    "uuid": directory.get("uuid"),
                    "agent": directory.get("agent"),
                    "scanner": directory.get("scanner"),
                    "language": directory.get("language"),
                    "locations": [
                        loc.get("path") for loc in directory.get("Location", [])
                    ],
                },
            )
            libraries.append(library)
        
        self._libraries = libraries
        logger.info(f"Found {len(libraries)} Plex libraries")
        return libraries
    
    async def scan_library(self, library_id: str) -> list[MediaSourceItem]:
        """Scan a Plex library and return all items.
        
        For movie libraries: GET /library/sections/{key}/all
        For TV libraries: GET /library/sections/{key}/all to get shows,
                         then GET /library/metadata/{ratingKey}/allLeaves for episodes
        
        Plex API Reference: https://developer.plex.tv/pms/
        """
        self.status = MediaSourceStatus.SCANNING
        items = []
        
        # First, determine library type
        library_type = await self._get_library_type(library_id)
        
        # Get all items in the library
        result = await self._request(
            f"/library/sections/{library_id}/all",
            params={"includeGuids": 1},
        )
        
        if not result:
            self.status = MediaSourceStatus.CONNECTED
            return []
        
        media_container = result.get("MediaContainer", {})
        metadata_list = media_container.get("Metadata", [])
        library_title = media_container.get("librarySectionTitle", "")
        
        # Handle TV show libraries - fetch episodes for each show
        if library_type == "show":
            logger.info(f"TV library detected: '{library_title}' with {len(metadata_list)} shows")
            
            for show_metadata in metadata_list:
                show_rating_key = show_metadata.get("ratingKey")
                show_title = show_metadata.get("title", "Unknown Show")
                
                if show_rating_key:
                    # Fetch all episodes for this show using allLeaves endpoint
                    episodes = await self._fetch_show_episodes(
                        show_rating_key, 
                        show_title,
                        show_metadata,
                        library_id, 
                        library_title
                    )
                    items.extend(episodes)
                    
            logger.info(f"Fetched {len(items)} episodes from {len(metadata_list)} shows")
        else:
            # Movie/other libraries - parse items directly
            for metadata in metadata_list:
                item = self._parse_metadata(metadata, library_id, library_title)
                if item:
                    items.append(item)
        
        # Update library item count
        for lib in self._libraries:
            if lib.id == library_id:
                lib.item_count = len(items)
                lib.last_scan = datetime.now()
                break
        
        self.status = MediaSourceStatus.CONNECTED
        logger.info(f"Scanned Plex library '{library_title}': {len(items)} items")
        return items
    
    async def _get_library_type(self, library_id: str) -> str:
        """Get the type of a library (movie, show, music, etc.)."""
        # Check cached libraries first
        for lib in self._libraries:
            if lib.id == library_id:
                plex_type = lib.metadata.get("plex_type", "")
                if plex_type:
                    return plex_type
        
        # Fetch library sections and find the matching one
        result = await self._request("/library/sections")
        if result:
            media_container = result.get("MediaContainer", {})
            directories = media_container.get("Directory", [])
            for directory in directories:
                if str(directory.get("key")) == str(library_id):
                    lib_type = directory.get("type", "unknown")
                    logger.debug(f"Library {library_id} type: {lib_type}")
                    return lib_type
        
        return "unknown"
    
    async def _fetch_show_episodes(
        self,
        show_rating_key: str,
        show_title: str,
        show_metadata: dict[str, Any],
        library_id: str,
        library_title: str,
    ) -> list[MediaSourceItem]:
        """Fetch all episodes for a TV show.
        
        Plex API: GET /library/metadata/{ratingKey}/allLeaves
        Returns all leaf items (episodes) for the show.
        """
        episodes = []
        
        result = await self._request(
            f"/library/metadata/{show_rating_key}/allLeaves",
            params={"includeGuids": 1},
        )
        
        if not result:
            return episodes
        
        media_container = result.get("MediaContainer", {})
        metadata_list = media_container.get("Metadata", [])
        
        # Get show-level artwork for fallback
        show_thumb = show_metadata.get("thumb")
        show_art = show_metadata.get("art")
        show_year = show_metadata.get("year")
        show_studio = show_metadata.get("studio")
        show_content_rating = show_metadata.get("contentRating")
        
        for episode_metadata in metadata_list:
            episode = self._parse_episode_metadata(
                episode_metadata,
                show_title,
                show_thumb,
                show_art,
                show_year,
                show_studio,
                show_content_rating,
                library_id,
                library_title,
            )
            if episode:
                episodes.append(episode)
        
        return episodes
    
    def _parse_episode_metadata(
        self,
        metadata: dict[str, Any],
        show_title: str,
        show_thumb: str | None,
        show_art: str | None,
        show_year: int | None,
        show_studio: str | None,
        show_content_rating: str | None,
        library_id: str,
        library_title: str,
    ) -> MediaSourceItem | None:
        """Parse Plex episode metadata into MediaSourceItem."""
        try:
            rating_key = str(metadata.get("ratingKey", ""))
            
            # Get media info
            media_list = metadata.get("Media", [])
            duration_ms = int(metadata.get("duration", 0))
            
            # Get file path from first media part
            file_path = None
            if media_list:
                parts = media_list[0].get("Part", [])
                if parts:
                    file_path = parts[0].get("file")
            
            # Episode-specific fields
            season_number = metadata.get("parentIndex", 1)
            episode_number = metadata.get("index", 1)
            episode_title = metadata.get("title", f"Episode {episode_number}")
            
            # Build thumbnail URL - prefer episode thumb, fall back to show
            thumb = metadata.get("thumb") or show_thumb
            thumbnail_url = f"{self.server_url}{thumb}?X-Plex-Token={self.token}" if thumb else None
            
            # Art URL - prefer episode, fall back to show
            art = metadata.get("art") or show_art
            art_url = f"{self.server_url}{art}?X-Plex-Token={self.token}" if art else None
            
            # Get directors and writers
            directors = [d.get("tag") for d in metadata.get("Director", [])]
            writers = [w.get("tag") for w in metadata.get("Writer", [])]
            
            return MediaSourceItem(
                id=rating_key,
                title=episode_title,
                type="episode",
                duration_ms=duration_ms,
                year=metadata.get("year") or show_year,
                show_title=show_title,
                season_number=season_number,
                episode_number=episode_number,
                file_path=file_path,
                thumbnail_url=thumbnail_url,
                art_url=art_url,
                summary=metadata.get("summary"),
                genres=[],  # Episodes don't have genres directly
                actors=[],  # Use show actors
                directors=directors,
                studio=show_studio,
                content_rating=metadata.get("contentRating") or show_content_rating,
                rating=metadata.get("audienceRating") or metadata.get("rating"),
                source_type="plex",
                source_id=self.name,
                library_id=library_id,
                raw_metadata={
                    "addedAt": metadata.get("addedAt"),
                    "updatedAt": metadata.get("updatedAt"),
                    "viewCount": metadata.get("viewCount"),
                    "lastViewedAt": metadata.get("lastViewedAt"),
                    "guids": metadata.get("Guid", []),
                    "grandparentRatingKey": metadata.get("grandparentRatingKey"),
                    "parentRatingKey": metadata.get("parentRatingKey"),
                    "originallyAvailableAt": metadata.get("originallyAvailableAt"),
                },
            )
        except Exception as e:
            logger.warning(f"Error parsing Plex episode metadata: {e}")
            return None
    
    def _parse_metadata(
        self,
        metadata: dict[str, Any],
        library_id: str,
        library_title: str,
    ) -> MediaSourceItem | None:
        """Parse Plex metadata into MediaSourceItem."""
        try:
            plex_type = metadata.get("type", "")
            rating_key = str(metadata.get("ratingKey", ""))
            
            # Map Plex types to our types
            item_type = {
                "movie": "movie",
                "episode": "episode",
                "track": "track",
                "show": "show",
                "season": "season",
                "artist": "artist",
                "album": "album",
            }.get(plex_type, "other")
            
            # Skip container types - we want individual playable items
            if item_type in ("show", "season", "artist", "album"):
                return None
            
            # Get media info
            media_list = metadata.get("Media", [])
            duration_ms = int(metadata.get("duration", 0))
            
            # Get file path from first media part
            file_path = None
            if media_list:
                parts = media_list[0].get("Part", [])
                if parts:
                    file_path = parts[0].get("file")
            
            # Build thumbnail URL
            thumb = metadata.get("thumb")
            thumbnail_url = f"{self.server_url}{thumb}?X-Plex-Token={self.token}" if thumb else None
            
            art = metadata.get("art")
            art_url = f"{self.server_url}{art}?X-Plex-Token={self.token}" if art else None
            
            # Get genres
            genres = [g.get("tag") for g in metadata.get("Genre", [])]
            
            # Get actors
            actors = [r.get("tag") for r in metadata.get("Role", [])]
            
            # Get directors
            directors = [d.get("tag") for d in metadata.get("Director", [])]
            
            # Episode-specific fields
            show_title = metadata.get("grandparentTitle")
            season_number = metadata.get("parentIndex")
            episode_number = metadata.get("index")
            
            return MediaSourceItem(
                id=rating_key,
                title=metadata.get("title", "Unknown"),
                type=item_type,
                duration_ms=duration_ms,
                year=metadata.get("year"),
                show_title=show_title,
                season_number=season_number,
                episode_number=episode_number,
                file_path=file_path,
                thumbnail_url=thumbnail_url,
                art_url=art_url,
                summary=metadata.get("summary"),
                genres=genres,
                actors=actors[:10],  # Limit to first 10
                directors=directors,
                studio=metadata.get("studio"),
                content_rating=metadata.get("contentRating"),
                rating=metadata.get("audienceRating") or metadata.get("rating"),
                source_type="plex",
                source_id=self.name,
                library_id=library_id,
                raw_metadata={
                    "addedAt": metadata.get("addedAt"),
                    "updatedAt": metadata.get("updatedAt"),
                    "viewCount": metadata.get("viewCount"),
                    "lastViewedAt": metadata.get("lastViewedAt"),
                    "guids": metadata.get("Guid", []),
                },
            )
        except Exception as e:
            logger.warning(f"Error parsing Plex metadata: {e}")
            return None
    
    async def get_item(self, item_id: str) -> MediaSourceItem | None:
        """Get a specific item by rating key.
        
        Plex API: GET /library/metadata/{ratingKey}
        """
        result = await self._request(
            f"/library/metadata/{item_id}",
            params={"includeGuids": 1},
        )
        
        if not result:
            return None
        
        media_container = result.get("MediaContainer", {})
        metadata_list = media_container.get("Metadata", [])
        
        if metadata_list:
            return self._parse_metadata(metadata_list[0], "", "")
        return None
    
    async def get_stream_url(self, item_id: str) -> str | None:
        """Get the streaming URL for an item.
        
        Returns a direct stream URL for the media.
        """
        # For direct play, construct the URL
        return f"{self.server_url}/library/metadata/{item_id}/file?X-Plex-Token={self.token}"
    
    async def get_transcode_url(
        self,
        item_id: str,
        video_quality: int = 8,  # 1-12, higher = better
        max_video_bitrate: int = 8000,  # kbps
    ) -> str | None:
        """Get a transcoded stream URL.
        
        Plex API: GET /video/:/transcode/universal/start.m3u8
        """
        params = {
            "path": f"/library/metadata/{item_id}",
            "mediaIndex": 0,
            "partIndex": 0,
            "protocol": "hls",
            "fastSeek": 1,
            "directPlay": 0,
            "directStream": 1,
            "subtitleSize": 100,
            "audioBoost": 100,
            "location": "lan",
            "addDebugOverlay": 0,
            "autoAdjustQuality": 0,
            "directStreamAudio": 1,
            "mediaBufferSize": 102400,
            "session": f"exstreamtv-{item_id}",
            "subtitles": "burn",
            "copyts": 1,
            "Accept-Language": "en",
            "X-Plex-Client-Profile-Extra": "",
            "X-Plex-Incomplete-Segments": 1,
            "X-Plex-Product": "EXStreamTV",
            "X-Plex-Platform": "Generic",
            "X-Plex-Token": self.token,
            "maxVideoBitrate": max_video_bitrate,
            "videoQuality": video_quality,
        }
        
        base = f"{self.server_url}/video/:/transcode/universal/start.m3u8"
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}?{query}"
    
    async def get_episodes_for_show(self, show_id: str) -> list[MediaSourceItem]:
        """Get all episodes for a TV show.
        
        Plex API: GET /library/metadata/{ratingKey}/allLeaves
        """
        result = await self._request(f"/library/metadata/{show_id}/allLeaves")
        if not result:
            return []
        
        items = []
        media_container = result.get("MediaContainer", {})
        metadata_list = media_container.get("Metadata", [])
        
        for metadata in metadata_list:
            item = self._parse_metadata(metadata, "", "")
            if item:
                items.append(item)
        
        return items
    
    async def refresh_library(self, library_id: str) -> bool:
        """Trigger a Plex library refresh.
        
        Plex API: GET /library/sections/{key}/refresh
        """
        result = await self._request(f"/library/sections/{library_id}/refresh")
        return result is not None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base = super().to_dict()
        base.update({
            "server_name": self._server_name,
            "server_version": self._server_version,
            "machine_id": self._machine_id,
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
