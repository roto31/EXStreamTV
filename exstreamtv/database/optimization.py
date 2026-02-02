"""
Database optimization utilities.

Provides:
- Index management
- Query optimization helpers
- Connection pool tuning
- Query result caching
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Type, TypeVar
import time

from sqlalchemy import Index, event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query

from exstreamtv.cache import cache_manager, CacheType


T = TypeVar("T")


# ============================================================================
# Database Indexes
# ============================================================================

# Define indexes for frequently queried columns
PERFORMANCE_INDEXES = [
    # Channels
    Index("ix_channels_number", "channels.number"),
    Index("ix_channels_group", "channels.group"),
    Index("ix_channels_enabled", "channels.is_enabled"),
    Index("ix_channels_streaming_mode", "channels.streaming_mode"),
    
    # Playlists
    Index("ix_playlists_name", "playlists.name"),
    
    # Playlist Items
    Index("ix_playlist_items_playlist_id", "playlist_items.playlist_id"),
    Index("ix_playlist_items_position", "playlist_items.position"),
    Index("ix_playlist_items_media_id", "playlist_items.media_item_id"),
    
    # Media Items
    Index("ix_media_items_library_id", "media_items.library_id"),
    Index("ix_media_items_media_type", "media_items.media_type"),
    Index("ix_media_items_title", "media_items.title"),
    Index("ix_media_items_year", "media_items.year"),
    Index("ix_media_items_external_id", "media_items.external_id"),
    
    # Playouts
    Index("ix_playouts_channel_id", "playouts.channel_id"),
    Index("ix_playouts_start_time", "playouts.start_time"),
    
    # Playout Items
    Index("ix_playout_items_playout_id", "playout_items.playout_id"),
    Index("ix_playout_items_start", "playout_items.start"),
    Index("ix_playout_items_finish", "playout_items.finish"),
    
    # Schedules
    Index("ix_schedules_channel_id", "program_schedules.channel_id"),
    
    # Libraries
    Index("ix_local_libraries_path", "local_libraries.path"),
    Index("ix_plex_libraries_server_url", "plex_libraries.server_url"),
]


async def create_indexes(session: AsyncSession) -> int:
    """
    Create performance indexes if they don't exist.
    
    Returns number of indexes created.
    """
    created = 0
    
    for index in PERFORMANCE_INDEXES:
        try:
            # Check if index exists
            check_sql = text(f"""
                SELECT 1 FROM sqlite_master 
                WHERE type='index' AND name=:name
            """)
            result = await session.execute(check_sql, {"name": index.name})
            
            if result.scalar() is None:
                # Create index
                await session.execute(text(str(index)))
                created += 1
        except Exception:
            # Index may already exist or table doesn't exist yet
            pass
    
    return created


# ============================================================================
# Connection Pool Configuration
# ============================================================================

@dataclass
class PoolConfig:
    """Database connection pool configuration."""
    
    # Pool size
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800  # 30 minutes
    pool_pre_ping: bool = True
    
    # Statement cache
    statement_cache_size: int = 100
    
    # Execution options
    execution_options: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.execution_options is None:
            self.execution_options = {
                "stream_results": True,  # Enable streaming for large results
            }
    
    def to_engine_kwargs(self) -> Dict[str, Any]:
        """Convert to SQLAlchemy engine kwargs."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
        }


