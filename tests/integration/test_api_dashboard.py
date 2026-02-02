"""
Integration tests for Dashboard API.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from exstreamtv.database.models.channel import Channel
from exstreamtv.database.models.playlist import Playlist
from exstreamtv.database.models.library import LocalLibrary


@pytest.mark.integration
class TestDashboardAPI:
    """Tests for /api/dashboard endpoints."""
    
    def test_get_dashboard_stats(self, client: TestClient):
        """Test getting dashboard statistics."""
        response = client.get("/api/dashboard/stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "quick_stats" in data
        assert "system_info" in data
        assert "resource_usage" in data
        assert "active_streams" in data
    
    def test_get_quick_stats(self, client: TestClient, db: Session):
        """Test getting quick stats."""
        # Create some test data
        for i in range(3):
            db.add(Channel(number=i + 1, name=f"Channel {i}"))
        for i in range(2):
            db.add(Playlist(name=f"Playlist {i}"))
        db.commit()
        
        response = client.get("/api/dashboard/quick-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        
        # Find channels stat
        channel_stat = next(
            (s for s in data if s.get("label") == "Channels"),
            None
        )
        if channel_stat:
            assert channel_stat["value"] == 3 or channel_stat["value"] == "3"
    
    def test_get_system_info(self, client: TestClient):
        """Test getting system information."""
        response = client.get("/api/dashboard/system-info")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "hostname" in data
        assert "platform" in data
        assert "python_version" in data
        assert "cpu_count" in data
        assert "memory_total_gb" in data
    
    def test_get_resource_usage(self, client: TestClient):
        """Test getting resource usage."""
        response = client.get("/api/dashboard/resource-usage")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "cpu_percent" in data
        assert "memory_percent" in data
        assert "disk_percent" in data
        
        # Values should be between 0 and 100
        assert 0 <= data["cpu_percent"] <= 100
        assert 0 <= data["memory_percent"] <= 100
    
    def test_get_active_streams(self, client: TestClient):
        """Test getting active streams."""
        response = client.get("/api/dashboard/active-streams")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_get_activity_feed(self, client: TestClient):
        """Test getting activity feed."""
        response = client.get("/api/dashboard/activity")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_get_activity_with_limit(self, client: TestClient):
        """Test getting activity with limit."""
        response = client.get("/api/dashboard/activity?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 5
    
    def test_get_library_stats(self, client: TestClient, db: Session):
        """Test getting library statistics."""
        # Create a library
        library = LocalLibrary(
            name="Test Library",
            path="/media/movies",
            library_type="movie",
            item_count=100,
        )
        db.add(library)
        db.commit()
        
        response = client.get("/api/dashboard/library-stats")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "local" in data or "total_libraries" in data
    
    def test_get_stream_history(self, client: TestClient):
        """Test getting stream history for charts."""
        response = client.get("/api/dashboard/stream-history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "hourly_viewers" in data or "daily_streams" in data


@pytest.mark.integration
class TestDashboardResourceMonitoring:
    """Tests for dashboard resource monitoring."""
    
    def test_resource_usage_reasonable_values(self, client: TestClient):
        """Test that resource values are reasonable."""
        response = client.get("/api/dashboard/resource-usage")
        data = response.json()
        
        # CPU should be a valid percentage
        assert isinstance(data["cpu_percent"], (int, float))
        assert data["cpu_percent"] >= 0
        
        # Memory should be positive
        assert data["memory_used_gb"] >= 0
        
        # Disk should be positive
        assert data["disk_used_gb"] >= 0
    
    def test_system_info_not_empty(self, client: TestClient):
        """Test that system info fields are not empty."""
        response = client.get("/api/dashboard/system-info")
        data = response.json()
        
        assert data["hostname"] != ""
        assert data["platform"] != ""
        assert data["python_version"] != ""
        assert data["cpu_count"] > 0
