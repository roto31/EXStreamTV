"""
Concrete stream commands; require StreamService for context resolution.
"""

from __future__ import annotations

import asyncio
import logging

from exstreamtv.patterns.commands.base import StreamCommand
from exstreamtv.patterns.commands.command_queue import StreamCommandQueue
from exstreamtv.patterns.commands.config_types import TranscodeConfig
from exstreamtv.patterns.state import (
    BufferingState,
    IdleState,
    LiveState,
    StreamError,
)
from exstreamtv.services.stream_service import StreamService

logger = logging.getLogger(__name__)


class StartStreamCommand(StreamCommand):
    """Start a channel's stream via FSM."""

    def __init__(self, channel_id: str, stream_service: StreamService) -> None:
        super().__init__(channel_id)
        self._stream_service = stream_service
        self._command_queue: StreamCommandQueue | None = None

    def set_queue_for_undo(self, queue: StreamCommandQueue) -> None:
        self._command_queue = queue

    async def execute(self) -> bool:
        try:
            ctx = await self._stream_service.get_or_create_context(self.channel_id)
            await ctx.get_state().start(ctx)
            return True
        except StreamError as e:
            logger.warning("%s", e)
            return False
        except Exception as e:
            logger.error("StartStreamCommand: %s", e, exc_info=True)
            return False

    async def undo(self) -> None:
        if self._command_queue is None:
            return
        stop = StopStreamCommand(self.channel_id, self._stream_service)
        await self._command_queue.enqueue(stop)


class StopStreamCommand(StreamCommand):
    def __init__(self, channel_id: str, stream_service: StreamService) -> None:
        super().__init__(channel_id)
        self._stream_service = stream_service

    async def execute(self) -> bool:
        try:
            ctx = await self._stream_service.get_context(self.channel_id)
            if ctx is None:
                logger.debug("StopStreamCommand: no context for %s", self.channel_id)
                return True
            await ctx.get_state().stop(ctx)
            return True
        except Exception as e:
            logger.error("StopStreamCommand: %s", e, exc_info=True)
            return False


class RestartStreamCommand(StreamCommand):
    def __init__(self, channel_id: str, stream_service: StreamService) -> None:
        super().__init__(channel_id)
        self._stream_service = stream_service

    async def execute(self) -> bool:
        try:
            ctx = await self._stream_service.get_or_create_context(self.channel_id)
            await ctx.get_state().stop(ctx)
            await asyncio.sleep(5)
            await ctx.get_state().start(ctx)
            return True
        except StreamError as e:
            logger.warning("%s", e)
            return False
        except Exception as e:
            logger.error("RestartStreamCommand: %s", e, exc_info=True)
            return False


class ReloadSourceCommand(StreamCommand):
    """Soft-reload source URL when live (placeholder until URL held on context)."""

    def __init__(
        self,
        channel_id: str,
        stream_service: StreamService,
        new_url: str | None = None,
    ) -> None:
        super().__init__(channel_id)
        self._stream_service = stream_service
        self._new_url = new_url

    async def execute(self) -> bool:
        ctx = await self._stream_service.get_context(self.channel_id)
        if ctx is None:
            return False
        state = ctx.get_state()
        if isinstance(state, LiveState) and self._new_url:
            logger.info(
                "ReloadSourceCommand: would reload URL for %s (integration pending)",
                self.channel_id,
            )
        return True


class ForceRestartCommand(StreamCommand):
    """Operator escape from FailedState: reset to Idle then start."""

    def __init__(self, channel_id: str, stream_service: StreamService) -> None:
        super().__init__(channel_id)
        self._stream_service = stream_service

    async def execute(self) -> bool:
        try:
            ctx = await self._stream_service.get_or_create_context(self.channel_id)
            ctx.reset_health_failures()
            ctx.set_state(IdleState())
            await ctx.get_state().start(ctx)
            return True
        except Exception as e:
            logger.error("ForceRestartCommand: %s", e, exc_info=True)
            return False


class UpdateTranscodeConfigCommand(StreamCommand):
    def __init__(
        self,
        channel_id: str,
        stream_service: StreamService,
        new_config: TranscodeConfig,
    ) -> None:
        super().__init__(channel_id)
        self._stream_service = stream_service
        self.new_config = new_config

    async def execute(self) -> bool:
        ctx = await self._stream_service.get_or_create_context(self.channel_id)
        self._stream_service.set_transcode_config(self.channel_id, self.new_config)
        state = ctx.get_state()
        if isinstance(state, (LiveState, BufferingState)):
            await ctx.get_state().stop(ctx)
            await ctx.get_state().start(ctx)
        return True
