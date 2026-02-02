"""
Metadata Extractors Package

Provides metadata extraction utilities for different media sources.
"""

from typing import Any, Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """Base class for metadata extraction."""
    
    def extract(self, source: Any) -> Dict[str, Any]:
        """Extract metadata from source."""
        raise NotImplementedError


class FilenameExtractor(MetadataExtractor):
    """Extract metadata from filenames."""
    
    TV_PATTERNS = [
        r"(?P<title>.+?)[\.\s_-]+S(?P<season>\d+)E(?P<episode>\d+)",
        r"(?P<title>.+?)[\.\s_-]+(?P<season>\d+)x(?P<episode>\d+)",
    ]
    
    MOVIE_PATTERNS = [
        r"(?P<title>.+?)[\.\s_-]+\(?(?P<year>\d{4})\)?",
    ]
    
    def extract(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from filename."""
        result: Dict[str, Any] = {"original_filename": filename}
        
        for pattern in self.TV_PATTERNS:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                result["media_type"] = "episode"
                result["title"] = match.group("title").replace(".", " ").strip()
                result["season"] = int(match.group("season"))
                result["episode"] = int(match.group("episode"))
                return result
        
        for pattern in self.MOVIE_PATTERNS:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                result["media_type"] = "movie"
                result["title"] = match.group("title").replace(".", " ").strip()
                result["year"] = int(match.group("year"))
                return result
        
        result["title"] = filename
        return result


class FFprobeExtractor(MetadataExtractor):
    """Extract metadata using FFprobe."""
    
    def extract(self, file_path: str) -> Dict[str, Any]:
        return {}


# Import sub-extractors
from exstreamtv.metadata.extractors.archive_org_v2 import (
    ArchiveOrgExtractor,
    ArchiveOrgExtractorV2,
    ArchiveOrgMetadataExtractorV2,
)
from exstreamtv.metadata.extractors.plex_v2 import (
    PlexMetadataExtractor,
    PlexMetadataExtractorV2,
    PlexExtractor,
)
from exstreamtv.metadata.extractors.youtube_v2 import (
    YouTubeMetadataExtractor,
    YouTubeMetadataExtractorV2,
    YouTubeExtractor,
)

__all__ = [
    "MetadataExtractor",
    "FilenameExtractor",
    "FFprobeExtractor",
    "ArchiveOrgExtractor",
    "ArchiveOrgExtractorV2",
    "ArchiveOrgMetadataExtractorV2",
    "PlexMetadataExtractor",
    "PlexMetadataExtractorV2",
    "PlexExtractor",
    "YouTubeMetadataExtractor",
    "YouTubeMetadataExtractorV2",
    "YouTubeExtractor",
]
