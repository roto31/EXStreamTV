"""
Method Selector for AI Channel Creation

Analyzes the user's intent, available sources, and system capabilities
to recommend the optimal channel creation approach.

Creation Methods:
- direct_api: Use API endpoints to create channel programmatically
- scripted_build: Execute a multi-step build script
- yaml_import: Import from YAML configuration file
- m3u_import: Import from M3U/M3U8 playlist file
- template_based: Use predefined channel template
- hybrid: Combination of methods
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from exstreamtv.ai_agent.intent_analyzer import AnalyzedIntent, ChannelPurpose
from exstreamtv.ai_agent.source_selector import SourceSelectionResult, SourceType

logger = logging.getLogger(__name__)


class CreationMethod(Enum):
    """Available channel creation methods."""
    
    DIRECT_API = "direct_api"
    SCRIPTED_BUILD = "scripted_build"
    YAML_IMPORT = "yaml_import"
    M3U_IMPORT = "m3u_import"
    TEMPLATE_BASED = "template_based"
    HYBRID = "hybrid"
    
    @property
    def display_name(self) -> str:
        """Get human-readable name."""
        names = {
            self.DIRECT_API: "Direct API Creation",
            self.SCRIPTED_BUILD: "Scripted Multi-Step Build",
            self.YAML_IMPORT: "YAML Configuration Import",
            self.M3U_IMPORT: "M3U Playlist Import",
            self.TEMPLATE_BASED: "Template-Based Creation",
            self.HYBRID: "Hybrid Approach",
        }
        return names.get(self, self.value)
    
    @property
    def description(self) -> str:
        """Get method description."""
        descriptions = {
            self.DIRECT_API: "Creates channel using direct API calls. Fast and straightforward for simple channels.",
            self.SCRIPTED_BUILD: "Executes a multi-step build process with collections, schedules, and playouts.",
            self.YAML_IMPORT: "Imports channel from a YAML configuration file with full settings.",
            self.M3U_IMPORT: "Imports from an existing M3U/M3U8 playlist with channel lineup.",
            self.TEMPLATE_BASED: "Uses a predefined template that matches the channel type.",
            self.HYBRID: "Combines multiple methods for complex channel requirements.",
        }
        return descriptions.get(self, "")


class MethodComplexity(Enum):
    """Complexity level of creation method."""
    
    SIMPLE = "simple"       # Single API call
    MODERATE = "moderate"   # Few steps, basic collections
    COMPLEX = "complex"     # Multiple collections, schedules
    ADVANCED = "advanced"   # Full scheduling, multiple sources, deco


@dataclass
class MethodRequirement:
    """A requirement for a creation method."""
    
    name: str
    met: bool
    reason: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "met": self.met,
            "reason": self.reason,
        }


@dataclass
class MethodRecommendation:
    """A recommended creation method with score and reasoning."""
    
    method: CreationMethod
    score: float  # 0.0 to 1.0
    complexity: MethodComplexity
    requirements: list[MethodRequirement] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    estimated_duration_seconds: int = 30
    notes: list[str] = field(default_factory=list)
    
    @property
    def all_requirements_met(self) -> bool:
        """Check if all requirements are met."""
        return all(req.met for req in self.requirements)
    
    @property
    def unmet_requirements(self) -> list[MethodRequirement]:
        """Get list of unmet requirements."""
        return [req for req in self.requirements if not req.met]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method.value,
            "method_name": self.method.display_name,
            "description": self.method.description,
            "score": self.score,
            "complexity": self.complexity.value,
            "requirements": [req.to_dict() for req in self.requirements],
            "all_requirements_met": self.all_requirements_met,
            "steps": self.steps,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "notes": self.notes,
        }


@dataclass
class MethodSelectionResult:
    """Result of method selection process."""
    
    recommended: MethodRecommendation
    alternatives: list[MethodRecommendation] = field(default_factory=list)
    fallback: MethodRecommendation | None = None
    reasoning: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended": self.recommended.to_dict(),
            "alternatives": [alt.to_dict() for alt in self.alternatives],
            "fallback": self.fallback.to_dict() if self.fallback else None,
            "reasoning": self.reasoning,
        }


class MethodSelector:
    """
    Selects the optimal channel creation method based on intent and sources.
    
    Analyzes:
    - Channel complexity (simple vs. complex scheduling)
    - Source availability and types
    - User preferences for import vs. build
    - System capabilities (templates, existing configs)
    """
    
    # Templates available for template-based creation
    AVAILABLE_TEMPLATES = {
        "classic_tv": "Classic TV Channel with dayparts",
        "movie_marathon": "24/7 Movie Channel",
        "kids_daytime": "Kids Programming (daytime only)",
        "sports_classics": "Classic Sports Channel",
        "documentary": "Documentary Channel",
        "tech_archive": "Tech/Computing Archive Channel",
        "pbs_style": "PBS-Style Educational Channel",
    }
    
    def __init__(self):
        """Initialize the method selector."""
        logger.info("MethodSelector initialized")
    
    def select(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
        has_yaml_config: bool = False,
        has_m3u_playlist: bool = False,
        existing_templates: list[str] | None = None,
    ) -> MethodSelectionResult:
        """
        Select the best creation method for the given intent and sources.
        
        Args:
            intent: Analyzed user intent
            sources: Selected media sources
            has_yaml_config: Whether user provided a YAML config
            has_m3u_playlist: Whether user provided an M3U playlist
            existing_templates: List of available template names
            
        Returns:
            MethodSelectionResult with recommended and alternative methods
        """
        recommendations = []
        
        # Evaluate each method
        recommendations.append(self._evaluate_direct_api(intent, sources))
        recommendations.append(self._evaluate_scripted_build(intent, sources))
        recommendations.append(self._evaluate_yaml_import(intent, sources, has_yaml_config))
        recommendations.append(self._evaluate_m3u_import(intent, sources, has_m3u_playlist))
        recommendations.append(self._evaluate_template_based(intent, sources, existing_templates))
        recommendations.append(self._evaluate_hybrid(intent, sources))
        
        # Sort by score (highest first), then filter out those with unmet critical requirements
        valid_recommendations = [r for r in recommendations if r.all_requirements_met]
        invalid_recommendations = [r for r in recommendations if not r.all_requirements_met]
        
        valid_recommendations.sort(key=lambda r: r.score, reverse=True)
        
        if valid_recommendations:
            recommended = valid_recommendations[0]
            alternatives = valid_recommendations[1:3]  # Top 2 alternatives
        else:
            # Fallback to direct API if nothing else works
            recommended = self._evaluate_direct_api(intent, sources)
            alternatives = []
        
        # Determine fallback (simplest working method)
        fallback = None
        if valid_recommendations and len(valid_recommendations) > 1:
            # Prefer template or direct API as fallback
            for rec in valid_recommendations:
                if rec.method in [CreationMethod.DIRECT_API, CreationMethod.TEMPLATE_BASED]:
                    fallback = rec
                    break
        
        # Build reasoning
        reasoning = self._build_reasoning(intent, sources, recommended)
        
        return MethodSelectionResult(
            recommended=recommended,
            alternatives=alternatives,
            fallback=fallback,
            reasoning=reasoning,
        )
    
    def _evaluate_direct_api(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
    ) -> MethodRecommendation:
        """Evaluate direct API method."""
        requirements = []
        score = 0.6  # Base score
        notes = []
        
        # Check requirements
        requirements.append(MethodRequirement(
            name="API Available",
            met=True,
            reason="EXStreamTV API is always available",
        ))
        
        # Simple channels score higher for direct API
        if intent.purpose == ChannelPurpose.SINGLE_SHOW:
            score += 0.3
            notes.append("Simple single-show channel ideal for direct API")
        elif intent.purpose == ChannelPurpose.GENRE_CHANNEL:
            score += 0.2
            notes.append("Genre channel works well with direct API")
        elif intent.purpose == ChannelPurpose.CLASSIC_TV:
            score += 0.1
            notes.append("Classic TV may need additional scheduling")
        
        # Single source is simpler
        if len(sources.recommended_combination) == 1:
            score += 0.1
            notes.append("Single source simplifies API calls")
        
        # Reduce score for complex scheduling
        if intent.scheduling.dayparts and len(intent.scheduling.dayparts) > 2:
            score -= 0.2
            notes.append("Complex daypart scheduling may need scripted build")
        
        # Determine complexity
        complexity = MethodComplexity.SIMPLE
        if len(sources.recommended_combination) > 1:
            complexity = MethodComplexity.MODERATE
        
        steps = [
            "Create channel with name and number",
            "Create collection(s) for content",
            "Create program schedule",
            "Create playout and activate",
        ]
        
        return MethodRecommendation(
            method=CreationMethod.DIRECT_API,
            score=min(1.0, max(0.0, score)),
            complexity=complexity,
            requirements=requirements,
            steps=steps,
            estimated_duration_seconds=30,
            notes=notes,
        )
    
    def _evaluate_scripted_build(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
    ) -> MethodRecommendation:
        """Evaluate scripted build method."""
        requirements = []
        score = 0.5  # Base score
        notes = []
        
        requirements.append(MethodRequirement(
            name="Build Script Engine",
            met=True,
            reason="Build scripts are processed by ChannelCreatorAgent",
        ))
        
        # Complex channels score higher for scripted build
        if intent.purpose in [ChannelPurpose.CLASSIC_TV, ChannelPurpose.NETWORK_SIMULATION]:
            score += 0.3
            notes.append("Complex channel type benefits from scripted approach")
        
        # Multiple sources benefit from scripted coordination
        if len(sources.recommended_combination) > 1:
            score += 0.2
            notes.append("Multiple sources need coordinated collection building")
        
        # Complex scheduling benefits from scripts
        if intent.scheduling.dayparts and len(intent.scheduling.dayparts) > 2:
            score += 0.2
            notes.append("Daypart scheduling implemented via script")
        
        if intent.scheduling.holiday_aware:
            score += 0.1
            notes.append("Holiday scheduling included in build script")
        
        complexity = MethodComplexity.COMPLEX
        
        steps = [
            "Analyze content requirements",
            "Build collections for each content type",
            "Generate daypart-aware schedule",
            "Configure filler content",
            "Set up deco (bumpers, watermarks)",
            "Create and activate playout",
            "Verify schedule integrity",
        ]
        
        return MethodRecommendation(
            method=CreationMethod.SCRIPTED_BUILD,
            score=min(1.0, max(0.0, score)),
            complexity=complexity,
            requirements=requirements,
            steps=steps,
            estimated_duration_seconds=120,
            notes=notes,
        )
    
    def _evaluate_yaml_import(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
        has_yaml_config: bool,
    ) -> MethodRecommendation:
        """Evaluate YAML import method."""
        requirements = []
        score = 0.4  # Base score
        notes = []
        
        requirements.append(MethodRequirement(
            name="YAML Configuration",
            met=has_yaml_config,
            reason="YAML config file provided" if has_yaml_config else "No YAML config file available",
        ))
        
        if has_yaml_config:
            score += 0.5
            notes.append("YAML configuration provided - ready for import")
        else:
            notes.append("Would need to generate YAML first")
        
        # YAML is good for replicating existing setups
        if intent.purpose == ChannelPurpose.NETWORK_SIMULATION:
            score += 0.1
            notes.append("Network simulation can be defined precisely in YAML")
        
        complexity = MethodComplexity.MODERATE if has_yaml_config else MethodComplexity.COMPLEX
        
        steps = [
            "Parse YAML configuration",
            "Validate configuration structure",
            "Create channel from config",
            "Import collections",
            "Apply schedule settings",
            "Activate playout",
        ]
        
        if not has_yaml_config:
            steps.insert(0, "Generate YAML from analyzed intent")
        
        return MethodRecommendation(
            method=CreationMethod.YAML_IMPORT,
            score=min(1.0, max(0.0, score)),
            complexity=complexity,
            requirements=requirements,
            steps=steps,
            estimated_duration_seconds=45 if has_yaml_config else 90,
            notes=notes,
        )
    
    def _evaluate_m3u_import(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
        has_m3u_playlist: bool,
    ) -> MethodRecommendation:
        """Evaluate M3U import method."""
        requirements = []
        score = 0.3  # Base score
        notes = []
        
        requirements.append(MethodRequirement(
            name="M3U Playlist",
            met=has_m3u_playlist,
            reason="M3U playlist provided" if has_m3u_playlist else "No M3U playlist available",
        ))
        
        if has_m3u_playlist:
            score += 0.5
            notes.append("M3U playlist provided - can import directly")
        
        # M3U is good for external IPTV sources
        if SourceType.YOUTUBE in sources.recommended_combination:
            score += 0.1
            notes.append("YouTube sources can be organized via M3U")
        
        complexity = MethodComplexity.SIMPLE if has_m3u_playlist else MethodComplexity.COMPLEX
        
        steps = [
            "Parse M3U playlist",
            "Extract channel entries",
            "Create channel and playout",
            "Map media items",
        ]
        
        return MethodRecommendation(
            method=CreationMethod.M3U_IMPORT,
            score=min(1.0, max(0.0, score)),
            complexity=complexity,
            requirements=requirements,
            steps=steps,
            estimated_duration_seconds=20 if has_m3u_playlist else 60,
            notes=notes,
        )
    
    def _evaluate_template_based(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
        existing_templates: list[str] | None,
    ) -> MethodRecommendation:
        """Evaluate template-based method."""
        requirements = []
        score = 0.5  # Base score
        notes = []
        
        templates = existing_templates or list(self.AVAILABLE_TEMPLATES.keys())
        matching_template = self._find_matching_template(intent, templates)
        
        requirements.append(MethodRequirement(
            name="Matching Template",
            met=matching_template is not None,
            reason=f"Template '{matching_template}' matches" if matching_template else "No matching template found",
        ))
        
        if matching_template:
            score += 0.4
            notes.append(f"Using '{matching_template}' template")
            notes.append(self.AVAILABLE_TEMPLATES.get(matching_template, ""))
        
        # Templates work well for standard channel types
        if intent.purpose in [ChannelPurpose.GENRE_CHANNEL, ChannelPurpose.MARATHON]:
            score += 0.1
            notes.append("Standard channel type works well with templates")
        
        complexity = MethodComplexity.SIMPLE if matching_template else MethodComplexity.MODERATE
        
        steps = [
            "Load matching template",
            "Customize template with user preferences",
            "Bind content sources",
            "Create channel from template",
            "Activate playout",
        ]
        
        return MethodRecommendation(
            method=CreationMethod.TEMPLATE_BASED,
            score=min(1.0, max(0.0, score)),
            complexity=complexity,
            requirements=requirements,
            steps=steps,
            estimated_duration_seconds=25,
            notes=notes,
        )
    
    def _evaluate_hybrid(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
    ) -> MethodRecommendation:
        """Evaluate hybrid method."""
        requirements = []
        score = 0.4  # Base score
        notes = []
        
        requirements.append(MethodRequirement(
            name="Multiple Methods Available",
            met=True,
            reason="Hybrid approach always available as fallback",
        ))
        
        # Hybrid shines for very complex requirements
        if intent.purpose == ChannelPurpose.NETWORK_SIMULATION:
            score += 0.3
            notes.append("Network simulation benefits from hybrid approach")
        
        if len(sources.recommended_combination) >= 3:
            score += 0.2
            notes.append("Many sources require hybrid coordination")
        
        if intent.scheduling.holiday_aware and intent.scheduling.dayparts:
            score += 0.1
            notes.append("Complex scheduling with holidays uses hybrid")
        
        complexity = MethodComplexity.ADVANCED
        
        steps = [
            "Analyze requirements and decompose",
            "Use template for base structure",
            "Use scripted build for collections",
            "Use API for fine-tuning",
            "Integrate all components",
            "Verify and activate",
        ]
        
        return MethodRecommendation(
            method=CreationMethod.HYBRID,
            score=min(1.0, max(0.0, score)),
            complexity=complexity,
            requirements=requirements,
            steps=steps,
            estimated_duration_seconds=180,
            notes=notes,
        )
    
    def _find_matching_template(
        self,
        intent: AnalyzedIntent,
        templates: list[str],
    ) -> str | None:
        """Find a template that matches the intent."""
        # Map purpose to template
        purpose_to_template = {
            ChannelPurpose.CLASSIC_TV: "classic_tv",
            ChannelPurpose.MARATHON: "movie_marathon",
            ChannelPurpose.GENRE_CHANNEL: "movie_marathon",  # Can be adapted
        }
        
        # Check genre-specific templates
        genres_lower = [g.lower() for g in intent.content.genres]
        
        if "documentary" in genres_lower or "educational" in genres_lower:
            if "documentary" in templates:
                return "documentary"
        
        if any(k in genres_lower for k in ["kids", "children", "animation", "cartoon"]):
            if "kids_daytime" in templates:
                return "kids_daytime"
        
        if any(s in genres_lower for s in ["sports", "football", "basketball", "baseball"]):
            if "sports_classics" in templates:
                return "sports_classics"
        
        if any(t in genres_lower for t in ["tech", "technology", "computing"]):
            if "tech_archive" in templates:
                return "tech_archive"
        
        if "pbs" in genres_lower or "educational" in genres_lower:
            if "pbs_style" in templates:
                return "pbs_style"
        
        # Fallback to purpose mapping
        suggested = purpose_to_template.get(intent.purpose)
        if suggested and suggested in templates:
            return suggested
        
        # Default to classic_tv if nothing else matches
        if "classic_tv" in templates:
            return "classic_tv"
        
        return None
    
    def _build_reasoning(
        self,
        intent: AnalyzedIntent,
        sources: SourceSelectionResult,
        recommended: MethodRecommendation,
    ) -> str:
        """Build explanation for the recommendation."""
        parts = []
        
        parts.append(f"Recommended: {recommended.method.display_name}")
        parts.append(f"Complexity: {recommended.complexity.value}")
        
        if recommended.notes:
            parts.append("Reasoning:")
            for note in recommended.notes[:3]:
                parts.append(f"  - {note}")
        
        if recommended.unmet_requirements:
            parts.append("Limitations:")
            for req in recommended.unmet_requirements:
                parts.append(f"  - {req.name}: {req.reason}")
        
        return "\n".join(parts)
    
    def get_method_steps(self, method: CreationMethod) -> list[str]:
        """Get the detailed steps for a creation method."""
        steps = {
            CreationMethod.DIRECT_API: [
                "1. POST /api/channels - Create channel record",
                "2. POST /api/collections - Create content collections",
                "3. POST /api/schedules - Create program schedule",
                "4. POST /api/playouts - Create and activate playout",
            ],
            CreationMethod.SCRIPTED_BUILD: [
                "1. Parse build plan and validate",
                "2. Query media sources for matching content",
                "3. Create collections with search results",
                "4. Generate schedule with daypart assignments",
                "5. Configure filler content sources",
                "6. Apply deco configuration (watermarks, bumpers)",
                "7. Create playout with all components",
                "8. Run validation checks",
                "9. Activate and monitor startup",
            ],
            CreationMethod.YAML_IMPORT: [
                "1. Load and parse YAML file",
                "2. Validate against channel schema",
                "3. Resolve source references",
                "4. Create channel from parsed config",
                "5. Import collections and schedules",
                "6. Activate playout",
            ],
            CreationMethod.M3U_IMPORT: [
                "1. Parse M3U/M3U8 file",
                "2. Extract channel metadata (name, logo, group)",
                "3. Map URLs to media items",
                "4. Create channel and playout",
                "5. Configure streaming settings",
            ],
            CreationMethod.TEMPLATE_BASED: [
                "1. Load template definition",
                "2. Substitute user preferences",
                "3. Bind to available content sources",
                "4. Generate collections from template rules",
                "5. Create channel with template schedule",
                "6. Activate playout",
            ],
            CreationMethod.HYBRID: [
                "1. Decompose requirements by complexity",
                "2. Apply template for base structure",
                "3. Use scripted build for custom collections",
                "4. Fine-tune via direct API calls",
                "5. Integrate all components",
                "6. Validate complete configuration",
                "7. Activate and verify",
            ],
        }
        return steps.get(method, [])
