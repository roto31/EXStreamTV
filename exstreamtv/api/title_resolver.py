"""
TitleResolver for EPG programme titles.

Resolves programme titles from playout_item, media_item, and channel.
Raises TitleResolutionError if no valid title; no silent fallbacks that hide missing metadata.
"""

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TitleResolutionError(Exception):
    """Raised when no valid title can be resolved."""
    pass


class TitleResolver:
    """
    Resolves programme titles for EPG.

    Contract: resolve_title(playout_item, media_item, channel) -> str.
    Raises TitleResolutionError if no valid title.
    """

    def resolve_title(
        self,
        playout_item: dict[str, Any],
        media_item: Any,
        channel: Any,
    ) -> str:
        """
        Resolve programme title. Raises TitleResolutionError if empty.

        Args:
            playout_item: Dict with custom_title, etc.
            media_item: MediaItem or similar with title, files.
            channel: Channel with number, name.

        Returns:
            Non-empty title string.

        Raises:
            TitleResolutionError: If no valid title found.
        """
        # 1. Custom title from playout item
        custom = playout_item.get("custom_title")
        if custom and str(custom).strip():
            return str(custom).strip()

        # 2. Media item title
        if media_item and hasattr(media_item, "title") and media_item.title:
            t = str(media_item.title).strip()
            if t:
                return t

        # 3. Filename stem from media item path/url
        if media_item:
            path = None
            if hasattr(media_item, "path") and media_item.path:
                path = media_item.path
            elif hasattr(media_item, "url") and media_item.url:
                path = media_item.url
            elif hasattr(media_item, "files") and media_item.files and len(media_item.files) > 0:
                f = media_item.files[0]
                if hasattr(f, "path"):
                    path = f.path
            if path:
                stem = Path(path).stem
                if stem:
                    return stem

        raise TitleResolutionError(
            f"Missing title: playout_item={playout_item.get('custom_title')}, "
            f"media_item.title={getattr(media_item, 'title', None) if media_item else None}"
        )
