"""Health check API endpoint for EXStreamTV"""

import asyncio
import logging
import platform
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from ..config import get_config
from exstreamtv import __version__

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


async def check_ffmpeg_async() -> dict[str, Any]:
    """Check FFmpeg installation and version (non-blocking subprocess)."""
    config = get_config()
    ffmpeg_path = config.ffmpeg.path or "ffmpeg"
    try:
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_path,
            "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"status": "error", "error": "FFmpeg check timed out"}
        text = (stdout or b"").decode(errors="replace")
        if proc.returncode == 0:
            version_line = text.split("\n")[0] if text else ""
            return {"status": "ok", "version": version_line, "path": ffmpeg_path}
        return {
            "status": "error",
            "error": "FFmpeg returned non-zero exit code",
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "error": "FFmpeg not found in PATH",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


async def check_ffprobe_async() -> dict[str, Any]:
    """Check FFprobe installation and version (non-blocking subprocess)."""
    config = get_config()
    ffprobe_path = config.ffmpeg.ffprobe_path or "ffprobe"
    try:
        proc = await asyncio.create_subprocess_exec(
            ffprobe_path,
            "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {"status": "error", "error": "FFprobe check timed out"}
        text = (stdout or b"").decode(errors="replace")
        if proc.returncode == 0:
            version_line = text.split("\n")[0] if text else ""
            return {"status": "ok", "version": version_line, "path": ffprobe_path}
        return {
            "status": "error",
            "error": "FFprobe returned non-zero exit code",
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "error": "FFprobe not found in PATH",
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


@router.get("")
async def health_check() -> dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns:
        dict: Basic health status
    """
    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """
    Detailed health check with component status.
    
    Returns:
        dict: Detailed health status for all components
    """
    config = get_config()
    ffmpeg_status, ffprobe_status = await asyncio.gather(
        check_ffmpeg_async(),
        check_ffprobe_async(),
    )

    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
        },
        "components": {
            "ffmpeg": ffmpeg_status,
            "ffprobe": ffprobe_status,
            "database": {"status": "ok"},
        },
        "config": {
            "server_port": config.server.port,
            "debug_mode": config.server.debug,
            "hdhomerun_enabled": config.hdhomerun.enabled,
        },
    }


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """
    Kubernetes-style readiness probe.
    
    Returns:
        dict: Readiness status
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """
    Kubernetes-style liveness probe.
    
    Returns:
        dict: Liveness status
    """
    return {"status": "alive"}


@router.get("/db")
async def database_health() -> dict[str, Any]:
    """
    Database connection pool health check.
    
    Returns:
        dict: Database pool status and statistics
    """
    from exstreamtv.database.connection import get_pool_stats
    
    try:
        stats = get_pool_stats()
        
        # Determine health status based on pool usage
        checked_out = stats.get("checked_out", 0)
        pool_size = stats.get("pool_size", 5)
        overflow = stats.get("overflow", 0)
        
        # Calculate utilization
        max_connections = pool_size + 20  # pool_size + max_overflow
        utilization = (checked_out + overflow) / max_connections if max_connections > 0 else 0
        
        if utilization > 0.9:
            status = "critical"
        elif utilization > 0.7:
            status = "degraded"
        elif checked_out > 10:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "pool_stats": stats,
            "utilization_percent": round(utilization * 100, 1),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/channels")
async def channel_health() -> dict[str, Any]:
    """
    Channel streaming health check.
    
    Returns:
        dict: Status of all active channels
    """
    from exstreamtv.tasks.health_tasks import get_channel_metrics, _channel_metrics
    
    try:
        channels = {}
        for channel_id, metrics in _channel_metrics.items():
            last_output = metrics.get("last_output_time")
            if last_output:
                seconds_since_output = (datetime.utcnow() - last_output).total_seconds()
            else:
                seconds_since_output = None
            
            channels[str(channel_id)] = {
                "last_output_seconds_ago": seconds_since_output,
                "restart_count": metrics.get("restart_count", 0),
                "error_count_5min": metrics.get("error_count_5min", 0),
            }
        
        # Determine overall status
        unhealthy_count = sum(
            1 for c in channels.values()
            if c.get("last_output_seconds_ago") and c["last_output_seconds_ago"] > 60
        )
        
        if unhealthy_count > 0:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "total_channels": len(channels),
            "unhealthy_channels": unhealthy_count,
            "channels": channels,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Channel health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@router.get("/streaming")
async def streaming_health() -> dict[str, Any]:
    """
    Streaming infrastructure health check.
    
    Returns:
        dict: Status of streaming components (watchdog, URL resolver, etc.)
    """
    from exstreamtv.streaming.process_watchdog import get_ffmpeg_watchdog
    from exstreamtv.streaming.url_resolver import get_url_resolver
    
    try:
        # Get watchdog stats
        watchdog = get_ffmpeg_watchdog()
        watchdog_stats = watchdog.get_stats()
        
        # Get URL resolver stats
        resolver = get_url_resolver()
        resolver_stats = resolver.get_stats()
        
        return {
            "status": "healthy",
            "watchdog": {
                "active_processes": watchdog_stats.get("active_processes", 0),
                "total_kills": watchdog_stats.get("total_kills", 0),
                "total_timeouts": watchdog_stats.get("total_timeouts", 0),
            },
            "url_resolver": {
                "cache_size": resolver_stats.get("global_cache_size", 0),
                "registered_resolvers": len(resolver_stats.get("registered_resolvers", [])),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Streaming health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
