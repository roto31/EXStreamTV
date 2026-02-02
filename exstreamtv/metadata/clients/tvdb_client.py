"""
TVDB Client

Provides TVDB (The TV Database) API client with full implementation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

import aiohttp

from exstreamtv.metadata.clients.base import MetadataClient

logger = logging.getLogger(__name__)


class TVDBClient(MetadataClient):
    """TVDB metadata client with full API implementation."""
    
    BASE_URL = "https://api4.thetvdb.com/v4"
    IMAGE_BASE_URL = "https://artworks.thetvdb.com"
    
    def __init__(self, api_key: Optional[str] = None, language: str = "eng"):
        super().__init__(api_key)
        self._token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self.language = language
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session
    
    async def authenticate(self) -> bool:
        """Authenticate with TVDB API and get token."""
        if not self.api_key:
            logger.warning("TVDB API key not configured")
            return False
        
        # Check if token is still valid
        if self._token and self._token_expires:
            if datetime.now() < self._token_expires:
                return True
        
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
                
                # Token expires in 30 days, refresh every 24 hours
                self._token_expires = datetime.now().replace(
                    hour=23, minute=59, second=59
                )
                logger.debug("TVDB authentication successful")
                return True
                
        except Exception as e:
            logger.error(f"TVDB authentication error: {e}")
            return False
    
    async def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated API request to TVDB."""
        if not await self.authenticate():
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
                    # Token expired, refresh and retry
                    self._token = None
                    if await self.authenticate():
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
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search TVDB for series or movies."""
        logger.debug(f"TVDB search: {query}")
        
        params: Dict[str, Any] = {"query": query}
        
        # Filter by type if specified
        media_type = kwargs.get("media_type", kwargs.get("type"))
        if media_type == "movie":
            params["type"] = "movie"
        elif media_type in ("tv", "series", "show"):
            params["type"] = "series"
        
        year = kwargs.get("year")
        if year:
            params["year"] = year
        
        data = await self._request("/search", params)
        if not data:
            return []
        
        results = []
        for item in data.get("data", [])[:10]:
            try:
                result = self._parse_search_result(item)
                results.append(result)
            except Exception as e:
                logger.debug(f"Error parsing search result: {e}")
        
        return results
    
    async def get_details(self, item_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Get TVDB series or movie details."""
        logger.debug(f"TVDB get details: {item_id}")
        
        media_type = kwargs.get("media_type", "series")
        
        if media_type == "movie":
            return await self.get_movie(int(item_id))
        else:
            return await self.get_series(int(item_id))
    
    async def get_series(self, series_id: int) -> Optional[Dict[str, Any]]:
        """Get series details."""
        data = await self._request(f"/series/{series_id}/extended")
        if not data:
            return None
        
        return self._parse_series_detail(data.get("data", {}))
    
    async def get_movie(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get movie details."""
        data = await self._request(f"/movies/{movie_id}/extended")
        if not data:
            return None
        
        return self._parse_movie_detail(data.get("data", {}))
    
    async def get_episodes(self, series_id: int, season: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get episodes for a series."""
        logger.debug(f"TVDB get episodes: {series_id} S{season}")
        
        data = await self._request(f"/series/{series_id}/episodes/default")
        if not data:
            return []
        
        episodes = []
        for ep in data.get("data", {}).get("episodes", []):
            if season is None or ep.get("seasonNumber") == season:
                try:
                    episodes.append(self._parse_episode(ep, series_id))
                except Exception as e:
                    logger.debug(f"Error parsing episode: {e}")
        
        # Sort by season and episode number
        episodes.sort(key=lambda x: (x.get("season_number", 0), x.get("episode_number", 0)))
        return episodes
    
    async def get_season(self, series_id: int, season_number: int) -> Optional[Dict[str, Any]]:
        """Get season details with episodes."""
        # Get series info
        series_data = await self._request(f"/series/{series_id}")
        series_title = ""
        if series_data and series_data.get("data"):
            series_title = series_data["data"].get("name", "")
        
        # Get episodes for this season
        episodes = await self.get_episodes(series_id, season_number)
        
        return {
            "series_id": series_id,
            "series_title": series_title,
            "season_number": season_number,
            "episodes": episodes,
        }
    
    async def get_episode(self, series_id: int, season: int, episode: int) -> Optional[Dict[str, Any]]:
        """Get specific episode details."""
        episodes = await self.get_episodes(series_id, season)
        
        for ep in episodes:
            if ep.get("episode_number") == episode:
                return ep
        
        return None
    
    def _parse_search_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse search result."""
        # Determine media type
        obj_type = data.get("type", "series")
        media_type = "movie" if obj_type == "movie" else "tv"
        
        return {
            "id": data.get("tvdb_id") or data.get("id"),
            "media_type": media_type,
            "title": data.get("name", "") or data.get("title", ""),
            "overview": data.get("overview"),
            "year": data.get("year"),
            "first_air_date": data.get("first_air_time"),
            "poster_path": data.get("image_url") or data.get("thumbnail"),
            "status": data.get("status"),
            "country": data.get("country"),
            "network": data.get("network"),
        }
    
    def _parse_series_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse series detail response."""
        # Get artwork
        poster_url = None
        backdrop_url = None
        for art in data.get("artworks", []):
            art_type = art.get("type")
            if art_type == 2 and not poster_url:  # Poster
                poster_url = art.get("image")
            elif art_type == 3 and not backdrop_url:  # Fanart
                backdrop_url = art.get("image")
        
        # Fallback to main image
        if not poster_url:
            poster_url = data.get("image")
        
        # Get networks
        networks = []
        for network in data.get("networks", []) or []:
            if isinstance(network, dict):
                networks.append(network.get("name", ""))
            elif isinstance(network, str):
                networks.append(network)
        
        # Get genres
        genres = [g.get("name", "") for g in data.get("genres", [])]
        
        return {
            "id": data.get("id"),
            "media_type": "tv",
            "title": data.get("name", ""),
            "original_title": data.get("originalName"),
            "overview": data.get("overview"),
            "first_air_date": data.get("firstAired"),
            "year": self._extract_year(data.get("firstAired")),
            "status": self._get_status_name(data.get("status")),
            "runtime": data.get("averageRuntime"),
            "imdb_id": data.get("imdb_id"),
            "score": data.get("score"),
            "poster_path": poster_url,
            "backdrop_path": backdrop_url,
            "genres": genres,
            "networks": networks,
            "original_country": data.get("originalCountry"),
            "original_language": data.get("originalLanguage"),
            "cast": self._parse_characters(data.get("characters", [])),
        }
    
    def _parse_movie_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse movie detail response."""
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
        
        return {
            "id": data.get("id"),
            "media_type": "movie",
            "title": data.get("name", ""),
            "overview": data.get("overview"),
            "year": data.get("year"),
            "runtime": data.get("runtime"),
            "imdb_id": data.get("imdb_id"),
            "status": self._get_status_name(data.get("status")),
            "poster_path": poster_url,
            "backdrop_path": backdrop_url,
            "genres": genres,
            "studios": [s.get("name", "") for s in data.get("studios", [])],
            "cast": self._parse_characters(data.get("characters", [])),
        }
    
    def _parse_episode(self, data: Dict[str, Any], series_id: int) -> Dict[str, Any]:
        """Parse episode data."""
        return {
            "id": data.get("id"),
            "series_id": series_id,
            "season_number": data.get("seasonNumber"),
            "episode_number": data.get("number"),
            "title": data.get("name", f"Episode {data.get('number')}"),
            "overview": data.get("overview"),
            "air_date": data.get("aired"),
            "year": self._extract_year(data.get("aired")),
            "runtime": data.get("runtime"),
            "image": data.get("image"),
        }
    
    def _parse_characters(self, characters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse character/cast list."""
        cast = []
        for char in characters[:20]:
            person = char.get("personName") or (
                char.get("people", {}).get("name") if char.get("people") else None
            )
            if person:
                cast.append({
                    "name": person,
                    "character": char.get("name", ""),
                    "image": char.get("image"),
                })
        return cast
    
    def _get_status_name(self, status: Any) -> Optional[str]:
        """Extract status name from status object or string."""
        if status is None:
            return None
        if isinstance(status, dict):
            return status.get("name")
        return str(status)
    
    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string."""
        if not date_str:
            return None
        if isinstance(date_str, int):
            return date_str
        try:
            return int(date_str.split("-")[0])
        except (ValueError, IndexError):
            return None
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


__all__ = ["TVDBClient"]
