"""
Stream lifecycle state machine (GoF State pattern).

Invalid transitions are logged and ignored; FailedState.start raises StreamError.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class StreamError(RuntimeError):
    """Raised when a stream operation is invalid for the current state (e.g. start in Failed)."""


class StreamState(ABC):
    """Abstract stream state."""

    @abstractmethod
    async def start(self, ctx: "ChannelContext") -> None:
        ...

    @abstractmethod
    async def stop(self, ctx: "ChannelContext") -> None:
        ...

    @abstractmethod
    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        ...

    @abstractmethod
    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        ...

    @abstractmethod
    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        ...

    @abstractmethod
    def __str__(self) -> str:
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """True if FFmpeg / continuous stream should be considered active."""
        ...


class IdleState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        ctx.set_state(StartingState())
        await ctx.spawn_ffmpeg()

    async def stop(self, ctx: "ChannelContext") -> None:
        pass

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        pass

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        pass

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        pass

    def __str__(self) -> str:
        return "IdleState"

    def is_running(self) -> bool:
        return False


class StartingState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        logger.warning(
            "channel_id=%s: already starting, ignoring duplicate start",
            ctx.channel_id,
        )

    async def stop(self, ctx: "ChannelContext") -> None:
        ctx.set_state(StoppingState())
        await ctx.kill_ffmpeg()

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        ctx.reset_health_failures()
        ctx.set_state(LiveState())

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        ctx.set_state(FailedState())

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        if return_code != 0:
            ctx.set_state(FailedState())
        else:
            ctx.set_state(IdleState())

    def __str__(self) -> str:
        return "StartingState"

    def is_running(self) -> bool:
        return True


class LiveState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        logger.warning(
            "channel_id=%s: already live, ignoring start (prevents double-spawn)",
            ctx.channel_id,
        )

    async def stop(self, ctx: "ChannelContext") -> None:
        ctx.set_state(StoppingState())
        await ctx.kill_ffmpeg()

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        ctx.reset_health_failures()

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        ctx.set_state(BufferingState())

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        if return_code != 0:
            ctx.set_state(FailedState())
        else:
            ctx.set_state(RestartingState())

    def __str__(self) -> str:
        return "LiveState"

    def is_running(self) -> bool:
        return True


class BufferingState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        logger.warning(
            "channel_id=%s: buffering, not double-spawning",
            ctx.channel_id,
        )

    async def stop(self, ctx: "ChannelContext") -> None:
        ctx.set_state(StoppingState())
        await ctx.kill_ffmpeg()

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        ctx.reset_health_failures()
        ctx.set_state(LiveState())

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        ctx.increment_health_failures()
        if ctx.consecutive_health_failures >= 3:
            ctx.set_state(FailedState())

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        ctx.set_state(FailedState())

    def __str__(self) -> str:
        return "BufferingState"

    def is_running(self) -> bool:
        return True


class FailedState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        raise StreamError(
            f"channel_id={ctx.channel_id}: manual intervention required (FailedState)"
        )

    async def stop(self, ctx: "ChannelContext") -> None:
        pass

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        pass

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        pass

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        pass

    def __str__(self) -> str:
        return "FailedState"

    def is_running(self) -> bool:
        return False


class RestartingState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        logger.warning(
            "channel_id=%s: restart in progress, ignoring start",
            ctx.channel_id,
        )

    async def stop(self, ctx: "ChannelContext") -> None:
        ctx.set_state(StoppingState())
        await ctx.kill_ffmpeg()

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        ctx.reset_health_failures()
        ctx.set_state(LiveState())

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        ctx.set_state(FailedState())

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        if return_code != 0:
            ctx.set_state(FailedState())

    def __str__(self) -> str:
        return "RestartingState"

    def is_running(self) -> bool:
        return True


class StoppingState(StreamState):
    async def start(self, ctx: "ChannelContext") -> None:
        logger.warning(
            "channel_id=%s: stopping in progress, ignoring start",
            ctx.channel_id,
        )

    async def stop(self, ctx: "ChannelContext") -> None:
        pass

    async def on_health_check_passed(self, ctx: "ChannelContext") -> None:
        pass

    async def on_health_check_failed(self, ctx: "ChannelContext") -> None:
        pass

    async def on_ffmpeg_exited(self, ctx: "ChannelContext", return_code: int) -> None:
        ctx.set_state(IdleState())

    def __str__(self) -> str:
        return "StoppingState"

    def is_running(self) -> bool:
        return True
