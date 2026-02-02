"""
Redis cache backend implementation.

Optional dependency - requires redis package:
    pip install redis
"""

import json
import pickle
from typing import Any, Dict, List, Optional
import zlib

from exstreamtv.cache.base import CacheBackend, CacheConfig, CacheType


class RedisCache(CacheBackend):
    """
    Redis-based cache implementation for distributed deployments.
    
    Features:
    - Distributed caching across multiple instances
    - Persistence (depending on Redis configuration)
    - Pattern-based key operations
    - Atomic operations
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        super().__init__(config)
        self._client = None
        self._prefix = config.redis_prefix if config else "exstreamtv:"
    
    async def connect(self) -> bool:
        """Connect to Redis server."""
        try:
            import redis.asyncio as aioredis
            
            url = self.config.redis_url or "redis://localhost:6379/0"
            self._client = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=False,
            )
            await self._client.ping()
            return True
        except ImportError:
            raise ImportError(
                "Redis support requires the 'redis' package. "
                "Install with: pip install redis"
            )
        except Exception as e:
            print(f"Failed to connect to Redis: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key."""
        return f"{self._prefix}{key}"
    
    def _serialize(self, value: Any) -> bytes:
        """Serialize value for storage."""
        data = pickle.dumps(value)
        
        # Compress if large
        if (self.config.compression_threshold > 0 and
            len(data) > self.config.compression_threshold):
            compressed = zlib.compress(data)
            if len(compressed) < len(data) * 0.9:
                return b"C" + compressed
        
        return b"P" + data
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserialize value from storage."""
        if data[0:1] == b"C":
            data = zlib.decompress(data[1:])
        else:
            data = data[1:]
        return pickle.loads(data)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        if not self._client:
            return None
        
        try:
            data = await self._client.get(self._make_key(key))
            if data is None:
                if self.config.enable_stats:
                    self.stats.misses += 1
                return None
            
            if self.config.enable_stats:
                self.stats.hits += 1
            
            return self._deserialize(data)
        except Exception:
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        cache_type: Optional[CacheType] = None,
    ) -> bool:
        """Set a value in cache."""
        if not self._client:
            return False
        
        try:
            if ttl is None and cache_type:
                ttl = self.config.get_ttl(cache_type)
            elif ttl is None:
                ttl = 60
            
            data = self._serialize(value)
            
            await self._client.setex(
                self._make_key(key),
                ttl,
                data,
            )
            
            if self.config.enable_stats:
                self.stats.sets += 1
            
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        if not self._client:
            return False
        
        try:
            result = await self._client.delete(self._make_key(key))
            if self.config.enable_stats and result:
                self.stats.deletes += 1
            return result > 0
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self._client:
            return False
        
        try:
            return await self._client.exists(self._make_key(key)) > 0
        except Exception:
            return False
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries matching pattern."""
        if not self._client:
            return 0
        
        try:
            if pattern is None:
                pattern = "*"
            
            full_pattern = self._make_key(pattern)
            
            # Use SCAN to find keys (safer than KEYS for production)
            cursor = 0
            keys_to_delete = []
            
            while True:
                cursor, keys = await self._client.scan(
                    cursor,
                    match=full_pattern,
                    count=1000,
                )
                keys_to_delete.extend(keys)
                if cursor == 0:
                    break
            
            if keys_to_delete:
                return await self._client.delete(*keys_to_delete)
            
            return 0
        except Exception:
            return 0
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        if not self._client or not keys:
            return {}
        
        try:
            full_keys = [self._make_key(k) for k in keys]
            values = await self._client.mget(full_keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    result[key] = self._deserialize(value)
                    if self.config.enable_stats:
                        self.stats.hits += 1
                else:
                    if self.config.enable_stats:
                        self.stats.misses += 1
            
            return result
        except Exception:
            return {}
    
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set multiple values in cache."""
        if not self._client or not items:
            return False
        
        try:
            if ttl is None:
                ttl = 60
            
            pipeline = self._client.pipeline()
            
            for key, value in items.items():
                data = self._serialize(value)
                pipeline.setex(self._make_key(key), ttl, data)
            
            await pipeline.execute()
            
            if self.config.enable_stats:
                self.stats.sets += len(items)
            
            return True
        except Exception:
            return False
    
    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple values from cache."""
        if not self._client or not keys:
            return 0
        
        try:
            full_keys = [self._make_key(k) for k in keys]
            result = await self._client.delete(*full_keys)
            
            if self.config.enable_stats:
                self.stats.deletes += result
            
            return result
        except Exception:
            return 0
    
    async def get_info(self) -> Dict[str, Any]:
        """Get Redis server info."""
        if not self._client:
            return {}
        
        try:
            info = await self._client.info()
            return {
                "connected": True,
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory"),
                "used_memory_human": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "keyspace_hits": info.get("keyspace_hits"),
                "keyspace_misses": info.get("keyspace_misses"),
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