def get_optimized_pool_config(
    max_connections: int = 50,
    is_production: bool = False,
) -> PoolConfig:
    """
    Get optimized pool configuration based on environment.
    
    Args:
        max_connections: Maximum total connections
        is_production: Whether this is a production deployment
    """
    if is_production:
        return PoolConfig(
            pool_size=min(10, max_connections // 2),
            max_overflow=min(20, max_connections // 2),
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            statement_cache_size=200,
        )
    else:
        return PoolConfig(
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True,
            statement_cache_size=100,
        )


# ============================================================================
# Query Helpers
# ============================================================================

class QueryOptimizer:
    """
    Query optimization helpers.
    
    Provides:
    - Eager loading suggestions
    - Query result caching
    - Pagination helpers
    - Batch operations
    """
    
    @staticmethod
    def paginate(
        query: Query,
        page: int = 1,
        per_page: int = 20,
        max_per_page: int = 100,
    ) -> tuple[Query, Dict[str, int]]:
        """
        Apply pagination to a query.
        
        Returns:
            Tuple of (paginated query, pagination metadata)
        """
        per_page = min(per_page, max_per_page)
        offset = (page - 1) * per_page
        
        paginated = query.offset(offset).limit(per_page)
        
        metadata = {
            "page": page,
            "per_page": per_page,
            "offset": offset,
        }
        
        return paginated, metadata
    
    @staticmethod
    async def count_total(session: AsyncSession, query: Query) -> int:
        """Get total count for a query (for pagination)."""
        from sqlalchemy import func, select
        
        count_query = select(func.count()).select_from(query.subquery())
        result = await session.execute(count_query)
        return result.scalar() or 0
    
    @staticmethod
    async def batch_insert(
        session: AsyncSession,
        model: Type[T],
        items: List[Dict[str, Any]],
        batch_size: int = 1000,
    ) -> int:
        """
        Batch insert items efficiently.
        
        Args:
            session: Database session
            model: SQLAlchemy model class
            items: List of dicts to insert
            batch_size: Number of items per batch
            
        Returns:
            Number of items inserted
        """
        total = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            await session.execute(
                model.__table__.insert(),
                batch,
            )
            total += len(batch)
        
        return total
    
    @staticmethod
    async def batch_update(
        session: AsyncSession,
        model: Type[T],
        items: List[Dict[str, Any]],
        key_column: str = "id",
        batch_size: int = 500,
    ) -> int:
        """
        Batch update items efficiently.
        
        Args:
            session: Database session
            model: SQLAlchemy model class
            items: List of dicts with key and update values
            key_column: Column to match for updates
            batch_size: Number of items per batch
            
        Returns:
            Number of items updated
        """
        total = 0
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            for item in batch:
                key_value = item.pop(key_column)
                await session.execute(
                    model.__table__.update()
                    .where(getattr(model, key_column) == key_value)
                    .values(**item)
                )
                total += 1
        
        return total


# ============================================================================
# Cached Queries
# ============================================================================

class CachedQuery:
    """
    Helper for caching query results.
    
    Usage:
        cached = CachedQuery(session)
        channels = await cached.get_or_fetch(
            "all_channels",
            lambda: session.execute(select(Channel)),
            ttl=300,
        )
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_or_fetch(
        self,
        cache_key: str,
        query_func: callable,
        ttl: int = 300,
        cache_type: CacheType = CacheType.API_RESPONSE,
    ) -> Any:
        """
        Get from cache or execute query and cache result.
        
        Args:
            cache_key: Unique cache key
            query_func: Async function that executes the query
            ttl: Cache TTL in seconds
            cache_type: Type of cache entry
            
        Returns:
            Query result
        """
        # Initialize cache if needed
        if not cache_manager._initialized:
            await cache_manager.initialize()
        
        # Try cache first
        cached = await cache_manager.get(f"query:{cache_key}")
        if cached is not None:
            return cached
        
        # Execute query
        result = await query_func()
        
        # Cache result
        await cache_manager.set(
            f"query:{cache_key}",
            result,
            ttl=ttl,
            cache_type=cache_type,
        )
        
        return result
    
    async def invalidate(self, cache_key: str) -> bool:
        """Invalidate a cached query."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.delete(f"query:{cache_key}")
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cached queries matching pattern."""
        if not cache_manager._initialized:
            await cache_manager.initialize()
        return await cache_manager.clear(f"query:{pattern}")


# ============================================================================
# Query Timing
# ============================================================================

class QueryTimer:
    """
    Context manager for timing queries.
    
    Usage:
        async with QueryTimer("get_channels") as timer:
            result = await session.execute(query)
        print(f"Query took {timer.duration_ms}ms")
    """
    
    def __init__(self, name: str = "query"):
        self.name = name
        self.start_time: float = 0
        self.end_time: float = 0
    
    @property
    def duration_ms(self) -> float:
        """Get query duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000
    
    async def __aenter__(self) -> "QueryTimer":
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_time = time.time()
        
        # Log slow queries
        if self.duration_ms > 1000:
            import logging
            logging.warning(
                f"Slow query '{self.name}': {self.duration_ms:.2f}ms"
            )


# ============================================================================
# Session Helpers
# ============================================================================

@asynccontextmanager
async def optimized_session(
    session: AsyncSession,
    autoflush: bool = False,
) -> AsyncSession:
    """
    Context manager for optimized session settings.
    
    Temporarily disables autoflush for batch operations.
    """
    original_autoflush = session.autoflush
    session.autoflush = autoflush
    
    try:
        yield session
    finally:
        session.autoflush = original_autoflush


async def prefetch_relationships(
    session: AsyncSession,
    instances: List[T],
    *relationships: str,
) -> None:
    """
    Eagerly load relationships for a list of instances.
    
    Helps avoid N+1 query problems.
    
    Args:
        session: Database session
        instances: List of model instances
        relationships: Relationship names to load
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    
    if not instances:
        return
    
    model = type(instances[0])
    ids = [inst.id for inst in instances]
    
    options = [selectinload(getattr(model, rel)) for rel in relationships]
    
    query = select(model).where(model.id.in_(ids)).options(*options)
    await session.execute(query)
