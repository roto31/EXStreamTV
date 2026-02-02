# Middleware Component Changelog

All notable changes to the Middleware component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to middleware module in this release

## [1.8.0] - 2026-01-14
### Added
- `performance.py` - Performance middleware
  - Gzip compression for API responses
  - ETag support with 304 responses
  - Request timing and slow query logging
  - Token bucket rate limiting
- `security.py` - Security middleware
