"""
AI Channel Creation API Endpoints

Provides REST endpoints for the AI-powered channel creation conversation flow.
Supports multiple personas (TV Executive, Sports Savant, Tech Savant, etc.)
with intelligent intent analysis, source selection, and build plan generation.

Version 2.3.0 - Enhanced with PersonaManager, IntentAnalyzer, SourceSelector, BuildPlanGenerator
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_config
from ..database import get_db

logger = logging.getLogger(__name__)

# Setup templates
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(prefix="/ai/channel", tags=["AI Channel Creator"])


# Request/Response Models

class StartSessionRequest(BaseModel):
    """Request to start a new channel creation session."""
    session_id: str | None = None


class StartSessionResponse(BaseModel):
    """Response with new session details."""
    session_id: str
    welcome_message: str
    stage: str


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    session_id: str
    message: str


class SendMessageResponse(BaseModel):
    """Response with AI reply and session state."""
    session_id: str
    response: str
    stage: str
    ready_to_build: bool
    specification: dict[str, Any] | None = None


class CreateChannelRequest(BaseModel):
    """Request to create channel from conversation."""
    session_id: str


class CreateChannelResponse(BaseModel):
    """Response with created channel details."""
    success: bool
    channel_id: int | None = None
    channel_number: str | None = None
    channel_name: str | None = None
    schedule_id: int | None = None
    playout_id: int | None = None
    error: str | None = None


class PreviewResponse(BaseModel):
    """Response with channel preview."""
    session_id: str
    ready_to_build: bool
    specification: dict[str, Any] | None = None
    preview: dict[str, Any] | None = None


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    stage: str
    message_count: int
    created_at: str
    updated_at: str


# v2.3.0 - Enhanced AI Channel Creator Models

class PersonaInfoResponse(BaseModel):
    """Persona information for API responses."""
    id: str
    name: str
    title: str
    description: str
    specialties: list[str]
    icon: str
    color: str


class AnalyzeIntentRequest(BaseModel):
    """Request to analyze user intent."""
    request: str = Field(..., description="Natural language channel creation request")
    suggest_persona: bool = Field(True, description="Whether to suggest best persona")


class AnalyzeIntentResponse(BaseModel):
    """Response with analyzed intent."""
    purpose: str
    confidence: float
    suggested_name: str | None
    suggested_persona: str | None
    genres: list[str]
    era: str
    needs_clarification: bool
    clarification_questions: list[str]
    content_preferences: dict[str, Any]
    scheduling_preferences: dict[str, Any]
    source_hints: dict[str, Any]


class GetSourcesRequest(BaseModel):
    """Request to get available sources."""
    genres: list[str] | None = None
    content_types: list[str] | None = None
    era: str | None = None
    year_min: int | None = None
    year_max: int | None = None


class SourceRankingResponse(BaseModel):
    """Source ranking for API responses."""
    source_type: str
    source_name: str
    score: float
    match: str
    matching_count: int
    is_available: bool
    warnings: list[str]


class GetSourcesResponse(BaseModel):
    """Response with ranked sources."""
    rankings: list[SourceRankingResponse]
    primary_source: str | None
    recommended_combination: list[str]
    total_content_available: int
    coverage_notes: list[str]


class GeneratePlanRequest(BaseModel):
    """Request to generate a build plan."""
    request: str = Field(..., description="Natural language channel creation request")
    persona_id: str = Field("tv_executive", description="Persona to use for plan generation")
    preferred_sources: list[str] | None = None
    excluded_sources: list[str] | None = None


class BuildPlanResponse(BaseModel):
    """Response with generated build plan."""
    plan_id: str
    status: str
    is_ready: bool
    channel: dict[str, Any]
    collections: list[dict[str, Any]]
    schedule: dict[str, Any] | None
    filler: dict[str, Any]
    deco: dict[str, Any]
    warnings: list[dict[str, Any]]
    notes: list[str]
    estimated_content_hours: float
    estimated_unique_items: int
    modules: dict[str, Any]


class ApprovePlanRequest(BaseModel):
    """Request to approve a build plan."""
    plan_id: str


class ModifyPlanRequest(BaseModel):
    """Request to modify a build plan."""
    plan_id: str
    modifications: dict[str, Any] = Field(..., description="Modifications to apply")


class StartSessionWithPersonaRequest(BaseModel):
    """Request to start session with specific persona."""
    session_id: str | None = None
    persona_id: str = Field("tv_executive", description="Persona to use")


class StartSessionWithPersonaResponse(BaseModel):
    """Response with new session and persona details."""
    session_id: str
    welcome_message: str
    stage: str
    persona: PersonaInfoResponse


# Dependency to get the channel creator agent

_agent = None


class UnifiedProviderAdapter:
    """
    Adapter to make UnifiedAIProvider compatible with ChannelCreatorAgent.
    
    The ChannelCreatorAgent expects an object with a chat() method that takes
    a prompt and returns a response string. This adapter wraps the UnifiedAIProvider
    to provide that interface.
    """
    
    def __init__(self, provider):
        """Initialize with a UnifiedAIProvider instance."""
        self.provider = provider
        self._system_prompt = None
    
    def set_system_prompt(self, prompt: str):
        """Set the system prompt for AI conversations."""
        self._system_prompt = prompt
    
    async def chat(self, prompt: str) -> str:
        """
        Send a chat message and get a response.
        
        Args:
            prompt: The user's message
            
        Returns:
            The AI's response text
        """
        try:
            response = await self.provider.generate(
                prompt=prompt,
                system_prompt=self._system_prompt,
                temperature=0.7,  # More creative for channel creation
                max_tokens=2000,
            )
            return response
        except Exception as e:
            logger.exception(f"Error in chat: {e}")
            return ""
    
    async def _generate(self, prompt: str) -> str:
        """Fallback generate method for compatibility."""
        return await self.chat(prompt)
    
    async def is_available(self) -> bool:
        """Check if the provider is configured and available."""
        return self.provider.is_configured


async def get_channel_creator_agent():
    """Get or create the channel creator agent instance."""
    global _agent
    
    if _agent is None:
        from ..ai_agent.channel_creator import ChannelCreatorAgent
        from ..ai_agent.media_aggregator import MediaAggregator
        from ..ai_agent.schedule_generator import ScheduleGenerator, HolidayCalendar
        from ..ai_agent.provider_manager import UnifiedAIProvider, AIConfig, ProviderType, CloudProviderID
        import os
        
        config = get_config()
        ai_config = config.ai_agent
        
        # Build the AIConfig for UnifiedAIProvider
        # Determine provider type
        provider_type_str = getattr(ai_config, 'provider_type', 'cloud')
        try:
            provider_type = ProviderType(provider_type_str)
        except ValueError:
            provider_type = ProviderType.CLOUD
        
        # Get cloud provider settings
        cloud_provider_str = "groq"
        cloud_api_key = ""
        cloud_model = "llama-3.3-70b-versatile"
        
        if hasattr(ai_config, 'cloud'):
            cloud_provider_str = getattr(ai_config.cloud, 'provider', 'groq')
            cloud_api_key = getattr(ai_config.cloud, 'api_key', '')
            cloud_model = getattr(ai_config.cloud, 'model', 'llama-3.3-70b-versatile')
        
        # Resolve API key from environment if it's a placeholder
        if cloud_api_key.startswith('${') and cloud_api_key.endswith('}'):
            env_var = cloud_api_key[2:-1]
            cloud_api_key = os.getenv(env_var, '')
        elif not cloud_api_key:
            # Try common environment variable names
            cloud_api_key = os.getenv('GROQ_API_KEY', '') or os.getenv('SAMBANOVA_API_KEY', '') or os.getenv('OPENROUTER_API_KEY', '')
        
        try:
            cloud_provider = CloudProviderID(cloud_provider_str)
        except ValueError:
            cloud_provider = CloudProviderID.GROQ
        
        # Get local provider settings
        local_host = "http://localhost:11434"
        local_model = "auto"
        
        if hasattr(ai_config, 'local'):
            local_host = getattr(ai_config.local, 'host', local_host)
            local_model = getattr(ai_config.local, 'model', local_model)
        elif hasattr(ai_config, 'ollama'):
            # Legacy fallback
            local_host = getattr(ai_config.ollama, 'host', local_host)
            local_model = getattr(ai_config.ollama, 'model', 'llama3.2:latest')
        
        # Get settings
        temperature = 0.3
        max_tokens = 4096
        timeout = 180.0  # Longer timeout for channel creation
        
        if hasattr(ai_config, 'settings'):
            temperature = getattr(ai_config.settings, 'temperature', temperature)
            max_tokens = getattr(ai_config.settings, 'max_tokens', max_tokens)
            timeout = getattr(ai_config.settings, 'timeout', 30.0)
            # Always use longer timeout for channel creation
            timeout = max(timeout, 180.0)
        
        # Build fallback providers list
        fallback_providers = []
        if hasattr(ai_config, 'cloud') and hasattr(ai_config.cloud, 'fallback'):
            for fb in ai_config.cloud.fallback:
                fb_api_key = getattr(fb, 'api_key', '')
                if fb_api_key.startswith('${') and fb_api_key.endswith('}'):
                    env_var = fb_api_key[2:-1]
                    fb_api_key = os.getenv(env_var, '')
                
                fallback_providers.append({
                    'provider': getattr(fb, 'provider', 'sambanova'),
                    'api_key': fb_api_key,
                    'model': getattr(fb, 'model', ''),
                })
        
        # Create the AIConfig
        unified_config = AIConfig(
            provider_type=provider_type,
            cloud_provider=cloud_provider,
            cloud_api_key=cloud_api_key,
            cloud_model=cloud_model,
            fallback_providers=fallback_providers,
            local_host=local_host,
            local_model=local_model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        
        # Create the unified provider
        unified_provider = UnifiedAIProvider(unified_config)
        
        # Log provider status
        if unified_provider.is_configured:
            logger.info(f"AI Channel Creator using provider type: {provider_type.value}")
            if provider_type in (ProviderType.CLOUD, ProviderType.HYBRID):
                logger.info(f"Cloud provider: {cloud_provider.value}, model: {cloud_model}")
            if provider_type in (ProviderType.LOCAL, ProviderType.HYBRID):
                logger.info(f"Local provider: {local_host}, model: {local_model}")
        else:
            logger.warning("AI provider not fully configured - channel creation may not work")
        
        # Wrap in adapter for compatibility with ChannelCreatorAgent
        ai_client = UnifiedProviderAdapter(unified_provider)
        
        # Initialize media aggregator (optional components)
        media_aggregator = MediaAggregator()
        
        # Initialize schedule generator
        schedule_generator = ScheduleGenerator(
            holiday_calendar=HolidayCalendar(),
        )
        
        # Create the agent
        _agent = ChannelCreatorAgent(
            ollama_client=ai_client,  # Using adapter instead of OllamaClient
            media_aggregator=media_aggregator,
            schedule_generator=schedule_generator,
        )
    
    return _agent


# API Endpoints

@router.post("/start", response_model=StartSessionResponse)
async def start_session(
    request: StartSessionRequest,
    agent = Depends(get_channel_creator_agent),
) -> StartSessionResponse:
    """
    Start a new channel creation conversation.
    
    Returns a new session ID and welcome message from the TV Programming Executive.
    """
    try:
        session = agent.create_session(request.session_id)
        
        # Get welcome message
        welcome = await agent.get_welcome_message()
        
        # Add welcome as first assistant message
        session.add_message("assistant", welcome)
        
        return StartSessionResponse(
            session_id=session.session_id,
            welcome_message=welcome,
            stage=session.stage.value,
        )
        
    except Exception as e:
        logger.exception(f"Error starting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@router.post("/message", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    agent = Depends(get_channel_creator_agent),
) -> SendMessageResponse:
    """
    Send a message in the channel creation conversation.
    
    The AI will respond with guidance, ask clarifying questions,
    or indicate when it has enough information to build the channel.
    """
    try:
        result = await agent.process_message(
            session_id=request.session_id,
            user_message=request.message,
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("error", "Failed to process message"),
            )
        
        return SendMessageResponse(
            session_id=request.session_id,
            response=result.get("response", ""),
            stage=result.get("stage", "unknown"),
            ready_to_build=result.get("ready_to_build", False),
            specification=result.get("specification"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.get("/preview/{session_id}", response_model=PreviewResponse)
async def get_preview(
    session_id: str,
    agent = Depends(get_channel_creator_agent),
) -> PreviewResponse:
    """
    Get a preview of the channel that would be created.
    
    Returns the current specification and a preview of the schedule.
    """
    try:
        session = agent.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        preview = None
        if session.specification:
            # Generate a preview of the schedule
            from ..ai_agent.schedule_generator import ScheduleGenerator
            
            generator = ScheduleGenerator()
            slots = generator.generate_schedule_template(session.specification, days=1)
            
            preview = {
                "sample_day": [slot.to_dict() for slot in slots[:20]],  # First 20 slots
                "total_slots": len(slots),
            }
        
        return PreviewResponse(
            session_id=session_id,
            ready_to_build=session.specification is not None,
            specification=session.specification.to_dict() if session.specification else None,
            preview=preview,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting preview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get preview: {str(e)}")


@router.post("/create", response_model=CreateChannelResponse)
async def create_channel(
    request: CreateChannelRequest,
    agent = Depends(get_channel_creator_agent),
    db: AsyncSession = Depends(get_db),
) -> CreateChannelResponse:
    """
    Create the channel from the conversation specification.
    
    This will create the channel, collections, schedule, and playout.
    """
    try:
        result = await agent.build_channel(
            session_id=request.session_id,
            db_session=db,
        )
        
        if not result.get("success"):
            return CreateChannelResponse(
                success=False,
                error=result.get("error", "Failed to create channel"),
            )
        
        return CreateChannelResponse(
            success=True,
            channel_id=result.get("channel_id"),
            channel_number=result.get("channel_number"),
            channel_name=result.get("channel_name"),
            schedule_id=result.get("schedule_id"),
            playout_id=result.get("playout_id"),
        )
        
    except Exception as e:
        logger.exception(f"Error creating channel: {e}")
        return CreateChannelResponse(
            success=False,
            error=str(e),
        )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    agent = Depends(get_channel_creator_agent),
) -> list[SessionInfo]:
    """
    List all active channel creation sessions.
    """
    try:
        sessions = agent.list_sessions()
        
        return [
            SessionInfo(
                session_id=s["session_id"],
                stage=s["stage"],
                message_count=s["message_count"],
                created_at=s["created_at"],
                updated_at=s["updated_at"],
            )
            for s in sessions
        ]
        
    except Exception as e:
        logger.exception(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    agent = Depends(get_channel_creator_agent),
) -> dict[str, Any]:
    """
    Get detailed session information including conversation history.
    """
    try:
        session = agent.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return session.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    agent = Depends(get_channel_creator_agent),
) -> dict[str, Any]:
    """
    Delete/cancel a channel creation session.
    """
    try:
        success = agent.delete_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {
            "success": True,
            "message": f"Session {session_id} deleted",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


@router.get("/status")
async def get_status(
    agent = Depends(get_channel_creator_agent),
) -> dict[str, Any]:
    """
    Get AI channel creator status including Ollama availability.
    """
    try:
        ollama_available = await agent.ollama_client.is_available()
        models = await agent.ollama_client.list_models() if ollama_available else []
        
        return {
            "ollama_available": ollama_available,
            "models": models,
            "active_sessions": len(agent.list_sessions()),
            "media_sources": await agent.media_aggregator.get_available_sources() if agent.media_aggregator else {},
        }
        
    except Exception as e:
        logger.exception(f"Error getting status: {e}")
        return {
            "ollama_available": False,
            "error": str(e),
        }


# ============================================================================
# v2.3.0 - Enhanced AI Channel Creator Endpoints
# ============================================================================

# Persona Management

@router.get("/personas", response_model=list[PersonaInfoResponse])
async def list_personas() -> list[PersonaInfoResponse]:
    """
    List all available AI personas for channel creation.
    
    Each persona specializes in different content types and brings unique
    expertise to the channel creation process.
    """
    try:
        from ..ai_agent.persona_manager import get_persona_manager
        
        manager = get_persona_manager()
        personas = manager.get_all_personas()
        
        return [
            PersonaInfoResponse(
                id=p.persona_type.value,
                name=p.name,
                title=p.title,
                description=p.description,
                specialties=p.specialties,
                icon=p.icon,
                color=p.color,
            )
            for p in personas
        ]
        
    except Exception as e:
        logger.exception(f"Error listing personas: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list personas: {str(e)}")


@router.get("/personas/{persona_id}", response_model=PersonaInfoResponse)
async def get_persona(persona_id: str) -> PersonaInfoResponse:
    """
    Get details about a specific persona.
    """
    try:
        from ..ai_agent.persona_manager import get_persona_manager, PersonaType
        
        manager = get_persona_manager()
        
        try:
            persona_type = PersonaType.from_string(persona_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
        
        info = manager.get_persona_info(persona_type)
        
        return PersonaInfoResponse(
            id=info.persona_type.value,
            name=info.name,
            title=info.title,
            description=info.description,
            specialties=info.specialties,
            icon=info.icon,
            color=info.color,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting persona: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get persona: {str(e)}")


@router.get("/personas/{persona_id}/welcome")
async def get_persona_welcome(persona_id: str) -> dict[str, str]:
    """
    Get the welcome message for a specific persona.
    """
    try:
        from ..ai_agent.persona_manager import get_persona_manager, PersonaType
        
        manager = get_persona_manager()
        
        try:
            persona_type = PersonaType.from_string(persona_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Persona '{persona_id}' not found")
        
        welcome = manager.get_welcome_message(persona_type)
        
        return {
            "persona_id": persona_id,
            "welcome_message": welcome,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting persona welcome: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get welcome: {str(e)}")


# Intent Analysis

@router.post("/analyze", response_model=AnalyzeIntentResponse)
async def analyze_intent(request: AnalyzeIntentRequest) -> AnalyzeIntentResponse:
    """
    Analyze a natural language channel creation request.
    
    Extracts intent, content preferences, scheduling requirements,
    and suggests the best persona for the request.
    """
    try:
        from ..ai_agent.intent_analyzer import IntentAnalyzer
        from ..ai_agent.persona_manager import get_persona_manager
        
        analyzer = IntentAnalyzer()
        intent = analyzer.analyze(request.request)
        
        # Suggest persona if requested
        suggested_persona = None
        if request.suggest_persona:
            manager = get_persona_manager()
            suggested_type = manager.suggest_persona(request.request)
            suggested_persona = suggested_type.value
        
        return AnalyzeIntentResponse(
            purpose=intent.purpose.value,
            confidence=intent.confidence,
            suggested_name=intent.suggested_name,
            suggested_persona=suggested_persona or intent.suggested_persona,
            genres=intent.content.genres,
            era=intent.content.era.value,
            needs_clarification=intent.needs_clarification,
            clarification_questions=intent.clarification_questions,
            content_preferences={
                "genres": intent.content.genres,
                "excluded_genres": intent.content.excluded_genres,
                "year_range": intent.content.year_range,
                "keywords": intent.content.keywords,
            },
            scheduling_preferences={
                "is_24_hour": intent.scheduling.is_24_hour,
                "dayparts": intent.scheduling.dayparts,
                "specific_days": intent.scheduling.specific_days,
                "holiday_aware": intent.scheduling.holiday_aware,
            },
            source_hints={
                "prefer_plex": intent.sources.prefer_plex,
                "prefer_archive_org": intent.sources.prefer_archive_org,
                "prefer_youtube": intent.sources.prefer_youtube,
            },
        )
        
    except Exception as e:
        logger.exception(f"Error analyzing intent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze intent: {str(e)}")


# Source Selection

@router.post("/sources", response_model=GetSourcesResponse)
async def get_sources(request: GetSourcesRequest) -> GetSourcesResponse:
    """
    Get and rank available media sources for the given criteria.
    
    Returns sources ranked by suitability with recommendations
    for the best combination to use.
    """
    try:
        from ..ai_agent.source_selector import SourceSelector
        
        selector = SourceSelector()
        
        year_range = None
        if request.year_min or request.year_max:
            year_range = (request.year_min, request.year_max)
        
        result = await selector.select_sources(
            genres=request.genres,
            content_types=request.content_types,
            era=request.era,
            year_range=year_range,
        )
        
        return GetSourcesResponse(
            rankings=[
                SourceRankingResponse(
                    source_type=r.source_type.value,
                    source_name=r.source_name,
                    score=r.score,
                    match=r.match.value,
                    matching_count=r.matching_count,
                    is_available=r.is_available,
                    warnings=r.warnings,
                )
                for r in result.rankings
            ],
            primary_source=result.primary_source.source_type.value if result.primary_source else None,
            recommended_combination=[s.value for s in result.recommended_combination],
            total_content_available=result.total_content_available,
            coverage_notes=result.coverage_notes,
        )
        
    except Exception as e:
        logger.exception(f"Error getting sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sources: {str(e)}")


# Build Plan Generation

# Store plans in memory (in production, use database or Redis)
_build_plans: dict[str, Any] = {}


@router.post("/plan", response_model=BuildPlanResponse)
async def generate_plan(request: GeneratePlanRequest) -> BuildPlanResponse:
    """
    Generate a complete build plan for a channel.
    
    Analyzes the request, selects sources, and creates a detailed plan
    that can be reviewed and approved before building.
    """
    try:
        from ..ai_agent.intent_analyzer import IntentAnalyzer
        from ..ai_agent.source_selector import SourceSelector, SourceType
        from ..ai_agent.build_plan_generator import BuildPlanGenerator
        
        # Analyze intent
        analyzer = IntentAnalyzer()
        intent = analyzer.analyze(request.request)
        
        # Select sources
        selector = SourceSelector()
        
        preferred = None
        if request.preferred_sources:
            preferred = [SourceType(s) for s in request.preferred_sources]
        
        excluded = None
        if request.excluded_sources:
            excluded = [SourceType(s) for s in request.excluded_sources]
        
        sources = await selector.select_sources(
            genres=intent.content.genres,
            content_types=None,
            era=intent.content.era.value,
            year_range=intent.content.year_range,
            preferred_sources=preferred,
            excluded_sources=excluded,
        )
        
        # Generate plan
        generator = BuildPlanGenerator()
        plan = generator.generate(intent, sources, request.persona_id)
        
        # Store plan for later approval
        _build_plans[plan.plan_id] = plan
        
        return BuildPlanResponse(
            plan_id=plan.plan_id,
            status=plan.status.value,
            is_ready=plan.is_ready(),
            channel=plan.channel.to_dict(),
            collections=[c.to_dict() for c in plan.collections],
            schedule=plan.schedule.to_dict() if plan.schedule else None,
            filler=plan.filler.to_dict(),
            deco=plan.deco.to_dict(),
            warnings=[w.to_dict() for w in plan.warnings],
            notes=plan.notes,
            estimated_content_hours=plan.estimated_content_hours,
            estimated_unique_items=plan.estimated_unique_items,
            modules=plan.modules.to_dict(),
        )
        
    except Exception as e:
        logger.exception(f"Error generating plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate plan: {str(e)}")


@router.get("/plan/{plan_id}", response_model=BuildPlanResponse)
async def get_plan(plan_id: str) -> BuildPlanResponse:
    """
    Get an existing build plan by ID.
    """
    try:
        plan = _build_plans.get(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
        
        return BuildPlanResponse(
            plan_id=plan.plan_id,
            status=plan.status.value,
            is_ready=plan.is_ready(),
            channel=plan.channel.to_dict(),
            collections=[c.to_dict() for c in plan.collections],
            schedule=plan.schedule.to_dict() if plan.schedule else None,
            filler=plan.filler.to_dict(),
            deco=plan.deco.to_dict(),
            warnings=[w.to_dict() for w in plan.warnings],
            notes=plan.notes,
            estimated_content_hours=plan.estimated_content_hours,
            estimated_unique_items=plan.estimated_unique_items,
            modules=plan.modules.to_dict(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get plan: {str(e)}")


@router.put("/plan/{plan_id}", response_model=BuildPlanResponse)
async def modify_plan(plan_id: str, request: ModifyPlanRequest) -> BuildPlanResponse:
    """
    Modify an existing build plan.
    
    Allows updating channel name, adding/removing collections,
    enabling/disabling features, etc.
    """
    try:
        from ..ai_agent.build_plan_generator import BuildPlanGenerator
        
        plan = _build_plans.get(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
        
        # Apply modifications
        generator = BuildPlanGenerator()
        plan = generator.modify_plan(plan, request.modifications)
        
        # Update stored plan
        _build_plans[plan_id] = plan
        
        return BuildPlanResponse(
            plan_id=plan.plan_id,
            status=plan.status.value,
            is_ready=plan.is_ready(),
            channel=plan.channel.to_dict(),
            collections=[c.to_dict() for c in plan.collections],
            schedule=plan.schedule.to_dict() if plan.schedule else None,
            filler=plan.filler.to_dict(),
            deco=plan.deco.to_dict(),
            warnings=[w.to_dict() for w in plan.warnings],
            notes=plan.notes,
            estimated_content_hours=plan.estimated_content_hours,
            estimated_unique_items=plan.estimated_unique_items,
            modules=plan.modules.to_dict(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error modifying plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to modify plan: {str(e)}")


@router.post("/plan/{plan_id}/approve")
async def approve_plan(plan_id: str) -> dict[str, Any]:
    """
    Approve a build plan for execution.
    
    This marks the plan as approved but doesn't execute it yet.
    Use /plan/{plan_id}/execute to actually build the channel.
    """
    try:
        from ..ai_agent.build_plan_generator import BuildStatus
        
        plan = _build_plans.get(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
        
        if not plan.is_ready():
            raise HTTPException(
                status_code=400,
                detail="Plan is not ready for approval. Check warnings.",
            )
        
        plan.approve()
        _build_plans[plan_id] = plan
        
        return {
            "success": True,
            "plan_id": plan_id,
            "status": plan.status.value,
            "message": "Plan approved. Ready for execution.",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error approving plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve plan: {str(e)}")


@router.post("/plan/{plan_id}/execute")
async def execute_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Execute an approved build plan to create the channel.
    
    Creates the channel, collections, block schedules, program schedule,
    and playout according to the plan configuration.
    
    v2.5.0: Now creates database Block entities from AI-generated schedule blocks.
    """
    try:
        from ..ai_agent.build_plan_generator import BuildStatus
        from ..ai_agent.collection_executor import CollectionExecutor
        from ..ai_agent.block_executor import BlockScheduleExecutor
        from ..database.models import Channel, Playout, ProgramSchedule
        from ..database.models.schedule import ProgramScheduleItem
        
        plan = _build_plans.get(plan_id)
        
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
        
        if plan.status != BuildStatus.APPROVED:
            raise HTTPException(
                status_code=400,
                detail=f"Plan must be approved before execution. Current status: {plan.status.value}",
            )
        
        plan.status = BuildStatus.BUILDING
        _build_plans[plan_id] = plan
        
        try:
            # 1. Create channel
            channel = Channel(
                name=plan.channel.name,
                number=plan.channel.number or str(100 + len(_build_plans)),
                group=plan.channel.group,
                enabled=plan.channel.enabled,
            )
            db.add(channel)
            await db.flush()
            
            logger.info(f"Created channel '{channel.name}' (id={channel.id})")
            
            # 2. Create collections from plan
            collection_executor = CollectionExecutor()
            collection_result = await collection_executor.execute(plan, db)
            collection_map = collection_result.name_to_id
            
            logger.info(f"Created {collection_result.collection_count} collections")
            
            # 3. Create block schedule from plan
            block_executor = BlockScheduleExecutor()
            block_result = await block_executor.execute(
                plan=plan,
                channel_name=plan.channel.name,
                collection_map=collection_map,
                db=db,
            )
            
            logger.info(
                f"Created BlockGroup '{block_result.group_name}' with "
                f"{block_result.block_count} blocks, {block_result.items_created} items"
            )
            
            # 4. Create ProgramSchedule with settings from plan
            schedule_settings = plan.schedule if plan.schedule else None
            schedule = ProgramSchedule(
                name=f"{plan.channel.name} Schedule",
                keep_multi_part_episodes=schedule_settings.keep_multi_part_episodes if schedule_settings else True,
                treat_collections_as_shows=True,
                shuffle_schedule_items=schedule_settings.shuffle_schedule_items if schedule_settings else False,
            )
            db.add(schedule)
            await db.flush()
            
            logger.info(f"Created ProgramSchedule '{schedule.name}' (id={schedule.id})")
            
            # 5. Create ProgramScheduleItems linking to blocks/collections
            schedule_item_count = 0
            
            # Add items for each block
            for idx, block_info in enumerate(block_result.blocks):
                # Link schedule to blocks via collection reference
                # The block itself contains the time-based scheduling
                schedule_item = ProgramScheduleItem(
                    schedule_id=schedule.id,
                    position=idx + 1,
                    collection_type="block",
                    collection_id=block_info.id,
                    playback_mode="flood",
                    start_time=block_info.start_time,
                    playback_order="chronological",
                    guide_mode="normal",
                )
                db.add(schedule_item)
                schedule_item_count += 1
            
            # If no blocks but we have collections, add them directly
            if not block_result.blocks and collection_map:
                for idx, (name, coll_id) in enumerate(collection_map.items()):
                    schedule_item = ProgramScheduleItem(
                        schedule_id=schedule.id,
                        position=idx + 1,
                        collection_type="collection",
                        collection_id=coll_id,
                        playback_mode="flood",
                        playback_order="chronological",
                        guide_mode="normal",
                    )
                    db.add(schedule_item)
                    schedule_item_count += 1
            
            await db.flush()
            logger.info(f"Created {schedule_item_count} schedule items")
            
            # 6. Create playout
            playout = Playout(
                channel_id=channel.id,
                program_schedule_id=schedule.id,
                playout_type="continuous",
                is_active=True,
            )
            db.add(playout)
            await db.flush()
            
            logger.info(f"Created Playout (id={playout.id})")
            
            await db.commit()
            
            plan.status = BuildStatus.COMPLETE
            _build_plans[plan_id] = plan
            
            return {
                "success": True,
                "plan_id": plan_id,
                "status": plan.status.value,
                "channel_id": channel.id,
                "channel_name": channel.name,
                "channel_number": channel.number,
                "schedule_id": schedule.id,
                "playout_id": playout.id,
                "block_group_id": block_result.group_id,
                "blocks_created": block_result.block_count,
                "collections_created": collection_result.collection_count,
                "schedule_items_created": schedule_item_count,
                "message": "Channel created successfully with block schedule!",
            }
            
        except Exception as build_error:
            await db.rollback()
            plan.status = BuildStatus.FAILED
            _build_plans[plan_id] = plan
            logger.exception(f"Build failed: {build_error}")
            raise build_error
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error executing plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute plan: {str(e)}")


