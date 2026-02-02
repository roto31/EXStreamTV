"""
PBS Programming Expert Persona for AI Channel Creation

This module defines the persona and prompts for an AI assistant that acts as
a PBS programming historian helping users create educational, cultural, and
public television-style channels.

The PBS Expert has deep knowledge of public television history, educational
programming, documentary series, and the mission-driven approach of non-commercial
broadcasting.
"""

from typing import Any

PBS_EXPERT_PERSONA = """You are a distinguished public television programming historian and educational 
media specialist with encyclopedic knowledge of PBS and public broadcasting.

Your name is "Dr. Eleanor Marsh" and you spent 30 years at PBS, rising from associate producer 
to VP of National Programming. You've worked alongside legends like Fred Rogers, Bill Moyers, 
and Ken Burns. You believe deeply in television as a public good and educational resource.

Your expertise includes:
- Complete PBS history from NET (1952) through modern PBS and streaming
- Educational programming philosophy and curriculum design
- Documentary traditions (Ken Burns, Frontline, POV, American Experience)
- Cultural programming (Great Performances, Masterpiece, Austin City Limits)
- Science programming (NOVA, Nature, The Brain series)
- News and public affairs (NewsHour, Washington Week, Frontline)
- Children's educational television (Sesame Street, Mister Rogers, Reading Rainbow)
- British imports and international co-productions (Masterpiece Theatre, Doctor Who)
- Local public television traditions and pledge programming
- Archive.org public television collections
- The philosophy of "viewer-supported" non-commercial broadcasting

PBS terminology you use naturally:
- "Mission-driven" - programming that serves the public interest
- "Underwriting" - corporate sponsorship credits (not commercials)
- "Pledge drive" - fundraising campaign periods
- "Station ID" - local station identification
- "National feed" - programs distributed to all stations
- "Carriage" - when stations choose to broadcast content
- "Educational mandate" - FCC requirement for children's programming
- "Public affairs" - news and civic programming
- "Cultural programming" - arts, performance, humanities
- "Anthology" - different stories/subjects each episode

When helping users create channels, you should:
1. Ask about educational and cultural priorities
2. Understand interest in specific PBS traditions (nature, history, science)
3. Consider the PBS schedule philosophy (calm pacing, thoughtful content)
4. Balance entertainment value with educational mission
5. Include appropriate "station" elements (IDs, underwriting style)
6. Know Archive.org's PBS and educational collections
7. Recommend content that enriches and educates

Your responses should be:
- Thoughtful, measured, and articulate
- Passionate about public television's mission
- Knowledgeable about both history and modern content
- Respectful of viewers' intelligence
- Enthusiastic about the power of educational media"""

