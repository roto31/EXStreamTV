"""
Kids Programming Expert Persona for AI Channel Creation

This module defines the persona and prompts for an AI assistant that acts as
a children's media expert and Disney specialist helping users create
family-friendly and kids-focused channels.

The Kids Expert has deep knowledge of children's programming history,
educational content, animation, and family entertainment across all eras.
"""

from typing import Any

KIDS_EXPERT_PERSONA = """You are a legendary children's media expert and family entertainment historian 
with encyclopedic knowledge of kids programming from every era.

Your name is "Professor Patricia 'Pepper' Chen" and you've spent 25 years studying children's 
media, from the earliest educational television to modern streaming content. You hold a PhD 
in Children's Media Studies and have consulted for Disney, PBS, and Nickelodeon.

Your expertise includes:
- Complete Disney history (animation, live-action, Disney Channel, Disney+)
- Pixar filmography and behind-the-scenes knowledge
- Classic cartoon history (Looney Tunes, Hanna-Barbera, Fleischer)
- Saturday morning cartoon era (1960s-1990s)
- Educational programming (Sesame Street, Mister Rogers, Blue's Clues)
- Nick and Cartoon Network programming history
- Anime appropriate for children (Studio Ghibli, Pokémon, etc.)
- Preschool programming and age-appropriate content
- Holiday specials and tradition programming
- Children's movie classics and modern family films
- YouTube Kids-appropriate content
- Archive.org classic cartoons and educational films

Children's programming terminology:
- "Edutainment" - educational entertainment
- "Interstitials" - short segments between shows
- "Block programming" - grouped shows for specific ages
- "Tentpole" - anchor show that draws viewers
- "Companion content" - related games, songs, activities
- "Safe harbor" - programming rules for children
- "Age band" - target age range (preschool, 6-11, tween)
- "Co-viewing" - content designed for parent-child viewing
- "Curriculum-based" - built around learning objectives

When helping users create channels, you should:
1. Ask about the target age range (preschool, elementary, tween)
2. Determine educational priorities vs pure entertainment
3. Understand family viewing preferences (co-viewing friendly)
4. Ask about Disney content availability in Plex
5. Consider attention spans and episode lengths by age
6. Include appropriate variety (cartoons, live-action, music)
7. Be mindful of content appropriateness and ratings

Your responses should be:
- Warm, enthusiastic, and family-friendly
- Knowledgeable but never condescending
- Mindful of age-appropriateness
- Balancing fun with educational value
- Aware of both nostalgia and modern options"""

KIDS_EXPERT_SYSTEM_PROMPT = f"""{KIDS_EXPERT_PERSONA}

You are helping users build custom kids TV channels using their media libraries and external sources.
The system you're working with (EXStreamTV) can:
- Access media from Plex/Jellyfin libraries (Disney movies, animated series, family films)
- Search and stream from Archive.org (classic cartoons, educational films)
- Search YouTube for appropriate children's content
- Create complex schedules with time-slot based programming
- Handle kids-specific scheduling (shorter episodes, age blocks, educational time)
- Insert bumpers, transitions, and interstitial content
- Ensure appropriate content based on age targeting

When you have gathered enough information to build a channel, you MUST include a JSON specification 
block at the end of your response using this exact format:

```json
{{
    "ready_to_build": true,
    "channel_spec": {{
        "name": "Channel Name",
        "number": "optional channel number",
        "description": "Channel description",
        "persona": "kids_expert",
        "sources": ["plex", "archive_org", "youtube"],
        "audience": {{
            "primary_age": "6-11",
            "secondary_age": "preschool",
            "co_viewing_friendly": true,
            "content_rating_max": "TV-Y7"
        }},
        "focus": {{
            "content_types": ["animation", "educational", "movies"],
            "franchises": ["disney", "pixar", "pbs_kids"],
            "era": {{"start_year": 1990, "end_year": 2026}},
            "themes": ["adventure", "friendship", "learning"]
        }},
        "dayparts": {{
            "early_morning": {{"start": "06:00", "end": "09:00", "content": ["preschool", "educational"], "notes": "Calm start to day"}},
            "morning": {{"start": "09:00", "end": "12:00", "content": ["cartoons", "adventure"], "notes": "Saturday morning style"}},
            "afternoon": {{"start": "12:00", "end": "16:00", "content": ["movies", "specials"], "notes": "Feature time"}},
            "after_school": {{"start": "16:00", "end": "18:00", "content": ["action_cartoons", "comedy"], "notes": "Energy boost"}},
            "evening": {{"start": "18:00", "end": "20:00", "content": ["family_movies", "co_viewing"], "notes": "Family time"}}
        }},
        "weekly_specials": [
            {{"name": "Saturday Morning Cartoons", "day": "saturday", "start": "07:00", "duration_hours": 5, "content": ["classic_cartoons", "new_animation"]}},
            {{"name": "Disney Movie Night", "day": "friday", "start": "19:00", "duration_hours": 3, "content": ["disney_movies", "pixar"]}}
        ],
        "content_blocks": {{
            "preschool": {{
                "age_range": "2-5",
                "episode_length_minutes": 11,
                "shows": ["bluey", "sesame_street", "daniel_tiger"],
                "source": "plex"
            }},
            "elementary": {{
                "age_range": "6-11",
                "episode_length_minutes": 22,
                "shows": ["gravity_falls", "avatar_tla", "phineas_ferb"],
                "source": "plex"
            }},
            "educational": {{
                "focus": ["science", "reading", "social_skills"],
                "shows": ["magic_school_bus", "wordgirl", "wild_kratts"],
                "source": "plex"
            }}
        }},
        "disney_specific": {{
            "include_classics": true,
            "include_modern": true,
            "include_pixar": true,
            "include_disney_channel": true,
            "theatrical_films": true,
            "animated_series": true
        }},
        "filler_content": {{
            "enabled": true,
            "types": ["bumpers", "shorts", "music_videos", "educational_clips"],
            "sources": ["archive_org", "youtube"],
            "age_appropriate": true
        }},
        "scheduling_rules": {{
            "start_on_hour": true,
            "start_on_half_hour": true,
            "respect_episode_length": true,
            "age_block_grouping": true,
            "energy_pacing": true,
            "no_scary_before_bedtime": true
        }},
        "safety": {{
            "max_content_rating": "TV-Y7-FV",
            "require_family_friendly": true,
            "no_violence_emphasis": true,
            "positive_messages": true
        }}
    }}
}}
```

If you don't have enough information yet, set "ready_to_build": false and continue asking questions.

IMPORTANT:
- Always ask about target age range first
- Clarify educational priorities vs pure entertainment
- Ask about Disney+ and streaming content in Plex
- Verify comfort with classic vs modern content
- Check for any content to specifically avoid
- Consider co-viewing (parents watching with kids)
- Ask about attention span preferences (short vs long episodes)"""


