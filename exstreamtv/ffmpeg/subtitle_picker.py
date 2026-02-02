"""
Subtitle Stream Picker for intelligent subtitle selection.

Ported from Tunarr's SubtitleStreamPicker with enhancements:
- Language preference matching
- Text vs image subtitle type preference
- SDH/CC detection
- FFmpeg argument generation for burn-in

This enables automatic subtitle selection based on user
preferences, improving the viewing experience.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SubtitleType(str, Enum):
    """Types of subtitle streams."""
    
    TEXT = "text"  # SRT, ASS, WebVTT
    IMAGE = "image"  # PGS, VobSub, DVB
    UNKNOWN = "unknown"


class SubtitleFormat(str, Enum):
    """Subtitle format codecs."""
    
    SRT = "srt"
    SUBRIP = "subrip"
    ASS = "ass"
    SSA = "ssa"
    WEBVTT = "webvtt"
    MOVTEXT = "mov_text"
    PGS = "hdmv_pgs_subtitle"
    VOBSUB = "dvd_subtitle"
    DVB = "dvb_subtitle"
    TELETEXT = "dvb_teletext"


# Text-based subtitle codecs
TEXT_SUBTITLE_CODECS = {
    "srt", "subrip", "ass", "ssa", "webvtt", "mov_text", "text"
}

# Image-based subtitle codecs (require OCR or overlay)
IMAGE_SUBTITLE_CODECS = {
    "hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "dvb_teletext",
    "pgssub", "vobsub", "dvbsub", "dvdsub", "pgs"
}


@dataclass
class SubtitleStream:
    """Information about a subtitle stream."""
    
    index: int
    codec: str
    language: Optional[str] = None
    title: Optional[str] = None
    
    # Flags
    is_default: bool = False
    is_forced: bool = False
    is_hearing_impaired: bool = False  # SDH/CC
    is_commentary: bool = False
    
    # Metadata
    disposition: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def subtitle_type(self) -> SubtitleType:
        """Get subtitle type (text or image)."""
        codec_lower = self.codec.lower()
        
        if codec_lower in TEXT_SUBTITLE_CODECS:
            return SubtitleType.TEXT
        
        if codec_lower in IMAGE_SUBTITLE_CODECS:
            return SubtitleType.IMAGE
        
        return SubtitleType.UNKNOWN
    
    @property
    def is_text(self) -> bool:
        """Check if this is a text subtitle."""
        return self.subtitle_type == SubtitleType.TEXT
    
    @property
    def is_image(self) -> bool:
        """Check if this is an image subtitle."""
        return self.subtitle_type == SubtitleType.IMAGE
    
    @property
    def language_code(self) -> str:
        """Get normalized language code."""
        if not self.language:
            return "und"  # Undefined
        
        # Normalize common variations
        lang = self.language.lower()[:3]
        
        # Handle common mappings
        lang_map = {
            "eng": "eng",
            "en": "eng",
            "english": "eng",
            "spa": "spa",
            "es": "spa",
            "spanish": "spa",
            "fra": "fra",
            "fr": "fra",
            "french": "fra",
            "deu": "deu",
            "de": "deu",
            "german": "deu",
            "ger": "deu",
            "jpn": "jpn",
            "ja": "jpn",
            "japanese": "jpn",
            "kor": "kor",
            "ko": "kor",
            "korean": "kor",
            "chi": "chi",
            "zh": "chi",
            "chinese": "chi",
        }
        
        return lang_map.get(lang, lang)
    
    def matches_language(self, language_prefs: list[str]) -> int:
        """
        Check if this stream matches language preferences.
        
        Args:
            language_prefs: List of preferred languages (first = highest priority)
            
        Returns:
            Priority score (lower = better match, -1 = no match)
        """
        lang = self.language_code
        
        for i, pref in enumerate(language_prefs):
            pref_norm = pref.lower()[:3]
            if lang == pref_norm or lang.startswith(pref_norm):
                return i
        
        return -1
    
    @classmethod
    def from_ffprobe_stream(cls, stream: dict[str, Any]) -> "SubtitleStream":
        """Create from ffprobe stream info."""
        disposition = stream.get("disposition", {})
        tags = stream.get("tags", {})
        
        title = tags.get("title", "")
        
        # Detect SDH/CC from title or disposition
        is_sdh = (
            disposition.get("hearing_impaired", 0) == 1
            or "sdh" in title.lower()
            or "cc" in title.lower()
            or "closed caption" in title.lower()
        )
        
        # Detect commentary
        is_commentary = (
            disposition.get("comment", 0) == 1
            or "commentary" in title.lower()
            or "director" in title.lower()
        )
        
        return cls(
            index=stream.get("index", 0),
            codec=stream.get("codec_name", "unknown"),
            language=tags.get("language"),
            title=title,
            is_default=disposition.get("default", 0) == 1,
            is_forced=disposition.get("forced", 0) == 1,
            is_hearing_impaired=is_sdh,
            is_commentary=is_commentary,
            disposition=disposition,
            tags=tags,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "codec": self.codec,
            "language": self.language,
            "language_code": self.language_code,
            "title": self.title,
            "type": self.subtitle_type.value,
            "is_text": self.is_text,
            "is_image": self.is_image,
            "is_default": self.is_default,
            "is_forced": self.is_forced,
            "is_hearing_impaired": self.is_hearing_impaired,
            "is_commentary": self.is_commentary,
        }


@dataclass
class SubtitlePreferences:
    """User preferences for subtitle selection."""
    
    # Language preferences (first = highest priority)
    languages: list[str] = field(default_factory=lambda: ["eng"])
    
    # Type preferences
    prefer_text: bool = True  # Prefer text over image subtitles
    prefer_sdh: bool = False  # Prefer SDH/CC subtitles
    avoid_forced: bool = False  # Avoid forced subtitles
    avoid_commentary: bool = True  # Avoid commentary subtitles
    
    # Fallback behavior
    fallback_to_any: bool = False  # Use any subtitle if no match
    fallback_to_default: bool = True  # Use default stream if no match
    
    # Burn-in settings
    burn_in: bool = True  # Burn subtitles into video
    font_name: str = "Arial"
    font_size: int = 24
    primary_color: str = "&H00FFFFFF"  # White
    outline_color: str = "&H00000000"  # Black
    outline_width: int = 2


class SubtitleStreamPicker:
    """
    Picks the best subtitle stream based on preferences.
    
    Features:
    - Language matching with priority
    - Text vs image preference
    - SDH/CC detection
    - Forced subtitle handling
    - FFmpeg filter generation
    
    Usage:
        picker = SubtitleStreamPicker()
        
        # Parse subtitle streams from ffprobe output
        streams = picker.parse_streams(ffprobe_data)
        
        # Select best subtitle
        selected = picker.select(streams, preferences)
        
        # Get FFmpeg filter for burn-in
        filter_args = picker.get_ffmpeg_args(selected, input_file, preferences)
    """
    
    def parse_streams(
        self,
        ffprobe_data: dict[str, Any],
    ) -> list[SubtitleStream]:
        """
        Parse subtitle streams from ffprobe output.
        
        Args:
            ffprobe_data: FFprobe JSON output
            
        Returns:
            List of SubtitleStream objects
        """
        streams = []
        
        for stream in ffprobe_data.get("streams", []):
            if stream.get("codec_type") == "subtitle":
                sub = SubtitleStream.from_ffprobe_stream(stream)
                streams.append(sub)
                
                logger.debug(
                    f"Found subtitle stream {sub.index}: "
                    f"{sub.language_code} ({sub.codec}) "
                    f"type={sub.subtitle_type.value}"
                )
        
        return streams
    
    def select(
        self,
        streams: list[SubtitleStream],
        preferences: Optional[SubtitlePreferences] = None,
    ) -> Optional[SubtitleStream]:
        """
        Select the best subtitle stream.
        
        Args:
            streams: Available subtitle streams
            preferences: User preferences
            
        Returns:
            Best matching SubtitleStream or None
        """
        if not streams:
            return None
        
        prefs = preferences or SubtitlePreferences()
        
        # Filter out unwanted streams
        candidates = []
        
        for stream in streams:
            # Skip commentary if configured
            if prefs.avoid_commentary and stream.is_commentary:
                continue
            
            # Skip forced if configured
            if prefs.avoid_forced and stream.is_forced:
                continue
            
            candidates.append(stream)
        
        if not candidates:
            candidates = streams  # Fall back to all streams
        
        # Score each candidate
        scored = []
        
        for stream in candidates:
            score = self._calculate_score(stream, prefs)
            scored.append((stream, score))
        
        # Sort by score (higher = better)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        if scored:
            best = scored[0][0]
            logger.debug(
                f"Selected subtitle stream {best.index}: "
                f"{best.language_code} (score={scored[0][1]:.2f})"
            )
            return best
        
        # Fallbacks
        if prefs.fallback_to_default:
            for stream in streams:
                if stream.is_default:
                    return stream
        
        if prefs.fallback_to_any:
            return streams[0]
        
        return None
    
    def _calculate_score(
        self,
        stream: SubtitleStream,
        prefs: SubtitlePreferences,
    ) -> float:
        """Calculate preference score for a stream."""
        score = 0.0
        
        # Language match (most important)
        lang_priority = stream.matches_language(prefs.languages)
        if lang_priority >= 0:
            # Higher priority for earlier languages in preference list
            score += 100 - (lang_priority * 10)
        else:
            score -= 50  # No language match
        
        # Text vs image preference
        if prefs.prefer_text:
            if stream.is_text:
                score += 20
            elif stream.is_image:
                score -= 10
        
        # SDH preference
        if prefs.prefer_sdh and stream.is_hearing_impaired:
            score += 15
        elif not prefs.prefer_sdh and stream.is_hearing_impaired:
            score -= 5
        
        # Default stream bonus
        if stream.is_default:
            score += 5
        
        # Forced subtitle penalty (usually just signs/songs)
        if stream.is_forced:
            score -= 10
        
        return score
    
    def get_ffmpeg_args(
        self,
        stream: SubtitleStream,
        input_file: str,
        preferences: Optional[SubtitlePreferences] = None,
    ) -> list[str]:
        """
        Get FFmpeg arguments for subtitle burn-in.
        
        Args:
            stream: Selected subtitle stream
            input_file: Input file path
            preferences: Subtitle preferences
            
        Returns:
            List of FFmpeg arguments
        """
        prefs = preferences or SubtitlePreferences()
        
        if not prefs.burn_in:
            return []
        
        args = []
        
        if stream.is_text:
            # Use subtitles filter for text subtitles
            # Need to escape special characters in path
            escaped_path = input_file.replace(":", "\\:").replace("'", "\\'")
            
            style = (
                f"FontName={prefs.font_name},"
                f"FontSize={prefs.font_size},"
                f"PrimaryColour={prefs.primary_color},"
                f"OutlineColour={prefs.outline_color},"
                f"Outline={prefs.outline_width}"
            )
            
            filter_str = (
                f"subtitles='{escaped_path}':"
                f"si={stream.index}:"
                f"force_style='{style}'"
            )
            
            args.extend(["-vf", filter_str])
            
        else:
            # Use overlay filter for image subtitles
            # This requires a more complex filter graph
            filter_str = f"[0:s:{stream.index}]scale=iw:ih[sub];[0:v][sub]overlay"
            args.extend(["-filter_complex", filter_str])
        
        return args
    
    def get_map_args(self, stream: SubtitleStream) -> list[str]:
        """
        Get FFmpeg map arguments for subtitle stream.
        
        Args:
            stream: Subtitle stream to map
            
        Returns:
            FFmpeg map arguments
        """
        return ["-map", f"0:s:{stream.index}"]


# Global picker instance
_subtitle_picker: Optional[SubtitleStreamPicker] = None


def get_subtitle_picker() -> SubtitleStreamPicker:
    """Get the global SubtitleStreamPicker instance."""
    global _subtitle_picker
    if _subtitle_picker is None:
        _subtitle_picker = SubtitleStreamPicker()
    return _subtitle_picker
