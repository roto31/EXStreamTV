"""
AI Agent Prompts Module

Contains persona definitions and prompt templates for AI-powered features.

Version 2.2.0 Personas:
- TV Executive (Max Sterling) - Classic TV programming expert
- Sports Savant (Howard "The Stat" Kowalski) - Sports historian, Schwab-style
- Tech Savant (Steve "Woz" Nakamura) - Technology historian, Apple specialist
- Movie Critics (Vincent & Clara) - Film critics, Siskel & Ebert style
- Kids Expert (Professor Pepper) - Children's programming, Disney specialist
- PBS Expert (Dr. Eleanor Marsh) - PBS programming historian
"""

from exstreamtv.ai_agent.prompts.tv_executive import (
    TV_EXECUTIVE_PERSONA,
    TV_EXECUTIVE_SYSTEM_PROMPT,
    build_channel_creation_prompt,
    build_schedule_generation_prompt,
)

from exstreamtv.ai_agent.prompts.sports_expert import (
    SPORTS_EXPERT_PERSONA,
    SPORTS_EXPERT_SYSTEM_PROMPT,
    build_sports_channel_prompt,
    build_sports_schedule_prompt,
    get_sports_welcome_message,
    YOUTUBE_SPORTS_CHANNELS,
    ARCHIVE_ORG_SPORTS_COLLECTIONS,
    SPORTS_DOCUMENTARY_SERIES,
    SPORTS_MOVIES,
)

from exstreamtv.ai_agent.prompts.tech_expert import (
    TECH_EXPERT_PERSONA,
    TECH_EXPERT_SYSTEM_PROMPT,
    build_tech_channel_prompt,
    build_tech_schedule_prompt,
    get_tech_welcome_message,
    APPLE_KEYNOTES,
    APPLE_COMMERCIALS,
    YOUTUBE_TECH_CHANNELS,
    ARCHIVE_ORG_TECH_COLLECTIONS,
    TECH_DOCUMENTARIES,
)

from exstreamtv.ai_agent.prompts.movie_critic import (
    MOVIE_CRITIC_PERSONA,
    MOVIE_CRITIC_SYSTEM_PROMPT,
    build_movie_channel_prompt,
    build_movie_schedule_prompt,
    get_movie_welcome_message,
    FILM_GENRES,
    CLASSIC_DIRECTORS,
    FILM_MOVEMENTS,
    ARCHIVE_ORG_FILM_COLLECTIONS,
)

from exstreamtv.ai_agent.prompts.kids_expert import (
    KIDS_EXPERT_PERSONA,
    KIDS_EXPERT_SYSTEM_PROMPT,
    build_kids_channel_prompt,
    build_kids_schedule_prompt,
    get_kids_welcome_message,
    DISNEY_CONTENT,
    PIXAR_FILMS,
    CLASSIC_CARTOONS,
    EDUCATIONAL_SHOWS,
    HOLIDAY_SPECIALS,
    YOUTUBE_KIDS_CHANNELS,
)

from exstreamtv.ai_agent.prompts.pbs_expert import (
    PBS_EXPERT_PERSONA,
    PBS_EXPERT_SYSTEM_PROMPT,
    build_pbs_channel_prompt,
    build_pbs_schedule_prompt,
    get_pbs_welcome_message,
    PBS_DOCUMENTARY_SERIES,
    KEN_BURNS_DOCUMENTARIES,
    BRITISH_IMPORTS,
    CULTURAL_PROGRAMMING,
    PBS_KIDS_CLASSICS,
    PUBLIC_AFFAIRS,
    ARCHIVE_ORG_EDUCATIONAL,
)

from exstreamtv.ai_agent.prompts.system_admin import (
    SYSTEM_ADMIN_PERSONA,
    SYSTEM_ADMIN_SYSTEM_PROMPT,
    build_troubleshooting_prompt,
    get_sysadmin_welcome_message,
    build_fix_suggestion_prompt,
)

