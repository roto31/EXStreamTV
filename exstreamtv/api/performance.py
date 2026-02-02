"""
Performance monitoring API endpoints.

Provides endpoints for:
- Cache statistics
- Database pool stats
- FFmpeg process pool stats
- Task queue status
- Request timing metrics
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/performance", tags=["Performance"])


# ============================================================================
# Response Models
# ============================================================================

class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    backend: str
    hits: int
    misses: int
    hit_rate: float
    sets: int
    deletes: int
    evictions: int
    memory_bytes: int
    entry_count: int


class PoolStatsResponse(BaseModel):
    """Connection pool statistics."""
    connections_created: int
    connections_recycled: int
    connections_invalidated: int
    pool_size: Optional[int] = None
    checked_in: Optional[int] = None
    checked_out: Optional[int] = None
    overflow: Optional[int] = None


class FFmpegPoolStatsResponse(BaseModel):
    """FFmpeg process pool statistics."""
    max_processes: int
    active_processes: int
    running_processes: int
    available_slots: int
    total_memory_mb: float
    total_cpu_percent: float
    queue_size: int


class TaskQueueStatsResponse(BaseModel):
    """Task queue statistics."""
    running: bool
    workers: int
    queue_size: int
    pending_tasks: int
    running_tasks: int
    tasks_submitted: int
    tasks_completed: int
    tasks_failed: int
    tasks_retried: int
    tasks_deduplicated: int


class PerformanceSummaryResponse(BaseModel):
    """Overall performance summary."""
    cache: Dict[str, Any]
    database: Dict[str, Any]
    ffmpeg: Dict[str, Any]
    tasks: Dict[str, Any]
    requests: Dict[str, Any]


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/stats", response_model=PerformanceSummaryResponse)
async def get_performance_stats() -> PerformanceSummaryResponse:
    """
    Get comprehensive performance statistics.
    
    Returns statistics for:
    - Cache (hits, misses, memory)
    - Database (connection pool)
    - FFmpeg (process pool)
    - Tasks (queue status)
    - Requests (timing metrics)
    """
    from exstreamtv.cache import cache_manager
    from exstreamtv.database.connection import get_pool_stats
    from exstreamtv.middleware.performance import performance_metrics
    
    # Get cache stats
    cache_stats = {}
    try:
        if cache_manager._initialized:
            stats = cache_manager.get_stats()
            cache_stats = stats.to_dict()
            cache_stats["backend"] = "redis" if cache_manager.is_redis else "memory"
    except Exception as e:
        cache_stats = {"error": str(e)}
    
    # Get database pool stats
    db_stats = {}
    try:
        db_stats = get_pool_stats()
    except Exception as e:
        db_stats = {"error": str(e)}
    
    # Get FFmpeg pool stats
    ffmpeg_stats = {}
    try:
        from exstreamtv.ffmpeg.process_pool import _process_pool
        if _process_pool:
            ffmpeg_stats = await _process_pool.get_stats()
    except Exception as e:
        ffmpeg_stats = {"error": str(e)}
    
    # Get task queue stats
    task_stats = {}
    try:
        from exstreamtv.tasks import task_queue
        if task_queue._running:
            status = await task_queue.get_status()
            task_stats = {
                "running": status["running"],
                "workers": status["workers"],
                "queue_size": status["queue_size"],
                "pending_tasks": status["pending_tasks"],
                "running_tasks": status["running_tasks"],
                **status["stats"],
            }
    except Exception as e:
        task_stats = {"error": str(e)}
    
    # Get request metrics
    request_stats = {}
    try:
        request_stats = performance_metrics.get_summary()
    except Exception as e:
        request_stats = {"error": str(e)}
    
    return PerformanceSummaryResponse(
        cache=cache_stats,
        database=db_stats,
        ffmpeg=ffmpeg_stats,
        tasks=task_stats,
        requests=request_stats,
    )


@router.get("/cache", response_model=CacheStatsResponse)
async def get_cache_stats() -> CacheStatsResponse:
    """Get detailed cache statistics."""
    from exstreamtv.cache import cache_manager
    
    if not cache_manager._initialized:
        await cache_manager.initialize()
    
    stats = cache_manager.get_stats()
    
    return CacheStatsResponse(
        backend="redis" if cache_manager.is_redis else "memory",
        hits=stats.hits,
        misses=stats.misses,
        hit_rate=stats.hit_rate,
        sets=stats.sets,
        deletes=stats.deletes,
        evictions=stats.evictions,
        memory_bytes=stats.memory_bytes,
        entry_count=stats.entry_count,
    )


@router.post("/cache/clear")
async def clear_cache(pattern: Optional[str] = None) -> Dict[str, Any]:
    """
    Clear cache entries.
    
    Args:
        pattern: Optional glob pattern to match keys
    """
    from exstreamtv.cache import cache_manager
    
    if not cache_manager._initialized:
        return {"cleared": 0, "message": "Cache not initialized"}
    
    cleared = await cache_manager.clear(pattern)
    
    return {
        "cleared": cleared,
        "pattern": pattern or "*",
    }


@router.get("/database", response_model=PoolStatsResponse)
async def get_database_stats() -> PoolStatsResponse:
    """Get database connection pool statistics."""
    from exstreamtv.database.connection import get_pool_stats
    
    stats = get_pool_stats()
    
    return PoolStatsResponse(**stats)


@router.get("/ffmpeg", response_model=FFmpegPoolStatsResponse)
async def get_ffmpeg_stats() -> FFmpegPoolStatsResponse:
    """Get FFmpeg process pool statistics."""
    from exstreamtv.ffmpeg.process_pool import get_process_pool
    
    pool = await get_process_pool()
    stats = await pool.get_stats()
    
    return FFmpegPoolStatsResponse(**stats)


@router.get("/ffmpeg/processes")
async def get_ffmpeg_processes() -> List[Dict[str, Any]]:
    """Get list of active FFmpeg processes."""
    from exstreamtv.ffmpeg.process_pool import get_process_pool
    
    pool = await get_process_pool()
    processes = await pool.get_all_processes()
    
    return [p.to_dict() for p in processes]


@router.get("/tasks", response_model=TaskQueueStatsResponse)
async def get_task_stats() -> TaskQueueStatsResponse:
    """Get task queue statistics."""
    from exstreamtv.tasks import get_task_queue
    
    queue = await get_task_queue()
    status = await queue.get_status()
    
    return TaskQueueStatsResponse(
        running=status["running"],
        workers=status["workers"],
        queue_size=status["queue_size"],
        pending_tasks=status["pending_tasks"],
        running_tasks=status["running_tasks"],
        **status["stats"],
    )


@router.get("/tasks/recent")
async def get_recent_tasks(limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent task history."""
    from exstreamtv.tasks import get_task_queue
    
    queue = await get_task_queue()
    return await queue.get_recent_tasks(limit=limit)


