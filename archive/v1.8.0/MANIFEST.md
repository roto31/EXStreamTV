# EXStreamTV v1.8.0 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Performance Optimization (Phase 10)

## Summary

Complete performance optimization layer with caching, database optimization, and background tasks.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Cache | 1.8.0 | Created |
| Tasks | 1.8.0 | Created |
| Middleware | 1.8.0 | Created |

## Caching Layer (`exstreamtv/cache/`)

- In-memory LRU cache with TTL and compression
- Optional Redis backend for distributed deployments
- Cache decorators (@cached, @invalidate_cache)
- Type-specific caching (EPG, M3U, metadata, FFprobe results)

## Database Optimization

- `exstreamtv/database/optimization.py` - Query optimization utilities
- Performance indexes for frequently queried columns
- Optimized connection pooling with tuning options
- SQLite WAL mode for better concurrency
- Batch operations for bulk inserts/updates

## FFmpeg Process Pooling

- `exstreamtv/ffmpeg/process_pool.py` - FFmpeg process manager
- Semaphore-based concurrency limiting
- Process health monitoring with CPU/memory tracking
- Graceful shutdown and error callbacks

## Background Task System (`exstreamtv/tasks/`)

- Priority-based task execution
- Task deduplication and retry with backoff
- Periodic task scheduler
- Task decorators (@background_task, @scheduled_task)

## API Performance Middleware

- `exstreamtv/middleware/performance.py`
- Gzip compression for API responses
- ETag support with 304 responses
- Request timing and slow query logging
- Token bucket rate limiting

## Performance Monitoring API

- `exstreamtv/api/performance.py`
- Comprehensive statistics endpoint
- Cache, database, FFmpeg, and task stats
- Slow request tracking
- Performance health checks

## Previous Version

← v1.6.0: Documentation & Release

## Next Version

→ v2.0.0: ErsatzTV-Compatible API