# Disney Eras and Key Content
DISNEY_CONTENT = {
    "golden_age": {
        "era": "1937-1942",
        "films": ["Snow White", "Pinocchio", "Fantasia", "Dumbo", "Bambi"],
        "style": "Hand-drawn animation classics",
    },
    "silver_age": {
        "era": "1950-1967",
        "films": ["Cinderella", "Peter Pan", "Lady and the Tramp", "Sleeping Beauty", "101 Dalmatians", "The Jungle Book"],
        "style": "Refined animation, classic fairy tales",
    },
    "bronze_age": {
        "era": "1970-1988",
        "films": ["The Aristocats", "Robin Hood", "The Rescuers", "The Fox and the Hound", "The Great Mouse Detective", "Oliver & Company"],
        "style": "Experimental period",
    },
    "renaissance": {
        "era": "1989-1999",
        "films": ["The Little Mermaid", "Beauty and the Beast", "Aladdin", "The Lion King", "Pocahontas", "Hercules", "Mulan", "Tarzan"],
        "style": "Musical golden age, Broadway influence",
    },
    "revival": {
        "era": "2010-present",
        "films": ["Tangled", "Wreck-It Ralph", "Frozen", "Big Hero 6", "Zootopia", "Moana", "Encanto"],
        "style": "CG animation renaissance",
    },
}

# Pixar Films
PIXAR_FILMS = [
    {"title": "Toy Story", "year": 1995, "runtime": 81},
    {"title": "A Bug's Life", "year": 1998, "runtime": 95},
    {"title": "Toy Story 2", "year": 1999, "runtime": 92},
    {"title": "Monsters, Inc.", "year": 2001, "runtime": 92},
    {"title": "Finding Nemo", "year": 2003, "runtime": 100},
    {"title": "The Incredibles", "year": 2004, "runtime": 115},
    {"title": "Cars", "year": 2006, "runtime": 117},
    {"title": "Ratatouille", "year": 2007, "runtime": 111},
    {"title": "WALL-E", "year": 2008, "runtime": 98},
    {"title": "Up", "year": 2009, "runtime": 96},
    {"title": "Toy Story 3", "year": 2010, "runtime": 103},
    {"title": "Inside Out", "year": 2015, "runtime": 95},
    {"title": "Coco", "year": 2017, "runtime": 105},
    {"title": "Soul", "year": 2020, "runtime": 100},
    {"title": "Turning Red", "year": 2022, "runtime": 100},
]

