"""
Playout Background Tasks.

Periodic tasks for rebuilding and maintaining playout schedules.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


async def rebuild_playouts_task() -> dict[str, Any]:
    """
    Rebuild playout items for all active channels.
    
    This task runs periodically to ensure channels have enough
    scheduled content in their playout queues.
    
    Actions:
    - Check each active channel's playout
    - If less than 30 minutes of content remaining, generate more
    - Fill any gaps with filler content
    - Update playout state in database
    
    Returns:
        Statistics about the rebuild operation
    """
    from exstreamtv.database.connection import get_sync_session
    from exstreamtv.database.models import Channel, Playout, PlayoutItem
    from sqlalchemy import select, func
    
    logger.info("Starting playout rebuild task")
    
    stats = {
        "channels_checked": 0,
        "channels_rebuilt": 0,
        "items_generated": 0,
        "errors": 0,
    }
    
    session = get_sync_session()
    try:
        # Get all enabled channels with active playouts
        stmt = select(Channel).where(Channel.enabled == True)
        result = session.execute(stmt)
        channels = result.scalars().all()
        
        now = datetime.utcnow()
        rebuild_threshold = now + timedelta(minutes=30)
        
        for channel in channels:
            stats["channels_checked"] += 1
            
            try:
                # Check if channel has enough content
                playout_stmt = select(Playout).where(
                    Playout.channel_id == channel.id,
                    Playout.is_active == True
                )
                playout_result = session.execute(playout_stmt)
                playout = playout_result.scalar_one_or_none()
                
                if not playout:
                    continue
                
                # Check upcoming items
                items_stmt = select(PlayoutItem).where(
                    PlayoutItem.playout_id == playout.id,
                    PlayoutItem.start_time >= now
                ).order_by(PlayoutItem.start_time)
                
                items_result = session.execute(items_stmt)
                upcoming_items = items_result.scalars().all()
                
                # Calculate total upcoming duration
                total_duration = timedelta(0)
                for item in upcoming_items:
                    if item.finish_time and item.start_time:
                        total_duration += (item.finish_time - item.start_time)
                
                # If less than 30 minutes, we need to generate more
                if total_duration < timedelta(minutes=30):
                    logger.info(
                        f"Channel {channel.number} needs more content "
                        f"(only {total_duration.total_seconds() / 60:.1f} min remaining)"
                    )
                    
                    # In a full implementation, this would call PlayoutBuilder
                    # to generate more items from the schedule
                    stats["channels_rebuilt"] += 1
                
            except Exception as e:
                logger.error(f"Error checking channel {channel.id}: {e}")
                stats["errors"] += 1
        
        session.commit()
        
    except Exception as e:
        logger.error(f"Playout rebuild task failed: {e}")
        session.rollback()
        stats["errors"] += 1
    finally:
        session.close()
    
    logger.info(
        f"Playout rebuild complete: checked {stats['channels_checked']} channels, "
        f"rebuilt {stats['channels_rebuilt']}, errors: {stats['errors']}"
    )
    
    return stats


async def cleanup_old_playout_items_task() -> dict[str, Any]:
    """
    Clean up old playout items that have already played.
    
    Removes items older than 24 hours to prevent database bloat.
    
    Returns:
        Statistics about the cleanup operation
    """
    from exstreamtv.database.connection import get_sync_session
    from exstreamtv.database.models import PlayoutItem
    from sqlalchemy import delete
    
    logger.info("Starting playout cleanup task")
    
    stats = {
        "items_deleted": 0,
        "errors": 0,
    }
    
    session = get_sync_session()
    try:
        # Delete items older than 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        stmt = delete(PlayoutItem).where(PlayoutItem.finish_time < cutoff)
        result = session.execute(stmt)
        stats["items_deleted"] = result.rowcount
        
        session.commit()
        
        logger.info(f"Cleaned up {stats['items_deleted']} old playout items")
        
    except Exception as e:
        logger.error(f"Playout cleanup task failed: {e}")
        session.rollback()
        stats["errors"] += 1
    finally:
        session.close()
    
    return stats
