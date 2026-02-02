"""
AI-Powered Channel Creator Agent

Orchestrates channel creation through natural language conversation using the
TV Programming Executive persona. Handles intent parsing, media queries,
and schedule generation.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from exstreamtv.ai_agent.prompts.tv_executive import (
    TV_EXECUTIVE_SYSTEM_PROMPT,
    build_channel_creation_prompt,
)

logger = logging.getLogger(__name__)


class ChannelCreationStage(Enum):
    """Stages in the channel creation conversation."""
    
    INITIAL = "initial"  # Just started, gathering basic info
    SOURCES = "sources"  # Discussing content sources
    SCHEDULE = "schedule"  # Defining schedule structure
    DETAILS = "details"  # Fine-tuning details
    READY = "ready"  # Specification complete, ready to build
    BUILDING = "building"  # Currently building the channel
    COMPLETE = "complete"  # Channel created successfully
    ERROR = "error"  # Error occurred


@dataclass
class ChannelIntent:
    """Parsed intent from user's channel creation request."""
    
    # Basic channel info
    channel_name: str | None = None
    channel_number: str | None = None
    description: str | None = None
    
    # Era preferences
    era_start: int | None = None
    era_end: int | None = None
    
    # Content sources
    use_plex: bool = False
    use_archive_org: bool = False
    use_youtube: bool = False
    plex_libraries: list[str] = field(default_factory=list)
    
    # Genre preferences
    genres: list[str] = field(default_factory=list)
    excluded_genres: list[str] = field(default_factory=list)
    
    # Schedule preferences
    is_24_hour: bool = True
    dayparts: dict[str, dict[str, Any]] = field(default_factory=dict)
    special_blocks: list[dict[str, Any]] = field(default_factory=list)
    
    # Commercial settings
    commercials_enabled: bool = False
    commercial_source: str = "archive_org"
    commercial_collection: str = "prelinger"
    
    # Holiday programming
    holiday_programming: bool = False
    
    # Scheduling rules
    start_on_hour: bool = True
    start_on_half_hour: bool = True
    chronological_episodes: bool = True
    no_repeat_in_block: bool = True
    genre_grouping: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "channel_name": self.channel_name,
            "channel_number": self.channel_number,
            "description": self.description,
            "era": {"start": self.era_start, "end": self.era_end},
            "sources": {
                "plex": self.use_plex,
                "archive_org": self.use_archive_org,
                "youtube": self.use_youtube,
                "plex_libraries": self.plex_libraries,
            },
            "genres": self.genres,
            "excluded_genres": self.excluded_genres,
            "schedule": {
                "is_24_hour": self.is_24_hour,
                "dayparts": self.dayparts,
                "special_blocks": self.special_blocks,
            },
            "commercials": {
                "enabled": self.commercials_enabled,
                "source": self.commercial_source,
                "collection": self.commercial_collection,
            },
            "holiday_programming": self.holiday_programming,
            "scheduling_rules": {
                "start_on_hour": self.start_on_hour,
                "start_on_half_hour": self.start_on_half_hour,
                "chronological_episodes": self.chronological_episodes,
                "no_repeat_in_block": self.no_repeat_in_block,
                "genre_grouping": self.genre_grouping,
            },
        }


