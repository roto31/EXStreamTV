"""
Background task queue implementation.

Provides async task queue with:
- Priority-based execution
- Task deduplication
- Retry with exponential backoff
- Task status tracking
- Concurrent workers
"""

import asyncio
import hashlib
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Callable, Dict, List, Optional, Set
import logging
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(IntEnum):
    """Task priority levels (lower = higher priority)."""
    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100
    BACKGROUND = 200


@dataclass
class RetryPolicy:
    """Retry configuration for tasks."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 300.0
    exponential_base: float = 2.0
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


@dataclass
class Task:
    """A background task."""
    
    id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    retry_policy: Optional[RetryPolicy] = None
    dedupe_key: Optional[str] = None
    
    # Execution tracking
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    attempts: int = 0
    result: Any = None
    error: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "Task") -> bool:
        """Compare by priority for heap queue."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get task duration in milliseconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.name,
            "attempts": self.attempts,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "started_at": datetime.fromtimestamp(self.started_at).isoformat() if self.started_at else None,
            "completed_at": datetime.fromtimestamp(self.completed_at).isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class QueueConfig:
    """Task queue configuration."""
    
    # Number of worker tasks
    num_workers: int = 4
    
    # Maximum queue size (0 = unlimited)
    max_queue_size: int = 10000
    
    # Default retry policy
    default_retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    
    # Enable task deduplication
    enable_deduplication: bool = True
    
    # Task history retention (seconds)
    history_retention: int = 3600
    
    # Maximum concurrent tasks per name
    max_concurrent_per_name: int = 0  # 0 = unlimited


