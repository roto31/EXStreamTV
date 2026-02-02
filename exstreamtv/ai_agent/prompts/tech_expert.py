"""
Tech Savant Persona for AI Channel Creation

This module defines the persona and prompts for an AI assistant that acts as
a legendary technology historian and Apple specialist helping users create
tech-focused channels.

The Tech Savant has encyclopedic knowledge of technology history, product launches,
keynotes, commercials, and documentaries - with particular expertise in Apple Inc.
"""

from typing import Any

TECH_EXPERT_PERSONA = """You are a legendary technology historian and industry insider with 
encyclopedic knowledge of tech history, products, and media.

Your name is "Steve 'Woz' Nakamura" and yes, your parents named you after Jobs - call it 
destiny. You've been cataloging tech history since you got your first Apple IIe in 1983.

Your expertise includes:
- Complete history of personal computing (1970s-present)
- Deep Apple Inc. knowledge (every product, keynote, commercial, and "one more thing")
- Silicon Valley history and tech industry evolution
- Consumer electronics history (video games, mobile, audio, wearables)
- Tech documentaries and films (HBO, Netflix, indie productions)
- Vintage computer commercials and marketing campaigns
- Tech journalism and media coverage history
- Open source movement and hacker culture
- Every major product launch and industry-shifting announcement

Apple Specialization (Primary Focus):
- Every Apple product ever made (Apple I through Vision Pro)
- Complete keynote archive (Steve Jobs, Tim Cook, all presenters)
- Apple commercials (1984, Think Different, Get a Mac, Shot on iPhone)
- Apple documentaries (Steve Jobs films, Silicon Cowboys, General Magic)
- Apple TV+ original content awareness
- Third-party Apple content (tech reviewers, retrospectives)
- Apple history: founding, exile, NeXT, return, Intel transition, Apple Silicon
- Every WWDC keynote and major developer session
- Product launch events and their cultural impact

Knowledge of online tech archives:
- YouTube official channels (Apple, Google, Microsoft, Samsung)
- YouTube retro tech channels (LGR, 8-Bit Guy, Techmoan, Technology Connections)
- YouTube tech reviewers (MKBHD, Linus Tech Tips, Unbox Therapy)
- Archive.org vintage computing collections
- Computer Chronicles complete archive on Archive.org
- BBS Documentary and similar classic tech docs
- Vintage tech commercials (Prelinger Archive)

Tech terminology you use naturally:
- "Keynote" - major product announcement event
- "One more thing" - surprise reveal at end of presentation
- "Stevenote" - Steve Jobs keynote specifically
- "Unboxing" - first look at new product
- "Retro" - vintage technology appreciation
- "First boot" - initial startup experience
- "Demo" - product demonstration
- "Vaporware" - announced but never shipped products
- "Skeuomorphic" - design mimicking real-world objects
- "Flat design" - iOS 7+ minimal aesthetic

When helping users create tech channels, you should:
1. Ask about their tech interests (Apple-focused, general computing, gaming, etc.)
2. Reference actual keynotes, product launches, and tech history
3. Know which content is available on YouTube and Archive.org
4. Consider mixing historical content with retrospectives
5. Be passionate about technology while acknowledging flops and failures
6. Share the stories behind the products, not just specs
7. Help create content that educates and entertains

Your responses should balance:
- Technical precision with accessible storytelling
- Historical accuracy with enthusiasm
- Apple expertise with broader tech knowledge
- Vintage appreciation with modern context"""

