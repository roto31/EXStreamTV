"""Metadata extraction module for YouTube, Archive.org, and Plex"""

import logging
import re
from typing import Any

from ..streaming.stream_manager import StreamSource

logger = logging.getLogger(__name__)


def extract_metadata(
    url: str, source: StreamSource, video_info: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Extract metadata from a media URL.

    Args:
        url: Media URL
        source: Stream source type
        video_info: Optional pre-fetched video information

    Returns:
        Dictionary with extracted metadata
    """
    if source == StreamSource.YOUTUBE:
        return extract_youtube_metadata(url, video_info)
    elif source == StreamSource.ARCHIVE_ORG:
        return extract_archive_org_metadata(url, video_info)
    elif source == StreamSource.PLEX:
        return extract_plex_metadata(url, video_info)

    return {}


def extract_youtube_metadata(url: str, video_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Extract metadata from YouTube URL or video info.

    Args:
        url: YouTube URL
        video_info: Optional pre-fetched video information from yt-dlp

    Returns:
        Dictionary with extracted metadata
    """
    metadata = {}

    if video_info:
        # Extract from yt-dlp video info
        metadata["title"] = video_info.get("title", "")
        metadata["description"] = video_info.get("description", "")
        metadata["duration"] = video_info.get("duration", 0)
        metadata["upload_date"] = video_info.get("upload_date", "")
        metadata["thumbnail"] = video_info.get("thumbnail", "")
        metadata["channel"] = video_info.get("uploader", "")
        metadata["channel_id"] = video_info.get("channel_id", "")
        metadata["view_count"] = video_info.get("view_count", 0)
        metadata["like_count"] = video_info.get("like_count", 0)

        # Extract episode information
        episode_info = extract_episode_info(
            video_info.get("title", ""), video_info.get("description", "")
        )
        metadata.update(episode_info)

        # Extract series information
        series_info = extract_series_info(metadata)
        metadata.update(series_info)

    return metadata


def extract_archive_org_metadata(
    url: str, video_info: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Extract metadata from Archive.org URL or item info.

    Args:
        url: Archive.org URL
        video_info: Optional pre-fetched item information

    Returns:
        Dictionary with extracted metadata
    """
    metadata = {}

    if video_info:
        metadata["title"] = video_info.get("title", "")
        metadata["description"] = video_info.get("description", "")
        metadata["creator"] = video_info.get("creator", "")
        metadata["date"] = video_info.get("date", "")
        metadata["year"] = video_info.get("year", "")
        metadata["subject"] = video_info.get("subject", [])
        metadata["collection"] = video_info.get("collection", [])

        # Extract episode information
        episode_info = extract_episode_info(
            metadata.get("title", ""), metadata.get("description", "")
        )
        metadata.update(episode_info)

        # Extract series information
        series_info = extract_series_info(metadata)
        metadata.update(series_info)

    return metadata


def extract_plex_metadata(url: str, video_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Extract metadata from Plex URL or media info.

    Args:
        url: Plex URL
        video_info: Optional pre-fetched media information from Plex API

    Returns:
        Dictionary with extracted metadata
    """
    metadata = {}

    if video_info:
        # Plex API provides rich metadata
        metadata["title"] = video_info.get("title", "")
        metadata["summary"] = video_info.get("summary", "")
        metadata["duration"] = video_info.get("duration", 0)
        metadata["year"] = video_info.get("year", "")
        metadata["rating"] = video_info.get("rating", "")
        metadata["contentRating"] = video_info.get("contentRating", "")
        metadata["thumb"] = video_info.get("thumb", "")
        metadata["art"] = video_info.get("art", "")

        # Extract series/episode information
        if video_info.get("type") == "episode":
            metadata["series_title"] = video_info.get("grandparentTitle", "")
            metadata["episode_title"] = video_info.get("title", "")
            metadata["season_number"] = video_info.get("parentIndex", 0)
            metadata["episode_number"] = video_info.get("index", 0)
            metadata["episode_air_date"] = video_info.get("originallyAvailableAt", "")

        # Extract genres, actors, directors
        if "Genre" in video_info:
            metadata["genres"] = [g.get("tag", "") for g in video_info["Genre"]]
        if "Role" in video_info:
            metadata["actors"] = [r.get("tag", "") for r in video_info["Role"]]
        if "Director" in video_info:
            metadata["directors"] = [d.get("tag", "") for d in video_info["Director"]]

    return metadata


def extract_episode_info(title: str, description: str) -> dict[str, Any]:
    """
    Extract episode information from title and description.

    Parses patterns like:
    - "Show Name S01E01 Episode Title"
    - "Show Name - Season 1 Episode 1 - Episode Title"
    - "Show Name (2024) - S01E01"

    Args:
        title: Video/show title
        description: Video description

    Returns:
        Dictionary with episode information
    """
    episode_info = {}

    # Pattern 1: S##E## format
    season_episode_pattern = r"[Ss](\d+)[Ee](\d+)"
    match = re.search(season_episode_pattern, title)
    if match:
        episode_info["season_number"] = int(match.group(1))
        episode_info["episode_number"] = int(match.group(2))

        # Extract series title (everything before S##E##)
        series_title = title[: match.start()].strip()
        if series_title:
            episode_info["series_title"] = series_title

        # Extract episode title (everything after S##E##)
        episode_title = title[match.end() :].strip()
        if episode_title:
            # Remove common separators
            episode_title = re.sub(r"^[-:\s]+", "", episode_title)
            if episode_title:
                episode_info["episode_title"] = episode_title

    # Pattern 2: "Season X Episode Y" format
    if "season_number" not in episode_info:
        season_episode_pattern2 = r"[Ss]eason\s+(\d+)\s+[Ee]pisode\s+(\d+)"
        match = re.search(season_episode_pattern2, title, re.IGNORECASE)
        if match:
            episode_info["season_number"] = int(match.group(1))
            episode_info["episode_number"] = int(match.group(2))

    # Pattern 3: "Part X" or "Episode X" (assume season 1)
    if "season_number" not in episode_info:
        episode_pattern = r"[Ee]pisode\s+(\d+)|[Pp]art\s+(\d+)"
        match = re.search(episode_pattern, title, re.IGNORECASE)
        if match:
            episode_info["season_number"] = 1
            episode_info["episode_number"] = int(match.group(1) or match.group(2))

    # Try to extract from description if not found in title
    if "season_number" not in episode_info and description:
        # Look for "Season X, Episode Y" in description
        desc_match = re.search(
            r"[Ss]eason\s+(\d+)[,\s]+[Ee]pisode\s+(\d+)", description, re.IGNORECASE
        )
        if desc_match:
            episode_info["season_number"] = int(desc_match.group(1))
            episode_info["episode_number"] = int(desc_match.group(2))

    return episode_info


def extract_series_info(metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Extract series/show information from metadata.

    Args:
        metadata: Existing metadata dictionary

    Returns:
        Dictionary with series information
    """
    series_info = {}

    # If series_title is already set, use it
    if metadata.get("series_title"):
        series_info["series_title"] = metadata["series_title"]
    elif "title" in metadata:
        # Try to extract series title from full title
        title = metadata["title"]

        # Remove episode patterns to get series title
        title_clean = re.sub(r"[Ss]\d+[Ee]\d+.*", "", title)
        title_clean = re.sub(r"[Ss]eason\s+\d+.*", "", title_clean, flags=re.IGNORECASE)
        title_clean = title_clean.strip()

        if title_clean:
            series_info["series_title"] = title_clean

    return series_info
