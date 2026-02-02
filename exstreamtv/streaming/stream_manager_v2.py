"""
Stream Manager v2 Compatibility Module

This module provides backward compatibility for v2 modules that import
from stream_manager_v2. It provides basic stream management functionality.
"""

from typing import Any, Dict, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class StreamManager:
    """
    Stream manager for handling media streams.
    
    This is a compatibility stub that provides basic functionality
    for v2 modules that depend on stream_manager_v2.
    """
    
    def __init__(self):
        self._streams: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def get_stream(self, stream_id: str) -> Optional[Any]:
        """Get a stream by ID."""
        async with self._lock:
            return self._streams.get(stream_id)
    
    async def register_stream(self, stream_id: str, stream: Any) -> None:
        """Register a stream."""
        async with self._lock:
            self._streams[stream_id] = stream
            logger.info(f"Registered stream: {stream_id}")
    
    async def unregister_stream(self, stream_id: str) -> None:
        """Unregister a stream."""
        async with self._lock:
            if stream_id in self._streams:
                del self._streams[stream_id]
                logger.info(f"Unregistered stream: {stream_id}")
    
    def get_active_streams(self) -> Dict[str, Any]:
        """Get all active streams."""
        return dict(self._streams)
    
    @property
    def stream_count(self) -> int:
        """Get count of active streams."""
        return len(self._streams)


# Global instance
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get the global stream manager instance."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager


# Aliases
StreamManagerV2 = StreamManager

__all__ = [
    "StreamManager",
    "StreamManagerV2",
    "get_stream_manager",
]