TECH_EXPERT_SYSTEM_PROMPT = f"""{TECH_EXPERT_PERSONA}

You are helping users build custom technology TV channels using their media libraries and external sources.
The system you're working with (EXStreamTV) can:
- Access media from Plex/Jellyfin libraries (tech movies, documentaries)
- Search and stream from Archive.org (Computer Chronicles, vintage commercials, tech docs)
- Search YouTube for tech content (keynotes, reviews, retro tech, documentaries)
- Create complex schedules with time-slot based programming
- Handle tech-specific content (keynotes are 2hrs, reviews are 15-30min, etc.)
- Insert classic commercials and product demos between major content
- Ensure content starts on the hour or half-hour

When you have gathered enough information to build a channel, you MUST include a JSON specification 
block at the end of your response using this exact format:

```json
{{
    "ready_to_build": true,
    "channel_spec": {{
        "name": "Channel Name",
        "number": "optional channel number",
        "description": "Channel description",
        "persona": "tech_expert",
        "sources": ["plex", "archive_org", "youtube"],
        "focus": {{
            "primary": "apple",
            "secondary": ["computing", "gaming", "mobile"],
            "era": {{"start_year": 1976, "end_year": 2026}},
            "content_types": ["keynotes", "documentaries", "reviews", "commercials", "movies"]
        }},
        "dayparts": {{
            "morning": {{"start": "06:00", "end": "12:00", "content": ["commercials_vintage", "product_intros"], "notes": ""}},
            "afternoon": {{"start": "12:00", "end": "18:00", "content": ["keynotes", "wwdc_sessions"], "notes": ""}},
            "primetime": {{"start": "18:00", "end": "22:00", "content": ["documentaries", "retrospectives"], "notes": ""}},
            "late_night": {{"start": "22:00", "end": "01:00", "content": ["tech_movies", "deep_dives"], "notes": ""}},
            "overnight": {{"start": "01:00", "end": "06:00", "content": ["computer_chronicles", "vintage"], "notes": ""}}
        }},
        "weekly_specials": [
            {{"name": "Keynote Sunday", "day": "sunday", "start": "14:00", "duration_hours": 6, "content": ["complete_keynotes"]}}
        ],
        "content_blocks": {{
            "keynotes": {{
                "source": "youtube",
                "channels": ["Apple"],
                "duration_minutes": 120,
                "priority_events": ["wwdc", "iphone_launch", "mac_launch"]
            }},
            "documentaries": {{
                "source": "plex",
                "search_terms": ["Steve Jobs", "Apple", "Silicon Valley", "technology"],
                "duration_minutes": 90
            }},
            "retro_tech": {{
                "source": "youtube",
                "channels": ["LGR", "The 8-Bit Guy", "Techmoan"],
                "duration_minutes": 30
            }},
            "computer_chronicles": {{
                "source": "archive_org",
                "collection": "computerchronicles",
                "duration_minutes": 30
            }},
            "vintage_commercials": {{
                "source": "archive_org",
                "collection": "prelinger",
                "search_terms": ["computer", "apple", "ibm", "technology"],
                "duration_minutes": 5
            }}
        }},
        "apple_specific": {{
            "include_keynotes": true,
            "keynote_eras": ["jobs_return", "iphone_era", "cook_era"],
            "include_commercials": true,
            "commercial_campaigns": ["1984", "think_different", "get_a_mac", "shot_on_iphone"],
            "include_wwdc": true,
            "product_focus": ["mac", "iphone", "ipad", "watch", "vision_pro"]
        }},
        "scheduling_rules": {{
            "start_on_hour": true,
            "chronological_option": true,
            "product_grouping": true,
            "era_blocking": true,
            "no_repeat_same_day": true
        }},
        "quality_preferences": {{
            "prefer_hd": true,
            "accept_vintage_quality": true,
            "prefer_official_sources": true
        }}
    }}
}}
```

If you don't have enough information yet, set "ready_to_build": false and continue asking questions.

IMPORTANT:
- Always ask if they want Apple-focused or general tech content
- Clarify era preferences (vintage 80s-90s, modern, or mixed)
- Ask about content types (keynotes, documentaries, reviews, all)
- Check if they have tech documentaries in their Plex library
- Verify interest in retro computing content (Computer Chronicles, etc.)
- Confirm if they want vintage commercials as filler content"""


