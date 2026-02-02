"""
EXStreamTV AI Agent Module

Intelligent log analysis, error detection, fix suggestions, and AI-powered channel creation.
Ported from StreamTV with all capabilities preserved.

Version 2.5.0 Components:

Core Error Handling:
- LogAnalyzer: Real-time log parsing and pattern detection
- FixSuggester: AI-powered fix suggestions (Ollama + rule-based fallback)
- FixApplier: Safe fix application with rollback capability
- ApprovalManager: Workflow for risky fix approvals
- LearningDatabase: Track fix effectiveness over time

Channel Creation (Enhanced):
- ChannelCreatorAgent: AI-powered channel creation with multi-persona support
- PersonaManager: Dynamic persona selection and management (6 personas)
- IntentAnalyzer: Natural language intent parsing
- SourceSelector: Media source ranking and selection
- BuildPlanGenerator: Complete channel build plan generation
- MethodSelector: Creation method selection (API, scripted, template, etc.)
- DecoIntegrator: Channel decoration (watermarks, bumpers, station IDs)

Plan Execution (v2.5.0):
- BlockScheduleExecutor: Converts AI schedule blocks to database Block entities
- CollectionExecutor: Persists collections from build plans to database

Supporting Components:
- ConversationManager: Multi-turn conversation state management
- MediaAggregator: Unified media source queries
- ScheduleGenerator: Complex schedule generation with holiday support
"""

from exstreamtv.ai_agent.approval_manager import ApprovalManager, ApprovalRequest, ApprovalStatus
from exstreamtv.ai_agent.fix_applier import FixAction, FixApplier, FixResult
from exstreamtv.ai_agent.fix_suggester import FixRiskLevel, FixSuggester, FixSuggestion
from exstreamtv.ai_agent.learning import (
    FixEffectiveness,
    FixLearningDatabase,
    PredictiveErrorPrevention,
)
from exstreamtv.ai_agent.log_analyzer import LogAnalyzer, LogMatch, LogPattern, LogSeverity

# Channel creation components
from exstreamtv.ai_agent.channel_creator import (
    ChannelCreatorAgent,
    ChannelCreationSession,
    ChannelCreationStage,
    ChannelIntent,
    ChannelSpecification,
)
from exstreamtv.ai_agent.conversation import (
    ConversationConfig,
    ConversationManager,
    ConversationSession,
    Message,
    get_conversation_manager,
)
from exstreamtv.ai_agent.media_aggregator import (
    MediaAggregator,
    MediaQueryResult,
    MediaSourceInfo,
)
from exstreamtv.ai_agent.schedule_generator import (
    DayOfWeek,
    HolidayCalendar,
    HolidayProgramming,
    ScheduleBlock,
    ScheduleGenerator,
    TimeSlot,
)

# v2.3.0 - Enhanced AI Channel Creator components
from exstreamtv.ai_agent.persona_manager import (
    PersonaManager,
    PersonaType,
    PersonaInfo,
    PersonaContext,
    get_persona_manager,
)
from exstreamtv.ai_agent.intent_analyzer import (
    IntentAnalyzer,
    AnalyzedIntent,
    ChannelPurpose,
    PlayoutPreference,
    ContentEra,
    analyze_intent,
)
from exstreamtv.ai_agent.source_selector import (
    SourceSelector,
    SourceType,
    SourceRanking,
    SourceSelectionResult,
    ContentMatch,
)
from exstreamtv.ai_agent.build_plan_generator import (
    BuildPlanGenerator,
    BuildPlan,
    BuildStatus,
    ChannelConfig,
    CollectionConfig,
    ScheduleConfig,
    FillerConfig,
    DecoConfig,
    ModuleUsage,
)

# v2.4.0 - Method selection and deco integration
from exstreamtv.ai_agent.method_selector import (
    MethodSelector,
    CreationMethod,
    MethodComplexity,
    MethodRecommendation,
    MethodSelectionResult,
)
from exstreamtv.ai_agent.deco_integrator import (
    DecoIntegrator,
    DecoType,
    DecoConfiguration,
    WatermarkConfig,
    WatermarkPosition,
    WatermarkStyle,
    BumperConfig,
    StationIdConfig,
    InterstitialConfig,
)

# v2.5.0 - Block schedule and collection execution
from exstreamtv.ai_agent.block_executor import (
    BlockScheduleExecutor,
    BlockExecutionResult,
    BlockInfo,
)
from exstreamtv.ai_agent.collection_executor import (
    CollectionExecutor,
    CollectionExecutionResult,
    CollectionInfo,
)

__all__ = [
    # Log analysis
    "LogAnalyzer",
    "LogMatch",
    "LogPattern",
    "LogSeverity",
    # Fix suggestions
    "FixRiskLevel",
    "FixSuggester",
    "FixSuggestion",
    # Fix application
    "FixAction",
    "FixApplier",
    "FixResult",
    # Approval workflow
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalStatus",
    # Learning
    "FixEffectiveness",
    "FixLearningDatabase",
    "PredictiveErrorPrevention",
    # Channel creation
    "ChannelCreatorAgent",
    "ChannelCreationSession",
    "ChannelCreationStage",
    "ChannelIntent",
    "ChannelSpecification",
    # Conversation management
    "ConversationConfig",
    "ConversationManager",
    "ConversationSession",
    "Message",
    "get_conversation_manager",
    # Media aggregation
    "MediaAggregator",
    "MediaQueryResult",
    "MediaSourceInfo",
    # Schedule generation
    "DayOfWeek",
    "HolidayCalendar",
    "HolidayProgramming",
    "ScheduleBlock",
    "ScheduleGenerator",
    "TimeSlot",
    # v2.3.0 - Persona management
    "PersonaManager",
    "PersonaType",
    "PersonaInfo",
    "PersonaContext",
    "get_persona_manager",
    # v2.3.0 - Intent analysis
    "IntentAnalyzer",
    "AnalyzedIntent",
    "ChannelPurpose",
    "PlayoutPreference",
    "ContentEra",
    "analyze_intent",
    # v2.3.0 - Source selection
    "SourceSelector",
    "SourceType",
    "SourceRanking",
    "SourceSelectionResult",
    "ContentMatch",
    # v2.3.0 - Build plan generation
    "BuildPlanGenerator",
    "BuildPlan",
    "BuildStatus",
    "ChannelConfig",
    "CollectionConfig",
    "ScheduleConfig",
    "FillerConfig",
    "DecoConfig",
    "ModuleUsage",
    # v2.4.0 - Method selection
    "MethodSelector",
    "CreationMethod",
    "MethodComplexity",
    "MethodRecommendation",
    "MethodSelectionResult",
    # v2.4.0 - Deco integration
    "DecoIntegrator",
    "DecoType",
    "DecoConfiguration",
    "WatermarkConfig",
    "WatermarkPosition",
    "WatermarkStyle",
    "BumperConfig",
    "StationIdConfig",
    "InterstitialConfig",
    # v2.5.0 - Block schedule execution
    "BlockScheduleExecutor",
    "BlockExecutionResult",
    "BlockInfo",
    # v2.5.0 - Collection execution
    "CollectionExecutor",
    "CollectionExecutionResult",
    "CollectionInfo",
]
