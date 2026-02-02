"""
NFO file parser for Kodi/Plex-style metadata.

Parses .nfo files commonly used by Kodi, Plex, Jellyfin, and other media managers.
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from exstreamtv.media.providers.base import MediaMetadata, PersonInfo

logger = logging.getLogger(__name__)


@dataclass
class NFOArtwork:
    """Artwork reference from NFO file."""

    type: str  # "poster", "fanart", "thumb", "banner"
    path: str
    aspect: Optional[str] = None
    preview: Optional[str] = None


class NFOParser:
    """
    Parser for NFO metadata files.

    Supports:
    - Kodi movie.nfo / tvshow.nfo / episode.nfo format
    - Basic and extended metadata
    - Actor/cast information
    - Artwork references
    """

    # NFO file patterns by type
    NFO_PATTERNS = {
        "movie": ["movie.nfo", "{title}.nfo"],
        "show": ["tvshow.nfo"],
        "episode": ["{show} - S{season}E{episode}.nfo", "S{season}E{episode}.nfo"],
    }

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize NFO parser.

        Args:
            base_path: Optional base path for relative artwork paths.
        """
        self.base_path = base_path

    def parse_file(self, nfo_path: Path) -> Optional[MediaMetadata]:
        """
        Parse an NFO file.

        Args:
            nfo_path: Path to the NFO file.

        Returns:
            MediaMetadata or None if parsing fails.
        """
        if not nfo_path.exists():
            return None

        try:
            content = nfo_path.read_text(encoding="utf-8", errors="ignore")

            # Try to parse as XML
            return self._parse_xml(content, nfo_path)

        except Exception as e:
            logger.warning(f"Error parsing NFO file {nfo_path}: {e}")
            return None

    def _parse_xml(self, content: str, nfo_path: Path) -> Optional[MediaMetadata]:
        """Parse NFO content as XML."""
        try:
            # Clean content - remove invalid XML
            content = self._clean_xml(content)

            root = ET.fromstring(content)
            root_tag = root.tag.lower()

            if root_tag == "movie":
                return self._parse_movie(root, nfo_path)
            elif root_tag == "tvshow":
                return self._parse_tvshow(root, nfo_path)
            elif root_tag == "episodedetails":
                return self._parse_episode(root, nfo_path)
            else:
                logger.debug(f"Unknown NFO root element: {root_tag}")
                return None

        except ET.ParseError as e:
            logger.debug(f"XML parse error: {e}")
            return None

    def _clean_xml(self, content: str) -> str:
        """Clean XML content for parsing."""
        # Remove BOM if present
        content = content.lstrip("\ufeff")

        # Check if content looks like a URL (common false positive)
        if content.strip().startswith("http"):
            raise ET.ParseError("Content is a URL, not NFO XML")

        # Remove content before XML declaration if present
        xml_decl = content.find("<?xml")
        if xml_decl > 0:
            content = content[xml_decl:]

        return content

    def _parse_movie(self, root: ET.Element, nfo_path: Path) -> MediaMetadata:
        """Parse movie NFO."""
        return MediaMetadata(
            title=self._get_text(root, "title", "Unknown"),
            original_title=self._get_text(root, "originaltitle"),
            media_type="movie",
            tmdb_id=self._get_text(root, "tmdbid") or self._get_id(root, "tmdb"),
            tvdb_id=self._get_text(root, "tvdbid") or self._get_id(root, "tvdb"),
            imdb_id=self._get_text(root, "imdbid") or self._get_id(root, "imdb") or self._extract_imdb(root),
            overview=self._get_text(root, "plot") or self._get_text(root, "outline"),
            tagline=self._get_text(root, "tagline"),
            release_date=self._parse_date(self._get_text(root, "premiered") or self._get_text(root, "releasedate")),
            year=self._get_int(root, "year"),
            rating=self._get_rating(root),
            vote_count=self._get_int(root, "votes"),
            content_rating=self._get_text(root, "mpaa") or self._get_text(root, "certification"),
            runtime_minutes=self._get_int(root, "runtime"),
            genres=self._get_list(root, "genre"),
            tags=self._get_list(root, "tag"),
            studios=self._get_list(root, "studio"),
            countries=self._get_list(root, "country"),
            cast=self._parse_actors(root),
            crew=self._parse_crew(root),
            poster_url=self._get_artwork(root, nfo_path, "poster"),
            backdrop_url=self._get_artwork(root, nfo_path, "fanart"),
            thumb_url=self._get_artwork(root, nfo_path, "thumb"),
        )

    def _parse_tvshow(self, root: ET.Element, nfo_path: Path) -> MediaMetadata:
        """Parse TV show NFO."""
        return MediaMetadata(
            title=self._get_text(root, "title", "Unknown"),
            original_title=self._get_text(root, "originaltitle"),
            media_type="show",
            tmdb_id=self._get_text(root, "tmdbid") or self._get_id(root, "tmdb"),
            tvdb_id=self._get_text(root, "tvdbid") or self._get_id(root, "tvdb") or self._get_text(root, "id"),
            imdb_id=self._get_text(root, "imdbid") or self._get_id(root, "imdb"),
            overview=self._get_text(root, "plot"),
            release_date=self._parse_date(self._get_text(root, "premiered")),
            year=self._get_int(root, "year"),
            rating=self._get_rating(root),
            vote_count=self._get_int(root, "votes"),
            content_rating=self._get_text(root, "mpaa"),
            runtime_minutes=self._get_int(root, "runtime"),
            status=self._get_text(root, "status"),
            genres=self._get_list(root, "genre"),
            tags=self._get_list(root, "tag"),
            studios=self._get_list(root, "studio"),
            networks=self._get_list(root, "network") or self._get_list(root, "studio"),
            cast=self._parse_actors(root),
            poster_url=self._get_artwork(root, nfo_path, "poster"),
            backdrop_url=self._get_artwork(root, nfo_path, "fanart"),
        )

    def _parse_episode(self, root: ET.Element, nfo_path: Path) -> MediaMetadata:
        """Parse episode NFO."""
        return MediaMetadata(
            title=self._get_text(root, "title", "Unknown"),
            media_type="episode",
            tmdb_id=self._get_text(root, "tmdbid") or self._get_id(root, "tmdb"),
            tvdb_id=self._get_text(root, "tvdbid") or self._get_id(root, "tvdb"),
            show_title=self._get_text(root, "showtitle"),
            season_number=self._get_int(root, "season"),
            episode_number=self._get_int(root, "episode"),
            overview=self._get_text(root, "plot"),
            release_date=self._parse_date(self._get_text(root, "aired")),
            year=self._get_int(root, "year"),
            rating=self._get_rating(root),
            vote_count=self._get_int(root, "votes"),
            runtime_minutes=self._get_int(root, "runtime"),
            cast=self._parse_actors(root),
            crew=self._parse_crew(root),
            thumb_url=self._get_artwork(root, nfo_path, "thumb"),
        )

    def _get_text(
        self, root: ET.Element, tag: str, default: Optional[str] = None
    ) -> Optional[str]:
        """Get text content of an element."""
        elem = root.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default

    def _get_int(self, root: ET.Element, tag: str) -> Optional[int]:
        """Get integer value of an element."""
        text = self._get_text(root, tag)
        if text:
            try:
                # Handle "123 min" format
                num_match = re.match(r"(\d+)", text)
                if num_match:
                    return int(num_match.group(1))
            except ValueError:
                pass
        return None

    def _get_rating(self, root: ET.Element) -> Optional[float]:
        """Get rating value."""
        # Try ratings element first (Kodi 17+)
        ratings = root.find("ratings")
        if ratings is not None:
            rating = ratings.find("rating")
            if rating is not None:
                value = rating.find("value")
                if value is not None and value.text:
                    try:
                        return float(value.text)
                    except ValueError:
                        pass

        # Fallback to simple rating element
        text = self._get_text(root, "rating")
        if text:
            try:
                return float(text)
            except ValueError:
                pass

        return None

    def _get_list(self, root: ET.Element, tag: str) -> List[str]:
        """Get list of text values for repeated elements."""
        items = []
        for elem in root.findall(tag):
            if elem.text:
                items.append(elem.text.strip())
        return items

    def _get_id(self, root: ET.Element, id_type: str) -> Optional[str]:
        """Get ID from uniqueid elements."""
        for uniqueid in root.findall("uniqueid"):
            if uniqueid.get("type", "").lower() == id_type:
                return uniqueid.text
        return None

    def _extract_imdb(self, root: ET.Element) -> Optional[str]:
        """Extract IMDB ID from various locations."""
        # Try id element with imdb prefix
        id_elem = root.find("id")
        if id_elem is not None and id_elem.text:
            if id_elem.text.startswith("tt"):
                return id_elem.text

        # Try trailer URL for IMDB reference
        trailer = self._get_text(root, "trailer")
        if trailer and "imdb.com" in trailer:
            match = re.search(r"tt\d+", trailer)
            if match:
                return match.group()

        return None

    def _parse_actors(self, root: ET.Element) -> List[PersonInfo]:
        """Parse actor elements."""
        actors = []
        for actor in root.findall("actor"):
            name = self._get_text(actor, "name")
            if name:
                actors.append(
                    PersonInfo(
                        name=name,
                        role=self._get_text(actor, "role") or "",
                        image_url=self._get_text(actor, "thumb"),
                        tmdb_id=self._get_text(actor, "tmdbid"),
                    )
                )
        return actors

    def _parse_crew(self, root: ET.Element) -> List[PersonInfo]:
        """Parse director and other crew."""
        crew = []

        # Directors
        for director in root.findall("director"):
            if director.text:
                crew.append(
                    PersonInfo(name=director.text.strip(), job="Director")
                )

        # Writers/Credits
        for credits_tag in ["credits", "writer"]:
            for writer in root.findall(credits_tag):
                if writer.text:
                    crew.append(
                        PersonInfo(name=writer.text.strip(), job="Writer")
                    )

        return crew

    def _get_artwork(
        self, root: ET.Element, nfo_path: Path, art_type: str
    ) -> Optional[str]:
        """Get artwork path."""
        elem = root.find(art_type)
        if elem is not None and elem.text:
            path = elem.text.strip()
            if path.startswith("http"):
                return path

            # Resolve relative path
            base = self.base_path or nfo_path.parent
            full_path = base / path
            if full_path.exists():
                return str(full_path)

        # Look for common artwork files
        base = self.base_path or nfo_path.parent
        common_names = {
            "poster": ["poster.jpg", "poster.png", "folder.jpg"],
            "fanart": ["fanart.jpg", "fanart.png", "backdrop.jpg"],
            "thumb": ["thumb.jpg", "thumb.png"],
        }

        for name in common_names.get(art_type, []):
            art_path = base / name
            if art_path.exists():
                return str(art_path)

        return None

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string."""
        if not date_str:
            return None

        try:
            # Try YYYY-MM-DD
            parts = date_str.split("-")
            if len(parts) >= 3:
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            elif len(parts) == 1 and len(parts[0]) == 4:
                return date(int(parts[0]), 1, 1)
        except (ValueError, IndexError):
            pass

        return None

    @classmethod
    def find_nfo_for_media(cls, media_path: Path) -> Optional[Path]:
        """
        Find the NFO file for a media file.

        Args:
            media_path: Path to the media file.

        Returns:
            Path to NFO file or None.
        """
        parent = media_path.parent
        stem = media_path.stem

        # Check for matching NFO file (same name)
        matching_nfo = parent / f"{stem}.nfo"
        if matching_nfo.exists():
            return matching_nfo

        # Check for generic movie.nfo
        movie_nfo = parent / "movie.nfo"
        if movie_nfo.exists():
            return movie_nfo

        # Check for tvshow.nfo (for episodes, look in parent)
        for check_dir in [parent, parent.parent]:
            tvshow_nfo = check_dir / "tvshow.nfo"
            if tvshow_nfo.exists():
                return tvshow_nfo

        return None

    @classmethod
    def scan_directory_for_nfo(cls, directory: Path) -> List[Path]:
        """
        Scan a directory for all NFO files.

        Args:
            directory: Directory to scan.

        Returns:
            List of NFO file paths.
        """
        nfo_files = []

        try:
            for nfo_path in directory.rglob("*.nfo"):
                if not nfo_path.name.startswith("."):
                    nfo_files.append(nfo_path)
        except PermissionError:
            logger.warning(f"Permission denied scanning {directory}")

        return sorted(nfo_files)
