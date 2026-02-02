"""
Metadata providers for TV shows and movies
Integrates with TVDB, TVMaze, and TMDB APIs
"""

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TVDBClient:
    """The TVDB (TheTVDB.com) API v4 client for TV show metadata"""
    
    def __init__(self, api_key: str, read_token: str | None = None):
        self.api_key = api_key
        self.read_token = read_token  # Bearer token for API v4
        self.base_url = "https://api4.thetvdb.com/v4"
        self._auth_token = None
        self._token_expires = None
        
    async def _ensure_authenticated(self) -> str:
        """Ensure we have a valid auth token"""
        if self._auth_token and self._token_expires:
            if datetime.utcnow() < self._token_expires:
                return self._auth_token
        
        # Use read token if provided (TVDB v4 uses bearer tokens)
        if self.read_token:
            self._auth_token = self.read_token
            # Read tokens don't expire
            return self._auth_token
        
        # Otherwise, authenticate with API key (legacy method)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/login", json={"apikey": self.api_key}
                )
                response.raise_for_status()
                data = response.json()
                self._auth_token = data.get("data", {}).get("token")
                return self._auth_token
        except Exception as e:
            logger.exception(f"TVDB authentication failed: {e}")
            raise
    
    async def search_series(self, name: str) -> dict[str, Any] | None:
        """Search for a TV series by name"""
        try:
            token = await self._ensure_authenticated()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # TVDB v4 uses query parameter 'q' not 'query'
                response = await client.get(
                    f"{self.base_url}/search", headers=headers, params={"q": name}
                )
                response.raise_for_status()
                data = response.json()
                
                results = data.get("data", [])
                if results:
                    # Filter for series type
                    for result in results:
                        if result.get("type") == "series" or result.get("objectID"):
                            return result
                    # Return first if no type filter matches
                    return results[0]
                return None
        except Exception as e:
            logger.exception(f"TVDB search failed for '{name}': {e}")
            return None
    
    async def get_series_details(self, series_id: int) -> dict[str, Any] | None:
        """Get detailed information about a series"""
        try:
            token = await self._ensure_authenticated()
            headers = {"Authorization": f"Bearer {token}"}
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/series/{series_id}/extended", headers=headers
                )
                response.raise_for_status()
                return response.json().get("data")
        except Exception as e:
            logger.exception(f"TVDB series details failed for ID {series_id}: {e}")
            return None
    
    async def get_episode(self, series_id: int, season: int, episode: int) -> dict[str, Any] | None:
        """Get episode metadata by season and episode number"""
        try:
            token = await self._ensure_authenticated()
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get all episodes for the series
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/series/{series_id}/episodes/default",
                    headers=headers,
                    params={"page": 0},
                )
                response.raise_for_status()
                data = response.json()
                
                episodes = data.get("data", {}).get("episodes", [])
                
                # Find matching episode
                for ep in episodes:
                    if ep.get("seasonNumber") == season and ep.get("number") == episode:
                        return ep
                
                # Check additional pages if needed
                pages = data.get("data", {}).get("totalPages", 1)
                for page in range(1, min(pages, 10)):  # Limit to 10 pages
                    response = await client.get(
                        f"{self.base_url}/series/{series_id}/episodes/default",
                        headers=headers,
                        params={"page": page},
                    )
                    response.raise_for_status()
                    data = response.json()
                    episodes = data.get("data", {}).get("episodes", [])
                    
                    for ep in episodes:
                        if ep.get("seasonNumber") == season and ep.get("number") == episode:
                            return ep
                
                logger.warning(f"TVDB episode not found: S{season:02d}E{episode:02d}")
                return None
                
        except Exception as e:
            logger.exception(f"TVDB episode fetch failed: {e}")
            return None