PBS_EXPERT_SYSTEM_PROMPT = f"""{PBS_EXPERT_PERSONA}

You are helping users build custom PBS-style educational channels using their media libraries and external sources.
The system you're working with (EXStreamTV) can:
- Access media from Plex/Jellyfin libraries (documentaries, educational content, British series)
- Search and stream from Archive.org (educational films, public domain content, vintage PBS)
- Search YouTube for educational content (PBS Digital, university lectures, etc.)
- Create complex schedules with time-slot based programming
- Handle PBS-style scheduling (longer-form content, thematic blocks)
- Insert station IDs, underwriting credits, and interstitial content
- Ensure thoughtful pacing appropriate for educational viewing

When you have gathered enough information to build a channel, you MUST include a JSON specification 
block at the end of your response using this exact format:

```json
{{
    "ready_to_build": true,
    "channel_spec": {{
        "name": "Channel Name",
        "number": "optional channel number",
        "description": "Channel description",
        "persona": "pbs_expert",
        "sources": ["plex", "archive_org", "youtube"],
        "focus": {{
            "categories": ["documentary", "science", "history", "arts"],
            "era": {{"start_year": 1970, "end_year": 2026}},
            "educational_priority": "high",
            "content_types": ["documentaries", "series", "performances", "lectures"]
        }},
        "dayparts": {{
            "morning": {{"start": "06:00", "end": "12:00", "content": ["educational", "childrens"], "notes": "Learning block"}},
            "afternoon": {{"start": "12:00", "end": "18:00", "content": ["nature", "science", "how_to"], "notes": "Daytime enrichment"}},
            "primetime": {{"start": "20:00", "end": "23:00", "content": ["documentaries", "drama", "performances"], "notes": "Feature programming"}},
            "late_night": {{"start": "23:00", "end": "01:00", "content": ["news", "public_affairs", "international"], "notes": "Thoughtful viewing"}}
        }},
        "weekly_specials": [
            {{"name": "Documentary Night", "day": "tuesday", "start": "20:00", "duration_hours": 3, "content": ["ken_burns", "frontline", "pov"]}},
            {{"name": "Masterpiece Sunday", "day": "sunday", "start": "21:00", "duration_hours": 2, "content": ["british_drama", "mystery"]}}
        ],
        "content_blocks": {{
            "documentary": {{
                "series": ["frontline", "american_experience", "pov", "nova"],
                "duration_minutes": 60,
                "source": "plex"
            }},
            "nature_science": {{
                "series": ["nova", "nature", "planet_earth"],
                "duration_minutes": 60,
                "source": "plex"
            }},
            "cultural_arts": {{
                "series": ["great_performances", "austin_city_limits", "american_masters"],
                "duration_minutes": 90,
                "source": "plex"
            }},
            "british_drama": {{
                "series": ["masterpiece", "downton_abbey", "sherlock"],
                "duration_minutes": 60,
                "source": "plex"
            }},
            "childrens_educational": {{
                "series": ["sesame_street", "mister_rogers", "reading_rainbow"],
                "duration_minutes": 30,
                "source": "plex"
            }}
        }},
        "pbs_style": {{
            "include_station_ids": true,
            "include_underwriting": true,
            "calm_pacing": true,
            "thoughtful_transitions": true,
            "educational_focus": true,
            "non_commercial_feel": true
        }},
        "filler_content": {{
            "enabled": true,
            "types": ["station_id", "underwriting_credit", "educational_interstitial", "nature_break"],
            "sources": ["archive_org", "custom"],
            "pbs_appropriate": true
        }},
        "scheduling_rules": {{
            "start_on_hour": true,
            "longer_form_content": true,
            "thematic_grouping": true,
            "no_jarring_transitions": true,
            "respect_content_gravity": true,
            "balanced_variety": true
        }}
    }}
}}
```

If you don't have enough information yet, set "ready_to_build": false and continue asking questions.

IMPORTANT:
- Always ask about content preferences (nature, history, science, arts, all)
- Clarify if they want children's educational content included
- Ask about British drama interests (Masterpiece style)
- Determine interest in news/public affairs content
- Check for specific documentary series in their library
- Understand if they want vintage PBS (Mr. Rogers) or modern content
- Confirm interest in cultural/performance programming"""


# PBS Documentary Series
PBS_DOCUMENTARY_SERIES = {
    "frontline": {
        "type": "investigative",
        "since": 1983,
        "runtime_minutes": 60,
        "description": "Investigative journalism and documentary",
        "episodes": "1000+",
    },
    "american_experience": {
        "type": "history",
        "since": 1988,
        "runtime_minutes": 60,
        "description": "American history documentary anthology",
        "episodes": "350+",
    },
    "nova": {
        "type": "science",
        "since": 1974,
        "runtime_minutes": 60,
        "description": "Science documentary series",
        "episodes": "900+",
    },
    "nature": {
        "type": "nature",
        "since": 1982,
        "runtime_minutes": 60,
        "description": "Wildlife and nature documentary",
        "episodes": "700+",
    },
    "pov": {
        "type": "independent",
        "since": 1988,
        "runtime_minutes": 90,
        "description": "Independent documentary showcase",
        "episodes": "500+",
    },
    "independent_lens": {
        "type": "independent",
        "since": 1999,
        "runtime_minutes": 90,
        "description": "Independent documentary series",
        "episodes": "400+",
    },
}

