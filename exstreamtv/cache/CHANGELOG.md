# Cache Component Changelog

All notable changes to the Cache component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to cache module in this release

## [1.8.0] - 2026-01-14
### Added
- Complete caching subsystem
- `base.py` - Cache interface definition
- `memory.py` - In-memory LRU cache with TTL and compression
- `redis_cache.py` - Optional Redis backend for distributed deployments
- `decorators.py` - Cache decorators (@cached, @invalidate_cache)
- `manager.py` - Type-specific caching (EPG, M3U, metadata, FFprobe results)
