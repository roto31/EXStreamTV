"""
Persona Manager for AI Channel Creation

Central manager for handling persona selection, switching, and prompt generation.
Provides a unified interface for all AI channel creation personas.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from exstreamtv.ai_agent.prompts import (
    PERSONAS,
    get_persona,
    list_personas,
    # TV Executive
    TV_EXECUTIVE_PERSONA,
    build_channel_creation_prompt,
    # Sports Expert
    SPORTS_EXPERT_PERSONA,
    build_sports_channel_prompt,
    get_sports_welcome_message,
    # Tech Expert
    TECH_EXPERT_PERSONA,
    build_tech_channel_prompt,
    get_tech_welcome_message,
    # Movie Critic
    MOVIE_CRITIC_PERSONA,
    build_movie_channel_prompt,
    get_movie_welcome_message,
    # Kids Expert
    KIDS_EXPERT_PERSONA,
    build_kids_channel_prompt,
    get_kids_welcome_message,
    # PBS Expert
    PBS_EXPERT_PERSONA,
    build_pbs_channel_prompt,
    get_pbs_welcome_message,
    # System Admin
    SYSTEM_ADMIN_PERSONA,
    build_troubleshooting_prompt,
    get_sysadmin_welcome_message,
)

logger = logging.getLogger(__name__)


class PersonaType(Enum):
    """Available persona types for channel creation and troubleshooting."""
    
    TV_EXECUTIVE = "tv_executive"
    SPORTS_EXPERT = "sports_expert"
    TECH_EXPERT = "tech_expert"
    MOVIE_CRITIC = "movie_critic"
    KIDS_EXPERT = "kids_expert"
    PBS_EXPERT = "pbs_expert"
    SYSTEM_ADMIN = "system_admin"
    
    @classmethod
    def from_string(cls, value: str) -> "PersonaType":
        """Convert string to PersonaType."""
        for persona in cls:
            if persona.value == value:
                return persona
        raise ValueError(f"Unknown persona type: {value}")
    
    @classmethod
    def all_types(cls) -> list["PersonaType"]:
        """Get all available persona types."""
        return list(cls)


@dataclass
class PersonaInfo:
    """Information about a persona."""
    
    persona_type: PersonaType
    name: str
    title: str
    description: str
    specialties: list[str]
    welcome_message: str | None = None
    icon: str = "person"  # SF Symbol or icon name
    color: str = "#007AFF"  # Primary color for UI
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.persona_type.value,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "specialties": self.specialties,
            "icon": self.icon,
            "color": self.color,
        }


@dataclass
class PersonaContext:
    """Context for persona-based conversation."""
    
    persona_type: PersonaType
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    available_media: dict[str, Any] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    session_data: dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
        })
    
    def get_history(self) -> list[dict[str, str]]:
        """Get conversation history."""
        return self.conversation_history.copy()
    
    def clear_history(self) -> None:
        """Clear conversation history."""
        self.conversation_history.clear()


class PersonaManager:
    """
    Manages AI personas for channel creation.
    
    Provides centralized access to all personas, handles persona switching,
    and builds appropriate prompts for each persona type.
    """
    
    # Persona metadata with descriptions and UI info
    PERSONA_METADATA = {
        PersonaType.TV_EXECUTIVE: PersonaInfo(
            persona_type=PersonaType.TV_EXECUTIVE,
            name="Max Sterling",
            title="TV Programming Executive",
            description="A veteran 1970s-80s TV programming executive who knows classic TV scheduling, dayparts, and the art of building compelling channel lineups.",
            specialties=["classic_tv", "scheduling", "dayparts", "commercials", "network_programming"],
            icon="tv",
            color="#FF9500",
        ),
        PersonaType.SPORTS_EXPERT: PersonaInfo(
            persona_type=PersonaType.SPORTS_EXPERT,
            name="Howard 'The Stat' Kowalski",
            title="Sports Savant",
            description="A legendary sports statistician with encyclopedic knowledge of sports history, classic games, and where to find vintage sports content online.",
            specialties=["sports", "classic_games", "documentaries", "youtube", "archive_org"],
            icon="sportscourt",
            color="#34C759",
        ),
        PersonaType.TECH_EXPERT: PersonaInfo(
            persona_type=PersonaType.TECH_EXPERT,
            name="Steve 'Woz' Nakamura",
            title="Tech Savant",
            description="A tech historian and Apple devotee who knows every keynote, product launch, and piece of tech media ever created.",
            specialties=["technology", "apple", "computing", "keynotes", "retro_tech"],
            icon="desktopcomputer",
            color="#5856D6",
        ),
        PersonaType.MOVIE_CRITIC: PersonaInfo(
            persona_type=PersonaType.MOVIE_CRITIC,
            name="Vincent Marlowe & Clara Fontaine",
            title="Movie Critics",
            description="A legendary pair of film critics who debate and collaborate on building the perfect movie channels, from classics to hidden gems.",
            specialties=["movies", "film_history", "directors", "genres", "international_cinema"],
            icon="film",
            color="#FF2D55",
        ),
        PersonaType.KIDS_EXPERT: PersonaInfo(
            persona_type=PersonaType.KIDS_EXPERT,
            name="Professor Patricia 'Pepper' Chen",
            title="Kids Programming Expert",
            description="A children's media specialist with deep Disney knowledge and expertise in age-appropriate, educational content.",
            specialties=["children", "disney", "animation", "educational", "family"],
            icon="figure.2.and.child.holdinghands",
            color="#FF9500",
        ),
        PersonaType.PBS_EXPERT: PersonaInfo(
            persona_type=PersonaType.PBS_EXPERT,
            name="Dr. Eleanor Marsh",
            title="PBS Programming Expert",
            description="A public television veteran who believes in television as a public good, specializing in documentaries, British drama, and educational content.",
            specialties=["documentary", "educational", "pbs", "british_drama", "public_television"],
            icon="book",
            color="#007AFF",
        ),
        PersonaType.SYSTEM_ADMIN: PersonaInfo(
            persona_type=PersonaType.SYSTEM_ADMIN,
            name="Alex Chen",
            title="DevOps Engineer",
            description="A senior DevOps engineer with deep expertise in media streaming infrastructure, log analysis, and system troubleshooting.",
            specialties=["troubleshooting", "logs", "ffmpeg", "plex", "devops", "debugging"],
            icon="wrench.and.screwdriver",
            color="#FF3B30",
        ),
    }
    
    # Prompt builders for each persona
    PROMPT_BUILDERS: dict[PersonaType, Callable] = {
        PersonaType.TV_EXECUTIVE: build_channel_creation_prompt,
        PersonaType.SPORTS_EXPERT: build_sports_channel_prompt,
        PersonaType.TECH_EXPERT: build_tech_channel_prompt,
        PersonaType.MOVIE_CRITIC: build_movie_channel_prompt,
        PersonaType.KIDS_EXPERT: build_kids_channel_prompt,
        PersonaType.PBS_EXPERT: build_pbs_channel_prompt,
        PersonaType.SYSTEM_ADMIN: build_troubleshooting_prompt,
    }
    
    # Welcome message getters for each persona
    WELCOME_GETTERS: dict[PersonaType, Callable] = {
        PersonaType.SPORTS_EXPERT: get_sports_welcome_message,
        PersonaType.TECH_EXPERT: get_tech_welcome_message,
        PersonaType.MOVIE_CRITIC: get_movie_welcome_message,
        PersonaType.KIDS_EXPERT: get_kids_welcome_message,
        PersonaType.PBS_EXPERT: get_pbs_welcome_message,
        PersonaType.SYSTEM_ADMIN: get_sysadmin_welcome_message,
    }
    
    def __init__(self, default_persona: PersonaType = PersonaType.TV_EXECUTIVE):
        """
        Initialize the persona manager.
        
        Args:
            default_persona: The default persona to use
        """
        self.default_persona = default_persona
        self._contexts: dict[str, PersonaContext] = {}
        
        logger.info(f"PersonaManager initialized with default persona: {default_persona.value}")
    
    def get_all_personas(self) -> list[PersonaInfo]:
        """Get information about all available personas."""
        return list(self.PERSONA_METADATA.values())
    
    def get_persona_info(self, persona_type: PersonaType) -> PersonaInfo:
        """Get information about a specific persona."""
        return self.PERSONA_METADATA[persona_type]
    
    def get_persona_data(self, persona_type: PersonaType) -> dict[str, Any] | None:
        """Get the data registries for a persona (e.g., YOUTUBE_SPORTS_CHANNELS)."""
        persona = get_persona(persona_type.value)
        if persona:
            return persona.get("data")
        return None
    
    def create_context(
        self,
        session_id: str,
        persona_type: PersonaType | None = None,
        available_media: dict[str, Any] | None = None,
    ) -> PersonaContext:
        """
        Create a new persona context for a session.
        
        Args:
            session_id: Unique session identifier
            persona_type: Persona to use (defaults to default_persona)
            available_media: Available media sources
            
        Returns:
            New PersonaContext
        """
        context = PersonaContext(
            persona_type=persona_type or self.default_persona,
            available_media=available_media or {},
        )
        self._contexts[session_id] = context
        
        logger.debug(f"Created persona context for session {session_id}: {context.persona_type.value}")
        return context
    
    def get_context(self, session_id: str) -> PersonaContext | None:
        """Get an existing persona context."""
        return self._contexts.get(session_id)
    
    def switch_persona(
        self,
        session_id: str,
        new_persona: PersonaType,
        preserve_history: bool = False,
    ) -> PersonaContext | None:
        """
        Switch the persona for a session.
        
        Args:
            session_id: Session identifier
            new_persona: New persona to use
            preserve_history: Whether to keep conversation history
            
        Returns:
            Updated PersonaContext or None if session not found
        """
        context = self._contexts.get(session_id)
        if not context:
            return None
        
        old_persona = context.persona_type
        context.persona_type = new_persona
        
        if not preserve_history:
            context.clear_history()
        
        logger.info(f"Switched persona for session {session_id}: {old_persona.value} -> {new_persona.value}")
        return context
    
    def delete_context(self, session_id: str) -> bool:
        """Delete a persona context."""
        if session_id in self._contexts:
            del self._contexts[session_id]
            return True
        return False
    
    def get_welcome_message(self, persona_type: PersonaType) -> str:
        """
        Get the welcome message for a persona.
        
        Args:
            persona_type: The persona type
            
        Returns:
            Welcome message string
        """
        # Check if persona has a dedicated welcome getter
        if persona_type in self.WELCOME_GETTERS:
            return self.WELCOME_GETTERS[persona_type]()
        
        # For TV Executive, use the existing method from channel_creator
        if persona_type == PersonaType.TV_EXECUTIVE:
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
        
        # Fallback generic message
        info = self.PERSONA_METADATA[persona_type]
        return f"Hello! I'm {info.name}, your {info.title}. How can I help you build your channel today?"
    
    def build_prompt(
        self,
        session_id: str,
        user_message: str,
    ) -> str | None:
        """
        Build a prompt for the current persona.
        
        Args:
            session_id: Session identifier
            user_message: The user's message
            
        Returns:
            Complete prompt string or None if session not found
        """
        context = self._contexts.get(session_id)
        if not context:
            return None
        
        builder = self.PROMPT_BUILDERS.get(context.persona_type)
        if not builder:
            logger.error(f"No prompt builder for persona: {context.persona_type.value}")
            return None
        
        # Build the prompt
        prompt = builder(
            user_message=user_message,
            conversation_history=context.get_history(),
            available_media=context.available_media if context.available_media else None,
        )
        
        return prompt
    
    def suggest_persona(self, user_request: str) -> PersonaType:
        """
        Suggest the best persona based on user's initial request.
        
        Args:
            user_request: The user's channel creation request
            
        Returns:
            Suggested PersonaType
        """
        request_lower = user_request.lower()
        
        # Sports keywords
        sports_keywords = [
            "sport", "nfl", "nba", "mlb", "nhl", "football", "basketball", "baseball",
            "hockey", "soccer", "boxing", "olympics", "game", "championship", "super bowl",
            "world series", "playoffs", "espn", "classic game", "highlights"
        ]
        if any(kw in request_lower for kw in sports_keywords):
            return PersonaType.SPORTS_EXPERT
        
        # Tech keywords
        tech_keywords = [
            "tech", "apple", "iphone", "mac", "computer", "keynote", "wwdc", "steve jobs",
            "silicon", "programming", "coding", "gadget", "retro computing", "vintage tech"
        ]
        if any(kw in request_lower for kw in tech_keywords):
            return PersonaType.TECH_EXPERT
        
        # Movie keywords
        movie_keywords = [
            "movie", "film", "cinema", "director", "actor", "actress", "oscar", "hollywood",
            "noir", "western", "horror", "sci-fi", "thriller", "documentary film", "criterion",
            "classic film", "double feature", "marathon"
        ]
        if any(kw in request_lower for kw in movie_keywords):
            return PersonaType.MOVIE_CRITIC
        
        # Kids keywords
        kids_keywords = [
            "kid", "child", "disney", "pixar", "cartoon", "animation", "family", "educational",
            "sesame", "nickelodeon", "pbs kids", "preschool", "bluey", "frozen", "toy story"
        ]
        if any(kw in request_lower for kw in kids_keywords):
            return PersonaType.KIDS_EXPERT
        
        # PBS keywords
        pbs_keywords = [
            "pbs", "documentary", "nature", "nova", "frontline", "masterpiece", "british",
            "educational", "ken burns", "public television", "bbc", "cultural", "arts"
        ]
        if any(kw in request_lower for kw in pbs_keywords):
            return PersonaType.PBS_EXPERT
        
        # Default to TV Executive for general requests
        return PersonaType.TV_EXECUTIVE
    
    def get_persona_for_content_type(self, content_types: list[str]) -> PersonaType:
        """
        Get the best persona based on content types.
        
        Args:
            content_types: List of content type strings
            
        Returns:
            Best matching PersonaType
        """
        content_lower = [ct.lower() for ct in content_types]
        
        # Score each persona based on content match
        scores = {persona: 0 for persona in PersonaType}
        
        for content in content_lower:
            if content in ["sports", "games", "athletics"]:
                scores[PersonaType.SPORTS_EXPERT] += 2
            if content in ["tech", "technology", "computing"]:
                scores[PersonaType.TECH_EXPERT] += 2
            if content in ["movies", "films", "cinema"]:
                scores[PersonaType.MOVIE_CRITIC] += 2
            if content in ["kids", "children", "family", "animation"]:
                scores[PersonaType.KIDS_EXPERT] += 2
            if content in ["documentary", "educational", "pbs"]:
                scores[PersonaType.PBS_EXPERT] += 2
            if content in ["tv", "television", "series", "shows"]:
                scores[PersonaType.TV_EXECUTIVE] += 1
        
        # Return persona with highest score, defaulting to TV Executive
        best_persona = max(scores, key=scores.get)
        if scores[best_persona] == 0:
            return PersonaType.TV_EXECUTIVE
        
        return best_persona


# Singleton instance
_manager: PersonaManager | None = None


def get_persona_manager() -> PersonaManager:
    """Get the global PersonaManager instance."""
    global _manager
    if _manager is None:
        _manager = PersonaManager()
    return _manager


def set_persona_manager(manager: PersonaManager) -> None:
    """Set the global PersonaManager instance."""
    global _manager
    _manager = manager