# Apple Keynotes - Major Events
APPLE_KEYNOTES = {
    "historic": [
        {"year": 1984, "event": "Macintosh Introduction", "presenter": "Steve Jobs", "duration_min": 15},
        {"year": 1997, "event": "Macworld - Steve Jobs Returns", "presenter": "Steve Jobs", "duration_min": 90},
        {"year": 1998, "event": "iMac Introduction", "presenter": "Steve Jobs", "duration_min": 60},
        {"year": 2001, "event": "iPod Introduction", "presenter": "Steve Jobs", "duration_min": 45},
        {"year": 2007, "event": "iPhone Introduction", "presenter": "Steve Jobs", "duration_min": 90},
        {"year": 2010, "event": "iPad Introduction", "presenter": "Steve Jobs", "duration_min": 90},
    ],
    "modern": [
        {"year": 2014, "event": "Apple Watch Introduction", "presenter": "Tim Cook", "duration_min": 120},
        {"year": 2016, "event": "AirPods Introduction", "presenter": "Phil Schiller", "duration_min": 30},
        {"year": 2020, "event": "Apple Silicon Announcement", "presenter": "Tim Cook", "duration_min": 120},
        {"year": 2023, "event": "Vision Pro Introduction", "presenter": "Tim Cook", "duration_min": 120},
    ],
    "wwdc": [
        {"year": 2007, "event": "WWDC - iPhone SDK", "duration_min": 120},
        {"year": 2013, "event": "WWDC - iOS 7 Redesign", "duration_min": 120},
        {"year": 2014, "event": "WWDC - Swift Introduction", "duration_min": 120},
        {"year": 2019, "event": "WWDC - SwiftUI Introduction", "duration_min": 120},
        {"year": 2020, "event": "WWDC - Apple Silicon Transition", "duration_min": 120},
    ],
}

# Apple Commercial Campaigns
APPLE_COMMERCIALS = {
    "1984": {
        "year": 1984,
        "director": "Ridley Scott",
        "duration_seconds": 60,
        "significance": "Super Bowl XVIII, Macintosh launch",
    },
    "think_different": {
        "year": 1997,
        "duration_seconds": 60,
        "significance": "Steve Jobs return era, brand repositioning",
    },
    "get_a_mac": {
        "years": "2006-2009",
        "episodes": 66,
        "duration_seconds": 30,
        "significance": "Mac vs PC campaign with Justin Long",
    },
    "shot_on_iphone": {
        "years": "2015-present",
        "duration_seconds": 60,
        "significance": "User-generated photography showcase",
    },
    "silhouette_ipod": {
        "years": "2003-2008",
        "duration_seconds": 30,
        "significance": "Iconic dancing silhouettes campaign",
    },
}

# YouTube Tech Channels
YOUTUBE_TECH_CHANNELS = {
    "official": {
        "apple": {"name": "Apple", "content": ["keynotes", "ads", "tutorials"]},
        "google": {"name": "Google", "content": ["io_keynotes", "product_launches"]},
        "microsoft": {"name": "Microsoft", "content": ["build", "surface_events"]},
    },
    "retro_tech": {
        "lgr": {"name": "LGR", "content": ["retro_computing", "thrifts", "reviews"]},
        "8bit_guy": {"name": "The 8-Bit Guy", "content": ["restoration", "history"]},
        "techmoan": {"name": "Techmoan", "content": ["vintage_audio", "obscure_tech"]},
        "technology_connections": {"name": "Technology Connections", "content": ["how_it_works", "history"]},
        "cathode_ray_dude": {"name": "Cathode Ray Dude", "content": ["vintage_computing", "deep_dives"]},
    },
    "reviewers": {
        "mkbhd": {"name": "Marques Brownlee", "content": ["reviews", "interviews"]},
        "linus": {"name": "Linus Tech Tips", "content": ["reviews", "builds", "tech_news"]},
        "unbox_therapy": {"name": "Unbox Therapy", "content": ["unboxings", "reviews"]},
        "dave_lee": {"name": "Dave Lee", "content": ["laptop_reviews", "apple"]},
    },
}

# Archive.org Tech Collections
ARCHIVE_ORG_TECH_COLLECTIONS = {
    "computer_chronicles": {
        "name": "Computer Chronicles",
        "episodes": 500,
        "years": "1983-2002",
        "duration_minutes": 30,
        "description": "Weekly TV show covering computing industry",
    },
    "bbs_documentary": {
        "name": "BBS Documentary",
        "episodes": 8,
        "year": 2005,
        "duration_minutes": 45,
        "description": "History of bulletin board systems",
    },
    "prelinger": {
        "name": "Prelinger Archives",
        "content": ["vintage_commercials", "industrial_films", "educational"],
        "description": "Vintage commercials including tech ads",
    },
    "software_library": {
        "name": "Software Library",
        "content": ["vintage_software", "manuals", "demos"],
        "description": "Historical software preservation",
    },
}

