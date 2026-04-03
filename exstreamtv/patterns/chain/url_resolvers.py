"""
Chain of Responsibility for raw URL strings (complements MediaURLResolver on items).
"""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class URLResolver(ABC):
    def __init__(self, next_resolver: URLResolver | None = None) -> None:
        self._next = next_resolver
        self._name = self.__class__.__name__

    @abstractmethod
    async def resolve(self, url: str) -> str | None:
        """Return resolved URL or None to pass."""

    async def resolve_or_pass(self, url: str) -> str | None:
        try:
            result = await self.resolve(url)
        except Exception as e:
            logger.warning("%s.resolve error: %s", self._name, e, exc_info=True)
            result = None
        if result is not None:
            logger.debug("%s: resolved %s...", self._name, url[:50])
            return result
        if self._next is not None:
            return await self._next.resolve_or_pass(url)
        logger.warning("No resolver handled URL: %s", url[:80])
        return None


class DirectHLSResolver(URLResolver):
    DIRECT_EXTENSIONS = frozenset({".m3u8", ".ts", ".mp4", ".mkv", ".avi"})

    async def resolve(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https", "rtmp", "rtsp", "udp"):
            return None
        if "archive.org/details/" in url.lower():
            return None
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in self.DIRECT_EXTENSIONS):
            return url
        if parsed.scheme in ("http", "https"):
            return url
        return None


class StreamlinkResolver(URLResolver):
    def __init__(
        self,
        session: Any,
        quality: str = "best",
        next_resolver: URLResolver | None = None,
    ) -> None:
        super().__init__(next_resolver)
        self._session = session
        self._quality = quality

    async def resolve(self, url: str) -> str | None:
        try:
            from streamlink import NoPluginError
        except ImportError:
            return None

        loop = asyncio.get_event_loop()

        def _streams() -> Any:
            return self._session.streams(url)

        try:
            streams = await loop.run_in_executor(None, _streams)
        except NoPluginError:
            return None
        except Exception as e:
            logger.warning("StreamlinkResolver error for %s: %s", url[:60], e)
            return None
        stream = streams.get(self._quality) or streams.get("best")
        if stream is None:
            return None
        return getattr(stream, "url", None)


class ArchiveOrgResolver(URLResolver):
    METADATA_API = "https://archive.org/metadata/{identifier}"
    VIDEO_FORMATS = frozenset({"h.264", "mpeg4", "512kb mpeg4", "ogg video"})

    async def resolve(self, url: str) -> str | None:
        if "archive.org/details/" not in url:
            return None
        match = re.search(r"/details/([^/?&#]+)", url)
        if not match:
            return None
        identifier = match.group(1)
        meta_url = self.METADATA_API.format(identifier=identifier)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(meta_url)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning("ArchiveOrgResolver metadata failed: %s", e)
            return None
        files = data.get("files") or []
        for f in files:
            name = (f.get("name") or "").lower()
            fmt = (f.get("format") or "").lower()
            if not name.endswith((".mp4", ".ogv", ".mpeg", ".mpg")):
                continue
            if fmt and fmt not in self.VIDEO_FORMATS and "h.264" not in fmt:
                continue
            return f"https://archive.org/download/{identifier}/{f.get('name')}"
        return None


def build_default_url_resolver_chain(streamlink_session: Any | None = None) -> URLResolver:
    """Direct URLs first, then Streamlink (optional), then archive.org metadata."""
    archive_tail = ArchiveOrgResolver()
    if streamlink_session is not None:
        after_direct = StreamlinkResolver(
            streamlink_session, next_resolver=archive_tail
        )
    else:
        after_direct = archive_tail
    return DirectHLSResolver(next_resolver=after_direct)