# Persona registry for dynamic selection
PERSONAS = {
    "tv_executive": {
        "name": "Max Sterling",
        "title": "TV Programming Executive",
        "persona": TV_EXECUTIVE_PERSONA,
        "system_prompt": TV_EXECUTIVE_SYSTEM_PROMPT,
        "build_prompt": build_channel_creation_prompt,
        "build_schedule": build_schedule_generation_prompt,
        "specialties": ["classic_tv", "scheduling", "dayparts", "commercials"],
    },
    "sports_expert": {
        "name": "Howard 'The Stat' Kowalski",
        "title": "Sports Savant",
        "persona": SPORTS_EXPERT_PERSONA,
        "system_prompt": SPORTS_EXPERT_SYSTEM_PROMPT,
        "build_prompt": build_sports_channel_prompt,
        "build_schedule": build_sports_schedule_prompt,
        "get_welcome": get_sports_welcome_message,
        "specialties": ["sports", "classic_games", "documentaries", "youtube", "archive_org"],
        "data": {
            "youtube_channels": YOUTUBE_SPORTS_CHANNELS,
            "archive_collections": ARCHIVE_ORG_SPORTS_COLLECTIONS,
            "documentary_series": SPORTS_DOCUMENTARY_SERIES,
            "movies": SPORTS_MOVIES,
        },
    },
    "tech_expert": {
        "name": "Steve 'Woz' Nakamura",
        "title": "Tech Savant",
        "persona": TECH_EXPERT_PERSONA,
        "system_prompt": TECH_EXPERT_SYSTEM_PROMPT,
        "build_prompt": build_tech_channel_prompt,
        "build_schedule": build_tech_schedule_prompt,
        "get_welcome": get_tech_welcome_message,
        "specialties": ["technology", "apple", "computing", "keynotes", "retro_tech"],
        "data": {
            "apple_keynotes": APPLE_KEYNOTES,
            "apple_commercials": APPLE_COMMERCIALS,
            "youtube_channels": YOUTUBE_TECH_CHANNELS,
            "archive_collections": ARCHIVE_ORG_TECH_COLLECTIONS,
            "documentaries": TECH_DOCUMENTARIES,
        },
    },
    "movie_critic": {
        "name": "Vincent Marlowe & Clara Fontaine",
        "title": "Movie Critics",
        "persona": MOVIE_CRITIC_PERSONA,
        "system_prompt": MOVIE_CRITIC_SYSTEM_PROMPT,
        "build_prompt": build_movie_channel_prompt,
        "build_schedule": build_movie_schedule_prompt,
        "get_welcome": get_movie_welcome_message,
        "specialties": ["movies", "film_history", "directors", "genres", "international_cinema"],
        "data": {
            "genres": FILM_GENRES,
            "directors": CLASSIC_DIRECTORS,
            "movements": FILM_MOVEMENTS,
            "archive_collections": ARCHIVE_ORG_FILM_COLLECTIONS,
        },
    },
    "kids_expert": {
        "name": "Professor Patricia 'Pepper' Chen",
        "title": "Kids Programming Expert",
        "persona": KIDS_EXPERT_PERSONA,
        "system_prompt": KIDS_EXPERT_SYSTEM_PROMPT,
        "build_prompt": build_kids_channel_prompt,
        "build_schedule": build_kids_schedule_prompt,
        "get_welcome": get_kids_welcome_message,
        "specialties": ["children", "disney", "animation", "educational", "family"],
        "data": {
            "disney": DISNEY_CONTENT,
            "pixar": PIXAR_FILMS,
            "classic_cartoons": CLASSIC_CARTOONS,
            "educational": EDUCATIONAL_SHOWS,
            "holidays": HOLIDAY_SPECIALS,
            "youtube_channels": YOUTUBE_KIDS_CHANNELS,
        },
    },
    "pbs_expert": {
        "name": "Dr. Eleanor Marsh",
        "title": "PBS Programming Expert",
        "persona": PBS_EXPERT_PERSONA,
        "system_prompt": PBS_EXPERT_SYSTEM_PROMPT,
        "build_prompt": build_pbs_channel_prompt,
        "build_schedule": build_pbs_schedule_prompt,
        "get_welcome": get_pbs_welcome_message,
        "specialties": ["documentary", "educational", "pbs", "british_drama", "public_television"],
        "data": {
            "documentary_series": PBS_DOCUMENTARY_SERIES,
            "ken_burns": KEN_BURNS_DOCUMENTARIES,
            "british_imports": BRITISH_IMPORTS,
            "cultural": CULTURAL_PROGRAMMING,
            "kids_classics": PBS_KIDS_CLASSICS,
            "public_affairs": PUBLIC_AFFAIRS,
            "archive_collections": ARCHIVE_ORG_EDUCATIONAL,
        },
    },
    "system_admin": {
        "name": "Alex Chen",
        "title": "DevOps Engineer",
        "persona": SYSTEM_ADMIN_PERSONA,
        "system_prompt": SYSTEM_ADMIN_SYSTEM_PROMPT,
        "build_prompt": build_troubleshooting_prompt,
        "get_welcome": get_sysadmin_welcome_message,
        "specialties": ["troubleshooting", "logs", "ffmpeg", "plex", "devops", "debugging"],
        "data": {},
    },
}


