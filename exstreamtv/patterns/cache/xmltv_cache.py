from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)


class LazyXmltvCache:
    """TTL XMLTV body cache with optional per-request async builder."""

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self.ttl_seconds = float(ttl_seconds)
        self._cached: str | None = None
        self._loaded_at: datetime | None = None
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._loaded_at = None
        self._cached = None
        logger.debug("XMLTV cache invalidated")

    def _is_stale(self) -> bool:
        if self._cached is None or self._loaded_at is None:
            return True
        return datetime.now(tz=timezone.utc) - self._loaded_at > self._ttl

    async def peek_fresh(self) -> str | None:
        async with self._lock:
            if not self._is_stale() and self._cached is not None:
                return self._cached
            return None

    async def prime(self, xml_body: str) -> None:
        async with self._lock:
            self._cached = xml_body
            self._loaded_at = datetime.now(tz=timezone.utc)

    async def get_xml(self, builder: Callable[[], Awaitable[str]]) -> str:
        if not self._is_stale() and self._cached is not None:
            return self._cached
        async with self._lock:
            if not self._is_stale() and self._cached is not None:
                return self._cached
            logger.debug("XMLTV cache miss — rebuilding via builder")
            try:
                self._cached = await builder()
                self._loaded_at = datetime.now(tz=timezone.utc)
            except Exception as e:
                logger.error("LazyXmltvCache builder failed: %s", e, exc_info=True)
                if self._cached is not None:
                    return self._cached
                raise
            return self._cached
