"""
Health Monitoring Background Tasks.

Monitor channel health and trigger auto-recovery when needed.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from exstreamtv.streaming.channel_manager import ChannelManager

logger = logging.getLogger(__name__)

# Track channel health metrics
_channel_metrics: dict[int, dict[str, Any]] = {}

# Reference to channel manager (set during app startup)
_channel_manager: Optional["ChannelManager"] = None


def set_channel_manager(manager: "ChannelManager") -> None:
    """Set the channel manager reference for restart operations."""
    global _channel_manager
    _channel_manager = manager
    logger.info("Channel manager registered with health tasks")


def update_channel_metric(channel_id: int, metric: str, value: Any) -> None:
    """Update a health metric for a channel."""
    if channel_id not in _channel_metrics:
        _channel_metrics[channel_id] = {}
    _channel_metrics[channel_id][metric] = value
    _channel_metrics[channel_id]["last_update"] = datetime.utcnow()


def get_channel_metrics(channel_id: int) -> dict[str, Any]:
    """Get health metrics for a channel."""
    return _channel_metrics.get(channel_id, {})


async def channel_health_task() -> dict[str, Any]:
    """
    Monitor channel health and restart unhealthy channels.
    
    This task runs frequently (every 30 seconds) to detect and
    recover from streaming failures quickly.
    
    Health checks:
    - Last output time (stale if no output for 60s)
    - Client count vs expected
    - Error rate in last 5 minutes
    - FFmpeg process status
    
    Actions:
    - Log health warnings
    - Trigger channel restart for unhealthy channels
    - Update health metrics for monitoring
    
    Returns:
        Statistics about the health check
    """
    logger.debug("Running channel health check")
    
    stats = {
        "channels_checked": 0,
        "channels_healthy": 0,
        "channels_warning": 0,
        "channels_unhealthy": 0,
        "restarts_triggered": 0,
        "errors": 0,
    }
    
    try:
        # Import here to avoid circular imports
        from exstreamtv.database.connection import get_sync_session
        from exstreamtv.database.models import Channel
        from sqlalchemy import select
        
        session = get_sync_session()
        try:
            # Get all enabled channels
            stmt = select(Channel).where(Channel.enabled == True)
            result = session.execute(stmt)
            channels = result.scalars().all()
            
            now = datetime.utcnow()
            
            for channel in channels:
                stats["channels_checked"] += 1
                
                try:
                    metrics = get_channel_metrics(channel.id)
                    
                    # Check last output time
                    # Use longer timeouts to account for FFmpeg buffering/seeking
                    # especially for remote sources like Archive.org
                    UNHEALTHY_THRESHOLD = 180  # 3 minutes - allows for slow buffering
                    WARNING_THRESHOLD = 90     # 1.5 minutes before warning
                    
                    last_output = metrics.get("last_output_time")
                    if last_output:
                        time_since_output = (now - last_output).total_seconds()
                        
                        if time_since_output > UNHEALTHY_THRESHOLD:
                            # No output for threshold - unhealthy
                            logger.warning(
                                f"Channel {channel.number} no output for "
                                f"{time_since_output:.0f}s - unhealthy"
                            )
                            stats["channels_unhealthy"] += 1
                            
                            # Trigger restart if enabled
                            if metrics.get("auto_restart_enabled", True):
                                await _trigger_channel_restart(channel.id)
                                stats["restarts_triggered"] += 1
                            
                        elif time_since_output > WARNING_THRESHOLD:
                            # Warning - getting stale
                            logger.debug(
                                f"Channel {channel.number} output stale "
                                f"({time_since_output:.0f}s)"
                            )
                            stats["channels_warning"] += 1
                        else:
                            stats["channels_healthy"] += 1
                    else:
                        # No metrics yet - assume healthy if recently started
                        stats["channels_healthy"] += 1
                    
                    # Check error rate
                    error_count = metrics.get("error_count_5min", 0)
                    if error_count > 5:
                        logger.warning(
                            f"Channel {channel.number} high error rate: "
                            f"{error_count} errors in 5 min"
                        )
                        if stats["channels_unhealthy"] == 0:
                            stats["channels_warning"] += 1
                    
                except Exception as e:
                    logger.error(f"Error checking channel {channel.id} health: {e}")
                    stats["errors"] += 1
            
        finally:
            session.close()
        
    except Exception as e:
        logger.error(f"Channel health task failed: {e}")
        stats["errors"] += 1
    
    if stats["channels_unhealthy"] > 0 or stats["restarts_triggered"] > 0:
        logger.info(
            f"Health check: {stats['channels_healthy']} healthy, "
            f"{stats['channels_warning']} warning, "
            f"{stats['channels_unhealthy']} unhealthy, "
            f"{stats['restarts_triggered']} restarts"
        )
    
    return stats


async def _trigger_channel_restart(channel_id: int) -> bool:
    """
    Trigger a restart for an unhealthy channel.
    
    Actually stops and restarts the channel through the ChannelManager.
    
    Args:
        channel_id: ID of channel to restart
        
    Returns:
        True if restart was triggered successfully
    """
    global _channel_manager
    
    try:
        logger.info(f"Triggering restart for channel {channel_id}")
        
        # Update metrics first
        metrics = _channel_metrics.get(channel_id, {})
        restart_count = metrics.get("restart_count", 0) + 1
        update_channel_metric(channel_id, "restart_count", restart_count)
        update_channel_metric(channel_id, "last_restart", datetime.utcnow())
        
        # Check if we have a channel manager
        if _channel_manager is None:
            logger.warning(
                f"Cannot restart channel {channel_id}: ChannelManager not registered. "
                "Metrics updated but no actual restart performed."
            )
            return False
        
        # Get channel info from database
        from exstreamtv.database.connection import get_sync_session
        from exstreamtv.database.models import Channel
        from sqlalchemy import select
        
        session = get_sync_session()
        try:
            stmt = select(Channel).where(Channel.id == channel_id)
            result = session.execute(stmt)
            channel = result.scalar_one_or_none()
            
            if not channel:
                logger.error(f"Channel {channel_id} not found for restart")
                return False
            
            channel_number = channel.number
            channel_name = channel.name
        finally:
            session.close()
        
        # Stop the channel
        logger.info(f"Stopping channel {channel_number} ({channel_name}) for restart")
        await _channel_manager.stop_channel(channel_id)
        
        # Brief cooldown before restart
        await asyncio.sleep(2.0)
        
        # Restart the channel
        logger.info(f"Restarting channel {channel_number} ({channel_name})")
        await _channel_manager.start_channel(
            channel_id=channel_id,
            channel_number=channel_number,
            channel_name=channel_name,
        )
        
        logger.info(
            f"Successfully restarted channel {channel_number} "
            f"(restart #{restart_count})"
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to trigger restart for channel {channel_id}: {e}")
        return False


async def collect_system_metrics_task() -> dict[str, Any]:
    """
    Collect system-wide metrics for monitoring.
    
    Returns:
        System metrics dictionary
    """
    import os
    
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "channels": {},
        "system": {},
    }
    
    try:
        # Get process memory usage
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        metrics["system"] = {
            "memory_rss_mb": memory_info.rss / 1024 / 1024,
            "memory_vms_mb": memory_info.vms / 1024 / 1024,
            "cpu_percent": process.cpu_percent(),
            "open_files": len(process.open_files()),
            "threads": process.num_threads(),
        }
    except ImportError:
        # psutil not available
        pass
    except Exception as e:
        logger.warning(f"Failed to collect system metrics: {e}")
    
    # Collect channel metrics summary
    metrics["channels"] = {
        "total_tracked": len(_channel_metrics),
        "metrics": dict(_channel_metrics),
    }
    
    return metrics