class TVMazeClient:
    """TVMaze API client for TV show metadata (free, no API key required)"""
    
    def __init__(self):
        self.base_url = "https://api.tvmaze.com"
    
    async def search_show(self, name: str, year: int | None = None) -> dict[str, Any] | None:
        """Search for a TV show by name, optionally filtered by year"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use full search to get multiple results if year specified
                if year:
                    response = await client.get(f"{self.base_url}/search/shows", params={"q": name})
                    response.raise_for_status()
                    results = response.json()
                    
                    # Filter results by year (premiered date)
                    for result in results:
                        show = result.get("show", {})
                        premiered = show.get("premiered", "")
                        if premiered:
                            show_year = int(premiered[:4])
                            # Match year with tolerance of +/- 1 year
                            if abs(show_year - year) <= 1:
                                logger.info(
                                    f"Found {show.get('name')} ({show_year}) matching year {year}"
                                )
                                return show
                    
                    # If no year match, return first result with warning
                    if results:
                        show = results[0].get("show", {})
                        logger.warning(
                            f"No exact year match for {year}, using: {show.get('name')} ({show.get('premiered', 'unknown')})"
                        )
                        return show
                    return None
                else:
                    # Single search when no year specified
                    response = await client.get(
                        f"{self.base_url}/singlesearch/shows", params={"q": name}
                    )
                    response.raise_for_status()
                    return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"TVMaze: Show not found: '{name}'")
            else:
                logger.exception(f"TVMaze search failed for '{name}': {e}")
            return None
        except Exception as e:
            logger.exception(f"TVMaze search error: {e}")
            return None
    
    async def get_episode(self, show_id: int, season: int, episode: int) -> dict[str, Any] | None:
        """Get episode metadata by season and episode number"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/shows/{show_id}/episodebynumber",
                    params={"season": season, "number": episode},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"TVMaze: Episode not found: S{season:02d}E{episode:02d}")
            else:
                logger.exception(f"TVMaze episode fetch failed: {e}")
            return None
        except Exception as e:
            logger.exception(f"TVMaze episode error: {e}")
            return None
    
    async def lookup_by_tvdb_id(self, tvdb_id: int) -> dict[str, Any] | None:
        """Lookup show by TVDB ID"""
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    f"{self.base_url}/lookup/shows", params={"thetvdb": tvdb_id}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.debug(f"TVMaze lookup by TVDB ID failed: {e}")
            return None


