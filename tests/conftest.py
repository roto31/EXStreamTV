"""
EXStreamTV Test Configuration

Shared fixtures and configuration for all tests.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from exstreamtv.database.models.base import Base
from exstreamtv.database.connection import get_db
from exstreamtv.main import create_app


# ============ Database Fixtures ============


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine (in-memory SQLite)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine) -> Generator[Session, None, None]:
    """Create a new database session for each test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def db(db_session: Session) -> Generator[Session, None, None]:
    """Alias for db_session."""
    yield db_session


# ============ FastAPI Test Client Fixtures ============


@pytest.fixture(scope="function")
def app(db_session: Session) -> FastAPI:
    """Create a test FastAPI application."""
    app = create_app()
    
    # Override the database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    return app


@pytest.fixture(scope="function")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create a synchronous test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


# ============ Temporary File Fixtures ============


@pytest.fixture(scope="function")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="function")
def temp_media_file(temp_dir: Path) -> Path:
    """Create a temporary media file for testing."""
    media_file = temp_dir / "test_video.mp4"
    # Create a minimal valid file (not a real video)
    media_file.write_bytes(b"\x00" * 1024)
    return media_file


@pytest.fixture(scope="function")
def temp_config_file(temp_dir: Path) -> Path:
    """Create a temporary config file."""
    config_file = temp_dir / "config.yaml"
    config_content = """
server:
  host: "127.0.0.1"
  port: 8411
  debug: true
  
database:
  url: "sqlite:///:memory:"
  
logging:
  level: "DEBUG"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""
    config_file.write_text(config_content)
    return config_file


# ============ Mock Fixtures ============


@pytest.fixture
def mock_ffprobe() -> Generator[MagicMock, None, None]:
    """Mock FFprobe for testing without actual FFmpeg."""
    with patch("exstreamtv.media.scanner.ffprobe.FFprobeAnalyzer") as mock:
        analyzer = MagicMock()
        analyzer.analyze = AsyncMock(return_value=MagicMock(
            format="mp4",
            duration=3600.0,
            size=1024 * 1024 * 100,
            bitrate=2000000,
            video_streams=[MagicMock(
                codec="h264",
                width=1920,
                height=1080,
                frame_rate=30.0,
                bit_depth=8,
            )],
            audio_streams=[MagicMock(
                codec="aac",
                channels=2,
                sample_rate=48000,
                language="eng",
            )],
            subtitle_streams=[],
        ))
        mock.return_value = analyzer
        yield mock


@pytest.fixture
def mock_plex_server() -> Generator[MagicMock, None, None]:
    """Mock Plex server for testing."""
    with patch("exstreamtv.media.libraries.plex.PlexServer") as mock:
        server = MagicMock()
        server.library.sections.return_value = [
            MagicMock(
                key="1",
                title="Movies",
                type="movie",
                totalSize=100,
            ),
            MagicMock(
                key="2", 
                title="TV Shows",
                type="show",
                totalSize=50,
            ),
        ]
        mock.return_value = server
        yield mock


@pytest.fixture
def mock_httpx() -> Generator[MagicMock, None, None]:
    """Mock httpx for network requests."""
    with patch("httpx.AsyncClient") as mock:
        client = AsyncMock()
        client.get = AsyncMock()
        client.post = AsyncMock()
        mock.return_value.__aenter__ = AsyncMock(return_value=client)
        mock.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock


# ============ Sample Data Fixtures ============


@pytest.fixture
def sample_channel_data() -> dict:
    """Sample channel data for testing."""
    return {
        "number": 1,
        "name": "Test Channel",
        "logo_url": "https://example.com/logo.png",
        "group": "Entertainment",
        "enabled": True,
    }


@pytest.fixture
def sample_playlist_data() -> dict:
    """Sample playlist data for testing."""
    return {
        "name": "Test Playlist",
        "description": "A test playlist",
        "is_enabled": True,
    }


@pytest.fixture
def sample_media_item_data() -> dict:
    """Sample media item data for testing."""
    return {
        "title": "Test Movie",
        "media_type": "movie",
        "year": 2024,
        "duration": 7200,
        "library_source": "local",
        "library_id": 1,
    }


@pytest.fixture
def sample_library_data() -> dict:
    """Sample library data for testing."""
    return {
        "name": "Test Library",
        "path": "/media/movies",
        "library_type": "movie",
        "is_enabled": True,
        "file_extensions": [".mp4", ".mkv", ".avi"],
    }


# ============ Environment Fixtures ============


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables for each test."""
    # Save current environment
    original_env = os.environ.copy()
    
    # Remove EXStreamTV-specific vars
    for key in list(os.environ.keys()):
        if key.startswith("EXSTREAMTV_"):
            del os.environ[key]
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables."""
    env_vars = {
        "EXSTREAMTV_PORT": "8411",
        "EXSTREAMTV_DEBUG": "true",
        "EXSTREAMTV_DB_URL": "sqlite:///:memory:",
    }
    with patch.dict(os.environ, env_vars):
        yield env_vars


# ============ Async Event Loop ============


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============ Markers ============


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "ffmpeg: FFmpeg required")
    config.addinivalue_line("markers", "network: Network access required")