def get_persona(persona_id: str) -> dict | None:
    """Get a persona by ID."""
    return PERSONAS.get(persona_id)


def list_personas() -> list[dict]:
    """List all available personas."""
    return [
        {
            "id": persona_id,
            "name": persona["name"],
            "title": persona["title"],
            "specialties": persona["specialties"],
        }
        for persona_id, persona in PERSONAS.items()
    ]


__all__ = [
    # TV Executive
    "TV_EXECUTIVE_PERSONA",
    "TV_EXECUTIVE_SYSTEM_PROMPT",
    "build_channel_creation_prompt",
    "build_schedule_generation_prompt",
    # Sports Expert
    "SPORTS_EXPERT_PERSONA",
    "SPORTS_EXPERT_SYSTEM_PROMPT",
    "build_sports_channel_prompt",
    "build_sports_schedule_prompt",
    "get_sports_welcome_message",
    "YOUTUBE_SPORTS_CHANNELS",
    "ARCHIVE_ORG_SPORTS_COLLECTIONS",
    "SPORTS_DOCUMENTARY_SERIES",
    "SPORTS_MOVIES",
    # Tech Expert
    "TECH_EXPERT_PERSONA",
    "TECH_EXPERT_SYSTEM_PROMPT",
    "build_tech_channel_prompt",
    "build_tech_schedule_prompt",
    "get_tech_welcome_message",
    "APPLE_KEYNOTES",
    "APPLE_COMMERCIALS",
    "YOUTUBE_TECH_CHANNELS",
    "ARCHIVE_ORG_TECH_COLLECTIONS",
    "TECH_DOCUMENTARIES",
    # Movie Critic
    "MOVIE_CRITIC_PERSONA",
    "MOVIE_CRITIC_SYSTEM_PROMPT",
    "build_movie_channel_prompt",
    "build_movie_schedule_prompt",
    "get_movie_welcome_message",
    "FILM_GENRES",
    "CLASSIC_DIRECTORS",
    "FILM_MOVEMENTS",
    "ARCHIVE_ORG_FILM_COLLECTIONS",
    # Kids Expert
    "KIDS_EXPERT_PERSONA",
    "KIDS_EXPERT_SYSTEM_PROMPT",
    "build_kids_channel_prompt",
    "build_kids_schedule_prompt",
    "get_kids_welcome_message",
    "DISNEY_CONTENT",
    "PIXAR_FILMS",
    "CLASSIC_CARTOONS",
    "EDUCATIONAL_SHOWS",
    "HOLIDAY_SPECIALS",
    "YOUTUBE_KIDS_CHANNELS",
    # PBS Expert
    "PBS_EXPERT_PERSONA",
    "PBS_EXPERT_SYSTEM_PROMPT",
    "build_pbs_channel_prompt",
    "build_pbs_schedule_prompt",
    "get_pbs_welcome_message",
    "PBS_DOCUMENTARY_SERIES",
    "KEN_BURNS_DOCUMENTARIES",
    "BRITISH_IMPORTS",
    "CULTURAL_PROGRAMMING",
    "PBS_KIDS_CLASSICS",
    "PUBLIC_AFFAIRS",
    "ARCHIVE_ORG_EDUCATIONAL",
    # System Admin
    "SYSTEM_ADMIN_PERSONA",
    "SYSTEM_ADMIN_SYSTEM_PROMPT",
    "build_troubleshooting_prompt",
    "get_sysadmin_welcome_message",
    "build_fix_suggestion_prompt",
    # Registry
    "PERSONAS",
    "get_persona",
    "list_personas",
]
