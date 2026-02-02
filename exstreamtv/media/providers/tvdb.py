"""
TVDB (TheTVDB) metadata provider.

Fetches TV show and episode metadata from TVDB API v4.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import aiohttp

from exstreamtv.media.providers.base import MediaMetadata, MetadataProvider, PersonInfo

logger = logging.getLogger(__name__)


class TVDBProvider(MetadataProvider):
    """
    TheTVDB metadata provider.

    Requires a TVDB API key (v4).
    Get one at: https://thetvdb.com/api-information
    """

    BASE_URL = "https://api4.thetvdb.com/v4"
    IMAGE_BASE_URL = "https://artworks.thetvdb.com"

    def __init__(
        self,
        api_key: str,
        language: str = "eng",
    ):
        """
        Initialize TVDB provider.

        Args:
            api_key: TVDB API key (v4).
            language: Language code for metadata (e.g., "eng").
        """
        super().__init__(api_key, language)
        self._session: Optional[aiohttp.ClientSession] = None
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    @property
    def name(self) -> str:
        return "TVDB"

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def _ensure_token(self) -> bool:
        """Ensure we have a valid authentication token."""
        # Check if token is still valid
        if self._token and self._token_expires:
            if datetime.now() < self._token_expires:
                return True

        # Get new token
        session = await self._ensure_session()

        try:
            url = f"{self.BASE_URL}/login"
            payload = {"apikey": self.api_key}

            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.error(f"TVDB authentication failed: HTTP {response.status}")
                    return False

                data = await response.json()
                self._token = data.get("data", {}).get("token")

                if not self._token:
                    logger.error("TVDB token not in response")
                    return False

                # Token expires in 30 days, but we'll refresh every 24 hours
                self._token_expires = datetime.now().replace(
                    hour=23, minute=59, second=59
                )
                return True

        except Exception as e:
            logger.error(f"TVDB authentication error: {e}")
            return False

    async def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated API request to TVDB."""
        if not await self._ensure_token():
            return None

        session = await self._ensure_session()

        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

        try:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, try to refresh
                    self._token = None
                    if await self._ensure_token():
                        headers["Authorization"] = f"Bearer {self._token}"
                        async with session.get(url, headers=headers, params=params) as retry:
                            if retry.status == 200:
                                return await retry.json()
                    logger.error("TVDB authentication failed after retry")
                elif response.status == 404:
                    logger.debug(f"TVDB resource not found: {endpoint}")
                else:
                    logger.warning(f"TVDB API error: HTTP {response.status}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"TVDB request failed: {e}")
            return None

    async def search_movie(
        self, query: str, year: Optional[int] = None
    ) -> List[MediaMetadata]:
        """Search for movies on TVDB."""
        params: Dict[str, Any] = {
            "query": query,
            "type": "movie",
        }
        if year:
            params["year"] = year

        data = await self._request("/search", params)
        if not data:
            return []

        results = []
        for item in data.get("data", [])[:10]:
            try:
                metadata = self._parse_search_result(item, "movie")
                results.append(metadata)
            except Exception as e:
                logger.debug(f"Error parsing movie result: {e}")

        return results

    async def search_tv(
        self, query: str, year: Optional[int] = None
    ) -> List[MediaMetadata]:
        """Search for TV shows on TVDB."""
        params: Dict[str, Any] = {
            "query": query,
            "type": "series",
        }
        if year:
            params["year"] = year

        data = await self._request("/search", params)
        if not data:
            return []

        results = []
        for item in data.get("data", [])[:10]:
            try:
                metadata = self._parse_search_result(item, "show")
                results.append(metadata)
            except Exception as e:
                logger.debug(f"Error parsing TV result: {e}")

        return results

    async def get_movie(self, movie_id: str) -> Optional[MediaMetadata]:
        """Get detailed movie information."""
        data = await self._request(f"/movies/{movie_id}/extended")
        if not data:
            return None

        return self._parse_movie_detail(data.get("data", {}))

    async def get_tv_show(self, show_id: str) -> Optional[MediaMetadata]:
        """Get detailed TV show information."""
        data = await self._request(f"/series/{show_id}/extended")
        if not data:
            return None

        return self._parse_tv_detail(data.get("data", {}))

    async def get_episode(
        self, show_id: str, season: int, episode: int
    ) -> Optional[MediaMetadata]:
        """Get episode details."""
        # First get show info for context
        show_data = await self._request(f"/series/{show_id}")
        show_title = ""
        if show_data and show_data.get("data"):
            show_title = show_data["data"].get("name", "")

        # Get episodes for the season
        data = await self._request(f"/series/{show_id}/episodes/default")
        if not data:
            return None

        # Find the specific episode
        episodes = data.get("data", {}).get("episodes", [])
        for ep in episodes:
            if ep.get("seasonNumber") == season and ep.get("number") == episode:
                return self._parse_episode_detail(ep, show_id, show_title)

        return None

    async def get_season_episodes(
        self, show_id: str, season: int
    ) -> List[MediaMetadata]:
        """Get all episodes in a season."""
        # Get show info
        show_data = await self._request(f"/series/{show_id}")
        show_title = ""
        if show_data and show_data.get("data"):
            show_title = show_data["data"].get("name", "")

        # Get all episodes
        data = await self._request(f"/series/{show_id}/episodes/default")
        if not data:
            return []

        episodes = []
        for ep in data.get("data", {}).get("episodes", []):
            if ep.get("seasonNumber") == season:
                try:
                    metadata = self._parse_episode_detail(ep, show_id, show_title)
                    episodes.append(metadata)
                except Exception as e:
                    logger.debug(f"Error parsing episode: {e}")

        # Sort by episode number
        episodes.sort(key=lambda x: x.episode_number or 0)
        return episodes

    def _parse_search_result(
        self, data: Dict[str, Any], media_type: str
    ) -> MediaMetadata:
        """Parse search result into MediaMetadata."""
        first_air = self._parse_date(data.get("first_air_time") or data.get("year"))

        return MediaMetadata(
            title=data.get("name", "") or data.get("title", ""),
            media_type=media_type,
            tvdb_id=str(data.get("tvdb_id", "") or data.get("id", "")),
            overview=data.get("overview"),
            release_date=first_air,
            year=int(data.get("year")) if data.get("year") else None,
            poster_url=data.get("image_url") or data.get("thumbnail"),
            status=data.get("status"),
            countries=[data.get("country")] if data.get("country") else [],
            networks=[data.get("network")] if data.get("network") else [],
        )

    def _parse_movie_detail(self, data: Dict[str, Any]) -> MediaMetadata:
        """Parse detailed movie data."""
        release_date = self._parse_date(data.get("year"))

        # Get artwork
        poster_url = None
        backdrop_url = None
        for art in data.get("artworks", []):
            art_type = art.get("type")
            if art_type == 1 and not poster_url:  # Poster
                poster_url = art.get("image")
            elif art_type == 2 and not backdrop_url:  # Fanart
                backdrop_url = art.get("image")

        # Get genres
        genres = [g.get("name", "") for g in data.get("genres", [])]

        return MediaMetadata(
            title=data.get("name", ""),
            media_type="movie",
            tvdb_id=str(data.get("id", "")),
            imdb_id=data.get("imdb_id"),
            overview=data.get("overview"),
            release_date=release_date,
            year=int(data.get("year")) if data.get("year") else None,
            runtime_minutes=data.get("runtime"),
            status=data.get("status", {}).get("name") if isinstance(data.get("status"), dict) else None,
            poster_url=poster_url,
            backdrop_url=backdrop_url,
            genres=genres,
            studios=[s.get("name", "") for s in data.get("studios", [])],
            cast=self._parse_characters(data.get("characters", [])),
        )

    def _parse_tv_detail(self, data: Dict[str, Any]) -> MediaMetadata:
        """Parse detailed TV show data."""
        first_air = self._parse_date(data.get("firstAired"))

        # Get artwork
        poster_url = None
        backdrop_url = None
        for art in data.get("artworks", []):
            art_type = art.get("type")
            if art_type == 2 and not poster_url:  # Poster (TVDB type 2)
                poster_url = art.get("image")
            elif art_type == 3 and not backdrop_url:  # Fanart (TVDB type 3)
                backdrop_url = art.get("image")

        # Fallback to simple image
        if not poster_url:
            poster_url = data.get("image")

        # Get genres
        genres = [g.get("name", "") for g in data.get("genres", [])]

        # Get networks
        networks = []
        for network in data.get("networks", []) or data.get("originalNetwork", []):
            if isinstance(network, dict):
                networks.append(network.get("name", ""))
            elif isinstance(network, str):
                networks.append(network)

        # Get average runtime
        runtime = data.get("averageRuntime") or data.get("defaultSeasonType")

        return MediaMetadata(
            title=data.get("name", ""),
            original_title=data.get("originalName"),
            media_type="show",
            tvdb_id=str(data.get("id", "")),
            imdb_id=data.get("imdb_id"),
            overview=data.get("overview"),
            release_date=first_air,
            year=first_air.year if first_air else None,
            rating=data.get("score"),
            runtime_minutes=runtime,
            status=data.get("status", {}).get("name") if isinstance(data.get("status"), dict) else None,
            poster_url=poster_url,
            backdrop_url=backdrop_url,
            genres=genres,
            networks=networks,
            countries=[data.get("originalCountry")] if data.get("originalCountry") else [],
            languages=[data.get("originalLanguage")] if data.get("originalLanguage") else [],
            cast=self._parse_characters(data.get("characters", [])),
        )

    def _parse_episode_detail(
        self, data: Dict[str, Any], show_id: str, show_title: str
    ) -> MediaMetadata:
        """Parse detailed episode data."""
        air_date = self._parse_date(data.get("aired"))

        return MediaMetadata(
            title=data.get("name", f"Episode {data.get('number')}"),
            media_type="episode",
            tvdb_id=str(data.get("id", "")),
            show_title=show_title,
            season_number=data.get("seasonNumber"),
            episode_number=data.get("number"),
            overview=data.get("overview"),
            release_date=air_date,
            year=air_date.year if air_date else None,
            runtime_minutes=data.get("runtime"),
            thumb_url=data.get("image"),
        )

    def _parse_characters(self, characters: List[Dict[str, Any]]) -> List[PersonInfo]:
        """Parse character/cast list."""
        cast = []
        for char in characters[:20]:
            person = char.get("personName") or (
                char.get("people", {}).get("name") if char.get("people") else None
            )
            if person:
                cast.append(
                    PersonInfo(
                        name=person,
                        role=char.get("name", ""),
                        image_url=char.get("image"),
                    )
                )
        return cast

    def _parse_date(self, date_value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if not date_value:
            return None

        # Handle year-only
        if isinstance(date_value, int):
            return date(date_value, 1, 1)

        if isinstance(date_value, str):
            # Try full date first
            try:
                parts = date_value.split("-")
                if len(parts) >= 3:
                    return date(int(parts[0]), int(parts[1]), int(parts[2]))
                elif len(parts) == 1 and len(parts[0]) == 4:
                    return date(int(parts[0]), 1, 1)
            except (ValueError, IndexError):
                pass

        return None

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
