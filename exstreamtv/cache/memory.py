"""
In-memory LRU cache implementation with TTL support.
"""

import asyncio
import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional, Set
import pickle
import zlib

from exstreamtv.cache.base import CacheBackend, CacheConfig, CacheType, CacheStats


@dataclass
class CacheEntry:
    """A single cache entry with metadata."""
    value: Any
    expires_at: float
    size_bytes: int
    cache_type: Optional[CacheType] = None
    compressed: bool = False
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() >= self.expires_at
    
    @property
    def ttl_remaining(self) -> int:
        """Get remaining TTL in seconds."""
        remaining = self.expires_at - time.time()
        return max(0, int(remaining))


class MemoryCache(CacheBackend):
    """
    Thread-safe in-memory LRU cache with TTL support.
    
    Features:
    - LRU eviction when max entries reached
    - Time-based expiration
    - Memory size tracking
    - Optional compression for large values
    - Pattern-based deletion
    - Batch operations
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        super().__init__(config)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._total_size = 0
    
    async def start(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired entries."""
        while True:
            await asyncio.sleep(60)  # Run every minute
            await self._cleanup_expired()
    
    async def _cleanup_expired(self) -> int:
        """Remove expired entries."""
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]
            for key in expired_keys:
                entry = self._cache.pop(key)
                self._total_size -= entry.size_bytes
                removed += 1
                if self.config.enable_stats:
                    self.stats.evictions += 1
        
        if removed > 0:
            self.stats.entry_count = len(self._cache)
            self.stats.memory_bytes = self._total_size
        
        return removed
    
    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of a value."""
        try:
            return sys.getsizeof(pickle.dumps(value))
        except Exception:
            return sys.getsizeof(str(value))
    
    def _compress(self, value: Any) -> tuple[bytes, bool]:
        """Compress value if it exceeds threshold."""
        data = pickle.dumps(value)
        
        if (self.config.compression_threshold > 0 and 
            len(data) > self.config.compression_threshold):
            compressed = zlib.compress(data)
            if len(compressed) < len(data) * 0.9:  # Only if 10%+ savings
                return compressed, True
        
        return data, False
    
    def _decompress(self, data: bytes, compressed: bool) -> Any:
        """Decompress value if needed."""
        if compressed:
            data = zlib.decompress(data)
        return pickle.loads(data)
    
    def _evict_lru(self) -> None:
        """Evict least recently used entries until under limit."""
        while len(self._cache) >= self.config.max_entries:
            key, entry = self._cache.popitem(last=False)
            self._total_size -= entry.size_bytes
            if self.config.enable_stats:
                self.stats.evictions += 1
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                if self.config.enable_stats:
                    self.stats.misses += 1
                return None
            
            if entry.is_expired:
                self._cache.pop(key)
                self._total_size -= entry.size_bytes
                if self.config.enable_stats:
                    self.stats.misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            
            if self.config.enable_stats:
                self.stats.hits += 1
            
            # Decompress if needed
            if entry.compressed:
                return self._decompress(entry.value, True)
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        cache_type: Optional[CacheType] = None,
    ) -> bool:
        """Set a value in cache."""
        try:
            # Determine TTL
            if ttl is None and cache_type:
                ttl = self.config.get_ttl(cache_type)
            elif ttl is None:
                ttl = 60  # Default 1 minute
            
            # Compress if needed
            if self.config.compression_threshold > 0:
                data, compressed = self._compress(value)
                store_value = data if compressed else value
            else:
                store_value = value
                compressed = False
            
            size = self._estimate_size(store_value)
            
            entry = CacheEntry(
                value=store_value,
                expires_at=time.time() + ttl,
                size_bytes=size,
                cache_type=cache_type,
                compressed=compressed,
            )
            
            with self._lock:
                # Remove old entry if exists
                if key in self._cache:
                    old_entry = self._cache.pop(key)
                    self._total_size -= old_entry.size_bytes
                
                # Evict if needed
                self._evict_lru()
                
                # Add new entry
                self._cache[key] = entry
                self._total_size += size
                
                if self.config.enable_stats:
                    self.stats.sets += 1
                    self.stats.entry_count = len(self._cache)
                    self.stats.memory_bytes = self._total_size
            
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._total_size -= entry.size_bytes
                if self.config.enable_stats:
                    self.stats.deletes += 1
                    self.stats.entry_count = len(self._cache)
                    self.stats.memory_bytes = self._total_size
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                self._cache.pop(key)
                self._total_size -= entry.size_bytes
                return False
            return True
    
    async def clear(self, pattern: Optional[str] = None) -> int:
        """Clear cache entries matching pattern."""
        import fnmatch
        
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                self._total_size = 0
            else:
                # Convert glob pattern to match
                keys_to_delete = [
                    key for key in self._cache.keys()
                    if fnmatch.fnmatch(key, pattern)
                ]
                count = len(keys_to_delete)
                for key in keys_to_delete:
                    entry = self._cache.pop(key)
                    self._total_size -= entry.size_bytes
            
            if self.config.enable_stats:
                self.stats.entry_count = len(self._cache)
                self.stats.memory_bytes = self._total_size
            
            return count
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> bool:
        """Set multiple values in cache."""
        success = True
        for key, value in items.items():
            if not await self.set(key, value, ttl=ttl):
                success = False
        return success
    
    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple values from cache."""
        count = 0
        for key in keys:
            if await self.delete(key):
                count += 1
        return count
    
    async def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all cache keys matching pattern."""
        import fnmatch
        
        with self._lock:
            if pattern is None:
                return list(self._cache.keys())
            return [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
    
    async def get_entry_info(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata about a cache entry."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired:
                return None
            
            return {
                "key": key,
                "size_bytes": entry.size_bytes,
                "ttl_remaining": entry.ttl_remaining,
                "cache_type": entry.cache_type.value if entry.cache_type else None,
                "compressed": entry.compressed,
            }
