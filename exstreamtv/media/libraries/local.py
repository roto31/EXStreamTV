"""
Local file system library.

Scans local folders for media files with metadata extraction.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from exstreamtv.media.libraries.base import (
    BaseLibrary,
    LibraryItem,
    LibraryType,
    MediaType,
)
from exstreamtv.media.scanner.file_scanner import FileScanner, ScannedFile

logger = logging.getLogger(__name__)


@dataclass
class ParsedMediaName:
    """Parsed media file name."""

    title: str
    year: Optional[int] = None
    show_title: Optional[str] = None
    season_number: Optional[int] = None
    episode_number: Optional[int] = None
    quality: Optional[str] = None
    is_episode: bool = False


class MediaNameParser:
    """
    Parses media file names to extract metadata.

    Supports common naming conventions:
    - Movies: "Movie Title (2023).mkv", "Movie.Title.2023.1080p.mkv"
    - Shows: "Show Name - S01E05 - Episode Title.mkv", "Show.Name.S01E05.mkv"
    """

    # Episode patterns
    EPISODE_PATTERNS = [
        # "Show Name - S01E05" or "Show Name S01E05"
        re.compile(r"^(.+?)[\s\-\.]+[Ss](\d{1,2})[Ee](\d{1,3})(?:[\s\-\.]+(.+))?$"),
        # "Show Name - 1x05"
        re.compile(r"^(.+?)[\s\-\.]+(\d{1,2})x(\d{1,3})(?:[\s\-\.]+(.+))?$"),
        # "Show Name - Season 1 Episode 5"
        re.compile(
            r"^(.+?)[\s\-\.]+[Ss]eason\s*(\d{1,2})[\s\-\.]+[Ee]pisode\s*(\d{1,3})(?:[\s\-\.]+(.+))?$",
            re.IGNORECASE,
        ),
    ]

    # Movie patterns
    MOVIE_PATTERNS = [
        # "Movie Title (2023)"
        re.compile(r"^(.+?)\s*\((\d{4})\)"),
        # "Movie.Title.2023.1080p"
        re.compile(r"^(.+?)\.(\d{4})\."),
    ]

    # Quality patterns
    QUALITY_PATTERNS = [
        re.compile(r"(2160p|4[Kk])", re.IGNORECASE),
        re.compile(r"(1080p|[Ff][Hh][Dd])", re.IGNORECASE),
        re.compile(r"(720p|[Hh][Dd])", re.IGNORECASE),
        re.compile(r"(480p|[Ss][Dd])", re.IGNORECASE),
    ]

    def parse(self, filename: str) -> ParsedMediaName:
        """
        Parse a media file name.

        Args:
            filename: File name (with or without extension).

        Returns:
            ParsedMediaName with extracted metadata.
        """
        # Remove extension
        name = Path(filename).stem

        # Clean up common artifacts
        name = self._clean_name(name)

        # Try episode patterns first
        for pattern in self.EPISODE_PATTERNS:
            match = pattern.match(name)
            if match:
                groups = match.groups()
                episode_title = groups[3] if len(groups) > 3 and groups[3] else None
                if episode_title:
                    episode_title = self._format_title(episode_title)

                return ParsedMediaName(
                    title=episode_title or f"Episode {int(groups[2])}",
                    show_title=self._format_title(groups[0]),
                    season_number=int(groups[1]),
                    episode_number=int(groups[2]),
                    quality=self._extract_quality(name),
                    is_episode=True,
                )

        # Try movie patterns
        for pattern in self.MOVIE_PATTERNS:
            match = pattern.match(name)
            if match:
                return ParsedMediaName(
                    title=self._format_title(match.group(1)),
                    year=int(match.group(2)),
                    quality=self._extract_quality(name),
                )

        # Fallback: just use the filename
        return ParsedMediaName(
            title=self._format_title(name),
            quality=self._extract_quality(name),
        )

    def _clean_name(self, name: str) -> str:
        """Remove common artifacts from name."""
        # Remove release group tags in brackets
        name = re.sub(r"\[.*?\]", "", name)
        # Remove common quality/codec tags at the end
        name = re.sub(
            r"[\.\s]+(x264|x265|HEVC|AAC|DTS|BluRay|BDRip|WEBRip|HDTV|WEB-DL).*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        return name.strip()

    def _format_title(self, title: str) -> str:
        """Format a title string."""
        # Replace dots and underscores with spaces
        title = title.replace(".", " ").replace("_", " ")
        # Remove extra whitespace
        title = " ".join(title.split())
        # Title case
        return title.strip()

    def _extract_quality(self, name: str) -> Optional[str]:
        """Extract quality from name."""
        for pattern in self.QUALITY_PATTERNS:
            match = pattern.search(name)
            if match:
                quality = match.group(1).lower()
                if "2160" in quality or "4k" in quality.lower():
                    return "4K"
                if "1080" in quality or "fhd" in quality.lower():
                    return "1080p"
                if "720" in quality or "hd" in quality.lower():
                    return "720p"
                if "480" in quality or "sd" in quality.lower():
                    return "480p"
        return None


class LocalLibrary(BaseLibrary):
    """
    Local file system media library.

    Features:
    - Recursive directory scanning
    - Automatic media type detection (movie/episode)
    - File name parsing for metadata
    - FFprobe integration for duration/resolution
    - Change detection for incremental updates
    """

    def __init__(
        self,
        library_id: int,
        name: str,
        path: str,
        media_type_hint: Optional[MediaType] = None,
        extensions: Optional[Set[str]] = None,
    ):
        """
        Initialize LocalLibrary.

        Args:
            library_id: Unique library identifier.
            name: Display name for the library.
            path: Root path to scan.
            media_type_hint: Hint for content type (movie/show).
            extensions: File extensions to include.
        """
        super().__init__(library_id, name, LibraryType.LOCAL)
        self.path = Path(path)
        self.media_type_hint = media_type_hint
        self.extensions = extensions
        self._parser = MediaNameParser()
        self._scanner: Optional[FileScanner] = None
        self._file_index: Dict[Path, ScannedFile] = {}

    async def connect(self) -> bool:
        """Check if the library path is accessible."""
        if not self.path.exists():
            logger.error(f"Library path does not exist: {self.path}")
            return False

        if not self.path.is_dir():
            logger.error(f"Library path is not a directory: {self.path}")
            return False

        self._scanner = FileScanner(
            library_id=self.library_id,
            library_path=str(self.path),
            extensions=self.extensions,
            analyze_media=True,
            max_concurrent=4,
        )

        logger.info(f"Connected to local library: {self.path}")
        return True

    async def disconnect(self) -> None:
        """Disconnect from the library."""
        self._scanner = None
        logger.debug(f"Disconnected from local library: {self.path}")

    async def sync(self) -> List[LibraryItem]:
        """
        Synchronize the library by scanning files.

        Returns:
            List of discovered LibraryItem objects.
        """
        if not self._scanner:
            raise RuntimeError("Library not connected")

        logger.info(f"Starting sync for library: {self.name}")
        result = await self._scanner.scan()

        if result.errors:
            for error in result.errors[:5]:  # Log first 5 errors
                logger.warning(f"Scan error: {error}")

        # Convert scanned files to library items
        items: List[LibraryItem] = []
        for scanned in result.items:
            try:
                item = self._create_library_item(scanned)
                items.append(item)
                self._items[item.id] = item
                self._file_index[scanned.path] = scanned
            except Exception as e:
                logger.warning(f"Error processing {scanned.path}: {e}")

        self._last_sync = datetime.now()

        logger.info(
            f"Sync complete: {len(items)} items from {self.name} "
            f"({result.progress.errors} errors)"
        )

        return items

    async def get_item(self, item_id: str) -> Optional[LibraryItem]:
        """Get a specific item by ID."""
        return self._items.get(item_id)

    async def get_stream_url(self, item_id: str) -> Optional[str]:
        """Get the file path for streaming."""
        item = self._items.get(item_id)
        if item and item.path:
            return f"file://{item.path}"
        return None

    async def get_file_path(self, item_id: str) -> Optional[Path]:
        """Get the actual file path for an item."""
        item = self._items.get(item_id)
        if item and item.path:
            return Path(item.path)
        return None

    async def check_item_exists(self, item_id: str) -> bool:
        """Check if the file for an item still exists."""
        item = self._items.get(item_id)
        if item and item.path:
            return Path(item.path).exists()
        return False

    async def get_shows(self) -> Dict[str, List[LibraryItem]]:
        """
        Get episodes grouped by show.

        Returns:
            Dict mapping show title to episodes.
        """
        shows: Dict[str, List[LibraryItem]] = {}

        for item in self._items.values():
            if item.media_type == MediaType.EPISODE and item.show_title:
                if item.show_title not in shows:
                    shows[item.show_title] = []
                shows[item.show_title].append(item)

        # Sort episodes within each show
        for show_title in shows:
            shows[show_title].sort(
                key=lambda x: (x.season_number or 0, x.episode_number or 0)
            )

        return shows

    async def get_movies(self) -> List[LibraryItem]:
        """Get all movies."""
        return [
            item for item in self._items.values()
            if item.media_type == MediaType.MOVIE
        ]

    def _create_library_item(self, scanned: ScannedFile) -> LibraryItem:
        """Create a LibraryItem from a scanned file."""
        # Parse filename
        parsed = self._parser.parse(scanned.filename)

        # Determine media type
        if parsed.is_episode or self.media_type_hint == MediaType.SHOW:
            media_type = MediaType.EPISODE
        elif self.media_type_hint == MediaType.MOVIE:
            media_type = MediaType.MOVIE
        elif parsed.year and not parsed.is_episode:
            media_type = MediaType.MOVIE
        else:
            # Try to detect from path structure
            media_type = self._detect_media_type(scanned.path)

        # Get duration from FFprobe analysis
        duration = timedelta(0)
        if scanned.media_info:
            duration = scanned.media_info.duration

        # Create unique ID from path
        item_id = str(scanned.relative_path)

        return LibraryItem(
            id=item_id,
            library_id=self.library_id,
            media_type=media_type,
            title=parsed.title,
            path=str(scanned.path),
            sort_title=parsed.title.lower(),
            duration=duration,
            year=parsed.year,
            show_title=parsed.show_title,
            season_number=parsed.season_number,
            episode_number=parsed.episode_number,
            added_at=scanned.modified_time,
            updated_at=datetime.now(),
        )

    def _detect_media_type(self, path: Path) -> MediaType:
        """
        Detect media type from path structure.

        Looks for patterns like:
        - /Movies/... -> Movie
        - /TV Shows/... -> Episode
        - /Series/... -> Episode
        - Contains "Season" folder -> Episode
        """
        path_lower = str(path).lower()

        # Check for TV/episode indicators
        tv_indicators = ["tv shows", "tv series", "series", "/season ", "\\season "]
        for indicator in tv_indicators:
            if indicator in path_lower:
                return MediaType.EPISODE

        # Check for movie indicators
        movie_indicators = ["/movies/", "\\movies\\"]
        for indicator in movie_indicators:
            if indicator in path_lower:
                return MediaType.MOVIE

        # Check parent folder names
        for parent in path.parents:
            parent_name = parent.name.lower()
            if parent_name.startswith("season"):
                return MediaType.EPISODE
            if parent_name in ("movies", "films"):
                return MediaType.MOVIE
            if parent_name in ("tv shows", "tv", "series", "shows"):
                return MediaType.EPISODE

        # Default to "other" if unsure
        return MediaType.OTHER
