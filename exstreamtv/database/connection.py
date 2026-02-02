"""
Database connection and session management.

Provides optimized connection pooling and session management for
both async (FastAPI) and sync (migrations) contexts.

Includes DatabaseConnectionManager with dynamic pool sizing based on
channel count (Tunarr-style optimization).
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncGenerator, Callable, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool

from exstreamtv.config import get_config
from exstreamtv.database.models.base import Base

logger = logging.getLogger(__name__)

# Async engine and session factory (for FastAPI)
_async_engine = None
_async_session_factory = None

# Sync engine (for migrations and scripts)
_sync_engine = None
_sync_session_factory = None

# Global connection manager instance
_connection_manager: Optional["DatabaseConnectionManager"] = None

# Connection pool statistics
_pool_stats = {
    "connections_created": 0,
    "connections_recycled": 0,
    "connections_invalidated": 0,
    "connections_checked_out": 0,
    "connections_checked_in": 0,
    "pool_exhausted_count": 0,
}


@dataclass
class ConnectionMetrics:
    """Metrics for connection pool monitoring."""
    
    pool_size: int = 0
    checked_out: int = 0
    checked_in: int = 0
    overflow: int = 0
    connections_created: int = 0
    connections_recycled: int = 0
    connections_invalidated: int = 0
    pool_exhausted_count: int = 0
    last_exhausted_at: Optional[datetime] = None
    active_channel_count: int = 0
    recommended_pool_size: int = 0


@dataclass
class PoolExhaustionEvent:
    """Event recorded when pool is exhausted."""
    
    timestamp: datetime
    channel_count: int
    pool_size: int
    checked_out: int
    wait_time_ms: float = 0.0


class DatabaseConnectionManager:
    """
    Advanced database connection manager with dynamic pool sizing.
    
    Ported from Tunarr's DBAccess pattern with enhancements:
    - Dynamic pool sizing based on active channel count
    - Connection event monitoring and metrics
    - Pool exhaustion detection and auto-scaling
    - Health checks with pool validation
    
    Usage:
        manager = DatabaseConnectionManager()
        await manager.initialize(channel_count=34)
        
        async with manager.get_session() as session:
            result = await session.execute(query)
    """
    
    # Pool sizing constants (Tunarr-style)
    CONNECTIONS_PER_CHANNEL = 2.5  # 2.5 connections per concurrent channel
    BASE_POOL_SIZE = 10  # Minimum pool size
    MAX_POOL_SIZE = 100  # Maximum pool size
    POOL_TIMEOUT = 60  # Seconds to wait for connection
    POOL_RECYCLE = 3600  # Recycle connections every hour
    
    def __init__(self):
        """Initialize the connection manager."""
        self._engine = None
        self._session_factory = None
        self._sync_engine = None
        self._sync_session_factory = None
        self._channel_count = 0
        self._current_pool_size = self.BASE_POOL_SIZE
        self._lock = asyncio.Lock()
        self._initialized = False
        
        # Metrics tracking
        self._exhaustion_events: list[PoolExhaustionEvent] = []
        self._last_resize_at: Optional[datetime] = None
        self._on_exhaustion_callbacks: list[Callable] = []
        
        logger.info("DatabaseConnectionManager created")
    
    def calculate_optimal_pool_size(self, channel_count: int) -> int:
        """
        Calculate optimal pool size based on channel count.
        
        Formula: (channel_count * CONNECTIONS_PER_CHANNEL) + BASE_POOL_SIZE
        Clamped between BASE_POOL_SIZE and MAX_POOL_SIZE.
        
        Args:
            channel_count: Number of active channels
            
        Returns:
            Optimal pool size
        """
        calculated = int(channel_count * self.CONNECTIONS_PER_CHANNEL) + self.BASE_POOL_SIZE
        optimal = max(self.BASE_POOL_SIZE, min(calculated, self.MAX_POOL_SIZE))
        
        logger.debug(
            f"Pool size calculation: {channel_count} channels * "
            f"{self.CONNECTIONS_PER_CHANNEL} + {self.BASE_POOL_SIZE} = "
            f"{calculated} (clamped to {optimal})"
        )
        
        return optimal
    
    async def initialize(
        self,
        channel_count: int = 0,
        is_production: bool = False,
    ) -> None:
        """
        Initialize database connections with optimal pool sizing.
        
        Args:
            channel_count: Number of expected concurrent channels
            is_production: Use production-optimized settings
        """
        async with self._lock:
            if self._initialized:
                logger.warning("DatabaseConnectionManager already initialized")
                return
            
            self._channel_count = channel_count
            self._current_pool_size = self.calculate_optimal_pool_size(channel_count)
            
            config = get_config()
            async_url = _get_async_url(config.database.url)
            
            # Build pool configuration
            pool_kwargs = self._build_pool_config(async_url, is_production)
            
            # Create async engine
            self._engine = create_async_engine(
                async_url,
                echo=config.database.echo,
                future=True,
                **pool_kwargs,
            )
            
            # Register event listeners for monitoring
            self._register_pool_events()
            
            # Create session factory
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            
            # Create tables
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            self._initialized = True
            
            logger.info(
                f"DatabaseConnectionManager initialized: "
                f"pool_size={self._current_pool_size}, "
                f"channel_count={channel_count}, "
                f"production={is_production}"
            )
    
    def _build_pool_config(self, url: str, is_production: bool) -> dict[str, Any]:
        """Build pool configuration based on database type."""
        if "sqlite" in url:
            from sqlalchemy.pool import StaticPool
            return {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            }
        
        # PostgreSQL/MySQL configuration
        max_overflow = min(
            int(self._current_pool_size * 0.5),
            40
        )
        
        config = {
            "poolclass": QueuePool,
            "pool_size": self._current_pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": self.POOL_TIMEOUT,
            "pool_recycle": self.POOL_RECYCLE,
            "pool_pre_ping": True,  # Validate connections before use
        }
        
        if is_production:
            config["pool_recycle"] = 1800  # 30 min in production
        
        logger.debug(
            f"Pool config: size={config['pool_size']}, "
            f"overflow={config['max_overflow']}, "
            f"timeout={config['pool_timeout']}"
        )
        
        return config
    
    def _register_pool_events(self) -> None:
        """Register SQLAlchemy pool event listeners for monitoring."""
        sync_engine = self._engine.sync_engine
        
        @event.listens_for(sync_engine, "connect")
        def on_connect(dbapi_conn, connection_record):
            _pool_stats["connections_created"] += 1
            logger.debug(f"New connection created (total: {_pool_stats['connections_created']})")
        
        @event.listens_for(sync_engine, "checkout")
        def on_checkout(dbapi_conn, connection_record, connection_proxy):
            _pool_stats["connections_checked_out"] += 1
            
            # Enable WAL mode for SQLite
            if "sqlite" in str(self._engine.url):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-64000")
                cursor.close()
        
        @event.listens_for(sync_engine, "checkin")
        def on_checkin(dbapi_conn, connection_record):
            _pool_stats["connections_checked_in"] += 1
        
        @event.listens_for(sync_engine, "invalidate")
        def on_invalidate(dbapi_conn, connection_record, exception):
            _pool_stats["connections_invalidated"] += 1
            logger.warning(f"Connection invalidated: {exception}")
        
        @event.listens_for(sync_engine, "reset")
        def on_reset(dbapi_conn, connection_record):
            _pool_stats["connections_recycled"] += 1
        
        logger.debug("Pool event listeners registered")
    
    async def resize_pool(self, new_channel_count: int) -> bool:
        """
        Resize the connection pool based on new channel count.
        
        This creates a new engine with the updated pool size.
        Existing connections are gracefully drained.
        
        Args:
            new_channel_count: New number of active channels
            
        Returns:
            True if resize was performed, False if not needed
        """
        async with self._lock:
            new_size = self.calculate_optimal_pool_size(new_channel_count)
            
            if new_size == self._current_pool_size:
                logger.debug(f"Pool size unchanged at {new_size}")
                return False
            
            old_size = self._current_pool_size
            self._channel_count = new_channel_count
            self._current_pool_size = new_size
            
            logger.info(
                f"Resizing pool: {old_size} -> {new_size} "
                f"(channels: {new_channel_count})"
            )
            
            # Dispose old engine and recreate
            if self._engine:
                old_engine = self._engine
                
                # Create new engine with updated size
                config = get_config()
                async_url = _get_async_url(config.database.url)
                pool_kwargs = self._build_pool_config(async_url, False)
                
                self._engine = create_async_engine(
                    async_url,
                    echo=config.database.echo,
                    future=True,
                    **pool_kwargs,
                )
                
                self._register_pool_events()
                
                self._session_factory = async_sessionmaker(
                    self._engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False,
                )
                
                # Dispose old engine (gracefully closes connections)
                await old_engine.dispose()
                
                self._last_resize_at = datetime.utcnow()
                
            return True
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with automatic cleanup.
        
        Yields:
            AsyncSession for database operations
        """
        if not self._initialized or not self._session_factory:
            raise RuntimeError("DatabaseConnectionManager not initialized")
        
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the database connection.
        
        Returns:
            Health check results
        """
        result = {
            "healthy": False,
            "latency_ms": 0.0,
            "pool_metrics": None,
            "error": None,
        }
        
        try:
            start = datetime.utcnow()
            
            async with self.get_session() as session:
                # Simple query to test connection
                await session.execute(text("SELECT 1"))
            
            latency = (datetime.utcnow() - start).total_seconds() * 1000
            
            result["healthy"] = True
            result["latency_ms"] = latency
            result["pool_metrics"] = self.get_metrics().model_dump() if hasattr(self.get_metrics(), 'model_dump') else vars(self.get_metrics())
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Database health check failed: {e}")
        
        return result
    
    def get_metrics(self) -> ConnectionMetrics:
        """Get current connection pool metrics."""
        metrics = ConnectionMetrics(
            pool_size=self._current_pool_size,
            active_channel_count=self._channel_count,
            recommended_pool_size=self.calculate_optimal_pool_size(self._channel_count),
            connections_created=_pool_stats.get("connections_created", 0),
            connections_recycled=_pool_stats.get("connections_recycled", 0),
            connections_invalidated=_pool_stats.get("connections_invalidated", 0),
            pool_exhausted_count=_pool_stats.get("pool_exhausted_count", 0),
        )
        
        # Get live pool stats if available
        if self._engine:
            pool = self._engine.sync_engine.pool
            if hasattr(pool, "size"):
                metrics.pool_size = pool.size()
            if hasattr(pool, "checkedin"):
                metrics.checked_in = pool.checkedin()
            if hasattr(pool, "checkedout"):
                metrics.checked_out = pool.checkedout()
            if hasattr(pool, "overflow"):
                metrics.overflow = pool.overflow()
        
        return metrics
    
    def on_pool_exhausted(self, callback: Callable) -> None:
        """Register callback for pool exhaustion events."""
        self._on_exhaustion_callbacks.append(callback)
    
    def _record_exhaustion(self, wait_time_ms: float) -> None:
        """Record a pool exhaustion event."""
        _pool_stats["pool_exhausted_count"] += 1
        
        event = PoolExhaustionEvent(
            timestamp=datetime.utcnow(),
            channel_count=self._channel_count,
            pool_size=self._current_pool_size,
            checked_out=self.get_metrics().checked_out,
            wait_time_ms=wait_time_ms,
        )
        
        self._exhaustion_events.append(event)
        
        # Keep only last 100 events
        if len(self._exhaustion_events) > 100:
            self._exhaustion_events = self._exhaustion_events[-100:]
        
        logger.warning(
            f"Pool exhaustion detected: "
            f"channels={self._channel_count}, "
            f"pool_size={self._current_pool_size}, "
            f"wait_time={wait_time_ms:.1f}ms"
        )
        
        # Notify callbacks
        for callback in self._on_exhaustion_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(event))
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Pool exhaustion callback error: {e}")
    
    async def close(self) -> None:
        """Close all database connections."""
        async with self._lock:
            if self._engine:
                await self._engine.dispose()
                self._engine = None
                self._session_factory = None
            
            self._initialized = False
            logger.info("DatabaseConnectionManager closed")


def get_connection_manager() -> DatabaseConnectionManager:
    """Get the global DatabaseConnectionManager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = DatabaseConnectionManager()
    return _connection_manager


