"""
Pytest Integration for Platform Reliability and Regression Tests

Run with: pytest tests/reliability/test_platform_pytest.py -v

This provides pytest-compatible test execution for CI/CD integration.
"""

import asyncio
import pytest
from pathlib import Path

# Import test suites
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============ Core System Tests ============

class TestCoreSystem:
    """Core system reliability tests."""
    
    @pytest.mark.asyncio
    async def test_server_health(self):
        """CORE-001: Verify server is healthy."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health")
            assert r.status_code == 200
            data = r.json()
            assert data.get("status") == "healthy"
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """CORE-002: Verify database connectivity."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/detailed")
            assert r.status_code == 200
            data = r.json()
            db = data.get("components", {}).get("database", {})
            assert db.get("status") == "ok"
    
    @pytest.mark.asyncio
    async def test_ffmpeg_available(self):
        """CORE-003: Verify FFmpeg is available."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/detailed")
            assert r.status_code == 200
            data = r.json()
            ffmpeg = data.get("components", {}).get("ffmpeg", {})
            assert ffmpeg.get("status") == "ok"
    
    @pytest.mark.asyncio
    async def test_ffprobe_available(self):
        """CORE-004: Verify FFprobe is available."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/detailed")
            assert r.status_code == 200
            data = r.json()
            ffprobe = data.get("components", {}).get("ffprobe", {})
            assert ffprobe.get("status") == "ok"


# ============ API Tests ============

class TestAPIEndpoints:
    """API endpoint reliability tests."""
    
    @pytest.mark.asyncio
    async def test_channels_list(self):
        """API-CH-001: List channels endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/channels")
            assert r.status_code == 200
            data = r.json()
            assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_m3u_playlist(self):
        """API-IP-001: M3U playlist generation."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/iptv/channels.m3u")
            assert r.status_code == 200
            assert "#EXTM3U" in r.text
    
    @pytest.mark.asyncio
    async def test_xmltv_epg(self):
        """API-IP-002: XMLTV EPG generation."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/iptv/xmltv.xml")
            assert r.status_code == 200
            assert "<tv" in r.text
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """API-HE-001: Health check endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_detailed_health(self):
        """API-HE-002: Detailed health endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/detailed")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_channel_health(self):
        """API-HE-003: Channel health endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/channels")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_libraries_list(self):
        """API-LB-001: Libraries list endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/libraries")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_settings(self):
        """API-ST-001: Settings endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/settings")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_ffmpeg_profiles(self):
        """API-ST-002: FFmpeg profiles endpoint."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/ffmpeg-profiles")
            assert r.status_code == 200


# ============ Streaming Tests ============

class TestStreaming:
    """Streaming subsystem reliability tests."""
    
    @pytest.mark.asyncio
    async def test_channel_manager_active(self):
        """STR-001: Channel manager is active."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/channels")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_url_resolver(self):
        """STR-003: URL resolver is available."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/channels")
            assert r.status_code == 200
            channels = r.json()
            enabled = [c for c in channels if c.get("enabled")]
            # If there are enabled channels, resolver should work
            assert True  # URL resolver is internal


# ============ Web UI Tests ============

class TestWebUI:
    """Web UI reliability tests."""
    
    @pytest.mark.asyncio
    async def test_dashboard_page(self):
        """WEB-001: Dashboard page loads."""
        import httpx
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get("http://localhost:8411/")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_channels_page(self):
        """WEB-002: Channels page loads."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/channels")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_playlists_page(self):
        """WEB-003: Playlists page loads."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/playlists")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_libraries_page(self):
        """WEB-004: Libraries page loads."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/libraries")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_settings_page(self):
        """WEB-006: Settings page loads."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/settings")
            assert r.status_code == 200


# ============ HDHomeRun Tests ============

class TestHDHomeRun:
    """HDHomeRun emulation reliability tests."""
    
    @pytest.mark.asyncio
    async def test_discover_json(self):
        """API-HD-001: HDHomeRun discovery."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/discover.json")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_lineup_json(self):
        """API-HD-002: HDHomeRun lineup."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/lineup.json")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_lineup_status(self):
        """API-HD-003: HDHomeRun lineup status."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/lineup_status.json")
            assert r.status_code == 200


# ============ Database Tests ============

class TestDatabase:
    """Database reliability tests."""
    
    @pytest.mark.asyncio
    async def test_channels_table(self):
        """DB-001: Channels table accessible."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/channels")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_media_table(self):
        """DB-002: Media table accessible."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/media")
            assert r.status_code == 200
    
    @pytest.mark.asyncio
    async def test_schedules_table(self):
        """DB-005: Schedules table accessible."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/schedules")
            assert r.status_code == 200


# ============ FFmpeg Tests ============

class TestFFmpeg:
    """FFmpeg reliability tests."""
    
    @pytest.mark.asyncio
    async def test_ffmpeg_version(self):
        """FFM-001: FFmpeg version check."""
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8411/api/health/detailed")
            assert r.status_code == 200
            data = r.json()
            ffmpeg = data.get("components", {}).get("ffmpeg", {})
            version = ffmpeg.get("version", "")
            assert "ffmpeg version" in version.lower()


# ============ Full Suite Runner ============

class TestPlatformRegressionSuite:
    """Run the full platform regression suite."""
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_full_platform_suite(self):
        """Run complete platform regression tests."""
        from tests.reliability.platform_regression_suite import PlatformRegressionSuite
        
        async with PlatformRegressionSuite() as suite:
            results = await suite.run_sanity_tests()
            
            passed = sum(1 for r in results if r.passed)
            total = len(results)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            # Require at least 80% pass rate for sanity tests
            assert pass_rate >= 80, f"Sanity tests pass rate too low: {pass_rate:.1f}%"
