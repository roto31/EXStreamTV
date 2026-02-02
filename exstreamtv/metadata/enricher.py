"""Metadata enrichment pipeline with TVDB/TMDB integration"""

import logging
import re
from pathlib import Path
from typing import Any

from ..database.models import MediaItem

logger = logging.getLogger(__name__)


class MetadataEnricher:
    """Enriches media item metadata from external sources"""

    def __init__(self, tvdb_client: Any | None = None, tmdb_client: Any | None = None):
        """
        Initialize metadata enricher.

        Args:
            tvdb_client: TVDB API client instance (optional)
            tmdb_client: TMDB API client instance (optional)
        """
        self.tvdb_client = tvdb_client
        self.tmdb_client = tmdb_client

    async def enrich_media_item(self, media_item: MediaItem) -> dict[str, Any]:
        """
        Enrich a media item with metadata from external sources.

        Args:
            media_item: MediaItem instance to enrich

        Returns:
            Dictionary with enriched metadata
        """
        enriched = {}

        # Try TVDB first (better for TV shows)
        if self.tvdb_client and media_item.series_title:
            try:
                tvdb_data = await self.enrich_from_tvdb(media_item)
                if tvdb_data:
                    enriched.update(tvdb_data)
            except Exception as e:
                logger.warning(f"Error enriching from TVDB: {e}")

        # Try TMDB as fallback or supplement
        if self.tmdb_client:
            try:
                tmdb_data = await self.enrich_from_tmdb(media_item)
                if tmdb_data:
                    # Merge TMDB data, but don't overwrite TVDB data
                    for key, value in tmdb_data.items():
                        if key not in enriched or not enriched[key]:
                            enriched[key] = value
            except Exception as e:
                logger.warning(f"Error enriching from TMDB: {e}")

        # Try local NFO files
        try:
            nfo_data = self.parse_nfo_file(media_item)
            if nfo_data:
                for key, value in nfo_data.items():
                    if key not in enriched or not enriched[key]:
                        enriched[key] = value
        except Exception as e:
            logger.debug(f"Error parsing NFO file: {e}")

        # Extract from filename as fallback
        if not enriched.get("series_title") or not enriched.get("episode_number"):
            try:
                filename_data = self.extract_from_filename(media_item.title or media_item.url)
                if filename_data:
                    for key, value in filename_data.items():
                        if key not in enriched or not enriched[key]:
                            enriched[key] = value
            except Exception as e:
                logger.debug(f"Error extracting from filename: {e}")

        # Get fallback metadata if still missing
        if not enriched:
            enriched = self.get_fallback_metadata(media_item)

        return enriched

    async def enrich_from_tvdb(self, media_item: MediaItem) -> dict[str, Any]:
        """
        Enrich metadata from TVDB API.

        Args:
            media_item: MediaItem instance

        Returns:
            Dictionary with TVDB metadata
        """
        if not self.tvdb_client or not media_item.series_title:
            return {}

        try:
            # Search for series
            search_results = await self.tvdb_client.search(media_item.series_title, type="series")
            if not search_results:
                return {}

            # Use first result (could be improved with better matching)
            series_id = search_results[0].get("tvdb_id") or search_results[0].get("id")
            if not series_id:
                return {}

            # Get series details
            series_info = await self.tvdb_client.get_series(series_id)
            if not series_info:
                return {}

            enriched = {
                "series_title": series_info.get("name", media_item.series_title),
                "genres": series_info.get("genres", []),
                "content_rating": series_info.get("rating", ""),
            }

            # Get episode information if we have season/episode numbers
            if media_item.season_number and media_item.episode_number:
                episode_info = await self.tvdb_client.get_episode(
                    series_id, media_item.season_number, media_item.episode_number
                )
                if episode_info:
                    enriched.update(
                        {
                            "episode_title": episode_info.get("name", media_item.episode_title),
                            "episode_air_date": episode_info.get(
                                "aired", media_item.episode_air_date
                            ),
                            "description": episode_info.get("overview", media_item.description),
                        }
                    )

            # Get external IDs
            if "remote_ids" in series_info:
                enriched["guids"] = {
                    "tvdb": str(series_id),
                    "imdb": series_info["remote_ids"].get("imdb"),
                }

            return enriched

        except Exception as e:
            logger.exception(f"Error enriching from TVDB: {e}")
            return {}

    async def enrich_from_tmdb(self, media_item: MediaItem) -> dict[str, Any]:
        """
        Enrich metadata from TMDB API.

        Args:
            media_item: MediaItem instance

        Returns:
            Dictionary with TMDB metadata
        """
        if not self.tmdb_client:
            return {}

        try:
            # Search for TV show or movie
            if media_item.series_title:
                # TV show
                search_results = await self.tmdb_client.search_tv(media_item.series_title)
                if search_results:
                    series_id = search_results[0].get("id")
                    if series_id:
                        series_info = await self.tmdb_client.get_tv_series(series_id)
                        if series_info:
                            enriched = {
                                "series_title": series_info.get("name", media_item.series_title),
                                "genres": [
                                    g.get("name", "") for g in series_info.get("genres", [])
                                ],
                                "content_rating": series_info.get("content_ratings", {})
                                .get("results", [{}])[0]
                                .get("rating", ""),
                            }

                            # Get episode info if available
                            if media_item.season_number and media_item.episode_number:
                                episode_info = await self.tmdb_client.get_tv_episode(
                                    series_id, media_item.season_number, media_item.episode_number
                                )
                                if episode_info:
                                    enriched.update(
                                        {
                                            "episode_title": episode_info.get(
                                                "name", media_item.episode_title
                                            ),
                                            "episode_air_date": episode_info.get(
                                                "air_date", media_item.episode_air_date
                                            ),
                                            "description": episode_info.get(
                                                "overview", media_item.description
                                            ),
                                        }
                                    )

                            # Add external IDs
                            external_ids = await self.tmdb_client.get_tv_external_ids(series_id)
                            if external_ids:
                                enriched["guids"] = {
                                    "tmdb": str(series_id),
                                    "imdb": external_ids.get("imdb_id"),
                                }

                            return enriched
            # Movie - search by title
            elif media_item.title:
                search_results = await self.tmdb_client.search_movie(media_item.title)
                if search_results:
                    movie_id = search_results[0].get("id")
                    if movie_id:
                        movie_info = await self.tmdb_client.get_movie(movie_id)
                        if movie_info:
                            return {
                                "title": movie_info.get("title", media_item.title),
                                "description": movie_info.get("overview", media_item.description),
                                "genres": [g.get("name", "") for g in movie_info.get("genres", [])],
                                "content_rating": movie_info.get("release_dates", {})
                                .get("results", [{}])[0]
                                .get("release_dates", [{}])[0]
                                .get("certification", ""),
                                "guids": {
                                    "tmdb": str(movie_id),
                                    "imdb": movie_info.get("external_ids", {}).get("imdb_id"),
                                },
                            }

            return {}

        except Exception as e:
            logger.exception(f"Error enriching from TMDB: {e}")
            return {}

    def parse_nfo_file(self, media_item: MediaItem) -> dict[str, Any]:
        """
        Parse local NFO file (ErsatzTV-style).

        Args:
            media_item: MediaItem instance

        Returns:
            Dictionary with NFO metadata
        """
        # Try to find NFO file based on URL or title
        # This is a simplified implementation - adjust based on your file structure
        nfo_paths = []

        if media_item.url:
            # Try to derive NFO path from URL
            url_path = Path(media_item.url)
            if url_path.exists():
                nfo_paths.append(url_path.with_suffix(".nfo"))

        for nfo_path in nfo_paths:
            if nfo_path.exists():
                try:
                    import xml.etree.ElementTree as ET

                    tree = ET.parse(nfo_path)
                    root = tree.getroot()

                    metadata = {}

                    # Parse common NFO fields
                    if root.find("title") is not None:
                        metadata["title"] = root.find("title").text
                    if root.find("showtitle") is not None:
                        metadata["series_title"] = root.find("showtitle").text
                    if root.find("episodename") is not None:
                        metadata["episode_title"] = root.find("episodename").text
                    if root.find("season") is not None:
                        metadata["season_number"] = int(root.find("season").text)
                    if root.find("episode") is not None:
                        metadata["episode_number"] = int(root.find("episode").text)
                    if root.find("aired") is not None:
                        metadata["episode_air_date"] = root.find("aired").text
                    if root.find("plot") is not None:
                        metadata["description"] = root.find("plot").text
                    if root.find("mpaa") is not None:
                        metadata["content_rating"] = root.find("mpaa").text

                    # Parse genres
                    genres = []
                    for genre in root.findall("genre"):
                        if genre.text:
                            genres.append(genre.text)
                    if genres:
                        metadata["genres"] = genres

                    # Parse actors
                    actors = []
                    for actor in root.findall("actor"):
                        name = actor.find("name")
                        if name is not None and name.text:
                            actors.append(name.text)
                    if actors:
                        metadata["actors"] = actors

                    return metadata

                except Exception as e:
                    logger.warning(f"Error parsing NFO file {nfo_path}: {e}")

        return {}

    def extract_from_filename(self, filename: str) -> dict[str, Any]:
        """
        Extract metadata from filename.

        Handles patterns like:
        - "Show.Name.S01E01.Episode.Title.mkv"
        - "Show Name - S01E01 - Episode Title"

        Args:
            filename: Filename or title string

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}

        # Pattern 1: Show.Name.S01E01.Episode.Title
        pattern1 = r"(.+?)[\.\s]+[Ss](\d+)[Ee](\d+)[\.\s]+(.+?)(?:\.[^.]+)?$"
        match = re.search(pattern1, filename)
        if match:
            metadata["series_title"] = match.group(1).replace(".", " ").strip()
            metadata["season_number"] = int(match.group(2))
            metadata["episode_number"] = int(match.group(3))
            metadata["episode_title"] = match.group(4).replace(".", " ").strip()
            return metadata

        # Pattern 2: Show Name - S01E01 - Episode Title
        pattern2 = r"(.+?)\s*-\s*[Ss](\d+)[Ee](\d+)\s*-\s*(.+?)(?:\.[^.]+)?$"
        match = re.search(pattern2, filename)
        if match:
            metadata["series_title"] = match.group(1).strip()
            metadata["season_number"] = int(match.group(2))
            metadata["episode_number"] = int(match.group(3))
            metadata["episode_title"] = match.group(4).strip()
            return metadata

        return metadata

    def get_fallback_metadata(self, media_item: MediaItem) -> dict[str, Any]:
        """
        Get fallback metadata when external sources fail.

        Args:
            media_item: MediaItem instance

        Returns:
            Dictionary with fallback metadata
        """
        metadata = {}

        # Use existing fields as fallback
        if media_item.title:
            metadata["title"] = media_item.title
        if media_item.description:
            metadata["description"] = media_item.description
        if media_item.thumbnail:
            metadata["thumbnail"] = media_item.thumbnail

        # Try to extract series/episode from title if not already set
        if not media_item.series_title and media_item.title:
            episode_info = self.extract_from_filename(media_item.title)
            if episode_info:
                metadata.update(episode_info)

        return metadata
