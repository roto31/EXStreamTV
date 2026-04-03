"""
Host for per-channel stream FSM; delegates spawn/kill to ChannelManager.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from exstreamtv.patterns.state.stream_states import (
    BufferingState,
    FailedState,
    IdleState,
    LiveState,
    RestartingState,
    StartingState,
    StoppingState,
    StreamState,
)

if TYPE_CHECKING:
    from exstreamtv.streaming.channel_manager import ChannelManager

logger = logging.getLogger(__name__)


class ChannelContext:
    """One FSM instance per logical channel (keyed by string id)."""

    def __init__(
        self,
        channel_id: str,
        channel_db_id: int,
        channel_number: int | str,
        channel_name: str,
        channel_manager: ChannelManager,
    ) -> None:
        self.channel_id = channel_id
        self.channel_db_id = channel_db_id
        self.channel_number = channel_number
        self.channel_name = channel_name
        self._channel_manager = channel_manager
        self._state: StreamState = IdleState()
        self._ffmpeg_process: Any | None = None
        self._consecutive_health_failures = 0

    def set_state(self, state: StreamState) -> None:
        logger.debug(
            "channel_id=%s: state %s -> %s",
            self.channel_id,
            self._state,
            state,
        )
        self._state = state

    def get_state(self) -> StreamState:
        return self._state

    def reset_health_failures(self) -> None:
        self._consecutive_health_failures = 0

    def increment_health_failures(self) -> None:
        self._consecutive_health_failures += 1

    @property
    def consecutive_health_failures(self) -> int:
        return self._consecutive_health_failures

    async def spawn_ffmpeg(self) -> None:
        """Start continuous stream via ChannelManager."""
        stream = await self._channel_manager.start_channel(
            self.channel_db_id,
            self.channel_number,
            self.channel_name,
        )
        self._ffmpeg_process = getattr(stream, "_stream_task", None)

    async def kill_ffmpeg(self) -> None:
        """Stop continuous stream; completes StoppingState -> Idle when applicable."""
        try:
            stream = await self._channel_manager.get_channel_stream(
                self.channel_db_id,
                self.channel_number,
                self.channel_name,
            )
            await stream.stop()
        except Exception as e:
            logger.error(
                "channel_id=%s: kill_ffmpeg failed: %s",
                self.channel_id,
                e,
                exc_info=True,
            )
        finally:
            self._ffmpeg_process = None
            if isinstance(self._state, StoppingState):
                self.set_state(IdleState())

    def sync_state_from_stream_running(self, is_running: bool) -> None:
        """
        Best-effort align FSM with ChannelStream._is_running when no explicit transition ran.
        Does not override FailedState or transient states.
        """
        if isinstance(
            self._state,
            (FailedState, StartingState, StoppingState, RestartingState),
        ):
            return
        if is_running and isinstance(self._state, IdleState):
            self.set_state(LiveState())
        if not is_running and isinstance(
            self._state, (LiveState, BufferingState, RestartingState)
        ):
            self.set_state(IdleState())
