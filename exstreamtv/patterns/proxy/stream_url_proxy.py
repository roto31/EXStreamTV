from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from exstreamtv.patterns.chain.url_resolvers import URLResolver

logger = logging.getLogger(__name__)


class StreamUrlProxy:
    """Lazy-resolving URL with TTL; use async get_url() (not a property)."""

    def __init__(
        self,
        raw_url: str,
        resolver: URLResolver,
        ttl_minutes: int = 10,
    ) -> None:
        self._raw_url = raw_url
        self._resolver = resolver
        self._resolved: str | None = None
        self._resolved_at: datetime | None = None
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = asyncio.Lock()

    async def get_url(self) -> str:
        async with self._lock:
            if self._needs_refresh():
                new_url = await self._resolver.resolve_or_pass(self._raw_url)
                if new_url:
                    self._resolved = new_url
                    self._resolved_at = datetime.now(tz=timezone.utc)
                    logger.debug("Proxy refreshed URL for %s...", self._raw_url[:50])
                else:
                    logger.warning(
                        "Proxy refresh failed for %s..., using last known",
                        self._raw_url[:50],
                    )
            return self._resolved or self._raw_url

    async def force_refresh(self) -> str:
        async with self._lock:
            self._resolved = None
            self._resolved_at = None
        return await self.get_url()

    def _needs_refresh(self) -> bool:
        if self._resolved is None or self._resolved_at is None:
            return True
        return datetime.now(tz=timezone.utc) - self._resolved_at > self._ttl

    def invalidate(self) -> None:
        self._resolved_at = None
