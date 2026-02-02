"""
Intent Analyzer for AI Channel Creation

Parses natural language requests into structured AnalyzedIntent objects
with channel purpose, playout preferences, source hints, and scheduling requirements.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ChannelPurpose(Enum):
    """Primary purpose/theme of the channel."""
    
    ENTERTAINMENT = "entertainment"
    EDUCATIONAL = "educational"
    SPORTS = "sports"
    MOVIES = "movies"
    KIDS = "kids"
    MUSIC = "music"
    NEWS = "news"
    DOCUMENTARY = "documentary"
    RETRO = "retro"
    TECH = "tech"
    MIXED = "mixed"
    CUSTOM = "custom"


class PlayoutPreference(Enum):
    """Preferred playout mode for the channel."""
    
    CONTINUOUS = "continuous"  # 24/7 streaming
    SCHEDULED = "scheduled"  # Time-based schedule
    ON_DEMAND = "on_demand"  # User-selected content
    LOOP = "loop"  # Single content looping
    SHUFFLE = "shuffle"  # Random from collection
    FLOOD = "flood"  # Fill until target time
    MIRROR = "mirror"  # Mirror another source


class ContentEra(Enum):
    """Time period for content."""
    
    CLASSIC = "classic"  # Pre-1970
    GOLDEN_AGE = "golden_age"  # 1970s-1980s
    MODERN_CLASSIC = "modern_classic"  # 1990s-2000s
    CONTEMPORARY = "contemporary"  # 2010s-present
    ALL_TIME = "all_time"  # Any era


@dataclass
class TimePreference:
    """Scheduling time preferences."""
    
    is_24_hour: bool = True
    preferred_start_hour: int | None = None
    dayparts: list[str] = field(default_factory=list)  # morning, afternoon, primetime, etc.
    specific_days: list[str] = field(default_factory=list)  # monday, saturday, etc.
    holiday_aware: bool = False
    weekend_focus: bool = False


@dataclass
class SourceHints:
    """Hints about preferred content sources."""
    
    prefer_plex: bool = False
    prefer_jellyfin: bool = False
    prefer_archive_org: bool = False
    prefer_youtube: bool = False
    prefer_local: bool = False
    specific_libraries: list[str] = field(default_factory=list)
    specific_collections: list[str] = field(default_factory=list)
    excluded_sources: list[str] = field(default_factory=list)


@dataclass
class ContentPreferences:
    """Content selection preferences."""
    
    genres: list[str] = field(default_factory=list)
    excluded_genres: list[str] = field(default_factory=list)
    content_ratings: list[str] = field(default_factory=list)  # G, PG, TV-Y7, etc.
    max_rating: str | None = None
    era: ContentEra = ContentEra.ALL_TIME
    year_range: tuple[int | None, int | None] = (None, None)
    directors: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    franchises: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)


@dataclass
class FillerPreferences:
    """Preferences for filler content."""
    
    include_commercials: bool = False
    commercial_style: str = "vintage"  # vintage, modern, none
    include_bumpers: bool = True
    include_station_ids: bool = True
    include_trailers: bool = False
    filler_source: str = "archive_org"


@dataclass
class AnalyzedIntent:
    """
    Complete analyzed intent from a user request.
    
    Contains all extracted information about what kind of channel
    the user wants to create.
    """
    
    # Core intent
    raw_request: str
    purpose: ChannelPurpose
    confidence: float  # 0.0 to 1.0
    
    # Channel details
    suggested_name: str | None = None
    suggested_number: str | None = None
    description: str | None = None
    
    # Playout preferences
    playout_preference: PlayoutPreference = PlayoutPreference.CONTINUOUS
    
    # Content preferences
    content: ContentPreferences = field(default_factory=ContentPreferences)
    
    # Scheduling preferences
    scheduling: TimePreference = field(default_factory=TimePreference)
    
    # Source hints
    sources: SourceHints = field(default_factory=SourceHints)
    
    # Filler preferences
    filler: FillerPreferences = field(default_factory=FillerPreferences)
    
    # Extracted entities
    mentioned_shows: list[str] = field(default_factory=list)
    mentioned_movies: list[str] = field(default_factory=list)
    mentioned_genres: list[str] = field(default_factory=list)
    mentioned_years: list[int] = field(default_factory=list)
    
    # Flags
    needs_clarification: bool = False
    clarification_questions: list[str] = field(default_factory=list)
    
    # Suggested persona
    suggested_persona: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "raw_request": self.raw_request,
            "purpose": self.purpose.value,
            "confidence": self.confidence,
            "suggested_name": self.suggested_name,
            "suggested_number": self.suggested_number,
            "description": self.description,
            "playout_preference": self.playout_preference.value,
            "content": {
                "genres": self.content.genres,
                "excluded_genres": self.content.excluded_genres,
                "era": self.content.era.value,
                "year_range": self.content.year_range,
                "directors": self.content.directors,
                "actors": self.content.actors,
                "franchises": self.content.franchises,
                "keywords": self.content.keywords,
            },
            "scheduling": {
                "is_24_hour": self.scheduling.is_24_hour,
                "dayparts": self.scheduling.dayparts,
                "specific_days": self.scheduling.specific_days,
                "holiday_aware": self.scheduling.holiday_aware,
            },
            "sources": {
                "prefer_plex": self.sources.prefer_plex,
                "prefer_archive_org": self.sources.prefer_archive_org,
                "prefer_youtube": self.sources.prefer_youtube,
                "specific_libraries": self.sources.specific_libraries,
            },
            "filler": {
                "include_commercials": self.filler.include_commercials,
                "commercial_style": self.filler.commercial_style,
                "include_bumpers": self.filler.include_bumpers,
            },
            "mentioned_shows": self.mentioned_shows,
            "mentioned_movies": self.mentioned_movies,
            "mentioned_genres": self.mentioned_genres,
            "needs_clarification": self.needs_clarification,
            "clarification_questions": self.clarification_questions,
            "suggested_persona": self.suggested_persona,
        }


class IntentAnalyzer:
    """
    Analyzes natural language requests to extract channel creation intent.
    
    Uses pattern matching and keyword extraction to understand what
    kind of channel the user wants to create.
    """
    
    # Genre keywords mapping
    GENRE_KEYWORDS = {
        "comedy": ["comedy", "funny", "sitcom", "laugh", "humorous"],
        "drama": ["drama", "dramatic", "serious"],
        "action": ["action", "adventure", "exciting", "thrilling"],
        "horror": ["horror", "scary", "spooky", "frightening", "halloween"],
        "sci_fi": ["sci-fi", "science fiction", "scifi", "space", "futuristic"],
        "fantasy": ["fantasy", "magical", "wizards", "dragons"],
        "documentary": ["documentary", "documentaries", "factual", "informative"],
        "animation": ["animation", "animated", "cartoon", "anime"],
        "western": ["western", "cowboy", "frontier", "wild west"],
        "noir": ["noir", "film noir", "detective", "hardboiled"],
        "romance": ["romance", "romantic", "love story"],
        "thriller": ["thriller", "suspense", "suspenseful"],
        "mystery": ["mystery", "whodunit", "detective"],
        "musical": ["musical", "music", "singing", "dancing"],
        "sports": ["sports", "athletic", "game", "competition"],
        "nature": ["nature", "wildlife", "animals", "planet earth"],
        "history": ["history", "historical", "period"],
        "true_crime": ["true crime", "murder", "investigation"],
    }
    
    # Era keywords mapping
    ERA_KEYWORDS = {
        ContentEra.CLASSIC: ["classic", "vintage", "old", "golden age", "1950s", "1960s"],
        ContentEra.GOLDEN_AGE: ["70s", "80s", "1970", "1980", "retro", "nostalgia"],
        ContentEra.MODERN_CLASSIC: ["90s", "2000s", "1990", "2000", "throwback"],
        ContentEra.CONTEMPORARY: ["modern", "new", "recent", "current", "latest", "2010", "2020"],
    }
    
    # Playout keywords mapping
    PLAYOUT_KEYWORDS = {
        PlayoutPreference.CONTINUOUS: ["24/7", "continuous", "always on", "non-stop"],
        PlayoutPreference.SCHEDULED: ["scheduled", "timed", "specific times", "programming"],
        PlayoutPreference.SHUFFLE: ["random", "shuffle", "mix", "variety"],
        PlayoutPreference.LOOP: ["loop", "repeat", "single"],
    }
    
    # Purpose keywords mapping
    PURPOSE_KEYWORDS = {
        ChannelPurpose.SPORTS: [
            "sports", "nfl", "nba", "mlb", "nhl", "football", "basketball",
            "baseball", "hockey", "soccer", "boxing", "olympics", "athletics"
        ],
        ChannelPurpose.MOVIES: [
            "movie", "movies", "film", "films", "cinema", "theatrical",
            "feature", "double feature"
        ],
        ChannelPurpose.KIDS: [
            "kids", "children", "family", "disney", "pixar", "cartoon",
            "preschool", "animated"
        ],
        ChannelPurpose.DOCUMENTARY: [
            "documentary", "documentaries", "pbs", "nature", "science",
            "educational", "informative"
        ],
        ChannelPurpose.TECH: [
            "tech", "technology", "apple", "computer", "computing",
            "keynote", "gadget"
        ],
        ChannelPurpose.MUSIC: [
            "music", "concert", "performance", "mtv", "vh1", "austin city limits"
        ],
        ChannelPurpose.NEWS: [
            "news", "current events", "journalism", "cnn", "newsroom"
        ],
        ChannelPurpose.RETRO: [
            "retro", "vintage", "classic tv", "nostalgia", "old school"
        ],
        ChannelPurpose.EDUCATIONAL: [
            "educational", "learning", "school", "teach", "sesame street",
            "pbs kids"
        ],
    }
    
    # Source keywords mapping
    SOURCE_KEYWORDS = {
        "plex": ["plex", "my library", "my collection", "local library"],
        "jellyfin": ["jellyfin", "jelly"],
        "archive_org": ["archive.org", "internet archive", "public domain", "prelinger"],
        "youtube": ["youtube", "yt", "streaming"],
    }
    
    def __init__(self):
        """Initialize the intent analyzer."""
        logger.info("IntentAnalyzer initialized")
    
    def analyze(self, request: str) -> AnalyzedIntent:
        """
        Analyze a natural language request.
        
        Args:
            request: The user's channel creation request
            
        Returns:
            AnalyzedIntent with extracted information
        """
        request_lower = request.lower()
        
        # Create base intent
        intent = AnalyzedIntent(
            raw_request=request,
            purpose=self._extract_purpose(request_lower),
            confidence=0.7,  # Base confidence
        )
        
        # Extract content preferences
        intent.content = self._extract_content_preferences(request_lower)
        
        # Extract scheduling preferences
        intent.scheduling = self._extract_scheduling_preferences(request_lower)
        
        # Extract source hints
        intent.sources = self._extract_source_hints(request_lower)
        
        # Extract playout preference
        intent.playout_preference = self._extract_playout_preference(request_lower)
        
        # Extract filler preferences
        intent.filler = self._extract_filler_preferences(request_lower)
        
        # Extract mentioned entities
        intent.mentioned_genres = self._extract_genres(request_lower)
        intent.mentioned_years = self._extract_years(request)
        
        # Suggest channel name
        intent.suggested_name = self._suggest_channel_name(intent)
        
        # Suggest persona
        intent.suggested_persona = self._suggest_persona(intent)
        
        # Check if clarification is needed
        intent.needs_clarification, intent.clarification_questions = self._check_clarification_needed(intent)
        
        # Adjust confidence based on completeness
        intent.confidence = self._calculate_confidence(intent)
        
        logger.info(f"Analyzed intent: purpose={intent.purpose.value}, confidence={intent.confidence:.2f}")
        
        return intent
    
    def _extract_purpose(self, request: str) -> ChannelPurpose:
        """Extract the primary channel purpose."""
        scores = {purpose: 0 for purpose in ChannelPurpose}
        
        for purpose, keywords in self.PURPOSE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in request:
                    scores[purpose] += 1
        
        best_purpose = max(scores, key=scores.get)
        if scores[best_purpose] > 0:
            return best_purpose
        
        return ChannelPurpose.ENTERTAINMENT
    
    def _extract_content_preferences(self, request: str) -> ContentPreferences:
        """Extract content preferences from request."""
        prefs = ContentPreferences()
        
        # Extract genres
        prefs.genres = self._extract_genres(request)
        
        # Extract era
        prefs.era = self._extract_era(request)
        
        # Extract year range
        years = self._extract_years(request.upper())  # Pass original for regex
        if len(years) >= 2:
            prefs.year_range = (min(years), max(years))
        elif len(years) == 1:
            # Single year mentioned - assume decade
            year = years[0]
            prefs.year_range = (year, year + 9)
        
        # Extract content ratings
        if any(word in request for word in ["kid", "family", "children"]):
            prefs.max_rating = "PG"
        
        # Extract keywords
        prefs.keywords = self._extract_keywords(request)
        
        return prefs
    
    def _extract_scheduling_preferences(self, request: str) -> TimePreference:
        """Extract scheduling preferences."""
        prefs = TimePreference()
        
        # Check for 24/7
        if any(phrase in request for phrase in ["24/7", "24 hours", "always", "continuous"]):
            prefs.is_24_hour = True
        
        # Check for specific dayparts
        daypart_keywords = {
            "morning": ["morning", "breakfast", "early"],
            "afternoon": ["afternoon", "daytime"],
            "primetime": ["primetime", "prime time", "evening", "night"],
            "late_night": ["late night", "midnight", "after hours"],
        }
        
        for daypart, keywords in daypart_keywords.items():
            if any(kw in request for kw in keywords):
                prefs.dayparts.append(daypart)
        
        # Check for specific days
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in days:
            if day in request:
                prefs.specific_days.append(day)
        
        # Weekend focus
        if any(word in request for word in ["weekend", "saturday", "sunday"]):
            prefs.weekend_focus = True
        
        # Holiday awareness
        if any(word in request for word in ["holiday", "christmas", "halloween", "thanksgiving"]):
            prefs.holiday_aware = True
        
        return prefs
    
    def _extract_source_hints(self, request: str) -> SourceHints:
        """Extract source preferences."""
        hints = SourceHints()
        
        for source, keywords in self.SOURCE_KEYWORDS.items():
            if any(kw in request for kw in keywords):
                if source == "plex":
                    hints.prefer_plex = True
                elif source == "jellyfin":
                    hints.prefer_jellyfin = True
                elif source == "archive_org":
                    hints.prefer_archive_org = True
                elif source == "youtube":
                    hints.prefer_youtube = True
        
        # If no specific source mentioned, default to Plex + Archive.org
        if not any([hints.prefer_plex, hints.prefer_jellyfin, 
                    hints.prefer_archive_org, hints.prefer_youtube]):
            hints.prefer_plex = True
            hints.prefer_archive_org = True
        
        return hints
    
    def _extract_playout_preference(self, request: str) -> PlayoutPreference:
        """Extract playout preference."""
        for playout, keywords in self.PLAYOUT_KEYWORDS.items():
            if any(kw in request for kw in keywords):
                return playout
        
        return PlayoutPreference.CONTINUOUS
    
    def _extract_filler_preferences(self, request: str) -> FillerPreferences:
        """Extract filler content preferences."""
        prefs = FillerPreferences()
        
        if any(word in request for word in ["commercial", "ads", "vintage ad"]):
            prefs.include_commercials = True
            
        if "vintage" in request or "classic" in request:
            prefs.commercial_style = "vintage"
            
        if "no commercial" in request or "without commercial" in request:
            prefs.include_commercials = False
            
        return prefs
    
    def _extract_genres(self, request: str) -> list[str]:
        """Extract mentioned genres."""
        genres = []
        for genre, keywords in self.GENRE_KEYWORDS.items():
            if any(kw in request for kw in keywords):
                genres.append(genre)
        return genres
    
    def _extract_era(self, request: str) -> ContentEra:
        """Extract content era preference."""
        for era, keywords in self.ERA_KEYWORDS.items():
            if any(kw in request for kw in keywords):
                return era
        return ContentEra.ALL_TIME
    
    def _extract_years(self, request: str) -> list[int]:
        """Extract mentioned years."""
        # Find 4-digit years
        year_pattern = r'\b(19[0-9]{2}|20[0-2][0-9])\b'
        matches = re.findall(year_pattern, request)
        return [int(y) for y in matches]
    
    def _extract_keywords(self, request: str) -> list[str]:
        """Extract important keywords from request."""
        # Simple keyword extraction - could be enhanced with NLP
        stop_words = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "i", "you", "he", "she",
            "it", "we", "they", "what", "which", "who", "when", "where", "why",
            "how", "all", "each", "every", "both", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "can", "want", "like", "make", "create",
            "build", "channel", "tv", "television"
        }
        
        words = request.split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords[:10]  # Limit to top 10
    
    def _suggest_channel_name(self, intent: AnalyzedIntent) -> str | None:
        """Suggest a channel name based on intent."""
        purpose_names = {
            ChannelPurpose.SPORTS: "Sports Classics",
            ChannelPurpose.MOVIES: "Movie Channel",
            ChannelPurpose.KIDS: "Kids Zone",
            ChannelPurpose.DOCUMENTARY: "Documentary Channel",
            ChannelPurpose.TECH: "Tech TV",
            ChannelPurpose.MUSIC: "Music Channel",
            ChannelPurpose.NEWS: "News Channel",
            ChannelPurpose.RETRO: "Retro TV",
            ChannelPurpose.EDUCATIONAL: "Learning Channel",
            ChannelPurpose.ENTERTAINMENT: "Entertainment",
        }
        
        base_name = purpose_names.get(intent.purpose, "Custom Channel")
        
        # Add era modifier if specific
        if intent.content.era == ContentEra.GOLDEN_AGE:
            base_name = f"Classic {base_name}"
        elif intent.content.era == ContentEra.CONTEMPORARY:
            base_name = f"Modern {base_name}"
        
        return base_name
    
    def _suggest_persona(self, intent: AnalyzedIntent) -> str:
        """Suggest the best persona for this intent."""
        persona_map = {
            ChannelPurpose.SPORTS: "sports_expert",
            ChannelPurpose.MOVIES: "movie_critic",
            ChannelPurpose.KIDS: "kids_expert",
            ChannelPurpose.DOCUMENTARY: "pbs_expert",
            ChannelPurpose.TECH: "tech_expert",
            ChannelPurpose.EDUCATIONAL: "pbs_expert",
        }
        
        return persona_map.get(intent.purpose, "tv_executive")
    
    def _check_clarification_needed(self, intent: AnalyzedIntent) -> tuple[bool, list[str]]:
        """Check if clarification is needed and generate questions."""
        questions = []
        
        # Check for missing critical info
        if not intent.content.genres and intent.purpose == ChannelPurpose.ENTERTAINMENT:
            questions.append("What genres would you like to include?")
        
        if not intent.sources.prefer_plex and not intent.sources.prefer_archive_org:
            questions.append("Do you have a Plex library, or should we use public domain content?")
        
        if intent.purpose == ChannelPurpose.KIDS:
            if not intent.content.max_rating:
                questions.append("What age range is this for?")
        
        return len(questions) > 0, questions
    
    def _calculate_confidence(self, intent: AnalyzedIntent) -> float:
        """Calculate confidence score based on intent completeness."""
        confidence = 0.5  # Base confidence
        
        # Add confidence for extracted information
        if intent.purpose != ChannelPurpose.ENTERTAINMENT:
            confidence += 0.1
        
        if intent.content.genres:
            confidence += 0.1
        
        if intent.content.era != ContentEra.ALL_TIME:
            confidence += 0.05
        
        if intent.sources.prefer_plex or intent.sources.prefer_archive_org:
            confidence += 0.05
        
        if intent.scheduling.dayparts:
            confidence += 0.05
        
        if not intent.needs_clarification:
            confidence += 0.1
        
        return min(confidence, 1.0)


# Convenience function
def analyze_intent(request: str) -> AnalyzedIntent:
    """Analyze a channel creation request."""
    analyzer = IntentAnalyzer()
    return analyzer.analyze(request)
