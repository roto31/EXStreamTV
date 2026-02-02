"""
Audio Stream Picker for intelligent audio track selection.

Ported from Tunarr's audio preferences with enhancements:
- Language preference matching
- Surround vs stereo preference
- Commentary track handling
- Channel count detection

This enables automatic audio track selection based on user
preferences, improving the viewing experience.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AudioLayout(str, Enum):
    """Audio channel layouts."""
    
    MONO = "mono"
    STEREO = "stereo"
    SURROUND_51 = "5.1"
    SURROUND_71 = "7.1"
    ATMOS = "atmos"
    UNKNOWN = "unknown"


class AudioCodec(str, Enum):
    """Common audio codecs."""
    
    AAC = "aac"
    AC3 = "ac3"
    EAC3 = "eac3"
    DTS = "dts"
    DTS_HD = "dts-hd"
    TRUEHD = "truehd"
    FLAC = "flac"
    MP3 = "mp3"
    OPUS = "opus"
    VORBIS = "vorbis"
    PCM = "pcm"


# High quality codecs (lossless or near-lossless)
HIGH_QUALITY_CODECS = {
    "truehd", "dts-hd", "dts_hdma", "flac", "pcm", "pcm_s16le", "pcm_s24le"
}

# Surround sound codecs
SURROUND_CODECS = {
    "ac3", "eac3", "dts", "dts-hd", "truehd", "dca"
}


@dataclass
class AudioStream:
    """Information about an audio stream."""
    
    index: int
    codec: str
    channels: int = 2
    channel_layout: str = "stereo"
    sample_rate: int = 48000
    bit_rate: Optional[int] = None
    language: Optional[str] = None
    title: Optional[str] = None
    
    # Flags
    is_default: bool = False
    is_original: bool = False
    is_commentary: bool = False
    is_dub: bool = False
    is_descriptive: bool = False  # Audio description for visually impaired
    
    # Metadata
    disposition: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    
    @property
    def layout(self) -> AudioLayout:
        """Get audio layout category."""
        if self.channels == 1:
            return AudioLayout.MONO
        elif self.channels == 2:
            return AudioLayout.STEREO
        elif self.channels == 6:
            return AudioLayout.SURROUND_51
        elif self.channels == 8:
            return AudioLayout.SURROUND_71
        elif "atmos" in self.channel_layout.lower():
            return AudioLayout.ATMOS
        else:
            return AudioLayout.UNKNOWN
    
    @property
    def is_surround(self) -> bool:
        """Check if this is surround sound."""
        return self.channels > 2 or self.codec.lower() in SURROUND_CODECS
    
    @property
    def is_stereo(self) -> bool:
        """Check if this is stereo."""
        return self.channels == 2
    
    @property
    def is_high_quality(self) -> bool:
        """Check if this is a high quality codec."""
        return self.codec.lower() in HIGH_QUALITY_CODECS
    
    @property
    def language_code(self) -> str:
        """Get normalized language code."""
        if not self.language:
            return "und"
        
        lang = self.language.lower()[:3]
        
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
        }
        
        return lang_map.get(lang, lang)
    
    def matches_language(self, language_prefs: list[str]) -> int:
        """
        Check if this stream matches language preferences.
        
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
    def from_ffprobe_stream(cls, stream: dict[str, Any]) -> "AudioStream":
        """Create from ffprobe stream info."""
        disposition = stream.get("disposition", {})
        tags = stream.get("tags", {})
        
        title = tags.get("title", "")
        
        # Detect commentary
        is_commentary = (
            disposition.get("comment", 0) == 1
            or "commentary" in title.lower()
            or "director" in title.lower()
        )
        
        # Detect dub
        is_dub = (
            disposition.get("dub", 0) == 1
            or "dub" in title.lower()
        )
        
        # Detect descriptive audio
        is_descriptive = (
            disposition.get("visual_impaired", 0) == 1
            or "descriptive" in title.lower()
            or "audio description" in title.lower()
        )
        
        # Detect original
        is_original = (
            disposition.get("original", 0) == 1
            or "original" in title.lower()
        )
        
        return cls(
            index=stream.get("index", 0),
            codec=stream.get("codec_name", "unknown"),
            channels=stream.get("channels", 2),
            channel_layout=stream.get("channel_layout", "stereo"),
            sample_rate=stream.get("sample_rate", 48000),
            bit_rate=stream.get("bit_rate"),
            language=tags.get("language"),
            title=title,
            is_default=disposition.get("default", 0) == 1,
            is_original=is_original,
            is_commentary=is_commentary,
            is_dub=is_dub,
            is_descriptive=is_descriptive,
            disposition=disposition,
            tags=tags,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "index": self.index,
            "codec": self.codec,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "layout": self.layout.value,
            "sample_rate": self.sample_rate,
            "bit_rate": self.bit_rate,
            "language": self.language,
            "language_code": self.language_code,
            "title": self.title,
            "is_surround": self.is_surround,
            "is_stereo": self.is_stereo,
            "is_high_quality": self.is_high_quality,
            "is_default": self.is_default,
            "is_original": self.is_original,
            "is_commentary": self.is_commentary,
            "is_dub": self.is_dub,
            "is_descriptive": self.is_descriptive,
        }


