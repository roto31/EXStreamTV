"""
Build Plan Generator for AI Channel Creation

Generates complete channel build plans including configuration, sources,
collections, schedules, filler, deco, warnings, and module usage.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from exstreamtv.ai_agent.intent_analyzer import AnalyzedIntent, ChannelPurpose, PlayoutPreference
from exstreamtv.ai_agent.source_selector import SourceSelectionResult, SourceType

logger = logging.getLogger(__name__)


class BuildStatus(Enum):
    """Status of the build plan."""
    
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    BUILDING = "building"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlayoutMode(Enum):
    """ErsatzTV playout modes."""
    
    CONTINUOUS = "continuous"
    FLOOD = "flood"
    ONE = "one"
    MULTIPLE = "multiple"
    DURATION = "duration"


@dataclass
class ChannelConfig:
    """Channel configuration."""
    
    name: str
    number: str | None = None
    group: str = "AI Generated"
    description: str = ""
    
    # Streaming settings
    streaming_mode: str = "hls"
    ffmpeg_profile: str = "default"
    
    # Flags
    enabled: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "number": self.number,
            "group": self.group,
            "description": self.description,
            "streaming_mode": self.streaming_mode,
            "ffmpeg_profile": self.ffmpeg_profile,
            "enabled": self.enabled,
        }


@dataclass
class CollectionConfig:
    """Smart collection configuration."""
    
    name: str
    source_type: SourceType
    source_name: str
    
    # Query parameters
    genres: list[str] = field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None
    keywords: list[str] = field(default_factory=list)
    
    # Archive.org specific
    archive_collection: str | None = None
    archive_query: str | None = None
    
    # Plex specific
    plex_library: str | None = None
    plex_filter: dict[str, Any] = field(default_factory=dict)
    
    # Content type
    content_type: str = "mixed"  # movies, shows, episodes, mixed
    
    # Order
    order: str = "chronological"  # chronological, shuffle, random
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "genres": self.genres,
            "year_range": [self.year_min, self.year_max],
            "keywords": self.keywords,
            "archive_collection": self.archive_collection,
            "plex_library": self.plex_library,
            "content_type": self.content_type,
            "order": self.order,
        }


@dataclass
class ScheduleBlock:
    """A block in the schedule."""
    
    name: str
    start_time: str  # HH:MM format
    duration_minutes: int
    
    # Content
    collection_name: str | None = None
    content_type: str = "mixed"
    
    # Playout
    playout_mode: PlayoutMode = PlayoutMode.FLOOD
    
    # Day restrictions
    days_of_week: list[str] = field(default_factory=lambda: [
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ])
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_time": self.start_time,
            "duration_minutes": self.duration_minutes,
            "collection_name": self.collection_name,
            "content_type": self.content_type,
            "playout_mode": self.playout_mode.value,
            "days_of_week": self.days_of_week,
        }


@dataclass
class ScheduleConfig:
    """Complete schedule configuration."""
    
    name: str
    blocks: list[ScheduleBlock] = field(default_factory=list)
    
    # Global settings
    start_on_hour: bool = True
    start_on_half_hour: bool = True
    keep_multi_part_episodes: bool = True
    shuffle_schedule_items: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "blocks": [b.to_dict() for b in self.blocks],
            "start_on_hour": self.start_on_hour,
            "start_on_half_hour": self.start_on_half_hour,
            "keep_multi_part_episodes": self.keep_multi_part_episodes,
            "shuffle_schedule_items": self.shuffle_schedule_items,
        }


@dataclass
class FillerConfig:
    """Filler content configuration."""
    
    enabled: bool = True
    
    # Filler types
    include_commercials: bool = False
    include_bumpers: bool = True
    include_trailers: bool = False
    
    # Commercial settings
    commercial_source: str = "archive_org"
    commercial_collection: str = "prelinger"
    commercial_style: str = "vintage"
    breaks_per_hour: int = 2
    break_duration_seconds: int = 120
    
    # Filler mode
    mode: str = "duration"  # duration, count, pad_to_boundary
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "include_commercials": self.include_commercials,
            "include_bumpers": self.include_bumpers,
            "include_trailers": self.include_trailers,
            "commercial_source": self.commercial_source,
            "commercial_collection": self.commercial_collection,
            "commercial_style": self.commercial_style,
            "breaks_per_hour": self.breaks_per_hour,
            "break_duration_seconds": self.break_duration_seconds,
            "mode": self.mode,
        }


@dataclass
class DecoConfig:
    """Deco (watermarks, bumpers, station IDs) configuration."""
    
    # Watermark
    watermark_enabled: bool = False
    watermark_path: str | None = None
    watermark_position: str = "top_right"
    watermark_opacity: float = 0.7
    
    # Station IDs
    station_id_enabled: bool = True
    station_id_frequency_minutes: int = 30
    
    # Bumpers
    bumpers_enabled: bool = True
    bumper_position: str = "between_shows"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "watermark": {
                "enabled": self.watermark_enabled,
                "path": self.watermark_path,
                "position": self.watermark_position,
                "opacity": self.watermark_opacity,
            },
            "station_id": {
                "enabled": self.station_id_enabled,
                "frequency_minutes": self.station_id_frequency_minutes,
            },
            "bumpers": {
                "enabled": self.bumpers_enabled,
                "position": self.bumper_position,
            },
        }


@dataclass
class BuildWarning:
    """Warning about the build plan."""
    
    level: str  # info, warning, error
    message: str
    category: str  # content, source, schedule, config
    suggestion: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "message": self.message,
            "category": self.category,
            "suggestion": self.suggestion,
        }


@dataclass
class ModuleUsage:
    """Modules that will be used in the build."""
    
    # Core modules
    channel_api: bool = True
    collection_api: bool = True
    schedule_api: bool = True
    playout_api: bool = True
    
    # Optional modules
    archive_org: bool = False
    youtube: bool = False
    tmdb: bool = False
    
    # Features
    filler_system: bool = False
    deco_system: bool = False
    watermarks: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "core": {
                "channel_api": self.channel_api,
                "collection_api": self.collection_api,
                "schedule_api": self.schedule_api,
                "playout_api": self.playout_api,
            },
            "external": {
                "archive_org": self.archive_org,
                "youtube": self.youtube,
                "tmdb": self.tmdb,
            },
            "features": {
                "filler_system": self.filler_system,
                "deco_system": self.deco_system,
                "watermarks": self.watermarks,
            },
        }


@dataclass
class BuildPlan:
    """
    Complete build plan for an AI-generated channel.
    
    Contains all configuration, sources, collections, schedules,
    filler, deco, warnings, and module usage information.
    """
    
    # Metadata
    plan_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: BuildStatus = BuildStatus.DRAFT
    
    # Original request
    original_request: str = ""
    persona_used: str = "tv_executive"
    
    # Core configuration
    channel: ChannelConfig = field(default_factory=lambda: ChannelConfig(name="New Channel"))
    
    # Content
    collections: list[CollectionConfig] = field(default_factory=list)
    schedule: ScheduleConfig | None = None
    
    # Extras
    filler: FillerConfig = field(default_factory=FillerConfig)
    deco: DecoConfig = field(default_factory=DecoConfig)
    
    # Analysis
    source_selection: SourceSelectionResult | None = None
    intent: AnalyzedIntent | None = None
    
    # Warnings and notes
    warnings: list[BuildWarning] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    
    # Module usage
    modules: ModuleUsage = field(default_factory=ModuleUsage)
    
    # Estimated content
    estimated_content_hours: float = 0.0
    estimated_unique_items: int = 0
    
    def is_ready(self) -> bool:
        """Check if plan is ready for building."""
        return (
            self.status == BuildStatus.READY
            and self.channel.name
            and len(self.collections) > 0
            and not any(w.level == "error" for w in self.warnings)
        )
    
    def approve(self) -> None:
        """Approve the plan for building."""
        if self.status == BuildStatus.READY:
            self.status = BuildStatus.APPROVED
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "original_request": self.original_request,
            "persona_used": self.persona_used,
            "channel": self.channel.to_dict(),
            "collections": [c.to_dict() for c in self.collections],
            "schedule": self.schedule.to_dict() if self.schedule else None,
            "filler": self.filler.to_dict(),
            "deco": self.deco.to_dict(),
            "source_selection": self.source_selection.to_dict() if self.source_selection else None,
            "intent": self.intent.to_dict() if self.intent else None,
            "warnings": [w.to_dict() for w in self.warnings],
            "notes": self.notes,
            "modules": self.modules.to_dict(),
            "estimated_content_hours": self.estimated_content_hours,
            "estimated_unique_items": self.estimated_unique_items,
            "is_ready": self.is_ready(),
        }


class BuildPlanGenerator:
    """
    Generates complete build plans from analyzed intent and source selection.
    
    Creates all necessary configurations for channel, collections,
    schedules, filler, and deco based on user requirements.
    """
    
    # Default daypart schedule templates
    DAYPART_TEMPLATES = {
        "classic_tv": [
            ScheduleBlock(name="Morning", start_time="06:00", duration_minutes=360, content_type="mixed"),
            ScheduleBlock(name="Daytime", start_time="12:00", duration_minutes=360, content_type="mixed"),
            ScheduleBlock(name="Primetime", start_time="20:00", duration_minutes=180, content_type="features"),
            ScheduleBlock(name="Late Night", start_time="23:00", duration_minutes=120, content_type="mixed"),
            ScheduleBlock(name="Overnight", start_time="01:00", duration_minutes=300, content_type="filler"),
        ],
        "movies": [
            ScheduleBlock(name="Morning Movie", start_time="08:00", duration_minutes=180, content_type="movies"),
            ScheduleBlock(name="Afternoon Feature", start_time="14:00", duration_minutes=180, content_type="movies"),
            ScheduleBlock(name="Primetime Feature", start_time="20:00", duration_minutes=180, content_type="movies"),
            ScheduleBlock(name="Late Night", start_time="23:30", duration_minutes=150, content_type="movies"),
        ],
        "kids": [
            ScheduleBlock(name="Early Morning", start_time="06:00", duration_minutes=180, content_type="preschool"),
            ScheduleBlock(name="Morning Cartoons", start_time="09:00", duration_minutes=180, content_type="animation"),
            ScheduleBlock(name="Afternoon", start_time="12:00", duration_minutes=240, content_type="mixed"),
            ScheduleBlock(name="After School", start_time="16:00", duration_minutes=180, content_type="animation"),
            ScheduleBlock(name="Family Time", start_time="19:00", duration_minutes=120, content_type="movies"),
        ],
        "documentary": [
            ScheduleBlock(name="Morning Docs", start_time="08:00", duration_minutes=240, content_type="documentary"),
            ScheduleBlock(name="Afternoon", start_time="14:00", duration_minutes=240, content_type="documentary"),
            ScheduleBlock(name="Primetime Feature", start_time="20:00", duration_minutes=180, content_type="documentary"),
            ScheduleBlock(name="Late Night", start_time="23:00", duration_minutes=120, content_type="documentary"),
        ],
        "sports": [
            ScheduleBlock(name="Morning Highlights", start_time="07:00", duration_minutes=180, content_type="highlights"),
            ScheduleBlock(name="Classic Game", start_time="12:00", duration_minutes=240, content_type="games"),
            ScheduleBlock(name="Afternoon Feature", start_time="16:00", duration_minutes=240, content_type="games"),
            ScheduleBlock(name="Primetime Game", start_time="20:00", duration_minutes=240, content_type="games"),
        ],
    }
    
    def __init__(self):
        """Initialize the build plan generator."""
        logger.info("BuildPlanGenerator initialized")
    
    def generate(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
        persona_id: str = "tv_executive",
    ) -> BuildPlan:
        """
        Generate a complete build plan.
        
        Args:
            intent: Analyzed user intent
            sources: Source selection result
            persona_id: Persona that was used
            
        Returns:
            Complete BuildPlan
        """
        import uuid
        
        plan = BuildPlan(
            plan_id=str(uuid.uuid4()),
            original_request=intent.raw_request,
            persona_used=persona_id,
            intent=intent,
            source_selection=sources,
        )
        
        # Generate channel config
        plan.channel = self._generate_channel_config(intent)
        
        # Generate collections based on sources
        plan.collections = self._generate_collections(intent, sources)
        
        # Generate schedule
        plan.schedule = self._generate_schedule(intent, plan.collections)
        
        # Generate filler config
        plan.filler = self._generate_filler_config(intent)
        
        # Generate deco config
        plan.deco = self._generate_deco_config(intent)
        
        # Determine module usage
        plan.modules = self._determine_modules(sources, plan)
        
        # Estimate content
        plan.estimated_content_hours, plan.estimated_unique_items = self._estimate_content(plan)
        
        # Generate warnings
        plan.warnings = self._generate_warnings(plan)
        
        # Generate notes
        plan.notes = self._generate_notes(plan, intent, sources)
        
        # Set status
        if plan.warnings and any(w.level == "error" for w in plan.warnings):
            plan.status = BuildStatus.DRAFT
        else:
            plan.status = BuildStatus.READY
        
        logger.info(f"Generated build plan {plan.plan_id} with status {plan.status.value}")
        
        return plan
    
    def _generate_channel_config(self, intent: AnalyzedIntent) -> ChannelConfig:
        """Generate channel configuration from intent."""
        return ChannelConfig(
            name=intent.suggested_name or "AI Channel",
            number=intent.suggested_number,
            group="AI Generated",
            description=intent.description or f"Channel created for: {intent.purpose.value}",
        )
    
    def _generate_collections(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
    ) -> list[CollectionConfig]:
        """Generate collection configurations."""
        collections = []
        
        # Create a collection for each recommended source
        for i, source_type in enumerate(sources.recommended_combination):
            source_ranking = next(
                (r for r in sources.rankings if r.source_type == source_type),
                None
            )
            
            if not source_ranking:
                continue
            
            # Determine collection name
            purpose_name = intent.purpose.value.title()
            collection_name = f"{purpose_name} - {source_type.value.title()}"
            
            collection = CollectionConfig(
                name=collection_name,
                source_type=source_type,
                source_name=source_ranking.source_name,
                genres=intent.content.genres,
                year_min=intent.content.year_range[0] if intent.content.year_range else None,
                year_max=intent.content.year_range[1] if intent.content.year_range else None,
                keywords=intent.content.keywords,
            )
            
            # Source-specific settings
            if source_type == SourceType.ARCHIVE_ORG:
                collection.archive_collection = self._get_archive_collection(intent)
                
            elif source_type == SourceType.PLEX:
                if source_ranking.recommended_libraries:
                    collection.plex_library = source_ranking.recommended_libraries[0]
            
            collections.append(collection)
        
        # If no collections, create a default
        if not collections:
            collections.append(CollectionConfig(
                name="Main Content",
                source_type=SourceType.PLEX,
                source_name="Plex Media Server",
                genres=intent.content.genres,
            ))
        
        return collections
    
    def _generate_schedule(
        self,
        intent: AnalyzedIntent,
        collections: list[CollectionConfig],
    ) -> ScheduleConfig:
        """Generate schedule configuration."""
        # Determine template based on purpose
        purpose_template_map = {
            ChannelPurpose.MOVIES: "movies",
            ChannelPurpose.KIDS: "kids",
            ChannelPurpose.DOCUMENTARY: "documentary",
            ChannelPurpose.SPORTS: "sports",
            ChannelPurpose.EDUCATIONAL: "documentary",
        }
        
        template_name = purpose_template_map.get(intent.purpose, "classic_tv")
        template_blocks = self.DAYPART_TEMPLATES.get(template_name, self.DAYPART_TEMPLATES["classic_tv"])
        
        # Create schedule with blocks
        schedule = ScheduleConfig(
            name=f"{intent.suggested_name or 'Channel'} Schedule",
            blocks=template_blocks.copy(),
            start_on_hour=intent.scheduling.is_24_hour,
            start_on_half_hour=True,
        )
        
        # Assign collections to blocks
        if collections:
            primary_collection = collections[0].name
            for block in schedule.blocks:
                block.collection_name = primary_collection
        
        return schedule
    
    def _generate_filler_config(self, intent: AnalyzedIntent) -> FillerConfig:
        """Generate filler configuration."""
        filler = FillerConfig(
            enabled=True,
            include_commercials=intent.filler.include_commercials,
            include_bumpers=intent.filler.include_bumpers,
            include_trailers=intent.filler.include_trailers,
            commercial_style=intent.filler.commercial_style,
        )
        
        # Adjust based on purpose
        if intent.purpose == ChannelPurpose.KIDS:
            filler.include_commercials = False
            filler.include_bumpers = True
            
        elif intent.purpose in [ChannelPurpose.RETRO, ChannelPurpose.ENTERTAINMENT]:
            filler.include_commercials = True
            filler.commercial_style = "vintage"
        
        return filler
    
    def _generate_deco_config(self, intent: AnalyzedIntent) -> DecoConfig:
        """Generate deco configuration."""
        deco = DecoConfig(
            station_id_enabled=True,
            bumpers_enabled=True,
        )
        
        # PBS-style channels might want more formal branding
        if intent.purpose in [ChannelPurpose.DOCUMENTARY, ChannelPurpose.EDUCATIONAL]:
            deco.station_id_frequency_minutes = 60
            
        return deco
    
    def _determine_modules(
        self,
        sources: SourceSelectionResult,
        plan: BuildPlan,
    ) -> ModuleUsage:
        """Determine which modules will be used."""
        modules = ModuleUsage()
        
        # Check sources
        for source_type in sources.recommended_combination:
            if source_type == SourceType.ARCHIVE_ORG:
                modules.archive_org = True
            elif source_type == SourceType.YOUTUBE:
                modules.youtube = True
        
        # Check features
        if plan.filler.enabled:
            modules.filler_system = True
            
        if plan.deco.watermark_enabled or plan.deco.station_id_enabled:
            modules.deco_system = True
            
        if plan.deco.watermark_enabled:
            modules.watermarks = True
        
        return modules
    
    def _estimate_content(self, plan: BuildPlan) -> tuple[float, int]:
        """Estimate content hours and unique items."""
        hours = 0.0
        items = 0
        
        if plan.source_selection:
            for ranking in plan.source_selection.rankings:
                if ranking.source_type in plan.source_selection.recommended_combination:
                    items += ranking.matching_count
                    # Estimate 45 min average per item
                    hours += ranking.matching_count * 0.75
        
        return hours, items
    
    def _generate_warnings(self, plan: BuildPlan) -> list[BuildWarning]:
        """Generate warnings about the plan."""
        warnings = []
        
        # Check for content availability
        if plan.estimated_unique_items == 0:
            warnings.append(BuildWarning(
                level="error",
                message="No matching content found",
                category="content",
                suggestion="Broaden search criteria or add more sources",
            ))
        elif plan.estimated_unique_items < 10:
            warnings.append(BuildWarning(
                level="warning",
                message="Limited content available - may cause repetition",
                category="content",
                suggestion="Consider adding more genres or sources",
            ))
        
        # Check collections
        if not plan.collections:
            warnings.append(BuildWarning(
                level="error",
                message="No collections configured",
                category="config",
            ))
        
        # Check for Archive.org dependency
        if plan.modules.archive_org:
            warnings.append(BuildWarning(
                level="info",
                message="Using Archive.org content - quality may vary",
                category="source",
            ))
        
        # Check YouTube dependency
        if plan.modules.youtube:
            warnings.append(BuildWarning(
                level="warning",
                message="YouTube content availability may change over time",
                category="source",
            ))
        
        return warnings
    
    def _generate_notes(
        self,
        plan: BuildPlan,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
    ) -> list[str]:
        """Generate helpful notes about the plan."""
        notes = []
        
        notes.append(f"Channel purpose: {intent.purpose.value}")
        notes.append(f"Content era: {intent.content.era.value}")
        
        if intent.content.genres:
            notes.append(f"Genres: {', '.join(intent.content.genres)}")
        
        if sources.primary_source:
            notes.append(f"Primary source: {sources.primary_source.source_name}")
        
        if plan.collections:
            notes.append(f"Collections to create: {len(plan.collections)}")
        
        if plan.schedule and plan.schedule.blocks:
            notes.append(f"Schedule blocks: {len(plan.schedule.blocks)}")
        
        return notes
    
    def _get_archive_collection(self, intent: AnalyzedIntent) -> str:
        """Get appropriate Archive.org collection for intent."""
        collection_map = {
            ChannelPurpose.MOVIES: "feature_films",
            ChannelPurpose.DOCUMENTARY: "prelinger",
            ChannelPurpose.EDUCATIONAL: "prelinger",
            ChannelPurpose.RETRO: "classic_tv",
            ChannelPurpose.SPORTS: "sports_films",
        }
        
        # Check for noir genre
        if "noir" in intent.content.genres:
            return "film_noir"
        
        return collection_map.get(intent.purpose, "feature_films")
    
    def modify_plan(
        self,
        plan: BuildPlan,
        modifications: dict[str, Any],
    ) -> BuildPlan:
        """
        Modify an existing build plan.
        
        Args:
            plan: The plan to modify
            modifications: Dict of modifications to apply
            
        Returns:
            Modified BuildPlan
        """
        if "channel_name" in modifications:
            plan.channel.name = modifications["channel_name"]
        
        if "channel_number" in modifications:
            plan.channel.number = modifications["channel_number"]
        
        if "add_collection" in modifications:
            collection_data = modifications["add_collection"]
            plan.collections.append(CollectionConfig(**collection_data))
        
        if "remove_collection" in modifications:
            name = modifications["remove_collection"]
            plan.collections = [c for c in plan.collections if c.name != name]
        
        if "filler_enabled" in modifications:
            plan.filler.enabled = modifications["filler_enabled"]
        
        if "commercials_enabled" in modifications:
            plan.filler.include_commercials = modifications["commercials_enabled"]
        
        # Regenerate warnings after modification
        plan.warnings = self._generate_warnings(plan)
        
        # Update status
        if any(w.level == "error" for w in plan.warnings):
            plan.status = BuildStatus.DRAFT
        else:
            plan.status = BuildStatus.READY
        
        return plan
