from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


class StreamEventBus:
    VALID_EVENTS = frozenset(
        {
            "stream.started",
            "stream.stopped",
            "stream.failed",
            "stream.recovered",
            "channel.created",
            "channel.updated",
            "channel.deleted",
            "source.updated",
            "epg.updated",
            "schedule.applied",
            "health.passed",
            "health.failed",
        }
    )

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[..., Awaitable[None]]]] = defaultdict(
            list
        )

    def subscribe(self, event: str, callback: Callable[..., Awaitable[None]]) -> None:
        if event not in self.VALID_EVENTS:
            raise ValueError(f"Unknown event: {event!r}")
        self._listeners[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable[..., Awaitable[None]]) -> None:
        self._listeners[event] = [cb for cb in self._listeners[event] if cb is not callback]

    def unsubscribe_all(self, channel_id: str) -> None:
        for event in list(self.VALID_EVENTS):
            self._listeners[event] = [
                cb
                for cb in self._listeners[event]
                if getattr(cb, "_channel_id", None) != channel_id
            ]

    async def emit(self, event: str, **kwargs: Any) -> None:
        listeners_snapshot = list(self._listeners.get(event, []))
        for callback in listeners_snapshot:
            try:
                await callback(**kwargs)
            except Exception as e:
                logger.error(
                    "EventBus callback %r failed on event %r: %s",
                    getattr(callback, "__qualname__", callback),
                    event,
                    e,
                    exc_info=True,
                )

    async def emit_background(self, event: str, **kwargs: Any) -> None:
        listeners_snapshot = list(self._listeners.get(event, []))
        for callback in listeners_snapshot:
            asyncio.create_task(self._safe_call(callback, event, kwargs))

    @staticmethod
    async def _safe_call(
        callback: Callable[..., Awaitable[None]], event: str, kwargs: dict[str, Any]
    ) -> None:
        try:
            await callback(**kwargs)
        except Exception as e:
            logger.error(
                "Background callback %r failed on %r: %s",
                getattr(callback, "__qualname__", callback),
                event,
                e,
                exc_info=True,
            )
