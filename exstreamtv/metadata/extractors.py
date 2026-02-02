"""
Metadata Extractors Module

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
    
    # Common patterns for TV shows
    TV_PATTERNS = [
        r"(?P<title>.+?)[\.\s_-]+S(?P<season>\d+)E(?P<episode>\d+)",
        r"(?P<title>.+?)[\.\s_-]+(?P<season>\d+)x(?P<episode>\d+)",
        r"(?P<title>.+?)[\.\s_-]+Season[\.\s_-]+(?P<season>\d+)[\.\s_-]+Episode[\.\s_-]+(?P<episode>\d+)",
    ]
    
    # Common patterns for movies
    MOVIE_PATTERNS = [
        r"(?P<title>.+?)[\.\s_-]+\(?(?P<year>\d{4})\)?",
    ]
    
    def extract(self, filename: str) -> Dict[str, Any]:
        """Extract metadata from filename."""
        result: Dict[str, Any] = {"original_filename": filename}
        
        # Clean filename
        clean = filename.replace(".", " ").replace("_", " ").replace("-", " ")
        
        # Try TV patterns
        for pattern in self.TV_PATTERNS:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                result["media_type"] = "episode"
                result["title"] = match.group("title").replace(".", " ").strip()
                result["season"] = int(match.group("season"))
                result["episode"] = int(match.group("episode"))
                return result
        
        # Try movie patterns
        for pattern in self.MOVIE_PATTERNS:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                result["media_type"] = "movie"
                result["title"] = match.group("title").replace(".", " ").strip()
                result["year"] = int(match.group("year"))
                return result
        
        # Fallback
        result["title"] = clean.strip()
        return result


class FFprobeExtractor(MetadataExtractor):
    """Extract metadata using FFprobe."""
    
    async def extract_async(self, file_path: str) -> Dict[str, Any]:
        """Extract metadata using FFprobe asynchronously."""
        from exstreamtv.media.scanner.ffprobe import FFprobeAnalyzer
        
        analyzer = FFprobeAnalyzer()
        try:
            result = await analyzer.analyze(file_path)
            return {
                "duration": result.duration,
                "format": result.format,
                "video_codec": result.video_streams[0].codec if result.video_streams else None,
                "audio_codec": result.audio_streams[0].codec if result.audio_streams else None,
                "width": result.video_streams[0].width if result.video_streams else None,
                "height": result.video_streams[0].height if result.video_streams else None,
            }
        except Exception as e:
            logger.warning(f"FFprobe extraction failed: {e}")
            return {}
    
    def extract(self, file_path: str) -> Dict[str, Any]:
        """Synchronous wrapper - returns empty dict, use extract_async."""
        return {}


__all__ = [
    "MetadataExtractor",
    "FilenameExtractor",
    "FFprobeExtractor",
]