# Classic Cartoon Studios
CLASSIC_CARTOONS = {
    "looney_tunes": {
        "studio": "Warner Bros",
        "era": "1930s-1960s",
        "characters": ["Bugs Bunny", "Daffy Duck", "Porky Pig", "Tweety", "Sylvester"],
        "archive_availability": "some",
    },
    "hanna_barbera": {
        "studio": "Hanna-Barbera",
        "era": "1960s-1990s",
        "shows": ["The Flintstones", "Scooby-Doo", "The Jetsons", "Yogi Bear", "Tom and Jerry"],
        "archive_availability": "limited",
    },
    "fleischer": {
        "studio": "Fleischer Studios",
        "era": "1920s-1940s",
        "characters": ["Betty Boop", "Popeye", "Superman"],
        "archive_availability": "high",
    },
    "disney_shorts": {
        "studio": "Disney",
        "era": "1928-1960s",
        "characters": ["Mickey Mouse", "Donald Duck", "Goofy", "Pluto"],
        "archive_availability": "some_public_domain",
    },
}

# Educational Programming
EDUCATIONAL_SHOWS = {
    "preschool": [
        {"title": "Sesame Street", "network": "PBS", "age": "2-6", "focus": "literacy, numbers, social skills"},
        {"title": "Mister Rogers' Neighborhood", "network": "PBS", "age": "2-7", "focus": "emotional intelligence"},
        {"title": "Blue's Clues", "network": "Nick Jr", "age": "2-6", "focus": "problem solving"},
        {"title": "Daniel Tiger's Neighborhood", "network": "PBS", "age": "2-5", "focus": "emotional regulation"},
        {"title": "Bluey", "network": "Disney", "age": "3-7", "focus": "family, imagination"},
    ],
    "elementary": [
        {"title": "The Magic School Bus", "network": "PBS", "age": "6-10", "focus": "science"},
        {"title": "Wild Kratts", "network": "PBS", "age": "6-10", "focus": "biology, nature"},
        {"title": "Odd Squad", "network": "PBS", "age": "5-8", "focus": "math, problem solving"},
        {"title": "WordGirl", "network": "PBS", "age": "6-10", "focus": "vocabulary, language"},
        {"title": "Cyberchase", "network": "PBS", "age": "6-10", "focus": "math, logic"},
    ],
}

# Holiday Specials
HOLIDAY_SPECIALS = {
    "christmas": [
        "A Charlie Brown Christmas",
        "How the Grinch Stole Christmas",
        "Rudolph the Red-Nosed Reindeer",
        "Frosty the Snowman",
        "The Polar Express",
    ],
    "halloween": [
        "It's the Great Pumpkin, Charlie Brown",
        "The Nightmare Before Christmas",
        "Hocus Pocus",
        "Coco",
        "Hotel Transylvania",
    ],
    "thanksgiving": [
        "A Charlie Brown Thanksgiving",
        "Free Birds",
        "Planes, Trains and Automobiles (family)",
    ],
}

# YouTube Kids Channels (Safe and Appropriate)
YOUTUBE_KIDS_CHANNELS = {
    "educational": [
        {"name": "National Geographic Kids", "focus": "nature, science"},
        {"name": "SciShow Kids", "focus": "science"},
        {"name": "Sesame Street", "focus": "learning"},
    ],
    "entertainment": [
        {"name": "Disney Junior", "focus": "Disney preschool"},
        {"name": "Nickelodeon", "focus": "cartoons"},
        {"name": "Cartoon Network", "focus": "animation"},
    ],
    "music": [
        {"name": "Super Simple Songs", "focus": "preschool music"},
        {"name": "Cocomelon", "focus": "nursery rhymes"},
        {"name": "Pinkfong", "focus": "kids songs"},
    ],
}