async def init_connection_manager(
    channel_count: int = 0,
    is_production: bool = False,
) -> DatabaseConnectionManager:
    """Initialize and return the global connection manager."""
    manager = get_connection_manager()
    await manager.initialize(channel_count=channel_count, is_production=is_production)
    return manager


def _get_async_url(url: str) -> str:
    """Convert sync database URL to async variant."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


def _get_pool_class(url: str):
    """Get appropriate pool class for database type."""
    if "sqlite" in url:
        # SQLite doesn't benefit from connection pooling
        return NullPool
    return QueuePool


def _get_pool_kwargs(url: str, is_production: bool = False) -> dict:
    """Get optimized pool configuration."""
    # SQLite with aiosqlite needs StaticPool for single connection reuse
    # NullPool creates a new connection each time which can cause issues
    if "sqlite" in url:
        from sqlalchemy.pool import StaticPool
        return {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
    
    # PostgreSQL/MySQL pool settings - increase limits for concurrent channels
    if is_production:
        return {
            "poolclass": QueuePool,
            "pool_size": 20,
            "max_overflow": 40,
            "pool_timeout": 60,
            "pool_recycle": 1800,  # 30 minutes
            "pool_pre_ping": True,  # Verify connections before use
        }
    else:
        return {
            "poolclass": QueuePool,
            "pool_size": 20,  # Increased from 5
            "max_overflow": 40,  # Increased from 10
            "pool_timeout": 60,  # Increased from 30
            "pool_recycle": 3600,  # 1 hour
            "pool_pre_ping": True,
        }


async def init_db(is_production: bool = False) -> None:
    """
    Initialize the database connection and create tables.
    
    Args:
        is_production: Use production-optimized pool settings
    """
    global _async_engine, _async_session_factory
    
    config = get_config()
    async_url = _get_async_url(config.database.url)
    pool_kwargs = _get_pool_kwargs(async_url, is_production)
    
    _async_engine = create_async_engine(
        async_url,
        echo=config.database.echo,
        future=True,
        **pool_kwargs,
    )
    
    # Register pool event listeners for monitoring
    @event.listens_for(_async_engine.sync_engine, "connect")
    def on_connect(dbapi_conn, connection_record):
        _pool_stats["connections_created"] += 1
    
    @event.listens_for(_async_engine.sync_engine, "checkout")
    def on_checkout(dbapi_conn, connection_record, connection_proxy):
        # Enable WAL mode for SQLite for better concurrency
        if "sqlite" in async_url:
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cursor.close()
    
    _async_session_factory = async_sessionmaker(
        _async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,  # Manual flush for better performance
    )
    
    # Create all tables
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_sync_db() -> None:
    """Initialize synchronous database connection (for scripts/migrations)."""
    global _sync_engine, _sync_session_factory
    
    config = get_config()
    pool_kwargs = _get_pool_kwargs(config.database.url)
    
    _sync_engine = create_engine(
        config.database.url,
        echo=config.database.echo,
        future=True,
        **pool_kwargs,
    )
    
    _sync_session_factory = sessionmaker(
        _sync_engine,
        class_=Session,
        expire_on_commit=False,
    )
    
    Base.metadata.create_all(_sync_engine)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    if _async_session_factory is None:
        await init_db()
    
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_session() as session:
        yield session


def get_sync_session() -> Session:
    """Get a synchronous database session."""
    if _sync_session_factory is None:
        init_sync_db()
    return _sync_session_factory()


def get_sync_session_factory():
    """Get the sync session factory for ChannelManager and other components."""
    if _sync_session_factory is None:
        init_sync_db()
    return _sync_session_factory


def get_pool_stats() -> dict:
    """Get connection pool statistics."""
    stats = dict(_pool_stats)
    
    if _async_engine is not None:
        pool = _async_engine.sync_engine.pool
        if hasattr(pool, "size"):
            stats["pool_size"] = pool.size()
        if hasattr(pool, "checkedin"):
            stats["checked_in"] = pool.checkedin()
        if hasattr(pool, "checkedout"):
            stats["checked_out"] = pool.checkedout()
        if hasattr(pool, "overflow"):
            stats["overflow"] = pool.overflow()
    
    return stats


async def close_db() -> None:
    """Close database connections and cleanup."""
    global _async_engine, _async_session_factory
    
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


# Alias for backward compatibility with migration scripts
get_async_session = get_session
