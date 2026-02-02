"""
Deco Integrator for AI Channel Creation

Suggests and configures channel decoration elements based on channel theme:
- Watermarks (corner logos, network bugs)
- Bumpers (transition graphics between programs)
- Station IDs (periodic channel identification clips)
- Interstitials (promos, PSAs, short clips between shows)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DecoType(Enum):
    """Types of channel decoration elements."""
    
    WATERMARK = "watermark"
    BUMPER = "bumper"
    STATION_ID = "station_id"
    INTERSTITIAL = "interstitial"
    LOWER_THIRD = "lower_third"


class WatermarkPosition(Enum):
    """Watermark position on screen."""
    
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"


class WatermarkStyle(Enum):
    """Watermark visual style."""
    
    SOLID = "solid"
    TRANSPARENT = "transparent"
    ANIMATED = "animated"
    FADE_IN_OUT = "fade_in_out"


@dataclass
class WatermarkConfig:
    """Configuration for a channel watermark/logo bug."""
    
    enabled: bool = True
    image_path: str | None = None
    position: WatermarkPosition = WatermarkPosition.BOTTOM_RIGHT
    style: WatermarkStyle = WatermarkStyle.TRANSPARENT
    opacity: float = 0.7  # 0.0 to 1.0
    size_percent: int = 8  # Percentage of screen width
    margin_x: int = 20  # Pixels from edge
    margin_y: int = 20
    show_during_commercials: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "image_path": self.image_path,
            "position": self.position.value,
            "style": self.style.value,
            "opacity": self.opacity,
            "size_percent": self.size_percent,
            "margin_x": self.margin_x,
            "margin_y": self.margin_y,
            "show_during_commercials": self.show_during_commercials,
        }


@dataclass
class BumperConfig:
    """Configuration for bumpers (transition elements)."""
    
    enabled: bool = True
    pre_program: bool = True  # Show before programs
    post_program: bool = True  # Show after programs
    between_segments: bool = False  # Show between commercial breaks
    video_paths: list[str] = field(default_factory=list)
    audio_paths: list[str] = field(default_factory=list)
    duration_seconds: float = 3.0
    fade_in: bool = True
    fade_out: bool = True
    archive_org_collection: str | None = None  # Archive.org collection for bumpers
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "pre_program": self.pre_program,
            "post_program": self.post_program,
            "between_segments": self.between_segments,
            "video_paths": self.video_paths,
            "audio_paths": self.audio_paths,
            "duration_seconds": self.duration_seconds,
            "fade_in": self.fade_in,
            "fade_out": self.fade_out,
            "archive_org_collection": self.archive_org_collection,
        }


@dataclass
class StationIdConfig:
    """Configuration for station identification clips."""
    
    enabled: bool = True
    frequency_minutes: int = 60  # How often to show
    video_paths: list[str] = field(default_factory=list)
    text_overlay: str | None = None  # "Channel 5" etc.
    duration_seconds: float = 10.0
    show_at_top_of_hour: bool = True
    show_at_half_hour: bool = False
    archive_org_collection: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "frequency_minutes": self.frequency_minutes,
            "video_paths": self.video_paths,
            "text_overlay": self.text_overlay,
            "duration_seconds": self.duration_seconds,
            "show_at_top_of_hour": self.show_at_top_of_hour,
            "show_at_half_hour": self.show_at_half_hour,
            "archive_org_collection": self.archive_org_collection,
        }


@dataclass
class InterstitialConfig:
    """Configuration for interstitial content."""
    
    enabled: bool = True
    types: list[str] = field(default_factory=lambda: ["promo", "psa"])
    frequency_per_hour: int = 2
    max_duration_seconds: float = 60.0
    sources: list[str] = field(default_factory=list)
    archive_org_collections: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "types": self.types,
            "frequency_per_hour": self.frequency_per_hour,
            "max_duration_seconds": self.max_duration_seconds,
            "sources": self.sources,
            "archive_org_collections": self.archive_org_collections,
        }


@dataclass
class DecoConfiguration:
    """Complete decoration configuration for a channel."""
    
    watermark: WatermarkConfig = field(default_factory=WatermarkConfig)
    bumpers: BumperConfig = field(default_factory=BumperConfig)
    station_id: StationIdConfig = field(default_factory=StationIdConfig)
    interstitials: InterstitialConfig = field(default_factory=InterstitialConfig)
    theme: str = "default"
    era: str | None = None  # "1970s", "1980s", etc. for period-appropriate deco
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "watermark": self.watermark.to_dict(),
            "bumpers": self.bumpers.to_dict(),
            "station_id": self.station_id.to_dict(),
            "interstitials": self.interstitials.to_dict(),
            "theme": self.theme,
            "era": self.era,
        }
    
    @property
    def has_any_enabled(self) -> bool:
        """Check if any deco element is enabled."""
        return (
            self.watermark.enabled
            or self.bumpers.enabled
            or self.station_id.enabled
            or self.interstitials.enabled
        )


class DecoIntegrator:
    """
    Integrates decoration elements into channel creation.
    
    Suggests appropriate deco based on:
    - Channel theme and era
    - Content type (movies, TV, sports)
    - User preferences
    - Available assets (local, Archive.org)
    """
    
    # Archive.org collections for various deco types
    ARCHIVE_ORG_COLLECTIONS = {
        "bumpers": {
            "1970s": ["classic_tv_bumpers", "retro_tv_graphics"],
            "1980s": ["80s_tv_bumpers", "mtv_graphics"],
            "1990s": ["90s_tv_graphics", "nickelodeon_bumpers"],
            "generic": ["tv_station_ids", "broadcast_graphics"],
        },
        "station_ids": {
            "network": ["network_station_ids", "local_tv_ids"],
            "cable": ["cable_tv_ids", "hbo_intros"],
            "public": ["pbs_station_ids", "public_tv"],
        },
        "interstitials": {
            "psa": ["public_service_announcements", "classic_psas"],
            "promo": ["tv_promos", "network_promos"],
            "educational": ["schoolhouse_rock", "educational_shorts"],
        },
    }
    
    # Theme presets
    THEME_PRESETS = {
        "classic_network": {
            "watermark": {"position": "bottom_right", "opacity": 0.5},
            "bumpers": {"duration_seconds": 5.0},
            "station_id": {"frequency_minutes": 30},
        },
        "cable_channel": {
            "watermark": {"position": "bottom_right", "opacity": 0.8},
            "bumpers": {"duration_seconds": 3.0},
            "station_id": {"frequency_minutes": 60},
        },
        "streaming": {
            "watermark": {"enabled": False},
            "bumpers": {"enabled": False},
            "station_id": {"enabled": False},
        },
        "retro_tv": {
            "watermark": {"position": "bottom_right", "opacity": 0.6, "style": "solid"},
            "bumpers": {"duration_seconds": 8.0, "fade_in": True},
            "station_id": {"frequency_minutes": 30, "show_at_top_of_hour": True},
        },
        "movie_channel": {
            "watermark": {"position": "top_right", "opacity": 0.4},
            "bumpers": {"pre_program": True, "post_program": False},
            "station_id": {"frequency_minutes": 120},
        },
        "kids_channel": {
            "watermark": {"position": "bottom_left", "opacity": 0.6},
            "bumpers": {"duration_seconds": 4.0},
            "station_id": {"frequency_minutes": 30},
            "interstitials": {"types": ["educational", "psa"]},
        },
        "sports_channel": {
            "watermark": {"position": "top_left", "opacity": 0.7},
            "bumpers": {"enabled": False},
            "station_id": {"show_at_half_hour": True},
        },
        "documentary": {
            "watermark": {"position": "bottom_right", "opacity": 0.3},
            "bumpers": {"duration_seconds": 2.0},
            "station_id": {"frequency_minutes": 60},
        },
    }
    
    def __init__(self):
        """Initialize the deco integrator."""
        logger.info("DecoIntegrator initialized")
    
    def suggest_deco(
        self,
        channel_name: str,
        genres: list[str],
        era: str | None = None,
        theme: str | None = None,
        prefer_archive_org: bool = True,
    ) -> DecoConfiguration:
        """
        Suggest decoration configuration based on channel characteristics.
        
        Args:
            channel_name: Name of the channel
            genres: List of content genres
            era: Era/decade for period-appropriate deco (e.g., "1980s")
            theme: Theme preset name (e.g., "retro_tv", "movie_channel")
            prefer_archive_org: Whether to prefer Archive.org sources
            
        Returns:
            DecoConfiguration with suggested settings
        """
        # Start with defaults
        config = DecoConfiguration()
        config.era = era
        
        # Determine theme from genres if not specified
        if not theme:
            theme = self._infer_theme(genres)
        
        config.theme = theme
        
        # Apply theme preset
        preset = self.THEME_PRESETS.get(theme, {})
        self._apply_preset(config, preset)
        
        # Suggest Archive.org sources
        if prefer_archive_org:
            self._suggest_archive_sources(config, era, genres)
        
        # Set station ID text
        if channel_name:
            config.station_id.text_overlay = channel_name
        
        logger.info(f"Suggested deco for '{channel_name}': theme={theme}, era={era}")
        
        return config
    
    def _infer_theme(self, genres: list[str]) -> str:
        """Infer appropriate theme from genres."""
        genres_lower = [g.lower() for g in genres]
        
        if any(g in genres_lower for g in ["movie", "film", "cinema"]):
            return "movie_channel"
        
        if any(g in genres_lower for g in ["kids", "children", "cartoon", "animation"]):
            return "kids_channel"
        
        if any(g in genres_lower for g in ["sports", "football", "basketball", "baseball"]):
            return "sports_channel"
        
        if any(g in genres_lower for g in ["documentary", "nature", "science"]):
            return "documentary"
        
        if any(g in genres_lower for g in ["classic", "retro", "vintage"]):
            return "retro_tv"
        
        return "classic_network"
    
    def _apply_preset(self, config: DecoConfiguration, preset: dict[str, Any]) -> None:
        """Apply a theme preset to the configuration."""
        if "watermark" in preset:
            wm = preset["watermark"]
            if "enabled" in wm:
                config.watermark.enabled = wm["enabled"]
            if "position" in wm:
                config.watermark.position = WatermarkPosition(wm["position"])
            if "opacity" in wm:
                config.watermark.opacity = wm["opacity"]
            if "style" in wm:
                config.watermark.style = WatermarkStyle(wm["style"])
        
        if "bumpers" in preset:
            bm = preset["bumpers"]
            if "enabled" in bm:
                config.bumpers.enabled = bm["enabled"]
            if "duration_seconds" in bm:
                config.bumpers.duration_seconds = bm["duration_seconds"]
            if "pre_program" in bm:
                config.bumpers.pre_program = bm["pre_program"]
            if "post_program" in bm:
                config.bumpers.post_program = bm["post_program"]
            if "fade_in" in bm:
                config.bumpers.fade_in = bm["fade_in"]
        
        if "station_id" in preset:
            sid = preset["station_id"]
            if "enabled" in sid:
                config.station_id.enabled = sid["enabled"]
            if "frequency_minutes" in sid:
                config.station_id.frequency_minutes = sid["frequency_minutes"]
            if "show_at_top_of_hour" in sid:
                config.station_id.show_at_top_of_hour = sid["show_at_top_of_hour"]
            if "show_at_half_hour" in sid:
                config.station_id.show_at_half_hour = sid["show_at_half_hour"]
        
        if "interstitials" in preset:
            inter = preset["interstitials"]
            if "types" in inter:
                config.interstitials.types = inter["types"]
            if "enabled" in inter:
                config.interstitials.enabled = inter["enabled"]
    
    def _suggest_archive_sources(
        self,
        config: DecoConfiguration,
        era: str | None,
        genres: list[str],
    ) -> None:
        """Suggest Archive.org sources for deco elements."""
        # Bumpers
        if config.bumpers.enabled:
            era_key = self._normalize_era(era)
            bumper_collections = self.ARCHIVE_ORG_COLLECTIONS["bumpers"].get(
                era_key, self.ARCHIVE_ORG_COLLECTIONS["bumpers"]["generic"]
            )
            if bumper_collections:
                config.bumpers.archive_org_collection = bumper_collections[0]
        
        # Station IDs
        if config.station_id.enabled:
            # Determine type based on theme
            if config.theme in ["movie_channel", "cable_channel"]:
                sid_type = "cable"
            elif config.theme in ["documentary", "kids_channel"]:
                sid_type = "public"
            else:
                sid_type = "network"
            
            sid_collections = self.ARCHIVE_ORG_COLLECTIONS["station_ids"].get(sid_type, [])
            if sid_collections:
                config.station_id.archive_org_collection = sid_collections[0]
        
        # Interstitials
        if config.interstitials.enabled:
            inter_collections = []
            for inter_type in config.interstitials.types:
                type_collections = self.ARCHIVE_ORG_COLLECTIONS["interstitials"].get(inter_type, [])
                inter_collections.extend(type_collections)
            config.interstitials.archive_org_collections = list(set(inter_collections))
    
    def _normalize_era(self, era: str | None) -> str:
        """Normalize era string to key format."""
        if not era:
            return "generic"
        
        era_lower = era.lower()
        
        if "70" in era_lower or "seventi" in era_lower:
            return "1970s"
        if "80" in era_lower or "eighti" in era_lower:
            return "1980s"
        if "90" in era_lower or "ninet" in era_lower:
            return "1990s"
        
        return "generic"
    
    def create_minimal_deco(self, channel_name: str) -> DecoConfiguration:
        """Create minimal deco configuration (watermark only)."""
        config = DecoConfiguration(
            watermark=WatermarkConfig(enabled=True),
            bumpers=BumperConfig(enabled=False),
            station_id=StationIdConfig(enabled=False),
            interstitials=InterstitialConfig(enabled=False),
            theme="minimal",
        )
        config.station_id.text_overlay = channel_name
        return config
    
    def create_full_deco(
        self,
        channel_name: str,
        era: str,
    ) -> DecoConfiguration:
        """Create full deco configuration with all elements enabled."""
        config = DecoConfiguration(
            watermark=WatermarkConfig(enabled=True),
            bumpers=BumperConfig(enabled=True),
            station_id=StationIdConfig(enabled=True),
            interstitials=InterstitialConfig(enabled=True),
            theme="retro_tv",
            era=era,
        )
        config.station_id.text_overlay = channel_name
        self._suggest_archive_sources(config, era, [])
        return config
    
    def validate_deco(self, config: DecoConfiguration) -> list[str]:
        """
        Validate a deco configuration.
        
        Returns list of warning messages (empty if valid).
        """
        warnings = []
        
        # Check watermark
        if config.watermark.enabled:
            if config.watermark.opacity < 0.1:
                warnings.append("Watermark opacity is very low, may not be visible")
            if config.watermark.opacity > 0.9:
                warnings.append("Watermark opacity is very high, may be distracting")
        
        # Check bumpers
        if config.bumpers.enabled:
            if config.bumpers.duration_seconds > 15:
                warnings.append("Bumper duration over 15 seconds may be too long")
            if not config.bumpers.video_paths and not config.bumpers.archive_org_collection:
                warnings.append("No bumper sources configured")
        
        # Check station IDs
        if config.station_id.enabled:
            if config.station_id.frequency_minutes < 15:
                warnings.append("Station ID frequency under 15 minutes may be intrusive")
            if not config.station_id.video_paths and not config.station_id.archive_org_collection:
                if not config.station_id.text_overlay:
                    warnings.append("No station ID sources or text configured")
        
        return warnings
    
    def get_available_themes(self) -> dict[str, str]:
        """Get list of available theme presets with descriptions."""
        descriptions = {
            "classic_network": "Traditional broadcast network style with subtle branding",
            "cable_channel": "Cable TV style with prominent branding",
            "streaming": "Modern streaming style with minimal decoration",
            "retro_tv": "Vintage TV experience with period-appropriate deco",
            "movie_channel": "Movie channel style with minimal interruption",
            "kids_channel": "Child-friendly with educational interstitials",
            "sports_channel": "Sports network style with scoreboard-friendly positioning",
            "documentary": "Documentary channel with subtle branding",
        }
        return descriptions
