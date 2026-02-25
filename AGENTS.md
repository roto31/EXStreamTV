# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

EXStreamTV is a unified IPTV streaming platform (Python/FastAPI backend on port 8411, SQLite database, FFmpeg for transcoding). The macOS Swift app (`EXStreamTVApp/`) cannot be built on Linux. See `README.md` for full feature list.

### Running the server

```bash
python3 -m exstreamtv
```

Server starts on port 8411. If `config.yaml` doesn't exist, copy from `config.example.yaml`. The server uses SQLite (file-based at `./exstreamtv.db`), so no external database is needed.

### Running tests

```bash
# Unit + AI tests (fast, reliable)
pytest tests/unit/ tests/ai/ -v

# Single test file
pytest tests/unit/test_config.py -v
```

**Known issue:** Integration and E2E tests (`tests/integration/`, `tests/e2e/`) hang indefinitely due to pre-existing async fixture compatibility issues with the installed `pytest-asyncio` version. Avoid running the full `pytest tests/` suite without scoping to specific directories.

The `tests/ai/test_unified_troubleshooting.py::TestTroubleshootingService` class also fails (pre-existing) due to a missing `exstreamtv.services` module reference.

### Linting

```bash
ruff check exstreamtv/
black --check exstreamtv/
```

Both tools have pre-existing findings in the codebase. `ruff` config is in `pyproject.toml`.

### API

- Swagger UI: `http://localhost:8411/api/docs`
- Health check: `GET /health`
- Channels API: `POST /api/channels` (note: `number` field is a string, not int)

### Gotchas

- The `channel.number` field in the API expects a **string**, not an integer.
- `$HOME/.local/bin` must be on `PATH` for tools like `ruff`, `black`, `pytest` to be found.
- The `timeout` config in `pytest.ini` requires `pytest-timeout` which is not in the dev dependencies; the warning is harmless.
