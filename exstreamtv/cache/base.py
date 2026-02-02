"""
Cache backend interface and configuration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any, Optional, Dict, List, Set
import hashlib
import json


class CacheType(str, Enum):
    """Types of cacheable data."""
    EPG = "epg"
    M3U = "m3u"
    DASHBOARD = "dashboard"
    METADATA = "metadata"
    FFPROBE = "ffprobe"
    API_RESPONSE = "api"
    LIBRARY = "library"
    CHANNEL = "channel"
    PLAYLIST = "playlist"


@dataclass
class CacheConfig:
    """Cache configuration settings."""
    
    # Default TTLs for different cache types (in seconds)
    ttl_defaults: Dict[CacheType, int] = field(default_factory=lambda: {
        CacheType.EPG: 300,          # 5 minutes
        CacheType.M3U: 300,          # 5 minutes
        CacheType.DASHBOARD: 30,     # 30 seconds
        CacheType.METADATA: 3600,    # 1 hour
        CacheType.FFPROBE: 86400,    # 24 hours
        CacheType.API_RESPONSE: 60,  # 1 minute
        CacheType.LIBRARY: 600,      # 10 minutes
        CacheType.CHANNEL: 120,      # 2 minutes
        CacheType.PLAYLIST: 300,     # 5 minutes
    })
    
    # Maximum cache sizes (number of entries)
    max_entries: int = 10000
    
    # Maximum memory usage (bytes, 0 = unlimited)
    max_memory_bytes: int = 0
    
    # Whether to enable cache statistics
    enable_stats: bool = True
    
    # Redis configuration (if using Redis backend)
    redis_url: Optional[str] = None
    redis_prefix: str = "exstreamtv:"
    
    # Compression threshold (bytes, 0 = disabled)
    compression_threshold: int = 1024
    
    def get_ttl(self, cache_type: CacheType) -> int:
        """Get TTL for a cache type."""
        return self.ttl_defaults.get(cache_type, 60)


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    memory_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "hit_rate": round(self.hit_rate, 2),
            "memory_bytes": self.memory_bytes,
            "entry_count": self.entry_count,
        }


class CacheBackend(ABC):
    """Abstract cache backend interface."""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.stats = CacheStats()
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        cache_type: Optional[CacheType] = None,
    ) -> bool:
        """Set a value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass
    
    @abstractmethod
    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries matching pattern."""
        pass
    
    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        pass
    
    @abstractmethod
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set multiple values in cache."""
        pass
    
    @abstractmethod
    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple values from cache."""
        pass
    
    async def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: Optional[int] = None,
        cache_type: Optional[CacheType] = None,
    ) -> Any:
        """Get value from cache or compute and cache it."""
        value = await self.get(key)
        if value is not None:
            return value
        
        # Compute value
        if callable(factory):
            import asyncio
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
        else:
            value = factory
        
        await self.set(key, value, ttl=ttl, cache_type=cache_type)
        return value
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.stats
    
    async def invalidate_type(self, cache_type: CacheType) -> int:
        """Invalidate all entries of a specific type."""
        return await self.clear(f"{cache_type.value}:*")


def generate_cache_key(*args, **kwargs) -> str:
    """Generate a cache key from arguments."""
    key_parts = []
    
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        elif isinstance(arg, (list, tuple)):
            key_parts.append(",".join(str(x) for x in arg))
        elif isinstance(arg, dict):
            key_parts.append(json.dumps(arg, sort_keys=True))
        elif hasattr(arg, "__dict__"):
            key_parts.append(json.dumps(arg.__dict__, sort_keys=True, default=str))
        else:
            key_parts.append(str(arg))
    
    for key, value in sorted(kwargs.items()):
        if value is not None:
            key_parts.append(f"{key}={value}")
    
    key_string = ":".join(key_parts)
    
    # Hash long keys
    if len(key_string) > 200:
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]
    
    return key_string
