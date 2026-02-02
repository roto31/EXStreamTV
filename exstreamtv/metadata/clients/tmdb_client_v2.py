"""
TMDB Client v2

Provides TMDB (The Movie Database) API client with full implementation.
"""

from typing import Any, Dict, List, Optional
import logging

import aiohttp

from exstreamtv.metadata.clients.base import MetadataClient

logger = logging.getLogger(__name__)


class TMDBClient(MetadataClient):
    """TMDB metadata client with full API implementation."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
    
    # Genre ID to name mapping
    GENRE_MAP = {
        28: "Action",
        12: "Adventure",
        16: "Animation",
        35: "Comedy",
        80: "Crime",
        99: "Documentary",
        18: "Drama",
        10751: "Family",
        14: "Fantasy",
        36: "History",
        27: "Horror",
        10402: "Music",
        9648: "Mystery",
        10749: "Romance",
        878: "Science Fiction",
        10770: "TV Movie",
        53: "Thriller",
        10752: "War",
        37: "Western",
        # TV genres
        10759: "Action & Adventure",
        10762: "Kids",
        10763: "News",
        10764: "Reality",
        10765: "Sci-Fi & Fantasy",
        10766: "Soap",
        10767: "Talk",
        10768: "War & Politics",
    }
    
    def __init__(self, api_key: Optional[str] = None, language: str = "en-US"):
        super().__init__(api_key)
        self._session: Optional[aiohttp.ClientSession] = None
        self.language = language
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session
    
    async def _request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make API request to TMDB."""
        if not self.api_key:
            logger.warning("TMDB API key not configured")
            return None
            
        session = await self._ensure_session()
        
        url = f"{self.BASE_URL}{endpoint}"
        request_params = {
            "api_key": self.api_key,
            "language": self.language,
        }
        if params:
            request_params.update(params)
        
        try:
            async with session.get(url, params=request_params) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    logger.error("TMDB API key invalid")
                elif response.status == 404:
                    logger.debug(f"TMDB resource not found: {endpoint}")
                else:
                    logger.warning(f"TMDB API error: HTTP {response.status}")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"TMDB request failed: {e}")
            return None
    
    async def search(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        """Search TMDB for movies or TV shows using multi-search."""
        logger.debug(f"TMDB search: {query}")
        
        media_type = kwargs.get("media_type")
        year = kwargs.get("year")
        
        # Use specific endpoint if media type is provided
        if media_type == "movie":
            return await self._search_movies(query, year)
        elif media_type == "tv":
            return await self._search_tv(query, year)
        
        # Default to multi-search
        params: Dict[str, Any] = {"query": query}
        if year:
            params["year"] = year
        
        data = await self._request("/search/multi", params)
        if not data:
            return []
        
        results = []
        for item in data.get("results", [])[:10]:
            try:
                result = self._parse_search_result(item)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"Error parsing search result: {e}")
        
        return results
    
    async def _search_movies(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for movies."""
        params: Dict[str, Any] = {"query": query}
        if year:
            params["year"] = year
        
        data = await self._request("/search/movie", params)
        if not data:
            return []
        
        results = []
        for item in data.get("results", [])[:10]:
            try:
                result = self._parse_movie_result(item)
                results.append(result)
            except Exception as e:
                logger.debug(f"Error parsing movie result: {e}")
        
        return results
    
    async def _search_tv(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for TV shows."""
        params: Dict[str, Any] = {"query": query}
        if year:
            params["first_air_date_year"] = year
        
        data = await self._request("/search/tv", params)
        if not data:
            return []
        
        results = []
        for item in data.get("results", [])[:10]:
            try:
                result = self._parse_tv_result(item)
                results.append(result)
            except Exception as e:
                logger.debug(f"Error parsing TV result: {e}")
        
        return results
    
    async def search_movies(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for movies (public API)."""
        return await self._search_movies(query, year)
    
    async def search_tv(self, query: str, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search for TV shows (public API)."""
        return await self._search_tv(query, year)
    
    async def get_details(self, item_id: str, media_type: str = "movie", **kwargs) -> Optional[Dict[str, Any]]:
        """Get TMDB details for a movie or TV show."""
        logger.debug(f"TMDB get details: {item_id} ({media_type})")
        
        if media_type == "movie":
            return await self.get_movie(int(item_id))
        elif media_type in ("tv", "show"):
            return await self.get_tv(int(item_id))
        
        return None
    
    async def get_movie(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """Get movie details."""
        data = await self._request(
            f"/movie/{movie_id}",
            {"append_to_response": "credits,external_ids"}
        )
        if not data:
            return None
        
        return self._parse_movie_detail(data)
    
    async def get_tv(self, tv_id: int) -> Optional[Dict[str, Any]]:
        """Get TV show details."""
        data = await self._request(
            f"/tv/{tv_id}",
            {"append_to_response": "credits,external_ids"}
        )
        if not data:
            return None
        
        return self._parse_tv_detail(data)
    
    async def get_season(self, tv_id: int, season_number: int) -> Optional[Dict[str, Any]]:
        """Get TV season details."""
        logger.debug(f"TMDB get season: {tv_id} S{season_number}")
        
        data = await self._request(f"/tv/{tv_id}/season/{season_number}")
        if not data:
            return None
        
        # Get show info for context
        show_data = await self._request(f"/tv/{tv_id}")
        show_title = show_data.get("name", "") if show_data else ""
        
        return {
            "id": data.get("id"),
            "season_number": data.get("season_number"),
            "name": data.get("name"),
            "overview": data.get("overview"),
            "air_date": data.get("air_date"),
            "poster_path": self.get_image_url(data.get("poster_path"), "w500"),
            "show_title": show_title,
            "episodes": [
                {
                    "id": ep.get("id"),
                    "episode_number": ep.get("episode_number"),
                    "name": ep.get("name"),
                    "overview": ep.get("overview"),
                    "air_date": ep.get("air_date"),
                    "runtime": ep.get("runtime"),
                    "still_path": self.get_image_url(ep.get("still_path"), "w500"),
                }
                for ep in data.get("episodes", [])
            ]
        }
    
    async def get_episode(self, tv_id: int, season_number: int, episode_number: int) -> Optional[Dict[str, Any]]:
        """Get TV episode details."""
        logger.debug(f"TMDB get episode: {tv_id} S{season_number}E{episode_number}")
        
        data = await self._request(
            f"/tv/{tv_id}/season/{season_number}/episode/{episode_number}",
            {"append_to_response": "credits"}
        )
        if not data:
            return None
        
        # Get show info for context
        show_data = await self._request(f"/tv/{tv_id}")
        show_title = show_data.get("name", "") if show_data else ""
        
        return {
            "id": data.get("id"),
            "name": data.get("name"),
            "overview": data.get("overview"),
            "air_date": data.get("air_date"),
            "runtime": data.get("runtime"),
            "season_number": data.get("season_number"),
            "episode_number": data.get("episode_number"),
            "still_path": self.get_image_url(data.get("still_path"), "w500"),
            "show_id": tv_id,
            "show_title": show_title,
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
        }
    
    async def get_images(self, item_id: str, media_type: str = "movie", **kwargs) -> List[str]:
        """Get images for an item."""
        endpoint = f"/{media_type}/{item_id}/images"
        data = await self._request(endpoint)
        if not data:
            return []
        
        images = []
        for img in data.get("posters", [])[:5]:
            url = self.get_image_url(img.get("file_path"), "original")
            if url:
                images.append(url)
        
        for img in data.get("backdrops", [])[:5]:
            url = self.get_image_url(img.get("file_path"), "original")
            if url:
                images.append(url)
        
        return images
    
    def get_image_url(self, path: Optional[str], size: str = "original") -> Optional[str]:
        """Get full image URL from path."""
        if not path:
            return None
        return f"{self.IMAGE_BASE_URL}/{size}{path}"
    
    def _parse_search_result(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse multi-search result."""
        media_type = data.get("media_type")
        
        if media_type == "movie":
            return self._parse_movie_result(data)
        elif media_type == "tv":
            return self._parse_tv_result(data)
        
        return None
    
    def _parse_movie_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse movie search result."""
        return {
            "id": data.get("id"),
            "media_type": "movie",
            "title": data.get("title", ""),
            "original_title": data.get("original_title"),
            "overview": data.get("overview"),
            "release_date": data.get("release_date"),
            "year": self._extract_year(data.get("release_date")),
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "popularity": data.get("popularity"),
            "poster_path": self.get_image_url(data.get("poster_path"), "w500"),
            "backdrop_path": self.get_image_url(data.get("backdrop_path"), "w1280"),
            "genres": self._get_genre_names(data.get("genre_ids", [])),
            "original_language": data.get("original_language"),
        }
    
    def _parse_tv_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse TV search result."""
        return {
            "id": data.get("id"),
            "media_type": "tv",
            "title": data.get("name", ""),
            "original_title": data.get("original_name"),
            "overview": data.get("overview"),
            "first_air_date": data.get("first_air_date"),
            "year": self._extract_year(data.get("first_air_date")),
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "popularity": data.get("popularity"),
            "poster_path": self.get_image_url(data.get("poster_path"), "w500"),
            "backdrop_path": self.get_image_url(data.get("backdrop_path"), "w1280"),
            "genres": self._get_genre_names(data.get("genre_ids", [])),
            "origin_country": data.get("origin_country", []),
        }
    
    def _parse_movie_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse movie detail response."""
        external_ids = data.get("external_ids", {})
        credits = data.get("credits", {})
        
        return {
            "id": data.get("id"),
            "media_type": "movie",
            "title": data.get("title", ""),
            "original_title": data.get("original_title"),
            "overview": data.get("overview"),
            "tagline": data.get("tagline"),
            "release_date": data.get("release_date"),
            "year": self._extract_year(data.get("release_date")),
            "runtime": data.get("runtime"),
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "popularity": data.get("popularity"),
            "status": data.get("status"),
            "budget": data.get("budget"),
            "revenue": data.get("revenue"),
            "homepage": data.get("homepage"),
            "imdb_id": external_ids.get("imdb_id"),
            "poster_path": self.get_image_url(data.get("poster_path"), "w500"),
            "backdrop_path": self.get_image_url(data.get("backdrop_path"), "w1280"),
            "genres": [g.get("name", "") for g in data.get("genres", [])],
            "production_companies": [c.get("name", "") for c in data.get("production_companies", [])],
            "production_countries": [c.get("iso_3166_1", "") for c in data.get("production_countries", [])],
            "spoken_languages": [l.get("iso_639_1", "") for l in data.get("spoken_languages", [])],
            "cast": self._parse_cast(credits.get("cast", [])),
            "crew": self._parse_crew(credits.get("crew", [])),
        }
    
    def _parse_tv_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse TV detail response."""
        external_ids = data.get("external_ids", {})
        credits = data.get("credits", {})
        
        # Calculate average episode runtime
        runtimes = data.get("episode_run_time", [])
        avg_runtime = sum(runtimes) // len(runtimes) if runtimes else None
        
        return {
            "id": data.get("id"),
            "media_type": "tv",
            "title": data.get("name", ""),
            "original_title": data.get("original_name"),
            "overview": data.get("overview"),
            "tagline": data.get("tagline"),
            "first_air_date": data.get("first_air_date"),
            "last_air_date": data.get("last_air_date"),
            "year": self._extract_year(data.get("first_air_date")),
            "runtime": avg_runtime,
            "number_of_seasons": data.get("number_of_seasons"),
            "number_of_episodes": data.get("number_of_episodes"),
            "vote_average": data.get("vote_average"),
            "vote_count": data.get("vote_count"),
            "popularity": data.get("popularity"),
            "status": data.get("status"),
            "type": data.get("type"),
            "homepage": data.get("homepage"),
            "imdb_id": external_ids.get("imdb_id"),
            "tvdb_id": external_ids.get("tvdb_id"),
            "poster_path": self.get_image_url(data.get("poster_path"), "w500"),
            "backdrop_path": self.get_image_url(data.get("backdrop_path"), "w1280"),
            "genres": [g.get("name", "") for g in data.get("genres", [])],
            "networks": [n.get("name", "") for n in data.get("networks", [])],
            "production_companies": [c.get("name", "") for c in data.get("production_companies", [])],
            "origin_country": data.get("origin_country", []),
            "spoken_languages": [l.get("iso_639_1", "") for l in data.get("spoken_languages", [])],
            "cast": self._parse_cast(credits.get("cast", [])),
            "crew": self._parse_crew(credits.get("crew", [])),
        }
    
    def _parse_cast(self, cast: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse cast list."""
        return [
            {
                "id": p.get("id"),
                "name": p.get("name", ""),
                "character": p.get("character", ""),
                "profile_path": self.get_image_url(p.get("profile_path"), "w185"),
            }
            for p in cast[:20]
        ]
    
    def _parse_crew(self, crew: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse crew list (key members only)."""
        key_jobs = {"Director", "Writer", "Screenplay", "Producer", "Executive Producer"}
        filtered = [c for c in crew if c.get("job") in key_jobs]
        
        return [
            {
                "id": p.get("id"),
                "name": p.get("name", ""),
                "job": p.get("job", ""),
                "profile_path": self.get_image_url(p.get("profile_path"), "w185"),
            }
            for p in filtered[:10]
        ]
    
    def _get_genre_names(self, genre_ids: List[int]) -> List[str]:
        """Convert genre IDs to names."""
        return [
            self.GENRE_MAP.get(gid, f"Unknown-{gid}")
            for gid in genre_ids
            if gid in self.GENRE_MAP
        ]
    
    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string."""
        if not date_str:
            return None
        try:
            return int(date_str.split("-")[0])
        except (ValueError, IndexError):
            return None
    
    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# Alias for v2 naming
TMDBClientV2 = TMDBClient

__all__ = ["TMDBClient", "TMDBClientV2"]