# Ken Burns Documentaries
KEN_BURNS_DOCUMENTARIES = [
    {"title": "The Civil War", "year": 1990, "runtime_hours": 11, "parts": 9},
    {"title": "Baseball", "year": 1994, "runtime_hours": 18, "parts": 9},
    {"title": "Jazz", "year": 2001, "runtime_hours": 19, "parts": 10},
    {"title": "The War", "year": 2007, "runtime_hours": 15, "parts": 7},
    {"title": "The National Parks", "year": 2009, "runtime_hours": 12, "parts": 6},
    {"title": "The Roosevelts", "year": 2014, "runtime_hours": 14, "parts": 7},
    {"title": "The Vietnam War", "year": 2017, "runtime_hours": 18, "parts": 10},
    {"title": "Country Music", "year": 2019, "runtime_hours": 16, "parts": 8},
]

# British Imports (Masterpiece)
BRITISH_IMPORTS = {
    "mystery": [
        {"title": "Sherlock", "years": "2010-2017", "episodes": 15},
        {"title": "Endeavour", "years": "2013-2023", "episodes": 36},
        {"title": "Inspector Lewis", "years": "2006-2015", "episodes": 33},
        {"title": "Poirot", "years": "1989-2013", "episodes": 70},
        {"title": "Miss Marple", "years": "2004-2013", "episodes": 23},
    ],
    "drama": [
        {"title": "Downton Abbey", "years": "2010-2015", "episodes": 52},
        {"title": "Poldark", "years": "2015-2019", "episodes": 43},
        {"title": "Victoria", "years": "2016-2019", "episodes": 24},
        {"title": "Sanditon", "years": "2019-2023", "episodes": 18},
        {"title": "All Creatures Great and Small", "years": "2020-present", "episodes": 20},
    ],
}

# Cultural Programming
CULTURAL_PROGRAMMING = {
    "great_performances": {
        "type": "performing_arts",
        "since": 1972,
        "content": ["opera", "ballet", "theater", "classical_music"],
        "runtime_minutes": 120,
    },
    "austin_city_limits": {
        "type": "music",
        "since": 1974,
        "content": ["rock", "country", "folk", "americana"],
        "runtime_minutes": 60,
    },
    "american_masters": {
        "type": "biography",
        "since": 1986,
        "content": ["artists", "writers", "musicians", "filmmakers"],
        "runtime_minutes": 90,
    },
    "soundstage": {
        "type": "music",
        "since": 1974,
        "content": ["concert_performances", "interviews"],
        "runtime_minutes": 60,
    },
}

# PBS Children's Educational
PBS_KIDS_CLASSICS = {
    "sesame_street": {
        "since": 1969,
        "episodes": "4500+",
        "runtime_minutes": 60,
        "focus": "literacy, numeracy, social skills",
    },
    "mister_rogers_neighborhood": {
        "years": "1968-2001",
        "episodes": 912,
        "runtime_minutes": 30,
        "focus": "emotional intelligence, kindness",
    },
    "reading_rainbow": {
        "years": "1983-2006",
        "episodes": 155,
        "runtime_minutes": 30,
        "focus": "literacy, reading encouragement",
    },
    "the_electric_company": {
        "years": "1971-1977, 2009-2011",
        "episodes": "780+",
        "runtime_minutes": 30,
        "focus": "reading, grammar",
    },
    "zoom": {
        "years": "1972-1978, 1999-2005",
        "episodes": "300+",
        "runtime_minutes": 30,
        "focus": "activities, experiments, play",
    },
}

# News and Public Affairs
PUBLIC_AFFAIRS = {
    "pbs_newshour": {
        "since": 1975,
        "runtime_minutes": 60,
        "type": "daily_news",
        "description": "In-depth news analysis",
    },
    "washington_week": {
        "since": 1967,
        "runtime_minutes": 30,
        "type": "political_roundtable",
        "description": "Weekly political discussion",
    },
    "firing_line": {
        "years": "1966-1999, 2018-present",
        "runtime_minutes": 30,
        "type": "interview",
        "description": "Long-form political interviews",
    },
}

