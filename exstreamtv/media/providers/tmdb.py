"""
TMDB (The Movie Database) metadata provider.

Fetches movie and TV metadata from TMDB API v3.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import aiohttp

from exstreamtv.media.providers.base import MediaMetadata, MetadataProvider, PersonInfo

logger = logging.getLogger(__name__)


class TMDBProvider(MetadataProvider):
    """
    The Movie Database (TMDB) metadata provider.

    Requires a TMDB API key (v3).
    Get one at: https://www.themoviedb.org/settings/api
    """

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

    def __init__(
        self,
        api_key: str,
        language: str = "en-US",
        include_adult: bool = False,
    ):
        """
        Initialize TMDB provider.

        Args:
            api_key: TMDB API key (v3).
            language: Language for metadata (e.g., "en-US").
            include_adult: Include adult content in searches.
        """
        super().__init__(api_key, language)
        self.include_adult = include_adult
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "TMDB"

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

    async def search_movie(
        self, query: str, year: Optional[int] = None
    ) -> List[MediaMetadata]:
        """Search for movies on TMDB."""
        params: Dict[str, Any] = {
            "query": query,
            "include_adult": str(self.include_adult).lower(),
        }
        if year:
            params["year"] = year

        data = await self._request("/search/movie", params)
        if not data:
            return []

        results = []
        for item in data.get("results", [])[:10]:
            try:
                metadata = self._parse_movie_result(item)
                results.append(metadata)
            except Exception as e:
                logger.debug(f"Error parsing movie result: {e}")

        return results

    async def search_tv(
        self, query: str, year: Optional[int] = None
    ) -> List[MediaMetadata]:
        """Search for TV shows on TMDB."""
        params: Dict[str, Any] = {
            "query": query,
            "include_adult": str(self.include_adult).lower(),
        }
        if year:
            params["first_air_date_year"] = year

        data = await self._request("/search/tv", params)
        if not data:
            return []

        results = []
        for item in data.get("results", [])[:10]:
            try:
                metadata = self._parse_tv_result(item)
                results.append(metadata)
            except Exception as e:
                logger.debug(f"Error parsing TV result: {e}")

        return results

    async def get_movie(self, movie_id: str) -> Optional[MediaMetadata]:
        """Get detailed movie information."""
        data = await self._request(
            f"/movie/{movie_id}",
            {"append_to_response": "credits,external_ids"},
        )
        if not data:
            return None

        return self._parse_movie_detail(data)

    async def get_tv_show(self, show_id: str) -> Optional[MediaMetadata]:
        """Get detailed TV show information."""
        data = await self._request(
            f"/tv/{show_id}",
            {"append_to_response": "credits,external_ids"},
        )
        if not data:
            return None

        return self._parse_tv_detail(data)

    async def get_episode(
        self, show_id: str, season: int, episode: int
    ) -> Optional[MediaMetadata]:
        """Get episode details."""
        # First get show info for context
        show_data = await self._request(f"/tv/{show_id}")
        show_title = show_data.get("name", "") if show_data else ""

        # Get episode data
        data = await self._request(
            f"/tv/{show_id}/season/{season}/episode/{episode}",
            {"append_to_response": "credits"},
        )
        if not data:
            return None

        return self._parse_episode_detail(data, show_id, show_title)

    async def get_season(
        self, show_id: str, season: int
    ) -> List[MediaMetadata]:
        """Get all episodes in a season."""
        data = await self._request(f"/tv/{show_id}/season/{season}")
        if not data:
            return []

        # Get show title
        show_data = await self._request(f"/tv/{show_id}")
        show_title = show_data.get("name", "") if show_data else ""

        episodes = []
        for ep in data.get("episodes", []):
            try:
                metadata = MediaMetadata(
                    title=ep.get("name", f"Episode {ep.get('episode_number')}"),
                    media_type="episode",
                    tmdb_id=str(ep.get("id", "")),
                    show_title=show_title,
                    season_number=season,
                    episode_number=ep.get("episode_number"),
                    overview=ep.get("overview"),
                    release_date=self._parse_date(ep.get("air_date")),
                    rating=ep.get("vote_average"),
                    vote_count=ep.get("vote_count"),
                    runtime_minutes=ep.get("runtime"),
                    thumb_url=self._get_image_url(ep.get("still_path"), "w500"),
                )
                episodes.append(metadata)
            except Exception as e:
                logger.debug(f"Error parsing episode: {e}")

        return episodes

    def _parse_movie_result(self, data: Dict[str, Any]) -> MediaMetadata:
        """Parse search result into MediaMetadata."""
        release_date = self._parse_date(data.get("release_date"))

        return MediaMetadata(
            title=data.get("title", ""),
            original_title=data.get("original_title"),
            media_type="movie",
            tmdb_id=str(data.get("id", "")),
            overview=data.get("overview"),
            release_date=release_date,
            year=release_date.year if release_date else None,
            rating=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            popularity=data.get("popularity"),
            poster_url=self._get_image_url(data.get("poster_path"), "w500"),
            backdrop_url=self._get_image_url(data.get("backdrop_path"), "w1280"),
            genres=self._get_genre_names(data.get("genre_ids", [])),
            languages=[data.get("original_language", "")]
            if data.get("original_language")
            else [],
        )

    def _parse_tv_result(self, data: Dict[str, Any]) -> MediaMetadata:
        """Parse TV search result into MediaMetadata."""
        first_air_date = self._parse_date(data.get("first_air_date"))

        return MediaMetadata(
            title=data.get("name", ""),
            original_title=data.get("original_name"),
            media_type="show",
            tmdb_id=str(data.get("id", "")),
            overview=data.get("overview"),
            release_date=first_air_date,
            year=first_air_date.year if first_air_date else None,
            rating=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            popularity=data.get("popularity"),
            poster_url=self._get_image_url(data.get("poster_path"), "w500"),
            backdrop_url=self._get_image_url(data.get("backdrop_path"), "w1280"),
            genres=self._get_genre_names(data.get("genre_ids", [])),
            countries=data.get("origin_country", []),
        )

    def _parse_movie_detail(self, data: Dict[str, Any]) -> MediaMetadata:
        """Parse detailed movie data."""
        release_date = self._parse_date(data.get("release_date"))
        external_ids = data.get("external_ids", {})
        credits = data.get("credits", {})

        return MediaMetadata(
            title=data.get("title", ""),
            original_title=data.get("original_title"),
            media_type="movie",
            tmdb_id=str(data.get("id", "")),
            imdb_id=external_ids.get("imdb_id"),
            overview=data.get("overview"),
            tagline=data.get("tagline"),
            release_date=release_date,
            year=release_date.year if release_date else None,
            rating=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            runtime_minutes=data.get("runtime"),
            popularity=data.get("popularity"),
            budget=data.get("budget"),
            revenue=data.get("revenue"),
            status=data.get("status"),
            homepage=data.get("homepage"),
            poster_url=self._get_image_url(data.get("poster_path"), "w500"),
            backdrop_url=self._get_image_url(data.get("backdrop_path"), "w1280"),
            genres=[g.get("name", "") for g in data.get("genres", [])],
            studios=[c.get("name", "") for c in data.get("production_companies", [])],
            countries=[c.get("iso_3166_1", "") for c in data.get("production_countries", [])],
            languages=[l.get("iso_639_1", "") for l in data.get("spoken_languages", [])],
            cast=self._parse_cast(credits.get("cast", [])),
            crew=self._parse_crew(credits.get("crew", [])),
        )

    def _parse_tv_detail(self, data: Dict[str, Any]) -> MediaMetadata:
        """Parse detailed TV show data."""
        first_air_date = self._parse_date(data.get("first_air_date"))
        external_ids = data.get("external_ids", {})
        credits = data.get("credits", {})

        # Calculate average episode runtime
        runtimes = data.get("episode_run_time", [])
        avg_runtime = sum(runtimes) // len(runtimes) if runtimes else None

        return MediaMetadata(
            title=data.get("name", ""),
            original_title=data.get("original_name"),
            media_type="show",
            tmdb_id=str(data.get("id", "")),
            tvdb_id=str(external_ids.get("tvdb_id", "")) if external_ids.get("tvdb_id") else None,
            imdb_id=external_ids.get("imdb_id"),
            overview=data.get("overview"),
            tagline=data.get("tagline"),
            release_date=first_air_date,
            year=first_air_date.year if first_air_date else None,
            rating=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            runtime_minutes=avg_runtime,
            popularity=data.get("popularity"),
            status=data.get("status"),
            homepage=data.get("homepage"),
            poster_url=self._get_image_url(data.get("poster_path"), "w500"),
            backdrop_url=self._get_image_url(data.get("backdrop_path"), "w1280"),
            genres=[g.get("name", "") for g in data.get("genres", [])],
            studios=[c.get("name", "") for c in data.get("production_companies", [])],
            networks=[n.get("name", "") for n in data.get("networks", [])],
            countries=data.get("origin_country", []),
            languages=[l.get("iso_639_1", "") for l in data.get("spoken_languages", [])],
            cast=self._parse_cast(credits.get("cast", [])),
            crew=self._parse_crew(credits.get("crew", [])),
        )

    def _parse_episode_detail(
        self, data: Dict[str, Any], show_id: str, show_title: str
    ) -> MediaMetadata:
        """Parse detailed episode data."""
        air_date = self._parse_date(data.get("air_date"))
        credits = data.get("credits", {})

        return MediaMetadata(
            title=data.get("name", ""),
            media_type="episode",
            tmdb_id=str(data.get("id", "")),
            show_title=show_title,
            season_number=data.get("season_number"),
            episode_number=data.get("episode_number"),
            overview=data.get("overview"),
            release_date=air_date,
            year=air_date.year if air_date else None,
            rating=data.get("vote_average"),
            vote_count=data.get("vote_count"),
            runtime_minutes=data.get("runtime"),
            thumb_url=self._get_image_url(data.get("still_path"), "w500"),
            cast=self._parse_cast(credits.get("cast", [])),
            crew=self._parse_crew(credits.get("crew", [])),
        )

    def _parse_cast(self, cast: List[Dict[str, Any]]) -> List[PersonInfo]:
        """Parse cast list."""
        return [
            PersonInfo(
                name=p.get("name", ""),
                role=p.get("character", ""),
                image_url=self._get_image_url(p.get("profile_path"), "w185"),
                tmdb_id=str(p.get("id", "")),
            )
            for p in cast[:20]  # Limit to 20
        ]

    def _parse_crew(self, crew: List[Dict[str, Any]]) -> List[PersonInfo]:
        """Parse crew list."""
        # Focus on key crew members
        key_jobs = {"Director", "Writer", "Screenplay", "Producer", "Executive Producer"}
        filtered = [c for c in crew if c.get("job") in key_jobs]

        return [
            PersonInfo(
                name=p.get("name", ""),
                job=p.get("job", ""),
                image_url=self._get_image_url(p.get("profile_path"), "w185"),
                tmdb_id=str(p.get("id", "")),
            )
            for p in filtered[:10]
        ]

    def _get_image_url(self, path: Optional[str], size: str) -> Optional[str]:
        """Build full image URL."""
        if not path:
            return None
        return f"{self.IMAGE_BASE_URL}/{size}{path}"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            parts = date_str.split("-")
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except (ValueError, IndexError):
            return None

    # Genre ID to name mapping (TMDB)
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

    def _get_genre_names(self, genre_ids: List[int]) -> List[str]:
        """Convert genre IDs to names."""
        return [
            self.GENRE_MAP.get(gid, f"Unknown-{gid}")
            for gid in genre_ids
            if gid in self.GENRE_MAP
        ]

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