@dataclass
class AudioPreferences:
    """User preferences for audio selection."""
    
    # Language preferences (first = highest priority)
    languages: list[str] = field(default_factory=lambda: ["eng"])
    
    # Layout preferences
    prefer_surround: bool = True  # Prefer surround over stereo
    prefer_original: bool = True  # Prefer original language
    prefer_high_quality: bool = False  # Prefer lossless codecs
    
    # Avoidance settings
    avoid_commentary: bool = True
    avoid_dub: bool = False
    avoid_descriptive: bool = True
    
    # Fallback behavior
    fallback_to_any: bool = True
    fallback_to_default: bool = True
    
    # Downmix settings (for surround to stereo)
    downmix_to_stereo: bool = False
    stereo_only: bool = False  # Force stereo output


class AudioStreamPicker:
    """
    Picks the best audio stream based on preferences.
    
    Features:
    - Language matching with priority
    - Surround vs stereo preference
    - Commentary filtering
    - Original language preference
    - FFmpeg map generation
    
    Usage:
        picker = AudioStreamPicker()
        
        # Parse audio streams from ffprobe output
        streams = picker.parse_streams(ffprobe_data)
        
        # Select best audio
        selected = picker.select(streams, preferences)
        
        # Get FFmpeg arguments
        args = picker.get_ffmpeg_args(selected, preferences)
    """
    
    def parse_streams(
        self,
        ffprobe_data: dict[str, Any],
    ) -> list[AudioStream]:
        """
        Parse audio streams from ffprobe output.
        
        Args:
            ffprobe_data: FFprobe JSON output
            
        Returns:
            List of AudioStream objects
        """
        streams = []
        
        for stream in ffprobe_data.get("streams", []):
            if stream.get("codec_type") == "audio":
                audio = AudioStream.from_ffprobe_stream(stream)
                streams.append(audio)
                
                logger.debug(
                    f"Found audio stream {audio.index}: "
                    f"{audio.language_code} ({audio.codec}) "
                    f"{audio.channels}ch"
                )
        
        return streams
    
    def select(
        self,
        streams: list[AudioStream],
        preferences: Optional[AudioPreferences] = None,
    ) -> Optional[AudioStream]:
        """
        Select the best audio stream.
        
        Args:
            streams: Available audio streams
            preferences: User preferences
            
        Returns:
            Best matching AudioStream or None
        """
        if not streams:
            return None
        
        prefs = preferences or AudioPreferences()
        
        # Filter out unwanted streams
        candidates = []
        
        for stream in streams:
            # Skip commentary if configured
            if prefs.avoid_commentary and stream.is_commentary:
                continue
            
            # Skip dub if configured
            if prefs.avoid_dub and stream.is_dub:
                continue
            
            # Skip descriptive if configured
            if prefs.avoid_descriptive and stream.is_descriptive:
                continue
            
            # Skip surround if stereo only
            if prefs.stereo_only and stream.is_surround:
                continue
            
            candidates.append(stream)
        
        if not candidates:
            candidates = streams
        
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
                f"Selected audio stream {best.index}: "
                f"{best.language_code} {best.channels}ch (score={scored[0][1]:.2f})"
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
        stream: AudioStream,
        prefs: AudioPreferences,
    ) -> float:
        """Calculate preference score for a stream."""
        score = 0.0
        
        # Language match (most important)
        lang_priority = stream.matches_language(prefs.languages)
        if lang_priority >= 0:
            score += 100 - (lang_priority * 10)
        else:
            score -= 50
        
        # Surround preference
        if prefs.prefer_surround:
            if stream.is_surround:
                score += 30
                # More channels = better
                score += stream.channels * 2
            elif stream.is_stereo:
                score += 10
        else:
            if stream.is_stereo:
                score += 20
            elif stream.is_surround:
                score += 10
        
        # Original language preference
        if prefs.prefer_original and stream.is_original:
            score += 25
        
        # High quality preference
        if prefs.prefer_high_quality and stream.is_high_quality:
            score += 15
        
        # Default stream bonus
        if stream.is_default:
            score += 5
        
        # Penalties
        if stream.is_commentary:
            score -= 50
        if stream.is_dub:
            score -= 20
        if stream.is_descriptive:
            score -= 15
        
        return score
    
    def get_ffmpeg_args(
        self,
        stream: AudioStream,
        preferences: Optional[AudioPreferences] = None,
    ) -> list[str]:
        """
        Get FFmpeg arguments for audio stream.
        
        Args:
            stream: Selected audio stream
            preferences: Audio preferences
            
        Returns:
            List of FFmpeg arguments
        """
        prefs = preferences or AudioPreferences()
        args = []
        
        # Map the selected stream
        args.extend(["-map", f"0:a:{stream.index}"])
        
        # Downmix to stereo if requested
        if prefs.downmix_to_stereo and stream.is_surround:
            args.extend(["-ac", "2"])
            logger.debug(f"Downmixing {stream.channels}ch to stereo")
        
        return args
    
    def get_map_args(self, stream: AudioStream) -> list[str]:
        """
        Get FFmpeg map arguments for audio stream.
        
        Args:
            stream: Audio stream to map
            
        Returns:
            FFmpeg map arguments
        """
        return ["-map", f"0:a:{stream.index}"]


# Global picker instance
_audio_picker: Optional[AudioStreamPicker] = None


def get_audio_picker() -> AudioStreamPicker:
    """Get the global AudioStreamPicker instance."""
    global _audio_picker
    if _audio_picker is None:
        _audio_picker = AudioStreamPicker()
    return _audio_picker