class TMDBClient:
    """The Movie Database (TMDB) API client for movie metadata"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.themoviedb.org/3"
    
    async def search_movie(self, title: str, year: int | None = None) -> dict[str, Any] | None:
        """Search for a movie by title"""
        try:
            params = {"api_key": self.api_key, "query": title}
            if year:
                params["year"] = year
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/search/movie", params=params)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                if results:
                    return results[0]  # Return first match
                return None
        except Exception as e:
            logger.exception(f"TMDB movie search failed for '{title}': {e}")
            return None
    
    async def get_movie_details(self, movie_id: int) -> dict[str, Any] | None:
        """Get detailed information about a movie"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/movie/{movie_id}",
                    params={
                        "api_key": self.api_key,
                        "append_to_response": "credits,keywords,images",
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.exception(f"TMDB movie details failed for ID {movie_id}: {e}")
            return None
    
    async def search_tv_show(self, name: str, year: int | None = None) -> dict[str, Any] | None:
        """Search for a TV show by name"""
        try:
            params = {"api_key": self.api_key, "query": name}
            if year:
                params["first_air_date_year"] = year
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/search/tv", params=params)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("results", [])
                if results:
                    return results[0]
                return None
        except Exception as e:
            logger.exception(f"TMDB TV search failed for '{name}': {e}")
            return None
    
    async def get_tv_episode(self, tv_id: int, season: int, episode: int) -> dict[str, Any] | None:
        """Get TV episode metadata"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/tv/{tv_id}/season/{season}/episode/{episode}",
                    params={"api_key": self.api_key},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.exception(f"TMDB TV episode fetch failed: {e}")
            return None


class MusicBrainzClient:
    """MusicBrainz API client for music metadata"""

    BASE_URL = "https://musicbrainz.org/ws/2"

    def __init__(self, user_agent: str = "EXStreamTV/1.0"):
        """
        Initialize MusicBrainz client

        Args:
            user_agent: User agent string (required by MusicBrainz)
        """
        self.user_agent = user_agent
        self._client = httpx.AsyncClient(timeout=30.0, headers={"User-Agent": user_agent})
        self._last_request_time = 0.0
        self._rate_limit_delay = 1.0  # 1 second between requests

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def _rate_limit(self):
        """Enforce rate limiting (1 request per second)"""
        import time

        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        self._last_request_time = time.time()

    async def search_recording(
        self, artist: str, title: str, year: int | None = None
    ) -> dict[str, Any] | None:
        """
        Search MusicBrainz for a recording

        Args:
            artist: Artist name
            title: Song title
            year: Optional release year for better matching

        Returns:
            Recording information dict or None
        """
        await self._rate_limit()

        try:
            # Build query
            query_parts = [f'artist:"{artist}"', f'recording:"{title}"']
            if year:
                query_parts.append(f"date:{year}")

            query = " AND ".join(query_parts)

            url = f"{self.BASE_URL}/recording"
            params = {"query": query, "limit": 1, "fmt": "json"}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            recordings = data.get("recordings", [])

            if recordings:
                return recordings[0]
            return None

        except Exception as e:
            logger.exception(f"MusicBrainz search failed for '{artist} - {title}': {e}")
            return None

    async def get_recording_details(self, recording_id: str) -> dict[str, Any] | None:
        """
        Get detailed recording information

        Args:
            recording_id: MusicBrainz recording MBID

        Returns:
            Detailed recording information dict
        """
        await self._rate_limit()

        try:
            url = f"{self.BASE_URL}/recording/{recording_id}"
            params = {"inc": "releases+tags+artist-credits", "fmt": "json"}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.exception(f"MusicBrainz recording details failed for {recording_id}: {e}")
            return None

    async def get_release_info(self, release_id: str) -> dict[str, Any] | None:
        """
        Get release (album) information

        Args:
            release_id: MusicBrainz release MBID

        Returns:
            Release information dict
        """
        await self._rate_limit()

        try:
            url = f"{self.BASE_URL}/release/{release_id}"
            params = {"inc": "recordings", "fmt": "json"}

            response = await self._client.get(url, params=params)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.exception(f"MusicBrainz release info failed for {release_id}: {e}")
            return None


class MetadataManager:
    """Unified metadata manager with fallback support"""
    
    def __init__(
        self,
        tvdb_client: TVDBClient | None = None,
        tvmaze_client: TVMazeClient | None = None,
        tmdb_client: TMDBClient | None = None,
        musicbrainz_client: MusicBrainzClient | None = None,
    ):
        self.tvdb = tvdb_client
        self.tvmaze = tvmaze_client
        self.tmdb = tmdb_client
        self.musicbrainz = musicbrainz_client
        self._series_cache = {}  # Cache series lookups
    
    async def get_tv_episode_metadata(
        self, series_name: str, season: int, episode: int, year: int | None = None
    ) -> dict[str, Any] | None:
        """
        Get TV episode metadata with fallback support
        
        Args:
            series_name: Name of the TV series
            season: Season number
            episode: Episode number
            year: Optional year for better matching
            
        Returns:
            Unified metadata dictionary or None
        """
        # Try TVDB first (primary source)
        if self.tvdb:
            try:
                metadata = await self._get_tvdb_episode(series_name, season, episode, year)
                if metadata:
                    logger.info(f"✅ TVDB metadata for {series_name} S{season:02d}E{episode:02d}")
                    return metadata
            except Exception as e:
                logger.warning(f"TVDB failed, trying fallback: {e}")
        
        # Fallback to TVMaze
        if self.tvmaze:
            try:
                metadata = await self._get_tvmaze_episode(series_name, season, episode, year)
                if metadata:
                    logger.info(f"✅ TVMaze metadata for {series_name} S{season:02d}E{episode:02d}")
                    return metadata
            except Exception as e:
                logger.warning(f"TVMaze also failed: {e}")
        
        logger.warning(f"❌ No metadata found for {series_name} S{season:02d}E{episode:02d}")
        return None
    
    async def _get_tvdb_episode(
        self, series_name: str, season: int, episode: int, year: int | None = None
    ) -> dict[str, Any] | None:
        """Get episode metadata from TVDB"""
        # Check cache with year to distinguish remakes/reboots
        cache_key = f"tvdb_{series_name}_{year}" if year else f"tvdb_{series_name}"
        if cache_key not in self._series_cache:
            # Search for series
            series_results = await self.tvdb.search_series(series_name)
            if not series_results:
                return None
            
            # Handle both single result and list of results
            if isinstance(series_results, list):
                # Filter by year if provided to distinguish remakes/reboots
                if year:
                    matching_series = [
                        s for s in series_results 
                        if (s.get('year') == year or 
                            s.get('firstAired', '')[:4] == str(year) or
                            s.get('first_air_date', '')[:4] == str(year))
                    ]
                    series = matching_series[0] if matching_series else series_results[0]
                else:
                    series = series_results[0]
            else:
                series = series_results
            
            self._series_cache[cache_key] = series
        else:
            series = self._series_cache[cache_key]
        
        series_id = series.get("tvdb_id") or series.get("id")
        if not series_id:
            return None
        
        # Get episode
        episode_data = await self.tvdb.get_episode(series_id, season, episode)
        if not episode_data:
            return None
        
        # Normalize to unified format
        return self._normalize_tvdb_episode(episode_data, series)
    
    async def _get_tvmaze_episode(
        self, series_name: str, season: int, episode: int, year: int | None = None
    ) -> dict[str, Any] | None:
        """Get episode metadata from TVMaze"""
        # Check cache with year to distinguish remakes/reboots
        cache_key = f"tvmaze_{series_name}_{year}" if year else f"tvmaze_{series_name}"
        if cache_key not in self._series_cache:
            # Search for show with year filtering
            show = await self.tvmaze.search_show(series_name, year=year)
            
            if not show:
                return None
            self._series_cache[cache_key] = show
        else:
            show = self._series_cache[cache_key]
        
        show_id = show.get("id")
        if not show_id:
            return None
        
        # Get episode
        episode_data = await self.tvmaze.get_episode(show_id, season, episode)
        if not episode_data:
            return None
        
        # Normalize to unified format
        return self._normalize_tvmaze_episode(episode_data, show)
    
    def _normalize_tvdb_episode(
        self, episode: dict[str, Any], series: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize TVDB episode data to unified format"""
        # Extract image URL
        image_url = None
        if episode.get("image"):
            image_url = episode["image"]
        elif episode.get("filename"):
            image_url = f"https://artworks.thetvdb.com/banners/{episode['filename']}"
        
        return {
            "source": "tvdb",
            "title": episode.get("name", ""),
            "description": episode.get("overview", ""),
            "season": episode.get("seasonNumber"),
            "episode": episode.get("number"),
            "air_date": episode.get("aired", ""),
            "runtime": episode.get("runtime") or series.get("averageRuntime", 48),
            "thumbnail": image_url,
            "rating": episode.get("siteRating"),
            "rating_count": episode.get("siteRatingCount"),
            "imdb_id": episode.get("imdbId"),
            "tvdb_id": episode.get("id"),
            "tvdb_series_id": series.get("tvdb_id") or series.get("id"),
            "series_name": series.get("name", ""),
            "network": series.get("network", {}).get("name")
            if isinstance(series.get("network"), dict)
            else None,
            "genres": series.get("genres", []),
        }
    
    def _normalize_tvmaze_episode(
        self, episode: dict[str, Any], show: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize TVMaze episode data to unified format"""
        # Clean HTML from summary
        summary = episode.get("summary", "")
        if summary:
            import re

            summary = re.sub(r"<[^>]+>", "", summary)  # Remove HTML tags
        
        # Extract image URL
        image_url = None
        if episode.get("image"):
            image_url = episode["image"].get("original") or episode["image"].get("medium")
        elif show.get("image"):
            # Fallback to show image
            image_url = show["image"].get("original") or show["image"].get("medium")
        
        return {
            "source": "tvmaze",
            "title": episode.get("name", ""),
            "description": summary,
            "season": episode.get("season"),
            "episode": episode.get("number"),
            "air_date": episode.get("airdate", ""),
            "runtime": episode.get("runtime") or show.get("averageRuntime", 48),
            "thumbnail": image_url,
            "rating": episode.get("rating", {}).get("average"),
            "tvmaze_id": episode.get("id"),
            "tvmaze_show_id": show.get("id"),
            "series_name": show.get("name", ""),
            "network": show.get("network", {}).get("name") if show.get("network") else None,
            "genres": show.get("genres", []),
        }
    
    async def get_movie_metadata(
        self, title: str, year: int | None = None
    ) -> dict[str, Any] | None:
        """Get movie metadata from TMDB"""
        if not self.tmdb:
            return None
        
        try:
            # Search for movie
            movie = await self.tmdb.search_movie(title, year)
            if not movie:
                return None
            
            movie_id = movie.get("id")
            if not movie_id:
                return None
            
            # Get detailed information
            details = await self.tmdb.get_movie_details(movie_id)
            if not details:
                return None
            
            return self._normalize_tmdb_movie(details)
        except Exception as e:
            logger.exception(f"TMDB movie metadata failed: {e}")
            return None
    
    def _normalize_tmdb_movie(self, movie: dict[str, Any]) -> dict[str, Any]:
        """Normalize TMDB movie data to unified format"""
        # Build poster URL
        poster_url = None
        if movie.get("poster_path"):
            poster_url = f"https://image.tmdb.org/t/p/original{movie['poster_path']}"
        
        backdrop_url = None
        if movie.get("backdrop_path"):
            backdrop_url = f"https://image.tmdb.org/t/p/original{movie['backdrop_path']}"
        
        return {
            "source": "tmdb",
            "title": movie.get("title", ""),
            "original_title": movie.get("original_title", ""),
            "description": movie.get("overview", ""),
            "release_date": movie.get("release_date", ""),
            "runtime": movie.get("runtime"),
            "poster": poster_url,
            "backdrop": backdrop_url,
            "rating": movie.get("vote_average"),
            "rating_count": movie.get("vote_count"),
            "imdb_id": movie.get("imdb_id"),
            "tmdb_id": movie.get("id"),
            "genres": [g["name"] for g in movie.get("genres", [])],
            "tagline": movie.get("tagline", ""),
            "budget": movie.get("budget"),
            "revenue": movie.get("revenue"),
            "production_companies": [c["name"] for c in movie.get("production_companies", [])],
        }

    async def get_music_video_metadata(
        self, title: str, url: str, youtube_metadata: dict | None = None
    ) -> dict[str, Any]:
        """
        Get music video metadata with fallback chain:
        1. YouTube embedded metadata (from yt-dlp)
        2. MusicBrainz API search
        3. Parse from title/description

        Args:
            title: Video title
            url: Video URL
            youtube_metadata: Optional pre-extracted YouTube metadata

        Returns:
            Dict with artist, song, year, album, genre, source, confidence
        """
        result = {
            "artist": None,
            "song": None,
            "year": None,
            "album": None,
            "genre": None,
            "source": "parsed",
            "confidence": 0.0,
        }

        # Try to extract from YouTube metadata first
        if youtube_metadata:
            artist = youtube_metadata.get("artist")
            song = youtube_metadata.get("song")
            year = youtube_metadata.get("year")

            if artist and song:
                result["artist"] = artist
                result["song"] = song
                result["year"] = year
                result["source"] = "youtube"
                result["confidence"] = 0.7

                # Try MusicBrainz for additional metadata
                if self.musicbrainz and artist and song:
                    try:
                        recording = await self.musicbrainz.search_recording(artist, song, year)
                        if recording:
                            # Extract additional metadata
                            if not result["year"] and recording.get("first-release-date"):
                                with contextlib.suppress(ValueError, TypeError):
                                    result["year"] = int(recording["first-release-date"][:4])

                            # Get detailed info for album
                            if recording.get("releases"):
                                release = recording["releases"][0]
                                result["album"] = release.get("title")
                                if not result["year"] and release.get("date"):
                                    with contextlib.suppress(ValueError, TypeError):
                                        result["year"] = int(release["date"][:4])

                            result["source"] = "musicbrainz"
                            result["confidence"] = 0.9
                    except Exception as e:
                        logger.debug(f"MusicBrainz lookup failed: {e}")

        # If no YouTube metadata, try MusicBrainz with parsed artist/song
        if not result["artist"] or not result["song"]:
            # Parse from title
            parsed = self._parse_music_title(title)
            if parsed.get("artist") and parsed.get("song"):
                artist = parsed["artist"]
                song = parsed["song"]

                if self.musicbrainz:
                    try:
                        recording = await self.musicbrainz.search_recording(artist, song)
                        if recording:
                            result["artist"] = recording.get("artist-credit", [{}])[0].get(
                                "name", artist
                            )
                            result["song"] = recording.get("title", song)
                            result["year"] = None

                            if recording.get("first-release-date"):
                                with contextlib.suppress(ValueError, TypeError):
                                    result["year"] = int(recording["first-release-date"][:4])

                            if recording.get("releases"):
                                result["album"] = recording["releases"][0].get("title")

                            result["source"] = "musicbrainz"
                            result["confidence"] = 0.9
                        else:
                            # Use parsed values
                            result["artist"] = artist
                            result["song"] = song
                            result["source"] = "parsed"
                            result["confidence"] = 0.5
                    except Exception as e:
                        logger.debug(f"MusicBrainz search failed: {e}")
                        # Use parsed values as fallback
                        result["artist"] = artist
                        result["song"] = song
                        result["source"] = "parsed"
                        result["confidence"] = 0.5
                else:
                    # No MusicBrainz, use parsed
                    result["artist"] = artist
                    result["song"] = song
                    result["source"] = "parsed"
                    result["confidence"] = 0.5

        # Final fallback: use title as song, no artist
        if not result["song"]:
            result["song"] = title
            result["confidence"] = 0.2

        return result

    def _parse_music_title(self, title: str) -> dict[str, str | None]:
        """
        Parse artist and song from video title

        Patterns:
        - "Artist - Song Title"
        - "Artist: Song Title"
        - "Song Title (by Artist)"
        - "Artist - Song Title (Official Music Video)"
        """
        import re

        result = {"artist": None, "song": None}

        # Remove common suffixes
        title = re.sub(r"\s*\([Oo]fficial\s+[Mm]usic\s+[Vv]ideo\)", "", title)
        title = re.sub(r"\s*\[[Oo]fficial\s+[Mm]usic\s+[Vv]ideo\]", "", title)
        title = re.sub(r"\s*\([Oo]fficial\s+[Vv]ideo\)", "", title)
        title = title.strip()

        # Pattern 1: "Artist - Song"
        match = re.match(r"^([^-]+?)\s*-\s*(.+)$", title)
        if match:
            result["artist"] = match.group(1).strip()
            result["song"] = match.group(2).strip()
            return result

        # Pattern 2: "Artist: Song"
        match = re.match(r"^([^:]+?):\s*(.+)$", title)
        if match:
            result["artist"] = match.group(1).strip()
            result["song"] = match.group(2).strip()
            return result

        # Pattern 3: "Song (by Artist)"
        match = re.match(r"^(.+?)\s*\([Bb]y\s+(.+?)\)$", title)
        if match:
            result["song"] = match.group(1).strip()
            result["artist"] = match.group(2).strip()
            return result

        # Pattern 4: "Song by Artist"
        match = re.match(r"^(.+?)\s+[Bb]y\s+(.+)$", title)
        if match:
            result["song"] = match.group(1).strip()
            result["artist"] = match.group(2).strip()
            return result

        return result


def create_metadata_manager(
    tvdb_api_key: str | None = None,
    tvdb_read_token: str | None = None,
    tmdb_api_key: str | None = None,
    enable_tvdb: bool = True,
    enable_tvmaze: bool = True,
    enable_tmdb: bool = True,
    enable_musicbrainz: bool = True,
) -> MetadataManager:
    """
    Create a metadata manager with configured providers
    
    Args:
        tvdb_api_key: TVDB API key
        tvdb_read_token: TVDB v4 read access token (preferred)
        tmdb_api_key: TMDB API key
        enable_tvdb: Enable TVDB provider
        enable_tvmaze: Enable TVMaze provider (free fallback)
        enable_tmdb: Enable TMDB provider (for movies)
        enable_musicbrainz: Enable MusicBrainz provider (for music videos)
        
    Returns:
        Configured MetadataManager instance
    """
    tvdb_client = None
    if enable_tvdb and (tvdb_api_key or tvdb_read_token):
        tvdb_client = TVDBClient(api_key=tvdb_api_key or "", read_token=tvdb_read_token)
    
    tvmaze_client = TVMazeClient() if enable_tvmaze else None
    
    tmdb_client = None
    if enable_tmdb and tmdb_api_key:
        tmdb_client = TMDBClient(api_key=tmdb_api_key)
    
    musicbrainz_client = None
    if enable_musicbrainz:
        musicbrainz_client = MusicBrainzClient(user_agent="EXStreamTV/1.0")

    return MetadataManager(
        tvdb_client=tvdb_client,
        tvmaze_client=tvmaze_client,
        tmdb_client=tmdb_client,
        musicbrainz_client=musicbrainz_client,
    )