@dataclass
class ChannelSpecification:
    """Complete channel specification ready for building."""
    
    name: str
    number: str | None = None
    description: str = ""
    
    # Sources configuration
    sources: list[str] = field(default_factory=list)
    era: dict[str, int] = field(default_factory=dict)
    
    # Daypart configuration
    dayparts: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Special programming blocks
    special_blocks: list[dict[str, Any]] = field(default_factory=list)
    
    # Commercial configuration
    commercials: dict[str, Any] = field(default_factory=dict)
    
    # Holiday configuration
    holidays: dict[str, bool] = field(default_factory=dict)
    
    # Scheduling rules
    scheduling_rules: dict[str, bool] = field(default_factory=dict)
    
    # Raw specification from AI
    raw_spec: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_ai_response(cls, spec_dict: dict[str, Any]) -> "ChannelSpecification":
        """Create specification from AI-generated JSON."""
        channel_spec = spec_dict.get("channel_spec", spec_dict)
        
        # Handle era - can be at top level or inside "focus" object
        era = channel_spec.get("era", {})
        if not era and "focus" in channel_spec:
            focus = channel_spec.get("focus", {})
            era = focus.get("era", {})
            # Normalize era format - might have start_year/end_year or start/end
            if era and "start_year" in era:
                era = {"start": era.get("start_year"), "end": era.get("end_year")}
        
        # Handle sources - can be at top level or inside "focus"
        sources = channel_spec.get("sources", [])
        if not sources and "focus" in channel_spec:
            focus = channel_spec.get("focus", {})
            sources = focus.get("sources", [])
        
        # Handle dayparts - normalize format
        dayparts = channel_spec.get("dayparts", {})
        
        # Handle special blocks / weekly specials
        special_blocks = channel_spec.get("special_blocks", [])
        if not special_blocks:
            special_blocks = channel_spec.get("weekly_specials", [])
        
        # Handle commercials - check content_blocks for vintage_commercials
        commercials = channel_spec.get("commercials", {})
        if not commercials:
            content_blocks = channel_spec.get("content_blocks", {})
            if "vintage_commercials" in content_blocks:
                commercials = {
                    "enabled": True,
                    "source": content_blocks["vintage_commercials"].get("source", "archive_org"),
                    "collection": content_blocks["vintage_commercials"].get("collection", "prelinger"),
                }
        
        return cls(
            name=channel_spec.get("name", "AI Generated Channel"),
            number=channel_spec.get("number"),
            description=channel_spec.get("description", ""),
            sources=sources,
            era=era,
            dayparts=dayparts,
            special_blocks=special_blocks,
            commercials=commercials,
            holidays=channel_spec.get("holidays", {}),
            scheduling_rules=channel_spec.get("scheduling_rules", {}),
            raw_spec=spec_dict,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "number": self.number,
            "description": self.description,
            "sources": self.sources,
            "era": self.era,
            "dayparts": self.dayparts,
            "special_blocks": self.special_blocks,
            "commercials": self.commercials,
            "holidays": self.holidays,
            "scheduling_rules": self.scheduling_rules,
        }


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelCreationSession:
    """Session state for channel creation conversation."""
    
    session_id: str
    stage: ChannelCreationStage = ChannelCreationStage.INITIAL
    messages: list[ConversationMessage] = field(default_factory=list)
    intent: ChannelIntent = field(default_factory=ChannelIntent)
    specification: ChannelSpecification | None = None
    available_media: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: str | None = None
    
    # Created resources (for cleanup on cancel)
    created_channel_id: int | None = None
    created_collection_ids: list[int] = field(default_factory=list)
    created_schedule_id: int | None = None
    created_playout_id: int | None = None
    
    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a message to the conversation."""
        self.messages.append(ConversationMessage(
            role=role,
            content=content,
            metadata=metadata or {},
        ))
        self.updated_at = datetime.utcnow()
    
    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get conversation history in format for AI prompt."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "stage": self.stage.value,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in self.messages
            ],
            "intent": self.intent.to_dict(),
            "specification": self.specification.to_dict() if self.specification else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_message": self.error_message,
            "created_resources": {
                "channel_id": self.created_channel_id,
                "collection_ids": self.created_collection_ids,
                "schedule_id": self.created_schedule_id,
                "playout_id": self.created_playout_id,
            },
        }


class ChannelCreatorAgent:
    """
    AI agent for creating channels through natural language conversation.
    
    Uses the TV Programming Executive persona to guide users through
    channel creation, asking clarifying questions and generating
    complete channel specifications.
    """
    
    def __init__(
        self,
        ollama_client: Any,
        media_aggregator: Any | None = None,
        schedule_generator: Any | None = None,
    ):
        """
        Initialize the channel creator agent.
        
        Args:
            ollama_client: OllamaClient instance for AI queries
            media_aggregator: Optional MediaAggregator for querying sources
            schedule_generator: Optional ScheduleGenerator for building schedules
        """
        self.ollama_client = ollama_client
        self.media_aggregator = media_aggregator
        self.schedule_generator = schedule_generator
        
        # Active sessions stored in memory
        self._sessions: dict[str, ChannelCreationSession] = {}
    
    def create_session(self, session_id: str | None = None) -> ChannelCreationSession:
        """
        Create a new channel creation session.
        
        Args:
            session_id: Optional custom session ID
            
        Returns:
            New ChannelCreationSession
        """
        import uuid
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        session = ChannelCreationSession(session_id=session_id)
        self._sessions[session_id] = session
        
        logger.info(f"Created new channel creation session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> ChannelCreationSession | None:
        """Get an existing session by ID."""
        return self._sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted channel creation session: {session_id}")
            return True
        return False
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return [
            {
                "session_id": session.session_id,
                "stage": session.stage.value,
                "message_count": len(session.messages),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }
            for session in self._sessions.values()
        ]
    
    async def process_message(
        self,
        session_id: str,
        user_message: str,
    ) -> dict[str, Any]:
        """
        Process a user message in a channel creation conversation.
        
        Args:
            session_id: Session ID
            user_message: User's message
            
        Returns:
            Response dict with AI response and session state
        """
        session = self.get_session(session_id)
        if not session:
            return {
                "success": False,
                "error": "Session not found",
            }
        
        try:
            # Add user message to history
            session.add_message("user", user_message)
            
            # Get available media context if aggregator is available
            if self.media_aggregator and not session.available_media:
                try:
                    session.available_media = await self.media_aggregator.get_available_sources()
                except Exception as e:
                    logger.warning(f"Could not fetch available media: {e}")
            
            # Build prompt with conversation history
            prompt = build_channel_creation_prompt(
                user_message=user_message,
                conversation_history=session.get_conversation_history()[:-1],  # Exclude current message
                available_media=session.available_media if session.available_media else None,
            )
            
            # Query Ollama
            ai_response = await self._query_ollama(prompt)
            
            if not ai_response:
                session.stage = ChannelCreationStage.ERROR
                session.error_message = "Failed to get AI response"
                return {
                    "success": False,
                    "error": "Failed to get AI response",
                    "session": session.to_dict(),
                }
            
            # Add AI response to history
            session.add_message("assistant", ai_response)
            
            # Check if response contains a ready specification
            spec = self._extract_specification(ai_response)
            
            if spec and spec.get("ready_to_build"):
                session.specification = ChannelSpecification.from_ai_response(spec)
                session.stage = ChannelCreationStage.READY
                logger.info(f"Session {session_id} ready to build channel")
                logger.debug(f"Session {session_id} specification: name={session.specification.name}, sources={session.specification.sources}")
            else:
                # Update stage based on conversation progress
                session.stage = self._infer_stage(session)
            
            return {
                "success": True,
                "response": ai_response,
                "stage": session.stage.value,
                "ready_to_build": session.stage == ChannelCreationStage.READY,
                "specification": session.specification.to_dict() if session.specification else None,
                "session": session.to_dict(),
            }
            
        except Exception as e:
            logger.exception(f"Error processing message in session {session_id}: {e}")
            session.stage = ChannelCreationStage.ERROR
            session.error_message = str(e)
            return {
                "success": False,
                "error": str(e),
                "session": session.to_dict(),
            }
    
    async def build_channel(
        self,
        session_id: str,
        db_session: Any,
    ) -> dict[str, Any]:
        """
        Build the channel from the conversation specification.
        
        Args:
            session_id: Session ID
            db_session: Database session for creating resources
            
        Returns:
            Result dict with created channel info
        """
        import uuid
        
        session = self.get_session(session_id)
        if not session:
            return {"success": False, "error": "Session not found"}
        
        if session.stage != ChannelCreationStage.READY:
            return {"success": False, "error": "Session not ready to build"}
        
        if not session.specification:
            return {"success": False, "error": "No specification available"}
        
        session.stage = ChannelCreationStage.BUILDING
        
        try:
            # Import here to avoid circular imports
            from sqlalchemy import select
            from exstreamtv.database.models import Channel, Deco, Playout, ProgramSchedule
            
            spec = session.specification
            
            # 1. Create the channel with new ErsatzTV-compatible fields
            # Generate channel number if not specified
            channel_number = spec.number
            if not channel_number:
                channel_number = await self._generate_channel_number(db_session)
                logger.info(f"Auto-assigned channel number: {channel_number}")
            
            channel = Channel(
                name=spec.name,
                number=channel_number,
                unique_id=str(uuid.uuid4()),  # Generate unique ID for stable references
                group="AI Generated",
                categories=spec.raw_spec.get("categories", "AI,Generated"),
                enabled=True,
            )
            db_session.add(channel)
            await db_session.flush()
            session.created_channel_id = channel.id
            
            # 2. Create Deco configuration if specified
            deco = await self._create_deco_config(spec, db_session)
            deco_id = deco.id if deco else None
            
            # 2. Create collections for content sources
            if self.media_aggregator:
                collection_ids = await self._create_collections(
                    spec, db_session, session
                )
                session.created_collection_ids = collection_ids
            
            # 3. Create schedule
            schedule = ProgramSchedule(
                name=f"{spec.name} Schedule",
                keep_multi_part_episodes=True,
                treat_collections_as_shows=True,
                shuffle_schedule_items=False,
                random_start_point=False,
            )
            db_session.add(schedule)
            await db_session.flush()
            session.created_schedule_id = schedule.id
            
            # 4. Generate schedule items if generator available
            if self.schedule_generator:
                await self.schedule_generator.generate_schedule_items(
                    spec, schedule.id, db_session
                )
            
            # 5. Create playout with Deco reference
            playout = Playout(
                channel_id=channel.id,
                program_schedule_id=schedule.id,
                deco_id=deco_id,
                playout_type="continuous",
                schedule_kind="flood",  # AI-created channels use flood mode
                is_active=True,
            )
            db_session.add(playout)
            await db_session.flush()
            session.created_playout_id = playout.id
            
            await db_session.commit()
            
            session.stage = ChannelCreationStage.COMPLETE
            
            logger.info(
                f"Created channel '{spec.name}' (ID: {channel.id}) "
                f"from session {session_id}"
            )
            
            return {
                "success": True,
                "channel_id": channel.id,
                "channel_number": channel.number,
                "channel_name": channel.name,
                "unique_id": channel.unique_id,
                "schedule_id": schedule.id,
                "playout_id": playout.id,
                "deco_id": deco_id,
                "collection_ids": session.created_collection_ids,
                "session": session.to_dict(),
            }
            
        except Exception as e:
            logger.exception(f"Error building channel from session {session_id}: {e}")
            session.stage = ChannelCreationStage.ERROR
            session.error_message = str(e)
            
            # Rollback will happen automatically, but clear our references
            await db_session.rollback()
            
            return {
                "success": False,
                "error": str(e),
                "session": session.to_dict(),
            }
    
    async def _query_ollama(self, prompt: str) -> str | None:
        """Query Ollama with the given prompt."""
        try:
            # Check if client has chat method (extended) or just generate
            if hasattr(self.ollama_client, "chat"):
                response = await self.ollama_client.chat(prompt)
            else:
                response = await self.ollama_client._generate(prompt)
            
            return response if response else None
            
        except Exception as e:
            logger.exception(f"Error querying Ollama: {e}")
            return None
    
    def _extract_specification(self, response: str) -> dict[str, Any] | None:
        """Extract JSON specification from AI response."""
        try:
            # Look for JSON block in response
            json_match = re.search(
                r'```json\s*(.*?)\s*```',
                response,
                re.DOTALL,
            )
            
            if json_match:
                json_str = json_match.group(1)
                spec = json.loads(json_str)
                return spec
            
            # Try to find raw JSON object
            start_idx = response.find('{"ready_to_build"')
            if start_idx == -1:
                start_idx = response.find('{\n  "ready_to_build"')
            
            if start_idx != -1:
                # Find matching closing brace
                brace_count = 0
                end_idx = start_idx
                for i, char in enumerate(response[start_idx:]):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = start_idx + i + 1
                            break
                
                if end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    spec = json.loads(json_str)
                    return spec
            
            return None
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from response: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error extracting specification: {e}")
            return None
    
    def _infer_stage(self, session: ChannelCreationSession) -> ChannelCreationStage:
        """Infer conversation stage based on what's been discussed."""
        message_count = len(session.messages)
        
        if message_count <= 2:
            return ChannelCreationStage.INITIAL
        
        # Look at recent messages for keywords
        recent_content = " ".join([
            msg.content.lower() 
            for msg in session.messages[-4:]
        ])
        
        if any(word in recent_content for word in ["plex", "archive", "youtube", "library", "source"]):
            return ChannelCreationStage.SOURCES
        
        if any(word in recent_content for word in ["schedule", "primetime", "daytime", "block", "hour"]):
            return ChannelCreationStage.SCHEDULE
        
        if any(word in recent_content for word in ["commercial", "holiday", "detail", "adjust"]):
            return ChannelCreationStage.DETAILS
        
        return ChannelCreationStage.SOURCES
    
    async def _generate_channel_number(self, db_session: Any = None) -> str:
        """Generate a unique channel number.
        
        If db_session is provided, finds the next available number.
        Otherwise, generates a random number in the 200-299 range for AI channels.
        """
        import random
        
        if db_session:
            try:
                # Get all existing channel numbers
                from sqlalchemy import select
                from exstreamtv.database.models import Channel
                
                result = await db_session.execute(select(Channel.number))
                existing_numbers = result.scalars().all()
                
                # Find numeric channels and get the max
                numeric_numbers = []
                for num in existing_numbers:
                    if num and num.isdigit():
                        numeric_numbers.append(int(num))
                
                if numeric_numbers:
                    max_num = max(numeric_numbers)
                    # AI channels start at 200, but go higher if needed
                    next_num = max(max_num + 1, 200)
                    return str(next_num)
                else:
                    return "200"  # Start AI channels at 200
                    
            except Exception as e:
                logger.warning(f"Could not query for next channel number: {e}")
        
        # Fallback: generate random in AI range (200-299)
        return str(random.randint(200, 299))
    
    async def _create_collections(
        self,
        spec: ChannelSpecification,
        db_session: Any,
        session: ChannelCreationSession,
    ) -> list[int]:
        """Create collections based on specification."""
        collection_ids = []
        
        # This would use the media aggregator to create smart collections
        # based on the specification's genres, era, and sources
        
        # For now, return empty list - actual implementation will
        # query media sources and create appropriate collections
        
        return collection_ids
    
    async def _create_deco_config(
        self,
        spec: ChannelSpecification,
        db_session: Any,
    ) -> Any | None:
        """
        Create Deco configuration based on channel specification.
        
        Args:
            spec: Channel specification with deco preferences
            db_session: Database session
            
        Returns:
            Created Deco entity or None
        """
        from exstreamtv.database.models import Deco
        
        # Check if deco configuration is specified
        deco_config = spec.raw_spec.get("deco", {})
        commercials_config = spec.commercials or {}
        
        # Determine deco modes based on specification
        watermark_mode = "inherit"
        default_filler_mode = "inherit"
        dead_air_fallback_mode = "inherit"
        
        if commercials_config.get("enabled"):
            default_filler_mode = "override"
        
        # Create the Deco entity
        deco = Deco(
            name=f"{spec.name} Deco",
            watermark_mode=deco_config.get("watermark_mode", watermark_mode),
            graphics_elements_mode="inherit",
            break_content_mode="inherit",
            default_filler_mode=default_filler_mode,
            default_filler_trim_to_fit=deco_config.get("trim_filler", False),
            dead_air_fallback_mode=dead_air_fallback_mode,
        )
        
        db_session.add(deco)
        await db_session.flush()
        
        logger.info(f"Created Deco configuration '{deco.name}' (ID: {deco.id})")
        
        return deco
    
    async def get_welcome_message(self) -> str:
        """Get the initial welcome message from the TV Executive."""
        return """Well hello there! Max Sterling here, former VP of Programming at CBS. 
I spent fifteen years putting together schedules that won time periods and kept Americans 
glued to their sets.

I hear you're looking to build a television channel. That's music to my ears! 
Nothing quite like the feeling of crafting the perfect programming lineup.

So, what kind of channel do you have in mind? Are we talking classic TV from the 
golden age of the '70s and '80s? Movies? Cartoons? Tell me your vision and I'll 
help you put together a schedule that would make Brandon Tartikoff proud.

Also, what's your content situation? Do you have a Plex library with shows, or 
are we pulling from the archives?"""
