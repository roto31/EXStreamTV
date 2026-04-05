"""
Chain of Responsibility for media source-type detection.

Replaces the monolithic ``_detect_source_type`` if/elif cascade in
``url_resolver.py`` with a composable chain of detectors.  Each detector
checks one heuristic and either returns a ``SourceType`` or defers to the
next link.

Decision-tree path (from design-pattern-decision-tree):
    Behaviour → accumulating conditionals per source type
    → each conditional is an independent detection strategy
    → Chain of Responsibility (ordered, first-match wins)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from exstreamtv.streaming.resolvers.base import SourceType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract handler
# ---------------------------------------------------------------------------

class SourceTypeDetector(ABC):
    """One link in the detection chain."""

    def __init__(self) -> None:
        self._next: SourceTypeDetector | None = None

    def set_next(self, handler: SourceTypeDetector) -> SourceTypeDetector:
        """Set the next handler in the chain. Returns *handler* for chaining."""
        self._next = handler
        return handler

    def detect(self, media_item: Any) -> SourceType:
        """Try to detect; delegate to the next handler on failure."""
        result = self._try_detect(media_item)
        if result is not None:
            return result
        if self._next is not None:
            return self._next.detect(media_item)
        return SourceType.UNKNOWN

    @abstractmethod
    def _try_detect(self, media_item: Any) -> SourceType | None:
        """Return a ``SourceType`` if this detector matches, else ``None``."""


# ---------------------------------------------------------------------------
# Helpers shared by several detectors
# ---------------------------------------------------------------------------

def _get_attr_or_key(obj: Any, *names: str) -> Any:
    """Return the first truthy attribute or dict-key found, else ``None``."""
    for name in names:
        if hasattr(obj, name):
            val = getattr(obj, name, None)
            if val:
                return val
        if isinstance(obj, dict):
            val = obj.get(name)
            if val:
                return val
    return None


# ---------------------------------------------------------------------------
# Concrete detectors (order matters – inserted into the chain by priority)
# ---------------------------------------------------------------------------

class PlexRatingKeyDetector(SourceTypeDetector):
    """Highest-priority: explicit Plex rating key on the item."""

    def _try_detect(self, media_item: Any) -> SourceType | None:
        if _get_attr_or_key(media_item, "plex_rating_key"):
            return SourceType.PLEX
        return None


class ExplicitSourceDetector(SourceTypeDetector):
    """Match an explicit ``source`` / ``source_type`` attribute by keyword."""

    _KEYWORDS: dict[str, SourceType] = {
        "youtube": SourceType.YOUTUBE,
        "plex": SourceType.PLEX,
        "jellyfin": SourceType.JELLYFIN,
        "emby": SourceType.EMBY,
        "archive": SourceType.ARCHIVE_ORG,
        "local": SourceType.LOCAL,
        "file": SourceType.LOCAL,
        "m3u": SourceType.M3U,
    }

    def _try_detect(self, media_item: Any) -> SourceType | None:
        source = _get_attr_or_key(media_item, "source", "source_type")
        if not source:
            return None
        source_lower = str(source).lower()
        for keyword, source_type in self._KEYWORDS.items():
            if keyword in source_lower:
                return source_type
        return None


class ArchiveOrgFieldDetector(SourceTypeDetector):
    """Detect Archive.org from dedicated metadata fields."""

    _FIELDS = (
        "archive_org_identifier",
        "archive_org_collection",
        "archive_org_creator",
        "archive_org_filename",
        "archive_org_subject",
    )

    def _try_detect(self, media_item: Any) -> SourceType | None:
        for field in self._FIELDS:
            if _get_attr_or_key(media_item, field):
                logger.debug("Detected Archive.org source from field: %s", field)
                return SourceType.ARCHIVE_ORG
        return None


class RawMetadataArchiveDetector(SourceTypeDetector):
    """Detect Archive.org from ``raw_metadata`` / ``meta_data`` JSON."""

    def _try_detect(self, media_item: Any) -> SourceType | None:
        raw = _get_attr_or_key(media_item, "raw_metadata", "meta_data")
        if not raw:
            return None
        try:
            meta = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError, AttributeError):
            return None
        if meta.get("identifier") or meta.get("archive_org_id"):
            logger.debug("Detected Archive.org source from raw_metadata identifier")
            return SourceType.ARCHIVE_ORG
        collection = str(meta.get("collection", "")).lower()
        if meta.get("collection") and "archive" in collection:
            logger.debug("Detected Archive.org source from raw_metadata collection")
            return SourceType.ARCHIVE_ORG
        return None


class URLPatternDetector(SourceTypeDetector):
    """Detect source type from the URL string itself."""

    def _try_detect(self, media_item: Any) -> SourceType | None:
        url = _get_attr_or_key(media_item, "url", "path")
        if not url:
            return None
        url_lower = str(url).lower()
        if "youtube.com" in url_lower or "youtu.be" in url_lower or "googlevideo.com" in url_lower:
            return SourceType.YOUTUBE
        if "archive.org" in url_lower:
            return SourceType.ARCHIVE_ORG
        if url_lower.startswith("/") or url_lower.startswith("file://"):
            return SourceType.LOCAL
        if "/library/metadata/" in url_lower:
            return SourceType.PLEX
        if ":8096" in url_lower or "jellyfin" in url_lower:
            return SourceType.JELLYFIN
        return None


# ---------------------------------------------------------------------------
# Chain builder (canonical order)
# ---------------------------------------------------------------------------

def build_source_type_detection_chain() -> SourceTypeDetector:
    """Build the default detection chain in priority order.

    Priority:
        1. Plex rating-key (most specific, avoids false-positive on other fields)
        2. Explicit source/source_type attribute
        3. Archive.org dedicated fields
        4. Archive.org identifiers in raw_metadata JSON
        5. URL pattern matching (least specific)

    Returns the *head* of the chain.
    """
    head = PlexRatingKeyDetector()
    link = head
    for detector_cls in (
        ExplicitSourceDetector,
        ArchiveOrgFieldDetector,
        RawMetadataArchiveDetector,
        URLPatternDetector,
    ):
        link = link.set_next(detector_cls())
    return head
