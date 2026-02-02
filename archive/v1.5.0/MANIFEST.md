# EXStreamTV v1.5.0 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Testing Suite (Phase 8)

## Summary

Comprehensive test infrastructure with unit, integration, and end-to-end tests.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Tests | 1.5.0 | Created |

## Test Infrastructure

### Configuration
- `pytest.ini` - Pytest configuration with markers
- `tests/conftest.py` - Shared fixtures and async setup

### Unit Tests
- `tests/unit/test_config.py` - Configuration loading tests
- `tests/unit/test_database_models.py` - SQLAlchemy model tests
- `tests/unit/test_scanner.py` - File scanner tests
- `tests/unit/test_libraries.py` - Library abstraction tests

### Integration Tests
- `tests/integration/test_api_channels.py` - Channel API tests
- `tests/integration/test_api_playlists.py` - Playlist API tests
- `tests/integration/test_api_dashboard.py` - Dashboard API tests

### End-to-End Tests
- `tests/e2e/test_channel_workflow.py` - Full channel creation workflow
- `tests/e2e/test_health_workflow.py` - Health check and monitoring

### Test Fixtures
- `tests/fixtures/factories.py` - Test data factories
- `tests/fixtures/mock_responses/` - Mock API responses (Plex, Jellyfin, TMDB)

## Previous Version

← v1.4.0: macOS App Enhancement

## Next Version

→ v1.6.0: Documentation & Release