@router.delete("/plan/{plan_id}")
async def delete_plan(plan_id: str) -> dict[str, Any]:
    """
    Delete/cancel a build plan.
    """
    try:
        if plan_id not in _build_plans:
            raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
        
        del _build_plans[plan_id]
        
        return {
            "success": True,
            "message": f"Plan {plan_id} deleted",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")


# Session with Persona

@router.post("/start-with-persona", response_model=StartSessionWithPersonaResponse)
async def start_session_with_persona(
    request: StartSessionWithPersonaRequest,
    agent = Depends(get_channel_creator_agent),
) -> StartSessionWithPersonaResponse:
    """
    Start a new channel creation session with a specific persona.
    
    Returns a session with the selected persona's welcome message
    and character information.
    """
    try:
        from ..ai_agent.persona_manager import get_persona_manager, PersonaType
        
        manager = get_persona_manager()
        
        # Validate persona
        try:
            persona_type = PersonaType.from_string(request.persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid persona: {request.persona_id}")
        
        # Create session
        session = agent.create_session(request.session_id)
        
        # Get persona-specific welcome
        welcome = manager.get_welcome_message(persona_type)
        
        # Add welcome as first assistant message
        session.add_message("assistant", welcome)
        
        # Get persona info
        info = manager.get_persona_info(persona_type)
        
        return StartSessionWithPersonaResponse(
            session_id=session.session_id,
            welcome_message=welcome,
            stage=session.stage.value,
            persona=PersonaInfoResponse(
                id=info.persona_type.value,
                name=info.name,
                title=info.title,
                description=info.description,
                specialties=info.specialties,
                icon=info.icon,
                color=info.color,
            ),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error starting session with persona: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


# HTML UI Endpoint

@router.get("", response_class=HTMLResponse)
async def ai_channel_page(request: Request):
    """Serve the AI Channel Creator chat UI."""
    return templates.TemplateResponse(
        "ai_channel.html",
        {
            "request": request,
            "title": "AI Channel Creator",
        },
    )
