"""
Plex library service using Python-PlexAPI when available.

Use for: server connection, library/section listing, metadata for "what's in the library".
DVR and Live TV (guide reload, tuners) stay on direct Plex PMS API via streaming.plex_api_client.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_PLEXAPI_AVAILABLE = False
try:
    from plexapi.server import PlexServer

    _PLEXAPI_AVAILABLE = True
except ImportError:
    pass


def is_plexapi_available() -> bool:
    """Return True if Python-PlexAPI is installed."""
    return _PLEXAPI_AVAILABLE


def get_plex_server(base_url: str, token: str) -> Any:
    """
    Connect to Plex Media Server using Python-PlexAPI.

    Args:
        base_url: Plex server base URL (e.g. http://192.168.1.1:32400).
        token: Plex authentication token.

    Returns:
        PlexServer instance from plexapi, or None if plexapi not available or connection fails.
    """
    if not _PLEXAPI_AVAILABLE:
        logger.debug("Python-PlexAPI not installed; Plex library service limited")
        return None
    try:
        return PlexServer(base_url.rstrip("/"), token)
    except Exception as e:
        logger.warning("Plex server connection failed: %s", e)
        return None


def list_sections(server: Any) -> list[dict[str, Any]]:
    """
    List library sections using PlexAPI.

    Args:
        server: PlexServer instance from get_plex_server().

    Returns:
        List of dicts with key, type, title for each section.
    """
    if server is None:
        return []
    try:
        return [
            {"key": s.key, "type": s.type, "title": s.title}
            for s in server.library.sections()
        ]
    except Exception as e:
        logger.warning("List Plex sections failed: %s", e)
        return []


def get_section_items(
    server: Any, section_key: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """
    Get items from a library section using PlexAPI.

    Args:
        server: PlexServer instance from get_plex_server().
        section_key: Section key (e.g. "1", "2").
        limit: Optional max number of items.

    Returns:
        List of item dicts with ratingKey, title, type, duration, summary, etc.
    """
    if server is None:
        return []
    try:
        section = server.library.sectionByID(section_key)
        items = section.all(maxresults=limit) if limit else section.all()
        out = []
        for item in items:
            d = {
                "ratingKey": getattr(item, "ratingKey", None),
                "title": getattr(item, "title", ""),
                "type": type(item).__name__.lower(),
            }
            if hasattr(item, "duration") and item.duration:
                d["duration"] = item.duration
            if hasattr(item, "summary") and item.summary:
                d["summary"] = item.summary
            if hasattr(item, "guid") and item.guid:
                d["guid"] = item.guid
            out.append(d)
        return out
    except Exception as e:
        logger.warning("Get Plex section items failed: %s", e)
        return []