@router.get("/tasks/scheduled")
async def get_scheduled_tasks() -> List[Dict[str, Any]]:
    """Get scheduled tasks."""
    from exstreamtv.tasks.scheduler import scheduler
    
    return scheduler.get_tasks()


@router.get("/requests/endpoints")
async def get_endpoint_stats() -> List[Dict[str, Any]]:
    """Get per-endpoint request statistics."""
    from exstreamtv.middleware.performance import performance_metrics
    
    return performance_metrics.get_endpoint_stats()


@router.get("/requests/slow")
async def get_slow_requests(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent slow requests."""
    from exstreamtv.middleware.performance import performance_metrics
    
    # Filter slow requests from history
    slow = [
        {
            "path": t.path,
            "method": t.method,
            "status_code": t.status_code,
            "duration_ms": round(t.duration_ms, 2),
        }
        for t in performance_metrics._request_timings
        if t.duration_ms > 1000  # Over 1 second
    ]
    
    return slow[-limit:]


@router.get("/health")
async def performance_health() -> Dict[str, Any]:
    """
    Check performance health.
    
    Returns warnings if any metrics indicate problems.
    """
    warnings = []
    
    # Check cache hit rate
    try:
        from exstreamtv.cache import cache_manager
        if cache_manager._initialized:
            stats = cache_manager.get_stats()
            if stats.hit_rate < 50 and (stats.hits + stats.misses) > 100:
                warnings.append(f"Low cache hit rate: {stats.hit_rate:.1f}%")
    except Exception:
        pass
    
    # Check database connections
    try:
        from exstreamtv.database.connection import get_pool_stats
        pool_stats = get_pool_stats()
        if pool_stats.get("checked_out", 0) > 8:
            warnings.append(f"High database connection usage: {pool_stats.get('checked_out')}")
    except Exception:
        pass
    
    # Check FFmpeg processes
    try:
        from exstreamtv.ffmpeg.process_pool import _process_pool
        if _process_pool:
            ffmpeg_stats = await _process_pool.get_stats()
            if ffmpeg_stats["available_slots"] == 0:
                warnings.append("FFmpeg process pool exhausted")
    except Exception:
        pass
    
    # Check task queue
    try:
        from exstreamtv.tasks import task_queue
        if task_queue._running:
            status = await task_queue.get_status()
            if status["queue_size"] > 100:
                warnings.append(f"Large task queue backlog: {status['queue_size']}")
    except Exception:
        pass
    
    return {
        "healthy": len(warnings) == 0,
        "warnings": warnings,
    }
