"""
Async Cancellation Guard — Graceful shutdown hardening.

Eliminates unhandled asyncio.CancelledError propagation during shutdown.
Only these layers may catch CancelledError: AsyncCancellationGuard,
top-level stream loop, FastAPI shutdown handler.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncCancellationGuard:
    """
    Centralized handling of asyncio.CancelledError during shutdown.

    Use protect() to wrap coroutines that may be cancelled.
    Use safe_lock() for lock acquisition during shutdown.
    Use cancel_and_wait() for graceful task termination.
    """

    @staticmethod
    async def protect(
        coro: Awaitable[T],
        *,
        name: str = "task",
        suppress: bool = False,
    ) -> Optional[T]:
        """
        Execute coroutine, catching CancelledError cleanly.

        Args:
            coro: Coroutine to execute.
            name: Name for structured logging.
            suppress: If True, return None on cancellation. Else re-raise.

        Returns:
            Result of coro, or None if suppress=True and cancelled.
        """
        try:
            return await coro
        except asyncio.CancelledError:
            logger.info(
                "Cancelled during shutdown",
                extra={"task": name, "phase": "protect"},
            )
            if suppress:
                return None
            raise

    @staticmethod
    async def shielded(coro: Awaitable[T]) -> T:
        """
        Wrap in asyncio.shield for critical cleanup blocks.
        Use sparingly; shielded work continues even when parent is cancelled.
        """
        return await asyncio.shield(coro)

    @staticmethod
    async def cancel_and_wait(
        task: asyncio.Task[Any],
        *,
        timeout: float = 5.0,
        name: str = "task",
    ) -> None:
        """
        Cancel task and wait for completion. Suppresses CancelledError.

        Logs if task ignores cancellation (e.g. timeout).
        """
        if task.done():
            return
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.CancelledError:
            logger.debug(f"CancelledError suppressed for {name}")
        except asyncio.TimeoutError:
            logger.warning(
                f"Task did not respect cancellation within {timeout}s",
                extra={"task": name},
            )

    @staticmethod
    @asynccontextmanager
    async def safe_lock(
        lock: asyncio.Lock,
        *,
        name: str = "lock",
    ):
        """
        Async context manager for lock acquisition with shutdown-safe behavior.

        On CancelledError during wait: log once, re-raise cleanly.
        Avoids stack trace spam during shutdown.
        """
        acquired = False
        try:
            await lock.acquire()
            acquired = True
            yield
        except asyncio.CancelledError:
            logger.info(
                "Lock acquisition cancelled during shutdown",
                extra={"lock": name},
            )
            raise
        finally:
            if acquired:
                lock.release()