class TaskQueue:
    """
    Async background task queue.
    
    Features:
    - Priority queue with multiple workers
    - Task deduplication
    - Retry with exponential backoff
    - Task status tracking
    - Graceful shutdown
    """
    
    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()
        
        # Priority queue (using heapq via asyncio.PriorityQueue)
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=self.config.max_queue_size if self.config.max_queue_size > 0 else 0
        )
        
        # Task tracking
        self._tasks: Dict[str, Task] = {}
        self._pending_dedupe: Set[str] = set()
        self._running_counts: Dict[str, int] = {}
        
        # Task history
        self._history: List[Task] = []
        
        # Workers
        self._workers: List[asyncio.Task] = []
        
        # State
        self._running = False
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_retried": 0,
            "tasks_deduplicated": 0,
        }
    
    async def start(self) -> None:
        """Start the task queue workers."""
        if self._running:
            return
        
        self._running = True
        
        # Start workers
        for i in range(self.config.num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"Task queue started with {self.config.num_workers} workers")
    
    async def stop(self, wait: bool = True, timeout: float = 30.0) -> None:
        """Stop the task queue."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel cleanup
        self._cleanup_task.cancel()
        
        if wait:
            # Wait for queue to drain
            try:
                await asyncio.wait_for(self._queue.join(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Task queue didn't drain in time")
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        
        logger.info("Task queue stopped")
    
    async def submit(
        self,
        func: Callable,
        *args,
        name: Optional[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        retry_policy: Optional[RetryPolicy] = None,
        dedupe_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Submit a task to the queue.
        
        Args:
            func: Async or sync function to execute
            args: Positional arguments
            name: Task name (defaults to function name)
            priority: Task priority
            retry_policy: Retry configuration
            dedupe_key: Key for deduplication (None = no deduplication)
            metadata: Additional task metadata
            kwargs: Keyword arguments
            
        Returns:
            Task ID
        """
        task_name = name or func.__name__
        task_id = str(uuid.uuid4())
        
        # Handle deduplication
        if dedupe_key and self.config.enable_deduplication:
            async with self._lock:
                if dedupe_key in self._pending_dedupe:
                    self._stats["tasks_deduplicated"] += 1
                    logger.debug(f"Task deduplicated: {dedupe_key}")
                    # Return ID of existing task
                    for task in self._tasks.values():
                        if task.dedupe_key == dedupe_key and task.status == TaskStatus.PENDING:
                            return task.id
                    return task_id
                self._pending_dedupe.add(dedupe_key)
        
        task = Task(
            id=task_id,
            name=task_name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            retry_policy=retry_policy or self.config.default_retry_policy,
            dedupe_key=dedupe_key,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._tasks[task_id] = task
            self._stats["tasks_submitted"] += 1
        
        await self._queue.put((priority, task))
        
        logger.debug(f"Task submitted: {task_name} ({task_id})")
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        async with self._lock:
            return self._tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                if task.dedupe_key:
                    self._pending_dedupe.discard(task.dedupe_key)
                return True
        return False
    
    async def get_status(self) -> Dict[str, Any]:
        """Get queue status."""
        async with self._lock:
            pending = sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING)
            running = sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING)
        
        return {
            "running": self._running,
            "workers": len(self._workers),
            "queue_size": self._queue.qsize(),
            "pending_tasks": pending,
            "running_tasks": running,
            "stats": dict(self._stats),
        }
    
    async def get_recent_tasks(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent task history."""
        async with self._lock:
            tasks = sorted(
                self._history,
                key=lambda t: t.completed_at or t.created_at,
                reverse=True,
            )[:limit]
        return [t.to_dict() for t in tasks]
    
    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes tasks."""
        while self._running:
            try:
                # Get next task
                priority, task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
                
                # Check if cancelled
                if task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue
                
                # Check concurrent limits
                if self.config.max_concurrent_per_name > 0:
                    async with self._lock:
                        count = self._running_counts.get(task.name, 0)
                        if count >= self.config.max_concurrent_per_name:
                            # Re-queue with slight delay
                            await asyncio.sleep(0.1)
                            await self._queue.put((priority, task))
                            continue
                        self._running_counts[task.name] = count + 1
                
                try:
                    await self._execute_task(task)
                finally:
                    if self.config.max_concurrent_per_name > 0:
                        async with self._lock:
                            self._running_counts[task.name] = max(
                                0, self._running_counts.get(task.name, 1) - 1
                            )
                    self._queue.task_done()
            
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
    
    async def _execute_task(self, task: Task) -> None:
        """Execute a single task with retry handling."""
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        task.attempts += 1
        
        try:
            # Execute function
            if asyncio.iscoroutinefunction(task.func):
                task.result = await task.func(*task.args, **task.kwargs)
            else:
                task.result = task.func(*task.args, **task.kwargs)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            
            async with self._lock:
                self._stats["tasks_completed"] += 1
                if task.dedupe_key:
                    self._pending_dedupe.discard(task.dedupe_key)
                self._history.append(task)
            
            logger.debug(f"Task completed: {task.name} ({task.id})")
        
        except Exception as e:
            task.error = str(e)
            logger.error(f"Task failed: {task.name} ({task.id}): {e}")
            
            # Check for retry
            if (task.retry_policy and 
                task.attempts < task.retry_policy.max_retries):
                task.status = TaskStatus.RETRYING
                delay = task.retry_policy.get_delay(task.attempts)
                
                async with self._lock:
                    self._stats["tasks_retried"] += 1
                
                logger.info(f"Retrying task {task.name} in {delay:.1f}s (attempt {task.attempts + 1})")
                
                await asyncio.sleep(delay)
                await self._queue.put((task.priority, task))
            else:
                task.status = TaskStatus.FAILED
                task.completed_at = time.time()
                
                async with self._lock:
                    self._stats["tasks_failed"] += 1
                    if task.dedupe_key:
                        self._pending_dedupe.discard(task.dedupe_key)
                    self._history.append(task)
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up old task history."""
        while self._running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                cutoff = time.time() - self.config.history_retention
                
                async with self._lock:
                    # Remove old history
                    self._history = [
                        t for t in self._history
                        if (t.completed_at or t.created_at) > cutoff
                    ]
                    
                    # Remove completed tasks from tracking
                    completed_ids = [
                        tid for tid, t in self._tasks.items()
                        if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)
                        and (t.completed_at or t.created_at) < cutoff
                    ]
                    for tid in completed_ids:
                        del self._tasks[tid]
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")


# Global task queue instance
task_queue = TaskQueue()


async def get_task_queue() -> TaskQueue:
    """Get the global task queue, starting if needed."""
    if not task_queue._running:
        await task_queue.start()
    return task_queue
