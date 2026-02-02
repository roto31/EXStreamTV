# Tasks Component Changelog

All notable changes to the Tasks component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to tasks module in this release

## [1.8.0] - 2026-01-14
### Added
- Async task queue system
- `queue.py` - Priority-based task execution
- `scheduler.py` - Periodic task scheduler
- `decorators.py` - Task decorators (@background_task, @scheduled_task)
- Task deduplication and retry with backoff
- `health_tasks.py` - Health check tasks
- `playout_tasks.py` - Playout maintenance tasks
- `url_refresh_task.py` - URL refresh tasks
