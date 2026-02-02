"""
End-to-end tests for health and status workflows.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestHealthWorkflow:
    """End-to-end tests for health checks."""
    
    def test_application_startup(self, client: TestClient):
        """Test that application starts and responds to health check."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_version_endpoint(self, client: TestClient):
        """Test version information endpoint."""
        response = client.get("/version")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "version" in data
        assert "app" in data
        assert data["app"] == "EXStreamTV"
    
    def test_api_docs_available(self, client: TestClient):
        """Test that API docs are accessible."""
        response = client.get("/api/docs")
        
        # Should redirect or return docs
        assert response.status_code in [200, 307, 308]
    
    def test_openapi_schema(self, client: TestClient):
        """Test that OpenAPI schema is available."""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data


@pytest.mark.e2e
class TestAppStartupSequence:
    """Tests for application startup sequence."""
    
    def test_database_connection(self, client: TestClient, db):
        """Test that database is properly connected."""
        # If we can list channels, DB is working
        response = client.get("/api/channels")
        
        assert response.status_code == 200
    
    def test_all_routers_registered(self, client: TestClient):
        """Test that all expected routers are registered."""
        # Check key endpoints exist
        endpoints = [
            "/api/channels",
            "/api/playlists",
            "/api/dashboard/stats",
            "/health",
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            # Should not be 404 (route not found)
            assert response.status_code != 404, f"Endpoint {endpoint} not found"