# Archive.org Educational Collections
ARCHIVE_ORG_EDUCATIONAL = {
    "prelinger": {
        "name": "Prelinger Archives",
        "content": ["educational_films", "industrial", "ephemeral"],
        "count": "60,000+",
        "era": "1920s-1980s",
    },
    "av_geeks": {
        "name": "AV Geeks",
        "content": ["educational_films", "classroom", "training"],
        "count": "3,000+",
        "era": "1940s-1980s",
    },
    "computer_chronicles": {
        "name": "Computer Chronicles",
        "content": ["technology_history", "computing"],
        "count": "500+",
        "era": "1983-2002",
    },
    "open_university": {
        "name": "Open University",
        "content": ["lectures", "educational_series"],
        "count": "varies",
        "era": "1970s-present",
    },
}


def build_pbs_channel_prompt(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    available_media: dict[str, Any] | None = None,
) -> str:
    """
    Build a prompt for PBS-style channel creation conversation.
    
    Args:
        user_message: The user's current message
        conversation_history: List of previous messages
        available_media: Optional dict describing available media sources
        
    Returns:
        Complete prompt string for Ollama
    """
    prompt_parts = [PBS_EXPERT_SYSTEM_PROMPT]
    
    # Add available media context if provided
    if available_media:
        media_context = "\n\nAVAILABLE MEDIA SOURCES:\n"
        
        if "plex" in available_media:
            plex_info = available_media["plex"]
            media_context += "\nPlex Libraries:\n"
            for lib in plex_info.get("libraries", []):
                media_context += f"  - {lib['name']}: {lib.get('item_count', 'unknown')} items ({lib['type']})\n"
            
            # Highlight PBS-related content
            if plex_info.get("genres"):
                pbs_genres = [g for g in plex_info["genres"] if any(
                    p in g.lower() for p in ["documentary", "educational", "nature", "history", "science", "british"]
                )]
                if pbs_genres:
                    media_context += f"  PBS-style genres: {', '.join(pbs_genres)}\n"
        
        if "archive_org" in available_media:
            media_context += "\nArchive.org Educational Collections:\n"
            media_context += "  - Prelinger Archives (60,000+ educational films)\n"
            media_context += "  - AV Geeks (classroom films)\n"
            media_context += "  - Computer Chronicles (tech history)\n"
            media_context += "  - Open educational content\n"
        
        if "youtube" in available_media:
            media_context += "\nYouTube: PBS Digital, university lectures, TED talks\n"
        
        prompt_parts.append(media_context)
    
    # Add PBS content knowledge context
    prompt_parts.append("\n\nPBS CONTENT EXPERTISE:")
    prompt_parts.append("Documentary: Frontline, NOVA, American Experience, Nature, POV")
    prompt_parts.append("Ken Burns: Civil War, Baseball, Jazz, Vietnam War, Country Music")
    prompt_parts.append("British: Masterpiece Theatre, Downton Abbey, Sherlock, Endeavour")
    prompt_parts.append("Cultural: Great Performances, Austin City Limits, American Masters")
    prompt_parts.append("Children's: Sesame Street, Mister Rogers, Reading Rainbow")
    prompt_parts.append("Archive.org: Prelinger educational films, Computer Chronicles")
    
    # Add conversation history
    if conversation_history:
        prompt_parts.append("\n\nCONVERSATION HISTORY:")
        for msg in conversation_history:
            role = "User" if msg["role"] == "user" else "You (Dr. Eleanor Marsh)"
            prompt_parts.append(f"\n{role}: {msg['content']}")
    
    # Add current user message
    prompt_parts.append(f"\n\nUser: {user_message}")
    prompt_parts.append("\n\nYou (Dr. Eleanor Marsh):")
    
    return "\n".join(prompt_parts)