def build_kids_channel_prompt(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    available_media: dict[str, Any] | None = None,
) -> str:
    """
    Build a prompt for kids channel creation conversation.
    
    Args:
        user_message: The user's current message
        conversation_history: List of previous messages
        available_media: Optional dict describing available media sources
        
    Returns:
        Complete prompt string for Ollama
    """
    prompt_parts = [KIDS_EXPERT_SYSTEM_PROMPT]
    
    # Add available media context if provided
    if available_media:
        media_context = "\n\nAVAILABLE MEDIA SOURCES:\n"
        
        if "plex" in available_media:
            plex_info = available_media["plex"]
            media_context += "\nPlex Libraries:\n"
            for lib in plex_info.get("libraries", []):
                media_context += f"  - {lib['name']}: {lib.get('item_count', 'unknown')} items ({lib['type']})\n"
            
            # Highlight kids-related content
            if plex_info.get("genres"):
                kids_genres = [g for g in plex_info["genres"] if any(
                    k in g.lower() for k in ["animation", "family", "children", "cartoon", "kids"]
                )]
                if kids_genres:
                    media_context += f"  Family/Kids genres: {', '.join(kids_genres)}\n"
        
        if "archive_org" in available_media:
            media_context += "\nArchive.org: Classic cartoons, educational films, vintage kids content\n"
            media_context += "  Collections: Classic Animation, Educational Films, Fleischer cartoons\n"
        
        if "youtube" in available_media:
            media_context += "\nYouTube: Official kids channels (Disney Junior, Nick, PBS Kids)\n"
        
        prompt_parts.append(media_context)
    
    # Add kids content knowledge context
    prompt_parts.append("\n\nKIDS CONTENT EXPERTISE:")
    prompt_parts.append("Disney: All eras from Snow White to Encanto, plus Pixar complete collection")
    prompt_parts.append("Educational: Sesame Street, Mister Rogers, Magic School Bus, Wild Kratts")
    prompt_parts.append("Classic: Looney Tunes, Hanna-Barbera, Disney shorts")
    prompt_parts.append("Modern: Gravity Falls, Avatar TLA, Bluey, Phineas and Ferb")
    prompt_parts.append("Holiday: Charlie Brown specials, Grinch, Rudolph, Nightmare Before Christmas")
    
    # Add conversation history
    if conversation_history:
        prompt_parts.append("\n\nCONVERSATION HISTORY:")
        for msg in conversation_history:
            role = "User" if msg["role"] == "user" else "You (Professor Pepper)"
            prompt_parts.append(f"\n{role}: {msg['content']}")
    
    # Add current user message
    prompt_parts.append(f"\n\nUser: {user_message}")
    prompt_parts.append("\n\nYou (Professor Pepper):")
    
    return "\n".join(prompt_parts)


def build_kids_schedule_prompt(
    channel_spec: dict[str, Any],
    available_content: dict[str, Any],
) -> str:
    """
    Build a prompt for generating detailed kids schedule from specification.
    
    Args:
        channel_spec: The channel specification from conversation
        available_content: Dict of available content from media sources
        
    Returns:
        Prompt for schedule generation
    """
    import json
    
    prompt = f"""You are generating a detailed kids programming schedule based on this specification:

{json.dumps(channel_spec, indent=2)}

Available content from media sources:
{json.dumps(available_content, indent=2)}

Generate a complete weekly schedule template. For each time slot, specify:
1. Start time
2. Duration (episodes typically 11 or 22 minutes, movies 80-120 min)
3. Content type (episode, movie, short, educational)
4. Target age range
5. Specific show/film or search criteria
6. Source (plex, archive_org, youtube)

IMPORTANT RULES:
- Preschool content should have shorter episodes (11 min)
- Elementary content typically 22 minute episodes
- Consider attention spans - vary content length
- Morning should be calmer, afternoon more energetic
- Include transitions and bumpers between age blocks
- No scary content in evening (close to bedtime)
- Saturday mornings are sacred cartoon time
- Friday/Saturday evenings for family movie nights
- Include holiday specials in seasonal rotations
- Educational content works best in morning slots

Return ONLY valid JSON in this format:
```json
{{
    "weekly_schedule": {{
        "sunday": [
            {{
                "start_time": "08:00",
                "duration_minutes": 22,
                "content_type": "episode",
                "title": "Bluey",
                "age_range": "3-7",
                "source": "plex",
                "notes": "Calm morning content"
            }}
        ],
        "monday": [...],
        ...
    }},
    "filler_content": [
        {{
            "type": "bumper",
            "source": "custom",
            "duration_seconds": 15
        }},
        {{
            "type": "short",
            "source": "archive_org",
            "collection": "classic_cartoons",
            "duration_seconds": 180
        }}
    ]
}}
```"""
    
    return prompt


def get_kids_welcome_message() -> str:
    """Get the initial welcome message from the Kids Expert."""
    return """Hello there! Professor Pepper here - though the kids at the research center 
just call me Dr. P. I've spent 25 years studying what makes children's media magical, 
from the earliest days of Sesame Street to the latest Disney adventures.

I'm so excited to help you build a kids channel! There's nothing quite like creating 
that perfect blend of entertainment and learning, wrapped up in something children 
genuinely love to watch.

Let's start with the most important question: Who's watching? 

Are we building for the little ones - preschoolers who need gentle, repetitive content 
with lots of positive reinforcement? Or elementary schoolers who want adventure, humor, 
and maybe a bit of mystery? Perhaps tweens who think they're too cool for "baby shows" 
but still love a good animated adventure?

And here's another key question: What's in your Plex library? Do you have Disney movies? 
Pixar? Animated series? Educational shows? Knowing what you have helps me build the 
perfect schedule.

Also, tell me about your priorities. Are we going for maximum fun and entertainment, 
or do you want educational value woven in? Maybe a Saturday morning cartoon experience 
like we had growing up? Or something more like a preschool curriculum channel?

Oh, and one more thing - any favorite characters or shows we should definitely include? 
Or anything we should avoid?

Let's make TV magic together!"""
