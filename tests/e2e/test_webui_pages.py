"""
WebUI Page Tests

End-to-end tests to verify all WebUI pages and navigation links work correctly.
These tests should be run whenever the WebUI is changed or updated to ensure
all pages and links resolve to their appropriate destinations.

Run with: pytest tests/e2e/test_webui_pages.py -v
"""

import pytest
from httpx import AsyncClient

from exstreamtv.main import app


# All pages that should return 200 OK
WEBUI_PAGES = [
    # Main navigation
    "/",
    "/dashboard",
    "/player",
    "/guide",
    "/browse",
    "/monitor",
    "/schedule-builder",
    "/channel-editor",
    
    # Channels group
    "/channels",
    "/api/ai/channel",
    "/import",
    "/import-m3u",
    
    # Content group
    "/media",
    "/playlists",
    "/collections",
    "/libraries",
    
    # Scheduling group
    "/playouts",
    "/schedules",
    "/blocks",
    "/templates",
    "/filler-presets",
    "/deco",
    "/schedule-items",
    
    # Integrations group
    "/settings/plex",
    "/settings/media-sources",
    "/api/auth/archive-org",
    "/api/auth/youtube",
    
    # Settings group
    "/settings",
    "/settings/ffmpeg",
    "/settings/hdhr",
    "/settings/hdhomerun",
    "/settings/playout",
    "/settings/quick-launch",
    "/settings/quicklaunch",
    "/settings/security",
    "/settings/watermarks",
    "/settings/resolutions",
    "/settings/ffmpeg-profiles",
    
    # Documentation group
    "/docs",
    "/docs/quick_start",
    "/docs/quick-start",
    "/docs/beginner",
    "/docs/beginner-guide",
    "/docs/navigation",
    "/docs/channel_creation",
    "/docs/installation",
    "/docs/troubleshooting",
    "/troubleshooting",
    
    # System & Debug group
    "/health-check",
    "/health-page",
    "/logs",
    "/plex-logs",
    "/ollama",
    "/ai-troubleshooting",
    "/test-stream",
    
    # API documentation
    "/api/docs",
    "/api/redoc",
    
    # Auth pages
    "/auth/archive",
    "/auth/youtube",
]

# API endpoints that should return 200 OK
API_ENDPOINTS = [
    "/health",
    "/version",
    "/api/health",
    "/iptv/channels.m3u",
    "/iptv/xmltv.xml",
]

# Pages that redirect (should return 307 or end up at 200)
REDIRECT_PAGES = [
    ("/", "/dashboard"),  # Root redirects to dashboard
    ("/settings", "/settings/ffmpeg"),  # Settings redirects to ffmpeg
    ("/health-check", "/health-page"),  # Health-check redirects to health-page
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
class TestWebUIPages:
    """Test that all WebUI pages load successfully."""

    @pytest.mark.parametrize("path", WEBUI_PAGES)
    async def test_webui_page_loads(self, path: str):
        """Test that each WebUI page returns 200 OK."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(path, follow_redirects=True)
            assert response.status_code == 200, f"Page {path} returned {response.status_code}"
            # Verify we got HTML content
            content_type = response.headers.get("content-type", "")
            assert "text/html" in content_type or "application/json" in content_type, \
                f"Page {path} returned unexpected content type: {content_type}"


@pytest.mark.anyio
class TestAPIEndpoints:
    """Test that core API endpoints work correctly."""

    @pytest.mark.parametrize("path", API_ENDPOINTS)
    async def test_api_endpoint_responds(self, path: str):
        """Test that each API endpoint returns 200 OK."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(path, follow_redirects=True)
            assert response.status_code == 200, f"API {path} returned {response.status_code}"


@pytest.mark.anyio
class TestRedirects:
    """Test that redirect pages work correctly."""

    @pytest.mark.parametrize("source,destination", REDIRECT_PAGES)
    async def test_redirect_works(self, source: str, destination: str):
        """Test that redirects work correctly."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # First check without following redirects
            response = await client.get(source, follow_redirects=False)
            assert response.status_code in [200, 301, 302, 303, 307, 308], \
                f"Redirect from {source} returned unexpected status {response.status_code}"
            
            # Then verify final destination
            response = await client.get(source, follow_redirects=True)
            assert response.status_code == 200, \
                f"Final destination for {source} returned {response.status_code}"


@pytest.mark.anyio
class TestNavigationLinks:
    """Test navigation links in base template match defined routes."""

    async def test_sidebar_links_exist(self):
        """Test that all sidebar navigation links resolve to valid pages."""
        # These are all the links from base.html sidebar
        sidebar_links = [
            "/",
            "/player",
            "/channels",
            "/api/ai/channel",
            "/import",
            "/import-m3u",
            "/media",
            "/playlists",
            "/collections",
            "/libraries",
            "/playouts",
            "/schedules",
            "/blocks",
            "/templates",
            "/filler-presets",
            "/deco",
            "/settings/plex",
            "/settings/media-sources",
            "/api/auth/archive-org",
            "/api/auth/youtube",
            "/settings/ffmpeg",
            "/settings/hdhr",
            "/settings/playout",
            "/settings/quick-launch",
            "/docs/quick_start",
            "/docs/beginner",
            "/docs/navigation",
            "/docs/channel_creation",
            "/docs/installation",
            "/docs/troubleshooting",
            "/health-check",
            "/logs",
            "/plex-logs",
            "/ollama",
            "/test-stream",
            "/docs",
            "/api/redoc",
        ]
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            for link in sidebar_links:
                response = await client.get(link, follow_redirects=True)
                assert response.status_code == 200, \
                    f"Sidebar link {link} returned {response.status_code}"

    async def test_quick_access_links_exist(self):
        """Test that quick access menu links resolve to valid pages."""
        quick_access_links = [
            "/channels",
            "/api/ai/channel",
            "/schedules",
            "/import",
            "/iptv/channels.m3u",
            "/iptv/xmltv.xml",
            "/settings",
            "/health-check",
        ]
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            for link in quick_access_links:
                response = await client.get(link, follow_redirects=True)
                assert response.status_code == 200, \
                    f"Quick access link {link} returned {response.status_code}"


@pytest.mark.anyio
class TestContentValidation:
    """Test that pages return expected content."""

    async def test_dashboard_has_content(self):
        """Test that dashboard page contains expected elements."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/dashboard", follow_redirects=True)
            assert response.status_code == 200
            content = response.text
            assert "Dashboard" in content
            assert "EXStreamTV" in content or "StreamTV" in content

    async def test_health_json_endpoint(self):
        """Test that health endpoint returns valid JSON."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health", follow_redirects=True)
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert data["status"] == "healthy"

    async def test_m3u_playlist_format(self):
        """Test that M3U playlist has correct format."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/iptv/channels.m3u", follow_redirects=True)
            assert response.status_code == 200
            content = response.text
            assert content.startswith("#EXTM3U")

    async def test_xmltv_epg_format(self):
        """Test that XMLTV EPG has correct format."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/iptv/xmltv.xml", follow_redirects=True)
            assert response.status_code == 200
            content = response.text
            assert "<?xml" in content
            assert "<tv" in content


# For running tests standalone
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
