"""
EXStreamTV Caching Layer

Provides high-performance caching for:
- API responses
- EPG/M3U generation
- Metadata lookups
- FFprobe results
- Dashboard statistics
"""

from exstreamtv.cache.base import CacheBackend, CacheConfig
from exstreamtv.cache.memory import MemoryCache
from exstreamtv.cache.manager import CacheManager, cache_manager
from exstreamtv.cache.decorators import cached, cache_key

__all__ = [
    "CacheBackend",
    "CacheConfig",
    "MemoryCache",
    "CacheManager",
    "cache_manager",
    "cached",
    "cache_key",
]