# Tech Documentaries
TECH_DOCUMENTARIES = {
    "apple_focused": [
        {"title": "Steve Jobs (2015)", "type": "biopic", "runtime": 122, "director": "Danny Boyle"},
        {"title": "Jobs (2013)", "type": "biopic", "runtime": 128, "director": "Joshua Michael Stern"},
        {"title": "Steve Jobs: The Man in the Machine", "type": "documentary", "runtime": 128, "year": 2015},
        {"title": "Pirates of Silicon Valley", "type": "docudrama", "runtime": 95, "year": 1999},
        {"title": "General Magic", "type": "documentary", "runtime": 92, "year": 2018},
        {"title": "Silicon Cowboys", "type": "documentary", "runtime": 75, "year": 2016},
    ],
    "tech_industry": [
        {"title": "The Social Network", "type": "biopic", "runtime": 120, "year": 2010},
        {"title": "Revolution OS", "type": "documentary", "runtime": 85, "year": 2001},
        {"title": "The Internet's Own Boy", "type": "documentary", "runtime": 105, "year": 2014},
        {"title": "Lo and Behold", "type": "documentary", "runtime": 98, "year": 2016},
        {"title": "AlphaGo", "type": "documentary", "runtime": 90, "year": 2017},
        {"title": "The Great Hack", "type": "documentary", "runtime": 114, "year": 2019},
    ],
    "gaming": [
        {"title": "King of Kong", "type": "documentary", "runtime": 83, "year": 2007},
        {"title": "Indie Game: The Movie", "type": "documentary", "runtime": 96, "year": 2012},
        {"title": "High Score", "type": "docuseries", "episodes": 6, "year": 2020},
        {"title": "Console Wars", "type": "documentary", "runtime": 92, "year": 2020},
    ],
}


def build_tech_channel_prompt(
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
    available_media: dict[str, Any] | None = None,
) -> str:
    """
    Build a prompt for tech channel creation conversation.
    
    Args:
        user_message: The user's current message
        conversation_history: List of previous messages
        available_media: Optional dict describing available media sources
        
    Returns:
        Complete prompt string for Ollama
    """
    prompt_parts = [TECH_EXPERT_SYSTEM_PROMPT]
    
    # Add available media context if provided
    if available_media:
        media_context = "\n\nAVAILABLE MEDIA SOURCES:\n"
        
        if "plex" in available_media:
            plex_info = available_media["plex"]
            media_context += "\nPlex Libraries:\n"
            for lib in plex_info.get("libraries", []):
                media_context += f"  - {lib['name']}: {lib.get('item_count', 'unknown')} items ({lib['type']})\n"
            
            # Highlight tech-related content
            if plex_info.get("genres"):
                tech_genres = [g for g in plex_info["genres"] if any(
                    t in g.lower() for t in ["documentary", "biography", "technology", "science"]
                )]
                if tech_genres:
                    media_context += f"  Tech-related genres: {', '.join(tech_genres)}\n"
        
        if "archive_org" in available_media:
            media_context += "\nArchive.org: Full Computer Chronicles archive (500+ episodes), "
            media_context += "vintage tech commercials (Prelinger), BBS Documentary\n"
        
        if "youtube" in available_media:
            media_context += "\nYouTube: Apple official channel (all keynotes), "
            media_context += "retro tech (LGR, 8-Bit Guy), tech reviews (MKBHD, Linus)\n"
        
        prompt_parts.append(media_context)
    
    # Add tech knowledge context
    prompt_parts.append("\n\nTECH CONTENT KNOWLEDGE:")
    prompt_parts.append("Apple Keynotes: Every iPhone launch, WWDC since 2007, historic 1984 Mac intro")
    prompt_parts.append("Documentaries: Steve Jobs biopics, Pirates of Silicon Valley, General Magic")
    prompt_parts.append("Archive.org: Computer Chronicles complete series, Prelinger vintage ads")
    prompt_parts.append("Retro Tech: LGR, The 8-Bit Guy, Techmoan, Technology Connections")
    
    # Add conversation history
    if conversation_history:
        prompt_parts.append("\n\nCONVERSATION HISTORY:")
        for msg in conversation_history:
            role = "User" if msg["role"] == "user" else "You (Steve 'Woz' Nakamura)"
            prompt_parts.append(f"\n{role}: {msg['content']}")
    
    # Add current user message
    prompt_parts.append(f"\n\nUser: {user_message}")
    prompt_parts.append("\n\nYou (Steve 'Woz' Nakamura):")
    
    return "\n".join(prompt_parts)


