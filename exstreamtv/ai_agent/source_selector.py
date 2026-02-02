"""
Source Selector for AI Channel Creation

Queries all available media sources (Plex, Jellyfin, Emby, local, Archive.org)
and ranks them by suitability for the request.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SourceType(Enum):
    """Types of media sources."""
    
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"
    LOCAL = "local"
    ARCHIVE_ORG = "archive_org"
    YOUTUBE = "youtube"
    M3U = "m3u"


class ContentMatch(Enum):
    """How well source matches request."""
    
    EXCELLENT = "excellent"  # 90%+ match
    GOOD = "good"  # 70-89% match
    FAIR = "fair"  # 50-69% match
    POOR = "poor"  # 30-49% match
    NONE = "none"  # <30% match


@dataclass
class SourceContent:
    """Content available from a source."""
    
    total_items: int = 0
    movies: int = 0
    tv_shows: int = 0
    episodes: int = 0
    music: int = 0
    other: int = 0
    
    genres: list[str] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    libraries: list[dict[str, Any]] = field(default_factory=list)
    
    def has_content(self) -> bool:
        """Check if source has any content."""
        return self.total_items > 0


@dataclass
class SourceRanking:
    """Ranking result for a source."""
    
    source_type: SourceType
    source_name: str
    score: float = 0.0  # 0.0 to 1.0
    match: ContentMatch = ContentMatch.NONE
    
    # Content details
    content: SourceContent = field(default_factory=SourceContent)
    
    # Matching details
    matching_genres: list[str] = field(default_factory=list)
    matching_years: list[int] = field(default_factory=list)
    matching_count: int = 0
    
    # Availability
    is_available: bool = True
    is_connected: bool = True
    
    # Recommendations
    recommended_libraries: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "score": self.score,
            "match": self.match.value,
            "content": {
                "total_items": self.content.total_items,
                "movies": self.content.movies,
                "tv_shows": self.content.tv_shows,
                "episodes": self.content.episodes,
                "genres": self.content.genres[:10],
                "year_range": (min(self.content.years), max(self.content.years)) if self.content.years else None,
            },
            "matching": {
                "genres": self.matching_genres,
                "count": self.matching_count,
            },
            "is_available": self.is_available,
            "recommended_libraries": self.recommended_libraries,
            "warnings": self.warnings,
        }


@dataclass 
class SourceSelectionResult:
    """Complete source selection result."""
    
    rankings: list[SourceRanking] = field(default_factory=list)
    primary_source: SourceRanking | None = None
    secondary_sources: list[SourceRanking] = field(default_factory=list)
    total_content_available: int = 0
    
    # Recommendations
    recommended_combination: list[SourceType] = field(default_factory=list)
    coverage_notes: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "rankings": [r.to_dict() for r in self.rankings],
            "primary_source": self.primary_source.to_dict() if self.primary_source else None,
            "secondary_sources": [s.to_dict() for s in self.secondary_sources],
            "total_content_available": self.total_content_available,
            "recommended_combination": [s.value for s in self.recommended_combination],
            "coverage_notes": self.coverage_notes,
        }


class SourceSelector:
    """
    Selects and ranks media sources for channel creation.
    
    Queries available sources and ranks them based on content match,
    availability, and suitability for the requested channel type.
    """
    
    # Archive.org collections by category
    ARCHIVE_COLLECTIONS = {
        "movies": ["feature_films", "film_noir", "silent_films", "sci_fi_horror", "Comedy_Films"],
        "tv": ["classic_tv", "television_archive"],
        "cartoons": ["classic_cartoons", "animation"],
        "educational": ["prelinger", "av_geeks", "computerchronicles"],
        "sports": ["sports_broadcasts", "sports_films"],
        "music": ["audio_music", "live_music_archive"],
        "commercials": ["prelinger"],
    }
    
    # Genre mappings for source matching
    GENRE_SOURCE_AFFINITY = {
        # Genres that are well-served by Archive.org
        "archive_strong": ["noir", "classic", "vintage", "public_domain", "educational", "documentary"],
        # Genres typically in Plex libraries
        "plex_strong": ["modern", "contemporary", "recent", "streaming"],
        # Genres available on YouTube
        "youtube_strong": ["sports", "tech", "keynotes", "retro_tech", "gaming"],
    }
    
    def __init__(
        self,
        plex_client: Any | None = None,
        jellyfin_client: Any | None = None,
        emby_client: Any | None = None,
        archive_client: Any | None = None,
    ):
        """
        Initialize the source selector.
        
        Args:
            plex_client: Optional Plex client
            jellyfin_client: Optional Jellyfin client
            emby_client: Optional Emby client
            archive_client: Optional Archive.org client
        """
        self.plex_client = plex_client
        self.jellyfin_client = jellyfin_client
        self.emby_client = emby_client
        self.archive_client = archive_client
        
        logger.info("SourceSelector initialized")
    
    async def select_sources(
        self,
        genres: list[str] | None = None,
        content_types: list[str] | None = None,
        era: str | None = None,
        year_range: tuple[int | None, int | None] | None = None,
        preferred_sources: list[SourceType] | None = None,
        excluded_sources: list[SourceType] | None = None,
    ) -> SourceSelectionResult:
        """
        Select and rank sources for the given criteria.
        
        Args:
            genres: Desired genres
            content_types: Desired content types (movies, tv, etc.)
            era: Content era preference
            year_range: Year range filter
            preferred_sources: User-preferred sources
            excluded_sources: Sources to exclude
            
        Returns:
            SourceSelectionResult with ranked sources
        """
        result = SourceSelectionResult()
        rankings = []
        
        excluded = excluded_sources or []
        
        # Check each available source
        if SourceType.PLEX not in excluded:
            plex_ranking = await self._rank_plex(genres, content_types, era, year_range)
            if plex_ranking:
                rankings.append(plex_ranking)
        
        if SourceType.JELLYFIN not in excluded:
            jellyfin_ranking = await self._rank_jellyfin(genres, content_types, era, year_range)
            if jellyfin_ranking:
                rankings.append(jellyfin_ranking)
        
        if SourceType.ARCHIVE_ORG not in excluded:
            archive_ranking = await self._rank_archive_org(genres, content_types, era, year_range)
            if archive_ranking:
                rankings.append(archive_ranking)
        
        if SourceType.YOUTUBE not in excluded:
            youtube_ranking = await self._rank_youtube(genres, content_types, era)
            if youtube_ranking:
                rankings.append(youtube_ranking)
        
        # Sort by score
        rankings.sort(key=lambda r: r.score, reverse=True)
        result.rankings = rankings
        
        # Determine primary and secondary sources
        if rankings:
            result.primary_source = rankings[0]
            result.secondary_sources = [r for r in rankings[1:] if r.score >= 0.3]
        
        # Calculate total content
        result.total_content_available = sum(r.matching_count for r in rankings)
        
        # Build recommended combination
        result.recommended_combination = self._recommend_combination(rankings, genres, content_types)
        
        # Add coverage notes
        result.coverage_notes = self._generate_coverage_notes(result, genres, content_types)
        
        return result
    
    async def _rank_plex(
        self,
        genres: list[str] | None,
        content_types: list[str] | None,
        era: str | None,
        year_range: tuple[int | None, int | None] | None,
    ) -> SourceRanking | None:
        """Rank Plex as a source."""
        ranking = SourceRanking(
            source_type=SourceType.PLEX,
            source_name="Plex Media Server",
        )
        
        # Check if Plex is available
        if not self.plex_client:
            ranking.is_available = False
            ranking.is_connected = False
            ranking.score = 0.0
            ranking.match = ContentMatch.NONE
            ranking.warnings.append("Plex server not configured")
            return ranking
        
        try:
            # Query Plex for content
            content = await self._query_plex_content()
            ranking.content = content
            
            if not content.has_content():
                ranking.score = 0.0
                ranking.match = ContentMatch.NONE
                ranking.warnings.append("No content found in Plex library")
                return ranking
            
            # Calculate score based on matching content
            score = 0.0
            matching_count = 0
            
            # Genre matching
            if genres:
                matching_genres = [g for g in genres if g.lower() in [cg.lower() for cg in content.genres]]
                ranking.matching_genres = matching_genres
                genre_match_ratio = len(matching_genres) / len(genres) if genres else 0
                score += genre_match_ratio * 0.4
            else:
                score += 0.3  # Base score if no specific genres requested
            
            # Year matching
            if year_range and content.years:
                start_year, end_year = year_range
                matching_years = [y for y in content.years 
                                  if (start_year is None or y >= start_year) 
                                  and (end_year is None or y <= end_year)]
                ranking.matching_years = matching_years[:10]
                year_match_ratio = len(matching_years) / len(content.years) if content.years else 0
                score += year_match_ratio * 0.2
            else:
                score += 0.1
            
            # Content type matching
            if content_types:
                if "movies" in content_types and content.movies > 0:
                    score += 0.2
                    matching_count += content.movies
                if "tv" in content_types and content.tv_shows > 0:
                    score += 0.2
                    matching_count += content.episodes
            else:
                score += 0.2
                matching_count = content.total_items
            
            ranking.score = min(score, 1.0)
            ranking.matching_count = matching_count
            ranking.match = self._score_to_match(ranking.score)
            
            # Add recommended libraries
            ranking.recommended_libraries = [lib["name"] for lib in content.libraries[:5]]
            
        except Exception as e:
            logger.exception(f"Error ranking Plex: {e}")
            ranking.is_available = False
            ranking.score = 0.0
            ranking.match = ContentMatch.NONE
            ranking.warnings.append(f"Error connecting to Plex: {str(e)}")
        
        return ranking
    
    async def _rank_jellyfin(
        self,
        genres: list[str] | None,
        content_types: list[str] | None,
        era: str | None,
        year_range: tuple[int | None, int | None] | None,
    ) -> SourceRanking | None:
        """Rank Jellyfin as a source."""
        ranking = SourceRanking(
            source_type=SourceType.JELLYFIN,
            source_name="Jellyfin",
        )
        
        if not self.jellyfin_client:
            ranking.is_available = False
            ranking.is_connected = False
            ranking.score = 0.0
            ranking.match = ContentMatch.NONE
            return ranking
        
        # Similar logic to Plex...
        # For now, return basic ranking
        ranking.score = 0.5
        ranking.match = ContentMatch.FAIR
        
        return ranking
    
    async def _rank_archive_org(
        self,
        genres: list[str] | None,
        content_types: list[str] | None,
        era: str | None,
        year_range: tuple[int | None, int | None] | None,
    ) -> SourceRanking | None:
        """Rank Archive.org as a source."""
        ranking = SourceRanking(
            source_type=SourceType.ARCHIVE_ORG,
            source_name="Internet Archive",
            is_available=True,
            is_connected=True,
        )
        
        content = SourceContent()
        score = 0.0
        
        # Archive.org is always available
        # Score based on how well content types match archive collections
        
        if content_types:
            for ct in content_types:
                if ct.lower() in self.ARCHIVE_COLLECTIONS:
                    score += 0.2
                    content.total_items += 1000  # Estimate
        
        # Era affinity - Archive.org is great for classic content
        if era in ["classic", "golden_age", "vintage"]:
            score += 0.3
            
        # Genre affinity
        if genres:
            archive_strong = self.GENRE_SOURCE_AFFINITY["archive_strong"]
            matching = [g for g in genres if any(a in g.lower() for a in archive_strong)]
            if matching:
                score += 0.2 * len(matching) / len(genres)
                ranking.matching_genres = matching
        
        # Year range affinity - better for older content
        if year_range:
            start_year, end_year = year_range
            if start_year and start_year < 1970:
                score += 0.2
            elif end_year and end_year < 1980:
                score += 0.1
        
        # Base availability score
        score += 0.2
        
        ranking.score = min(score, 1.0)
        ranking.match = self._score_to_match(ranking.score)
        ranking.content = content
        ranking.matching_count = content.total_items
        
        # Add collection recommendations
        if content_types:
            for ct in content_types:
                if ct.lower() in self.ARCHIVE_COLLECTIONS:
                    ranking.recommended_libraries.extend(self.ARCHIVE_COLLECTIONS[ct.lower()])
        
        return ranking
    
    async def _rank_youtube(
        self,
        genres: list[str] | None,
        content_types: list[str] | None,
        era: str | None,
    ) -> SourceRanking | None:
        """Rank YouTube as a source."""
        ranking = SourceRanking(
            source_type=SourceType.YOUTUBE,
            source_name="YouTube",
            is_available=True,
            is_connected=True,
        )
        
        score = 0.0
        
        # YouTube is good for specific content types
        youtube_content = ["sports", "tech", "keynotes", "music", "documentary", "gaming"]
        
        if content_types:
            matching = [ct for ct in content_types if ct.lower() in youtube_content]
            if matching:
                score += 0.3 * len(matching) / len(content_types)
        
        if genres:
            youtube_strong = self.GENRE_SOURCE_AFFINITY["youtube_strong"]
            matching = [g for g in genres if any(y in g.lower() for y in youtube_strong)]
            if matching:
                score += 0.2
                ranking.matching_genres = matching
        
        # Base availability
        score += 0.2
        
        ranking.score = min(score, 1.0)
        ranking.match = self._score_to_match(ranking.score)
        
        ranking.warnings.append("YouTube content may have availability limitations")
        
        return ranking
    
    async def _query_plex_content(self) -> SourceContent:
        """Query Plex for content information."""
        content = SourceContent()
        
        try:
            # This would use the actual Plex client
            # For now, return placeholder data
            content.total_items = 500
            content.movies = 200
            content.tv_shows = 50
            content.episodes = 250
            content.genres = ["Drama", "Comedy", "Action", "Sci-Fi", "Documentary"]
            content.years = list(range(1980, 2024))
            content.libraries = [
                {"name": "Movies", "type": "movie", "count": 200},
                {"name": "TV Shows", "type": "show", "count": 50},
            ]
        except Exception as e:
            logger.error(f"Error querying Plex: {e}")
        
        return content
    
    def _score_to_match(self, score: float) -> ContentMatch:
        """Convert score to ContentMatch enum."""
        if score >= 0.9:
            return ContentMatch.EXCELLENT
        elif score >= 0.7:
            return ContentMatch.GOOD
        elif score >= 0.5:
            return ContentMatch.FAIR
        elif score >= 0.3:
            return ContentMatch.POOR
        else:
            return ContentMatch.NONE
    
    def _recommend_combination(
        self,
        rankings: list[SourceRanking],
        genres: list[str] | None,
        content_types: list[str] | None,
    ) -> list[SourceType]:
        """Recommend the best combination of sources."""
        combination = []
        
        # Always include best source
        if rankings:
            combination.append(rankings[0].source_type)
        
        # Add complementary sources
        for ranking in rankings[1:]:
            if ranking.score >= 0.5:
                # Check if it adds value
                if ranking.matching_genres and rankings[0].matching_genres:
                    new_genres = set(ranking.matching_genres) - set(rankings[0].matching_genres)
                    if new_genres:
                        combination.append(ranking.source_type)
                        continue
                
                # Add if different content type
                if ranking.source_type != rankings[0].source_type:
                    combination.append(ranking.source_type)
        
        # Limit to 3 sources
        return combination[:3]
    
    def _generate_coverage_notes(
        self,
        result: SourceSelectionResult,
        genres: list[str] | None,
        content_types: list[str] | None,
    ) -> list[str]:
        """Generate notes about source coverage."""
        notes = []
        
        if result.primary_source:
            notes.append(f"Primary source: {result.primary_source.source_name} "
                        f"({result.primary_source.match.value} match)")
        
        if result.total_content_available == 0:
            notes.append("Warning: No matching content found in any source")
        elif result.total_content_available < 10:
            notes.append("Limited content available - consider broader criteria")
        
        if result.secondary_sources:
            secondary_names = [s.source_name for s in result.secondary_sources]
            notes.append(f"Supplementary sources: {', '.join(secondary_names)}")
        
        return notes
