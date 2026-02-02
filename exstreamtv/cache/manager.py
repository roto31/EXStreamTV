"""
Cache manager - central access point for caching operations.
"""

import asyncio
from typing import Any, Dict, List, Optional, Type

from exstreamtv.cache.base import CacheBackend, CacheConfig, CacheType, CacheStats
from exstreamtv.cache.memory import MemoryCache


class CacheManager:
    """
    Central cache manager that provides a unified interface to caching.
    
    Supports multiple backends (memory, Redis) and provides:
    - Automatic backend selection
    - Fallback to memory cache if Redis unavailable
    - Type-aware caching with appropriate TTLs
    - Cache invalidation by type
    - Statistics aggregation
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self._backend: Optional[CacheBackend] = None
        self._fallback: Optional[MemoryCache] = None
        self._initialized = False
    
    async def initialize(self, use_redis: bool = False) -> None:
        """Initialize the cache manager."""
        if self._initialized:
            return
        
        # Always create memory cache as fallback
        self._fallback = MemoryCache(self.config)
        await self._fallback.start()
        
        if use_redis and self.config.redis_url:
            try:
                from exstreamtv.cache.redis_cache import RedisCache
                redis_cache = RedisCache(self.config)
                if await redis_cache.connect():
                    self._backend = redis_cache
                else:
                    self._backend = self._fallback
            except ImportError:
                self._backend = self._fallback
        else:
            self._backend = self._fallback
        
        self._initialized = True
    
    async def shutdown(self) -> None:
        """Shutdown the cache manager."""
        if self._fallback:
            await self._fallback.stop()
        
        if self._backend and self._backend != self._fallback:
            if hasattr(self._backend, "disconnect"):
                await self._backend.disconnect()
        
        self._initialized = False
    
    @property
    def backend(self) -> CacheBackend:
        """Get the current cache backend."""
        if not self._initialized or self._backend is None:
            raise RuntimeError("Cache manager not initialized. Call initialize() first.")
        return self._backend
    
    @property
    def is_redis(self) -> bool:
        """Check if using Redis backend."""
        from exstreamtv.cache.redis_cache import RedisCache
        return isinstance(self._backend, RedisCache)
    
    # Convenience methods that delegate to backend
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        return await self.backend.get(key)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        cache_type: Optional[CacheType] = None,
    ) -> bool:
        """Set a value in cache."""
        return await self.backend.set(key, value, ttl=ttl, cache_type=cache_type)
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        return await self.backend.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        return await self.backend.exists(key)
    
    async def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: Optional[int] = None,
        cache_type: Optional[CacheType] = None,
    ) -> Any:
        """Get value from cache or compute and cache it."""
        return await self.backend.get_or_set(key, factory, ttl=ttl, cache_type=cache_type)
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries matching pattern."""
        return await self.backend.clear(pattern)
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        return await self.backend.get_many(keys)
    
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set multiple values in cache."""
        return await self.backend.set_many(items, ttl=ttl)
    
    # Type-specific cache methods
    
    async def cache_epg(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """Cache EPG data."""
        return await self.set(
            f"epg:{key}",
            data,
            ttl=ttl,
            cache_type=CacheType.EPG,
        )
    
    async def get_epg(self, key: str) -> Optional[Any]:
        """Get cached EPG data."""
        return await self.get(f"epg:{key}")
    
    async def cache_m3u(self, key: str, data: str, ttl: Optional[int] = None) -> bool:
        """Cache M3U playlist data."""
        return await self.set(
            f"m3u:{key}",
            data,
            ttl=ttl,
            cache_type=CacheType.M3U,
        )
    
    async def get_m3u(self, key: str) -> Optional[str]:
        """Get cached M3U playlist."""
        return await self.get(f"m3u:{key}")
    
    async def cache_dashboard(self, key: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """Cache dashboard statistics."""
        return await self.set(
            f"dashboard:{key}",
            data,
            ttl=ttl,
            cache_type=CacheType.DASHBOARD,
        )
    
    async def get_dashboard(self, key: str) -> Optional[Dict]:
        """Get cached dashboard data."""
        return await self.get(f"dashboard:{key}")
    
    async def cache_metadata(
        self,
        provider: str,
        item_id: str,
        data: Dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache metadata lookup result."""
        return await self.set(
            f"metadata:{provider}:{item_id}",
            data,
            ttl=ttl,
            cache_type=CacheType.METADATA,
        )
    
    async def get_metadata(self, provider: str, item_id: str) -> Optional[Dict]:
        """Get cached metadata."""
        return await self.get(f"metadata:{provider}:{item_id}")
    
    async def cache_ffprobe(self, file_path: str, data: Dict, ttl: Optional[int] = None) -> bool:
        """Cache FFprobe analysis result."""
        import hashlib
        path_hash = hashlib.sha256(file_path.encode()).hexdigest()[:16]
        return await self.set(
            f"ffprobe:{path_hash}",
            data,
            ttl=ttl,
            cache_type=CacheType.FFPROBE,
        )
    
    async def get_ffprobe(self, file_path: str) -> Optional[Dict]:
        """Get cached FFprobe result."""
        import hashlib
        path_hash = hashlib.sha256(file_path.encode()).hexdigest()[:16]
        return await self.get(f"ffprobe:{path_hash}")
    
    # Invalidation methods
    
    async def invalidate_epg(self) -> int:
        """Invalidate all EPG cache entries."""
        return await self.clear("epg:*")
    
    async def invalidate_m3u(self) -> int:
        """Invalidate all M3U cache entries."""
        return await self.clear("m3u:*")
    
    async def invalidate_dashboard(self) -> int:
        """Invalidate all dashboard cache entries."""
        return await self.clear("dashboard:*")
    
    async def invalidate_channel(self, channel_id: int) -> int:
        """Invalidate cache entries for a specific channel."""
        return await self.clear(f"*channel:{channel_id}*")
    
    async def invalidate_library(self, library_id: int) -> int:
        """Invalidate cache entries for a specific library."""
        return await self.clear(f"*library:{library_id}*")
    
    # Statistics
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self.backend.get_stats()
    
    async def get_detailed_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics."""
        stats = self.get_stats().to_dict()
        stats["backend"] = "redis" if self.is_redis else "memory"
        
        if self.is_redis:
            from exstreamtv.cache.redis_cache import RedisCache
            if isinstance(self._backend, RedisCache):
                stats["redis_info"] = await self._backend.get_info()
        
        return stats


# Global cache manager instance
cache_manager = CacheManager()


async def get_cache() -> CacheManager:
    """Get the global cache manager."""
    if not cache_manager._initialized:
        await cache_manager.initialize()
    return cache_manager