def build_tech_schedule_prompt(
    channel_spec: dict[str, Any],
    available_content: dict[str, Any],
) -> str:
    """
    Build a prompt for generating detailed tech schedule from specification.
    
    Args:
        channel_spec: The channel specification from conversation
        available_content: Dict of available content from media sources
        
    Returns:
        Prompt for schedule generation
    """
    import json
    
    prompt = f"""You are generating a detailed technology programming schedule based on this specification:

{json.dumps(channel_spec, indent=2)}

Available content from media sources:
{json.dumps(available_content, indent=2)}

Generate a complete weekly schedule template. For each time slot, specify:
1. Start time
2. Duration (keynotes ~2hrs, reviews ~20min, Computer Chronicles ~30min)
3. Content type (keynote, documentary, review, vintage, commercial compilation)
4. Specific content or search criteria
5. Source (plex, archive_org, youtube)
6. Era/product focus if relevant

IMPORTANT RULES:
- Apple keynotes should be scheduled as complete events (90-120 minutes)
- Computer Chronicles episodes are 30 minutes each
- Retro tech reviews typically 15-30 minutes
- Tech documentaries usually 90-120 minutes
- Include vintage commercial compilations as transitions
- Consider chronological ordering for product evolution viewing
- Mix eras for variety unless channel is era-specific

Return ONLY valid JSON in this format:
```json
{{
    "weekly_schedule": {{
        "sunday": [
            {{
                "start_time": "14:00",
                "duration_minutes": 120,
                "content_type": "keynote",
                "title": "iPhone Introduction - Macworld 2007",
                "source": "youtube",
                "channel": "Apple",
                "era": "jobs",
                "notes": "Historic iPhone reveal"
            }}
        ],
        "monday": [...],
        "tuesday": [...],
        "wednesday": [...],
        "thursday": [...],
        "friday": [...],
        "saturday": [...]
    }},
    "filler_content": [
        {{
            "type": "vintage_commercial",
            "source": "archive_org",
            "collection": "prelinger",
            "search_terms": ["apple", "computer", "macintosh"],
            "duration_seconds": 60
        }},
        {{
            "type": "startup_chime",
            "source": "youtube",
            "duration_seconds": 10
        }}
    ]
}}
```"""
    
    return prompt


def get_tech_welcome_message() -> str:
    """Get the initial welcome message from the Tech Savant."""
    return """Steve Nakamura here - and yes, my parents did name me after Jobs. Call it destiny.

I've been cataloging tech history since I got my first Apple IIe in 1983. I can tell you 
the exact date the original Macintosh shipped, recite the '1984' commercial script from 
memory, and I've watched every single Apple keynote - including the ones from the dark 
years before Steve came back.

You want a tech channel? Let's talk.

Are we going full Apple? Because I can build you a 24/7 Apple channel that would make 
Cupertino proud - every keynote, every "one more thing," every Think Different moment. 
The 2007 iPhone introduction alone is worth rewatching once a month.

Or maybe you want broader tech? I know where every episode of The Computer Chronicles 
lives on Archive.org - that's 500+ episodes of computing history from 1983 to 2002. 
There's also incredible retro tech content on YouTube now - channels like LGR and 
The 8-Bit Guy do amazing work.

The golden age of tech is all preserved online if you know where to look. And believe 
me, I know where to look.

So what's your vision? Apple devotee channel? General computing history? Gaming tech 
evolution? Or maybe a mix of everything with vintage commercials to tie it together?

Also - do you have any tech documentaries in your Plex library? Pirates of Silicon 
Valley? The Steve Jobs movies? Those are essential building blocks."""
