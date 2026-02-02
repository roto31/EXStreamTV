"""
EXStreamTV Background Task System

Provides:
- Task queue for background processing
- Task scheduling
- Priority-based execution
- Task deduplication
- Retry policies
- Playout rebuild tasks
- URL refresh tasks
- Health monitoring tasks
"""

from exstreamtv.tasks.queue import (
    TaskQueue,
    Task,
    TaskStatus,
    TaskPriority,
    task_queue,
    get_task_queue,
)
from exstreamtv.tasks.scheduler import TaskScheduler
from exstreamtv.tasks.decorators import background_task, scheduled_task
from exstreamtv.tasks.playout_tasks import (
    rebuild_playouts_task,
    cleanup_old_playout_items_task,
)
from exstreamtv.tasks.url_refresh_task import (
    refresh_urls_task,
    cleanup_url_cache_task,
)
from exstreamtv.tasks.health_tasks import (
    channel_health_task,
    collect_system_metrics_task,
    update_channel_metric,
    get_channel_metrics,
)

__all__ = [
    # Queue
    "TaskQueue",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "task_queue",
    "get_task_queue",
    # Scheduler
    "TaskScheduler",
    # Decorators
    "background_task",
    "scheduled_task",
    # Playout tasks
    "rebuild_playouts_task",
    "cleanup_old_playout_items_task",
    # URL tasks
    "refresh_urls_task",
    "cleanup_url_cache_task",
    # Health tasks
    "channel_health_task",
    "collect_system_metrics_task",
    "update_channel_metric",
    "get_channel_metrics",
]
