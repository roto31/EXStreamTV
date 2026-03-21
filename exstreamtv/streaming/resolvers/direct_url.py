"""
Direct URL Resolver — Passthrough for generic HTTP/URL sources.

Used when source_type is UNKNOWN but a URL exists.
No transformation; validates URL is present.
"""

import logging
from typing import Any

from exstreamtv.streaming.resolvers.base import BaseResolver, ResolvedURL, ResolverError, SourceType

logger = logging.getLogger(__name__)


class DirectURLResolver(BaseResolver):
    """
    Passes through URL from media item. No API calls.
    For SourceType.UNKNOWN when URL is already available.
    """

    source_type = SourceType.UNKNOWN

    def _extract_url(self, media_item: Any) -> str | None:
        if hasattr(media_item, "url") and media_item.url:
            return str(media_item.url).strip()
        if hasattr(media_item, "path") and media_item.path:
            val = str(media_item.path).strip()
            if val.startswith("http://") or val.startswith("https://"):
                return val
            return val
        if isinstance(media_item, dict):
            u = media_item.get("url") or media_item.get("path")
            return str(u).strip() if u else None
        if isinstance(media_item, str):
            return media_item.strip()
        return None

    async def can_handle(self, media_item: Any) -> bool:
        return self._extract_url(media_item) is not None

    async def resolve(self, media_item: Any, force_refresh: bool = False) -> ResolvedURL:
        url = self._extract_url(media_item)
        if not url:
            raise ResolverError(
                "No URL in media item",
                source_type=SourceType.UNKNOWN,
                is_retryable=False,
            )
        return ResolvedURL(
            url=url,
            source_type=SourceType.UNKNOWN,
            media_id=getattr(media_item, "id", None) if not isinstance(media_item, dict) else media_item.get("id"),
        )
