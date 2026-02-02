"""
Task scheduler for periodic and cron-style tasks.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A scheduled task configuration."""
    
    name: str
    func: Callable
    interval_seconds: Optional[int] = None  # For interval-based
    cron: Optional[str] = None  # For cron-style (not implemented yet)
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    
    # State
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    is_running: bool = False
    
    def calculate_next_run(self) -> datetime:
        """Calculate the next run time."""
        if self.interval_seconds:
            base = self.last_run or datetime.now()
            return base + timedelta(seconds=self.interval_seconds)
        return datetime.now()


class TaskScheduler:
    """
    Task scheduler for periodic background tasks.
    
    Features:
    - Interval-based scheduling
    - Immediate execution option
    - Task status tracking
    - Graceful shutdown
    """
    
    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    def add_task(
        self,
        name: str,
        func: Callable,
        interval_seconds: int,
        run_immediately: bool = False,
        *args,
        **kwargs,
    ) -> None:
        """
        Add a scheduled task.
        
        Args:
            name: Unique task name
            func: Async function to execute
            interval_seconds: Run interval in seconds
            run_immediately: Run once immediately on start
            args: Function arguments
            kwargs: Function keyword arguments
        """
        task = ScheduledTask(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            args=args,
            kwargs=kwargs,
        )
        
        if run_immediately:
            task.next_run = datetime.now()
        else:
            task.next_run = datetime.now() + timedelta(seconds=interval_seconds)
        
        self._tasks[name] = task
        logger.info(f"Scheduled task added: {name} (every {interval_seconds}s)")
    
    def remove_task(self, name: str) -> bool:
        """Remove a scheduled task."""
        if name in self._tasks:
            del self._tasks[name]
            logger.info(f"Scheduled task removed: {name}")
            return True
        return False
    
    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Task scheduler started")
    
    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task scheduler stopped")
    
    async def run_task(self, name: str) -> bool:
        """Manually trigger a scheduled task."""
        async with self._lock:
            task = self._tasks.get(name)
            if not task:
                return False
        
        await self._execute_task(task)
        return True
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        """Get all scheduled tasks."""
        return [
            {
                "name": t.name,
                "interval_seconds": t.interval_seconds,
                "last_run": t.last_run.isoformat() if t.last_run else None,
                "next_run": t.next_run.isoformat() if t.next_run else None,
                "run_count": t.run_count,
                "is_running": t.is_running,
            }
            for t in self._tasks.values()
        ]
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                now = datetime.now()
                
                # Find tasks that need to run
                tasks_to_run = []
                async with self._lock:
                    for task in self._tasks.values():
                        if (task.next_run and 
                            task.next_run <= now and 
                            not task.is_running):
                            tasks_to_run.append(task)
                
                # Execute tasks
                for task in tasks_to_run:
                    asyncio.create_task(self._execute_task(task))
                
                # Sleep until next check
                await asyncio.sleep(1)
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(5)
    
    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task."""
        task.is_running = True
        task.last_run = datetime.now()
        
        try:
            logger.debug(f"Running scheduled task: {task.name}")
            
            if asyncio.iscoroutinefunction(task.func):
                await task.func(*task.args, **task.kwargs)
            else:
                task.func(*task.args, **task.kwargs)
            
            task.run_count += 1
            logger.debug(f"Scheduled task completed: {task.name}")
        
        except Exception as e:
            logger.error(f"Scheduled task failed: {task.name}: {e}")
        
        finally:
            task.is_running = False
            task.next_run = task.calculate_next_run()


# Global scheduler instance
scheduler = TaskScheduler()


async def get_scheduler() -> TaskScheduler:
    """Get the global task scheduler."""
    if not scheduler._running:
        await scheduler.start()
    return scheduler
