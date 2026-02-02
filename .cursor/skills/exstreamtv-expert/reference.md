# EXStreamTV Codebase Reference

Use this when you need a detailed map of modules and how changes propagate.

## Python Backend (`exstreamtv/`)

| Module | Role | Change impact |
|--------|------|----------------|
| `api/` | REST and IPTV (M3U/EPG) routes. Entry point for clients. | Changing routes or response shape affects all API consumers (web UI, EXStreamTVApp, IPTV players). |
| `database/` | SQLAlchemy models, migrations (Alembic). | Schema or model changes may need migrations; any code that queries these models is affected. |
| `streaming/` | Channel manager, MPEG-TS streamer, resolvers (Plex, Jellyfin, local, Archive.org, YouTube). | Core to playback; changes can break tuning or stream resolution. |
| `playout/` | Program builder, scheduler, filler, state. | Affects what plays and when. |
| `scheduling/` | Schedule rules and logic. | Tightly coupled to playout; changes can alter program lineup. |
| `ffmpeg/`, `transcoding/` | Encoding, decoding, hardware acceleration, FFmpeg pipeline. | Affects stream quality and compatibility. |
| `metadata/` | Providers (TMDB, TVDB, etc.), extractors, enrichment. | Affects guide and metadata in UI/EPG. |
| `media/` | Libraries (Plex, Jellyfin, local), providers, scanner. | Affects library sync and media resolution. |
| `middleware/` | Request/response middleware. | Cross-cutting; changes affect all API requests. |
| `config.py`, `constants.py` | App config and shared constants. | Consumers across the codebase; keep backward compatibility or update all usages. |
| `main.py`, `__main__.py` | App entry and startup. | Changes can affect startup, CLI, or server lifecycle. |

## macOS App (`EXStreamTVApp/`)

- Swift/SwiftUI: status bar, dashboard, settings, channel switcher, player.
- Talks to backend via REST API; respects config and URLs from the server.
- Changing API contracts or config keys used by the app requires updating the app and/or backend defaults.

## Tests (`tests/`)

- `conftest.py`: Shared fixtures (DB, app, mocks).
- `unit/`: Fast, isolated unit tests.
- `integration/`: Tests that may use DB or external services.
- `e2e/`: Full-stack or workflow tests.
- `reliability/`, `migration/`: Regression and migration tests.
- `pytest.ini`: Markers `unit`, `integration`, `e2e`, `slow`, `ffmpeg`, `network`; discovery under `tests/`.

When you change a module, run the tests that cover it (e.g. same name under `tests/` or `tests/unit/`) and the full suite before concluding nothing is broken.

## Verification Commands

```bash
# Lint
ruff check exstreamtv/ tests/ --output-format=concise

# Unit + integration (no e2e/slow)
pytest tests/unit/ tests/integration/ -v

# By marker
pytest -m "not e2e and not slow" -v

# Full suite
pytest tests/ -v
```

## Architecture Doc

High-level design and data flow: `docs/architecture/SYSTEM_DESIGN.md`.
