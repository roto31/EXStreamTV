"""
Core utilities: async cancellation guard, subprocess safety, shutdown state.
"""

from exstreamtv.core.async_guard import AsyncCancellationGuard
from exstreamtv.core.shutdown_state import is_shutting_down, set_shutting_down
from exstreamtv.core.subprocess_safe import SafeAsyncSubprocess

__all__ = [
    "AsyncCancellationGuard",
    "SafeAsyncSubprocess",
    "is_shutting_down",
    "set_shutting_down",
]
