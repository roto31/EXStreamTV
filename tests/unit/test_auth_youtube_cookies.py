"""Unit tests for YouTube cookies upload API."""

import pytest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from exstreamtv.main import create_app


@pytest.fixture
def app():
    """Create test app with mocked DB."""
    from exstreamtv.database.connection import get_db
    from exstreamtv.database.models.base import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    app = create_app()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_youtube_cookies_upload_success(app, temp_dir: Path) -> None:
    """POST /api/auth/youtube/cookies accepts file and returns 200."""
    cookies_path = temp_dir / "youtube_cookies.txt"
    cookies_path.write_text("# Netscape HTTP Cookie File\n.example.com\tTRUE\t/\tFALSE\t0\tname\tvalue\n")

    transport = ASGITransport(app=app)
    with (
        patch("exstreamtv.api.auth._get_youtube_cookies_path", return_value=cookies_path),
        patch("exstreamtv.api.auth._read_write_config_yaml") as mock_write,
        patch("exstreamtv.api.auth.reload_config"),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(cookies_path, "rb") as f:
                response = await client.post(
                    "/api/auth/youtube/cookies",
                    files={"file": ("cookies.txt", f, "text/plain")},
                )

    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "success"
    mock_write.assert_called_once()


@pytest.mark.asyncio
async def test_youtube_cookies_upload_missing_file_returns_422(app) -> None:
    """POST without file returns 422 (FastAPI validation)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/youtube/cookies")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_youtube_cookies_upload_non_txt_returns_400(app, temp_dir: Path) -> None:
    """POST with non-.txt file returns 400."""
    bad_file = temp_dir / "cookies.json"
    bad_file.write_text("{}")

    transport = ASGITransport(app=app)
    with patch("exstreamtv.api.auth._get_youtube_cookies_path"):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with open(bad_file, "rb") as f:
                response = await client.post(
                    "/api/auth/youtube/cookies",
                    files={"file": ("cookies.json", f, "application/json")},
                )

    assert response.status_code == 400
    assert "txt" in response.json().get("detail", "").lower()
