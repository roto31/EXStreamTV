from __future__ import annotations

import logging
from typing import Any

from exstreamtv.patterns.commands.command_queue import StreamCommandQueue
from exstreamtv.patterns.commands.stream_commands import (
    RestartStreamCommand,
    StopStreamCommand,
)
from exstreamtv.services.stream_service import StreamService

logger = logging.getLogger(__name__)


class StreamMediator:
    def __init__(
        self,
        command_queue: StreamCommandQueue,
        stream_service: StreamService,
    ) -> None:
        self._command_queue = command_queue
        self._stream_service = stream_service
        self._scheduler: Any = None
        self._health_checker: Any = None
        self._epg_updater: Any = None
        self._event_bus: Any = None

    def register(self, component_type: str, component: object) -> None:
        key = component_type.lower().replace("-", "_")
        if key == "scheduler":
            self._scheduler = component
        elif key in ("health_checker", "healthchecker"):
            self._health_checker = component
        elif key in ("epg_updater", "epgupdater"):
            self._epg_updater = component
        elif key in ("event_bus", "eventbus", "stream_event_bus"):
            self._event_bus = component
        else:
            logger.debug("StreamMediator.register: unknown type %s", component_type)

    async def notify(self, sender_type: str, event: str, payload: dict[str, Any]) -> None:
        logger.debug("Mediator: %s -> %s %s", sender_type, event, payload)

        if event == "stream_failed":
            channel_id = str(payload["channel_id"])
            failures = int(payload.get("consecutive_failures", 1))
            if failures <= 3:
                cmd = RestartStreamCommand(channel_id, self._stream_service)
                await self._command_queue.enqueue(cmd)
            else:
                cmd = StopStreamCommand(channel_id, self._stream_service)
                await self._command_queue.enqueue(cmd)
            if self._event_bus:
                await self._event_bus.emit("stream.failed", channel_id=channel_id)

        elif event == "stream_recovered":
            if self._event_bus:
                await self._event_bus.emit(
                    "stream.recovered", channel_id=payload.get("channel_id")
                )

        elif event == "schedule_changed":
            if self._epg_updater and hasattr(self._epg_updater, "invalidate_cache"):
                await self._epg_updater.invalidate_cache()
            if self._event_bus:
                await self._event_bus.emit("schedule.applied")

        elif event == "source_updated":
            if self._epg_updater and hasattr(self._epg_updater, "invalidate_cache"):
                await self._epg_updater.invalidate_cache()
            if self._event_bus:
                await self._event_bus.emit("source.updated")

        elif event == "channel_deleted":
            channel_id = str(payload["channel_id"])
            if self._health_checker and hasattr(self._health_checker, "unregister"):
                self._health_checker.unregister(channel_id)
            cmd = StopStreamCommand(channel_id, self._stream_service)
            await self._command_queue.enqueue(cmd)
            if self._event_bus:
                self._event_bus.unsubscribe_all(channel_id)
                await self._event_bus.emit("channel.deleted", channel_id=channel_id)

        elif event == "channel_created":
            if self._event_bus:
                await self._event_bus.emit(
                    "channel.created", channel_id=payload.get("channel_id")
                )

        elif event == "health_check_passed":
            if self._event_bus:
                await self._event_bus.emit(
                    "health.passed", channel_id=payload.get("channel_id")
                )

        elif event == "health_check_failed":
            if self._event_bus:
                await self._event_bus.emit(
                    "health.failed", channel_id=payload.get("channel_id")
                )

        elif event == "epg_updated":
            if self._event_bus:
                await self._event_bus.emit("epg.updated")
