"""
Mock API Responses

Pre-defined mock responses for external service testing.
"""

from .plex_responses import (
    PLEX_LIBRARY_SECTIONS,
    PLEX_MOVIES_RESPONSE,
    PLEX_SHOWS_RESPONSE,
    PLEX_METADATA_RESPONSE,
)
from .jellyfin_responses import (
    JELLYFIN_LIBRARIES,
    JELLYFIN_ITEMS,
)
from .tmdb_responses import (
    TMDB_MOVIE_SEARCH,
    TMDB_TV_SEARCH,
    TMDB_MOVIE_DETAILS,
)

__all__ = [
    "PLEX_LIBRARY_SECTIONS",
    "PLEX_MOVIES_RESPONSE",
    "PLEX_SHOWS_RESPONSE",
    "PLEX_METADATA_RESPONSE",
    "JELLYFIN_LIBRARIES",
    "JELLYFIN_ITEMS",
    "TMDB_MOVIE_SEARCH",
    "TMDB_TV_SEARCH",
    "TMDB_MOVIE_DETAILS",
]
