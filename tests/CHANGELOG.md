# Tests Component Changelog

All notable changes to the Tests component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to tests in this release

## [1.5.0] - 2026-01-14
### Added
- **Test Infrastructure**
  - `pytest.ini` - Pytest configuration with markers
  - `conftest.py` - Shared fixtures and async setup

- **Unit Tests**
  - `unit/test_config.py` - Configuration loading tests
  - `unit/test_database_models.py` - SQLAlchemy model tests
  - `unit/test_scanner.py` - File scanner tests
  - `unit/test_libraries.py` - Library abstraction tests
  - `unit/test_log_lifecycle.py` - Log lifecycle tests

- **Integration Tests**
  - `integration/test_api_channels.py` - Channel API tests
  - `integration/test_api_playlists.py` - Playlist API tests
  - `integration/test_api_dashboard.py` - Dashboard API tests

- **End-to-End Tests**
  - `e2e/test_channel_workflow.py` - Full channel creation workflow
  - `e2e/test_health_workflow.py` - Health check and monitoring
  - `e2e/test_streaming_e2e.py` - Streaming E2E tests
  - `e2e/test_webui_pages.py` - WebUI page tests

- **Test Fixtures**
  - `fixtures/factories.py` - Test data factories
  - Various mock responses (Plex, Jellyfin, TMDB)
