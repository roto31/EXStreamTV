"""
Command pattern base for serialized stream lifecycle operations.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from uuid import uuid4


class StreamCommand(ABC):
    """Abstract stream command executed by StreamCommandQueue."""

    def __init__(self, channel_id: str) -> None:
        self.command_id: str = str(uuid4())
        self.created_at: datetime = datetime.now(tz=timezone.utc)
        self.channel_id: str = channel_id
        self._completion_future: asyncio.Future[bool] | None = None

    def attach_completion(self, fut: asyncio.Future[bool]) -> None:
        self._completion_future = fut

    def complete(self, success: bool) -> None:
        if self._completion_future is not None and not self._completion_future.done():
            self._completion_future.set_result(success)

    @abstractmethod
    async def execute(self) -> bool:
        """Return True on success, False on handled failure."""

    async def undo(self) -> None:
        """Optional reversal; default no-op."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(channel={self.channel_id}, id={self.command_id[:8]})"
