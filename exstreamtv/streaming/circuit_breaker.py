"""
Per-channel circuit breaker for EXStreamTV stability.

States: CLOSED, OPEN, HALF_OPEN.
Bounded failure count with rolling time window. No recursion.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Per-channel circuit breaker. Async-safe via asyncio.Lock.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: float = 300.0,
        cooldown_seconds: float = 120.0,
    ):
        self._failure_threshold = failure_threshold
        self._window_seconds = window_seconds
        self._cooldown_seconds = cooldown_seconds
        self._state: Dict[int, CircuitState] = {}
        self._failure_timestamps: Dict[int, list[float]] = {}
        self._open_until: Dict[int, float] = {}
        self._lock = asyncio.Lock()

    async def can_restart(self, channel_id: int) -> bool:
        """Return True if restart allowed. Fail-fast when OPEN."""
        async with self._lock:
            now = time.monotonic()
            self._prune_failures(channel_id, now)
            state = self._state.get(channel_id, CircuitState.CLOSED)

            if state == CircuitState.OPEN:
                if now < self._open_until.get(channel_id, 0):
                    return False
                self._state[channel_id] = CircuitState.HALF_OPEN
                return True

            if state == CircuitState.HALF_OPEN:
                return True

            # CLOSED
            fail_count = len(self._failure_timestamps.get(channel_id, []))
            if fail_count >= self._failure_threshold:
                self._state[channel_id] = CircuitState.OPEN
                self._open_until[channel_id] = now + self._cooldown_seconds
                logger.warning(
                    f"Circuit breaker OPEN for channel {channel_id} "
                    f"({fail_count} failures in {self._window_seconds}s)"
                )
                return False
            return True

    async def record_failure(self, channel_id: int) -> None:
        """Record a failure. Call after restart or acquire fails."""
        async with self._lock:
            now = time.monotonic()
            if channel_id not in self._failure_timestamps:
                self._failure_timestamps[channel_id] = []
            self._failure_timestamps[channel_id].append(now)
            self._prune_failures(channel_id, now)
            if self._state.get(channel_id) == CircuitState.HALF_OPEN:
                self._state[channel_id] = CircuitState.OPEN
                self._open_until[channel_id] = now + self._cooldown_seconds
                logger.warning(f"Circuit breaker OPEN for channel {channel_id} (half-open failed)")

    async def record_success(self, channel_id: int) -> None:
        """Record success. Resets to CLOSED from HALF_OPEN."""
        async with self._lock:
            if self._state.get(channel_id) == CircuitState.HALF_OPEN:
                self._state[channel_id] = CircuitState.CLOSED
                self._failure_timestamps.pop(channel_id, None)

    def _prune_failures(self, channel_id: int, now: float) -> None:
        cutoff = now - self._window_seconds
        if channel_id in self._failure_timestamps:
            self._failure_timestamps[channel_id] = [
                t for t in self._failure_timestamps[channel_id] if t > cutoff
            ]
            if not self._failure_timestamps[channel_id]:
                self._state[channel_id] = CircuitState.CLOSED

    async def get_state(self, channel_id: int) -> CircuitState:
        async with self._lock:
            now = time.monotonic()
            self._prune_failures(channel_id, now)
            if self._state.get(channel_id) == CircuitState.OPEN:
                if now >= self._open_until.get(channel_id, 0):
                    self._state[channel_id] = CircuitState.HALF_OPEN
            return self._state.get(channel_id, CircuitState.CLOSED)


# Global instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = CircuitBreaker()
    return _circuit_breaker