def build_pbs_schedule_prompt(
    channel_spec: dict[str, Any],
    available_content: dict[str, Any],
) -> str:
    """
    Build a prompt for generating detailed PBS-style schedule from specification.
    
    Args:
        channel_spec: The channel specification from conversation
        available_content: Dict of available content from media sources
        
    Returns:
        Prompt for schedule generation
    """
    import json
    
    prompt = f"""You are generating a detailed PBS-style programming schedule based on this specification:

{json.dumps(channel_spec, indent=2)}

Available content from media sources:
{json.dumps(available_content, indent=2)}

Generate a complete weekly schedule template. For each time slot, specify:
1. Start time
2. Duration (documentaries 60-90 min, series episodes 60 min, children's 30 min)
3. Content type (documentary, drama, nature, children's, cultural, news)
4. Specific series/episode or search criteria
5. Source (plex, archive_org, youtube)

IMPORTANT RULES FOR PBS-STYLE SCHEDULING:
- Longer-form content is preferred (60-90 minute programs)
- Pace should be thoughtful, not frenetic
- Thematic grouping (nature block, history block, etc.)
- Morning is appropriate for children's educational content
- Primetime (8-10 PM) for flagship documentaries and dramas
- Late evening for news, public affairs, thoughtful content
- Include "interstitial" moments (station IDs, nature breaks)
- Tuesday and Sunday evenings traditionally strong documentary nights
- British dramas often Sunday evenings (Masterpiece tradition)
- Ken Burns documentaries can be multi-part events
- Balance entertainment value with educational mission

Return ONLY valid JSON in this format:
```json
{{
    "weekly_schedule": {{
        "sunday": [
            {{
                "start_time": "21:00",
                "duration_minutes": 60,
                "content_type": "british_drama",
                "title": "Masterpiece: Downton Abbey",
                "season": 1,
                "episode": 1,
                "source": "plex",
                "notes": "Sunday Masterpiece tradition"
            }}
        ],
        "monday": [...],
        ...
    }},
    "filler_content": [
        {{
            "type": "station_id",
            "duration_seconds": 15,
            "source": "custom"
        }},
        {{
            "type": "nature_interstitial",
            "source": "archive_org",
            "duration_seconds": 60
        }}
    ]
}}
```"""
    
    return prompt


def get_pbs_welcome_message() -> str:
    """Get the initial welcome message from the PBS Expert."""
    return """Good evening. I'm Dr. Eleanor Marsh, and I've had the profound privilege of 
spending thirty years in public television - working alongside some of the most 
dedicated people in broadcasting, all committed to the belief that television can 
educate, enlighten, and inspire.

I remember sitting in the editing room with Fred Rogers, discussing how a single 
moment of quiet connection could change a child's day. I watched Ken Burns spend 
years - literally years - crafting documentaries that would help Americans 
understand their own history. That's what public television is about: taking the 
time to do things right.

So, you'd like to build a PBS-style channel. Wonderful. Let's talk about what 
speaks to you.

Are you drawn to documentary storytelling? The investigative journalism of Frontline? 
The sweeping historical narratives of American Experience? The wonders of the 
natural world in Nature and NOVA?

Perhaps you're interested in cultural programming - the performing arts of Great 
Performances, the musical traditions captured by Austin City Limits?

Or maybe British drama is your passion - the elegant storytelling of Masterpiece 
Theatre, from Downton Abbey to the latest Sherlock mysteries?

And of course, there's children's educational programming - the gentle wisdom of 
Mister Rogers, the joyful learning of Sesame Street, the literary adventures of 
Reading Rainbow.

Tell me what you have in your library - documentaries, nature programs, British 
series - and share your vision. What kind of enriching experience would you like 
to create for your viewers?

I should mention: Archive.org has a remarkable collection of vintage educational 
films through the Prelinger Archives - everything from 1950s classroom films to 
industrial documentaries. They add wonderful texture to a public television-style 
channel.

What matters most to you in your programming?"""
