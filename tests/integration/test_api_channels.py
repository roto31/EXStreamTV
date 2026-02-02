"""
Integration tests for Channels API.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from exstreamtv.database.models.channel import Channel


@pytest.mark.integration
class TestChannelsAPI:
    """Tests for /api/channels endpoints."""
    
    def test_list_channels_empty(self, client: TestClient):
        """Test listing channels when none exist."""
        response = client.get("/api/channels")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_channels(self, client: TestClient, db: Session):
        """Test listing channels."""
        # Create test channels
        for i in range(3):
            channel = Channel(
                number=i + 1,
                name=f"Channel {i + 1}",
                enabled=True,
            )
            db.add(channel)
        db.commit()
        
        response = client.get("/api/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    def test_create_channel(self, client: TestClient, sample_channel_data: dict):
        """Test creating a channel."""
        response = client.post("/api/channels", json=sample_channel_data)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["name"] == sample_channel_data["name"]
        assert data["number"] == sample_channel_data["number"]
        assert "id" in data
    
    def test_create_channel_duplicate_number(
        self, client: TestClient, sample_channel_data: dict
    ):
        """Test creating channel with duplicate number fails."""
        # Create first channel
        client.post("/api/channels", json=sample_channel_data)
        
        # Try to create second with same number
        response = client.post("/api/channels", json=sample_channel_data)
        
        # Should fail
        assert response.status_code in [400, 409, 422]
    
    def test_get_channel(self, client: TestClient, db: Session):
        """Test getting a single channel."""
        channel = Channel(number=1, name="Test Channel")
        db.add(channel)
        db.commit()
        db.refresh(channel)
        
        response = client.get(f"/api/channels/{channel.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Channel"
    
    def test_get_channel_not_found(self, client: TestClient):
        """Test getting non-existent channel."""
        response = client.get("/api/channels/99999")
        
        assert response.status_code == 404
    
    def test_update_channel(self, client: TestClient, db: Session):
        """Test updating a channel."""
        channel = Channel(number=1, name="Original Name")
        db.add(channel)
        db.commit()
        db.refresh(channel)
        
        update_data = {"name": "Updated Name"}
        response = client.put(f"/api/channels/{channel.id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
    
    def test_delete_channel(self, client: TestClient, db: Session):
        """Test deleting a channel."""
        channel = Channel(number=1, name="To Delete")
        db.add(channel)
        db.commit()
        db.refresh(channel)
        
        response = client.delete(f"/api/channels/{channel.id}")
        
        assert response.status_code in [200, 204]
        
        # Verify deleted
        get_response = client.get(f"/api/channels/{channel.id}")
        assert get_response.status_code == 404


@pytest.mark.integration
class TestChannelsAPIValidation:
    """Tests for channels API input validation."""
    
    def test_create_channel_missing_fields(self, client: TestClient):
        """Test creating channel with missing required fields."""
        response = client.post("/api/channels", json={})
        
        assert response.status_code == 422
    
    def test_create_channel_invalid_number(self, client: TestClient):
        """Test creating channel with invalid number."""
        response = client.post("/api/channels", json={
            "number": -1,
            "name": "Invalid",
        })
        
        assert response.status_code == 422
    
    def test_create_channel_empty_name(self, client: TestClient):
        """Test creating channel with empty name."""
        response = client.post("/api/channels", json={
            "number": 1,
            "name": "",
        })
        
        assert response.status_code == 422
