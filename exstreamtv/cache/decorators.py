"""
Cache decorators for easy caching of function results.
"""

import asyncio
import functools
import hashlib
import inspect
import json
from typing import Any, Callable, Optional, Union

from exstreamtv.cache.base import CacheType, generate_cache_key
from exstreamtv.cache.manager import cache_manager


def cache_key(*key_args: str) -> Callable:
    """
    Decorator to generate cache key from specific function arguments.
    
    Usage:
        @cache_key("user_id", "channel_id")
        @cached(ttl=300)
        async def get_user_channel(user_id: int, channel_id: int, extra: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        func._cache_key_args = key_args
        return func
    return decorator


def cached(
    ttl: Optional[int] = None,
    cache_type: Optional[CacheType] = None,
    prefix: Optional[str] = None,
    key_builder: Optional[Callable] = None,
    condition: Optional[Callable] = None,
    unless: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time-to-live in seconds (uses cache_type default if not specified)
        cache_type: Type of cache (affects default TTL)
        prefix: Custom key prefix (defaults to function name)
        key_builder: Custom function to build cache key from args/kwargs
        condition: Only cache if this callable returns True (receives result)
        unless: Don't cache if this callable returns True (receives result)
    
    Usage:
        @cached(ttl=300, cache_type=CacheType.API_RESPONSE)
        async def get_channels():
            return await db.fetch_all_channels()
        
        @cached(prefix="user", key_builder=lambda user_id, **kw: str(user_id))
        async def get_user(user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        # Get function signature for argument inspection
        sig = inspect.signature(func)
        func_name = func.__name__
        cache_prefix = prefix or func_name
        
        # Check for @cache_key decorator
        cache_key_args = getattr(func, "_cache_key_args", None)
        
        def build_key(*args, **kwargs) -> str:
            """Build cache key from function arguments."""
            if key_builder:
                return f"{cache_prefix}:{key_builder(*args, **kwargs)}"
            
            # Bind arguments to parameter names
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            if cache_key_args:
                # Use only specified arguments
                key_parts = [
                    str(bound.arguments.get(arg, ""))
                    for arg in cache_key_args
                ]
            else:
                # Use all arguments (excluding self/cls)
                key_parts = []
                for name, value in bound.arguments.items():
                    if name in ("self", "cls"):
                        continue
                    if value is None:
                        continue
                    if isinstance(value, (str, int, float, bool)):
                        key_parts.append(f"{name}={value}")
                    elif isinstance(value, (list, tuple)):
                        key_parts.append(f"{name}={','.join(str(v) for v in value)}")
                    elif isinstance(value, dict):
                        key_parts.append(f"{name}={json.dumps(value, sort_keys=True)}")
            
            key = ":".join(key_parts) if key_parts else "default"
            
            # Hash if too long
            if len(key) > 200:
                key = hashlib.sha256(key.encode()).hexdigest()[:32]
            
            return f"{cache_prefix}:{key}"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Ensure cache is initialized
            if not cache_manager._initialized:
                await cache_manager.initialize()
            
            # Build cache key
            key = build_key(*args, **kwargs)
            
            # Try to get from cache
            cached_value = await cache_manager.get(key)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Check caching conditions
            should_cache = True
            
            if condition is not None:
                should_cache = condition(result)
            
            if unless is not None and unless(result):
                should_cache = False
            
            # Cache result
            if should_cache and result is not None:
                await cache_manager.set(
                    key,
                    result,
                    ttl=ttl,
                    cache_type=cache_type,
                )
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # For sync functions, run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(async_wrapper(*args, **kwargs))
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            async_wrapper.cache_key_builder = build_key
            async_wrapper.invalidate = lambda *a, **kw: cache_manager.delete(build_key(*a, **kw))
            return async_wrapper
        else:
            sync_wrapper.cache_key_builder = build_key
            sync_wrapper.invalidate = lambda *a, **kw: cache_manager.delete(build_key(*a, **kw))
            return sync_wrapper
    
    return decorator


def invalidate_cache(
    patterns: Optional[list[str]] = None,
    cache_types: Optional[list[CacheType]] = None,
) -> Callable:
    """
    Decorator to invalidate cache after function execution.
    
    Args:
        patterns: Glob patterns to match keys for invalidation
        cache_types: Cache types to invalidate
    
    Usage:
        @invalidate_cache(patterns=["channels:*", "m3u:*"])
        async def update_channel(channel_id: int, data: dict):
            ...
        
        @invalidate_cache(cache_types=[CacheType.EPG, CacheType.M3U])
        async def regenerate_guide():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)
            
            # Invalidate by patterns
            if patterns:
                for pattern in patterns:
                    await cache_manager.clear(pattern)
            
            # Invalidate by type
            if cache_types:
                for ct in cache_types:
                    await cache_manager.clear(f"{ct.value}:*")
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            result = func(*args, **kwargs)
            
            loop = asyncio.get_event_loop()
            
            if patterns:
                for pattern in patterns:
                    loop.run_until_complete(cache_manager.clear(pattern))
            
            if cache_types:
                for ct in cache_types:
                    loop.run_until_complete(cache_manager.clear(f"{ct.value}:*"))
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class CacheAside:
    """
    Cache-aside pattern helper for explicit cache management.
    
    Usage:
        cache = CacheAside("users", ttl=300)
        
        async def get_user(user_id: int):
            # Try cache
            user = await cache.get(user_id)
            if user:
                return user
            
            # Load from DB
            user = await db.get_user(user_id)
            
            # Store in cache
            await cache.set(user_id, user)
            
            return user
    """
    
    def __init__(
        self,
        namespace: str,
        ttl: int = 300,
        cache_type: Optional[CacheType] = None,
    ):
        self.namespace = namespace
        self.ttl = ttl
        self.cache_type = cache_type
    
    def _make_key(self, key: Any) -> str:
        """Create namespaced key."""
        if isinstance(key, (list, tuple)):
            key = ":".join(str(k) for k in key)
        return f"{self.namespace}:{key}"
    
    async def get(self, key: Any) -> Optional[Any]:
        """Get value from cache."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.get(self._make_key(key))
    
    async def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.set(
            self._make_key(key),
            value,
            ttl=ttl or self.ttl,
            cache_type=self.cache_type,
        )
    
    async def delete(self, key: Any) -> bool:
        """Delete value from cache."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.delete(self._make_key(key))
    
    async def get_or_set(self, key: Any, factory: Callable) -> Any:
        """Get from cache or compute and set."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.get_or_set(
            self._make_key(key),
            factory,
            ttl=self.ttl,
            cache_type=self.cache_type,
        )
    
    async def invalidate_all(self) -> int:
        """Invalidate all entries in this namespace."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.clear(f"{self.namespace}:*")
