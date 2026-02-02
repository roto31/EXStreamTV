"""
URL Refresh Background Task.

Proactively refreshes expiring stream URLs before they expire.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


async def refresh_urls_task() -> dict[str, Any]:
    """
    Refresh URLs that will expire within the threshold.
    
    This task runs periodically to refresh expiring URLs (especially
    YouTube URLs which expire after ~6 hours) before they cause
    streaming failures.
    
    Actions:
    - Get all URLs expiring within 1 hour
    - Re-resolve each URL using the appropriate resolver
    - Update the cache with fresh URLs
    
    Returns:
        Statistics about the refresh operation
    """
    from exstreamtv.streaming.url_resolver import get_url_resolver
    
    logger.info("Starting URL refresh task")
    
    stats = {
        "urls_checked": 0,
        "urls_refreshed": 0,
        "errors": 0,
    }
    
    try:
        resolver = get_url_resolver()
        
        # Get URLs expiring within 1 hour
        expiring = resolver.get_expiring_urls(threshold_minutes=60)
        stats["urls_checked"] = len(expiring)
        
        if not expiring:
            logger.debug("No URLs need refreshing")
            return stats
        
        logger.info(f"Found {len(expiring)} URLs expiring soon")
        
        for cached in expiring:
            try:
                # Create a simple media item dict for re-resolution
                media_item = {
                    "id": cached.resolved_url.media_id,
                    "source": cached.resolved_url.source_type.value,
                    **cached.resolved_url.metadata,
                }
                
                # Force refresh
                await resolver.resolve(media_item, force_refresh=True)
                stats["urls_refreshed"] += 1
                
                logger.debug(f"Refreshed URL: {cached.cache_key}")
                
            except Exception as e:
                logger.warning(f"Failed to refresh URL {cached.cache_key}: {e}")
                stats["errors"] += 1
        
    except Exception as e:
        logger.error(f"URL refresh task failed: {e}")
        stats["errors"] += 1
    
    logger.info(
        f"URL refresh complete: checked {stats['urls_checked']}, "
        f"refreshed {stats['urls_refreshed']}, errors: {stats['errors']}"
    )
    
    return stats


async def cleanup_url_cache_task() -> dict[str, Any]:
    """
    Clean up expired URL cache entries.
    
    Removes expired entries to free memory.
    
    Returns:
        Statistics about the cleanup operation
    """
    from exstreamtv.streaming.url_resolver import get_url_resolver
    
    logger.info("Starting URL cache cleanup task")
    
    stats = {
        "entries_before": 0,
        "entries_after": 0,
        "entries_removed": 0,
    }
    
    try:
        resolver = get_url_resolver()
        
        # Get stats before cleanup
        before_stats = resolver.get_stats()
        stats["entries_before"] = before_stats.get("global_cache_size", 0)
        
        # Clear expired entries from global cache
        expired_keys = [
            key for key, cached in resolver._global_cache.items()
            if not cached.is_valid
        ]
        
        for key in expired_keys:
            del resolver._global_cache[key]
        
        stats["entries_removed"] = len(expired_keys)
        stats["entries_after"] = len(resolver._global_cache)
        
        logger.info(f"Removed {stats['entries_removed']} expired cache entries")
        
    except Exception as e:
        logger.error(f"URL cache cleanup failed: {e}")
    
    return stats
