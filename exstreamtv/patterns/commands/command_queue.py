"""
Single-consumer asyncio queue for stream commands (serializes start/stop/restart).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from exstreamtv.patterns.commands.base import StreamCommand

logger = logging.getLogger(__name__)


class StreamCommandQueue:
    """Serializes stream lifecycle commands through an asyncio.Queue."""

    def __init__(self, max_size: int = 200) -> None:
        self._queue: asyncio.Queue[StreamCommand] = asyncio.Queue(maxsize=max_size)
        self._processing: bool = False
        self._history: list[tuple[str, str, bool]] = []
        self._max_history: int = 100

    def _record_history(self, cmd: StreamCommand, success: bool) -> None:
        self._history.append((cmd.command_id, repr(cmd), success))
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history :]

    async def enqueue(self, cmd: StreamCommand) -> None:
        """Non-blocking enqueue. Raises asyncio.QueueFull if at capacity."""
        await self._queue.put(cmd)

    async def enqueue_wait(self, cmd: StreamCommand, timeout: float = 30.0) -> bool:
        """Enqueue and wait until the command finishes processing."""
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        cmd.attach_completion(fut)
        await self.enqueue(cmd)
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError:
            logger.error("Command %s timed out after %.1fs", cmd, timeout)
            return False

    async def process_forever(self) -> None:
        """Background task body: process commands until cancelled."""
        self._processing = True
        logger.info("StreamCommandQueue processor started")
        try:
            while True:
                cmd = await self._queue.get()
                logger.info("Executing %s", cmd)
                success = False
                try:
                    success = await cmd.execute()
                except Exception as e:
                    logger.error("Command %s failed: %s", cmd, e, exc_info=True)
                    success = False
                finally:
                    self._record_history(cmd, success)
                    cmd.complete(success)
                    self._queue.task_done()
        except asyncio.CancelledError:
            logger.info("StreamCommandQueue processor cancelled")
            raise

    def get_history(self) -> list[dict[str, Any]]:
        return [
            {"command_id": cid, "command": r, "success": s}
            for cid, r, s in self._history
        ]
