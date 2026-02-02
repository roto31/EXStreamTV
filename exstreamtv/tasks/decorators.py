"""
Task decorators for easy background task definition.
"""

import asyncio
import functools
from typing import Callable, Optional

from exstreamtv.tasks.queue import task_queue, TaskPriority, RetryPolicy
from exstreamtv.tasks.scheduler import scheduler


def background_task(
    name: Optional[str] = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    retry_policy: Optional[RetryPolicy] = None,
    dedupe: bool = False,
):
    """
    Decorator to mark a function as a background task.
    
    The decorated function gains a .delay() method that submits
    it to the task queue instead of running immediately.
    
    Usage:
        @background_task(priority=TaskPriority.HIGH)
        async def process_video(video_id: int):
            ...
        
        # Run immediately
        await process_video(123)
        
        # Run in background
        task_id = await process_video.delay(123)
    
    Args:
        name: Task name (defaults to function name)
        priority: Task priority
        retry_policy: Retry configuration
        dedupe: Enable deduplication based on arguments
    """
    def decorator(func: Callable) -> Callable:
        task_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Direct execution
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        
        async def delay(*args, **kwargs) -> str:
            """Submit task to background queue."""
            dedupe_key = None
            if dedupe:
                # Generate dedupe key from args
                import hashlib
                import json
                key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
                dedupe_key = f"{task_name}:{hashlib.sha256(key_data.encode()).hexdigest()[:16]}"
            
            # Ensure queue is started
            if not task_queue._running:
                await task_queue.start()
            
            return await task_queue.submit(
                func,
                *args,
                name=task_name,
                priority=priority,
                retry_policy=retry_policy,
                dedupe_key=dedupe_key,
                **kwargs,
            )
        
        wrapper.delay = delay
        wrapper.task_name = task_name
        return wrapper
    
    return decorator


def scheduled_task(
    interval_seconds: int,
    name: Optional[str] = None,
    run_immediately: bool = False,
):
    """
    Decorator to mark a function as a scheduled task.
    
    The decorated function will be registered with the scheduler
    and run periodically.
    
    Usage:
        @scheduled_task(interval_seconds=300)  # Every 5 minutes
        async def refresh_cache():
            ...
    
    Args:
        interval_seconds: Run interval in seconds
        name: Task name (defaults to function name)
        run_immediately: Run once immediately when registered
    """
    def decorator(func: Callable) -> Callable:
        task_name = name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        
        def register():
            """Register the task with the scheduler."""
            scheduler.add_task(
                name=task_name,
                func=func,
                interval_seconds=interval_seconds,
                run_immediately=run_immediately,
            )
        
        def unregister():
            """Unregister the task from the scheduler."""
            scheduler.remove_task(task_name)
        
        wrapper.register = register
        wrapper.unregister = unregister
        wrapper.task_name = task_name
        wrapper.interval_seconds = interval_seconds
        
        return wrapper
    
    return decorator
