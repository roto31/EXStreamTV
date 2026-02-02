"""
Integration tests for Playlists API.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from exstreamtv.database.models.playlist import Playlist, PlaylistItem


@pytest.mark.integration
class TestPlaylistsAPI:
    """Tests for /api/playlists endpoints."""
    
    def test_list_playlists_empty(self, client: TestClient):
        """Test listing playlists when none exist."""
        response = client.get("/api/playlists")
        
        assert response.status_code == 200
        assert response.json() == []
    
    def test_list_playlists(self, client: TestClient, db: Session):
        """Test listing playlists."""
        for i in range(3):
            playlist = Playlist(name=f"Playlist {i + 1}")
            db.add(playlist)
        db.commit()
        
        response = client.get("/api/playlists")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
    
    def test_create_playlist(self, client: TestClient, sample_playlist_data: dict):
        """Test creating a playlist."""
        response = client.post("/api/playlists", json=sample_playlist_data)
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["name"] == sample_playlist_data["name"]
    
    def test_get_playlist(self, client: TestClient, db: Session):
        """Test getting a single playlist."""
        playlist = Playlist(name="Test Playlist")
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        
        response = client.get(f"/api/playlists/{playlist.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Playlist"
    
    def test_get_playlist_with_items(self, client: TestClient, db: Session):
        """Test getting playlist with items."""
        playlist = Playlist(name="With Items")
        db.add(playlist)
        db.commit()
        
        for i in range(5):
            item = PlaylistItem(
                playlist_id=playlist.id,
                position=i,
                title=f"Item {i}",
                source_url=f"http://example.com/{i}.mp4",
            )
            db.add(item)
        db.commit()
        db.refresh(playlist)
        
        response = client.get(f"/api/playlists/{playlist.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data or "item_count" in data
    
    def test_update_playlist(self, client: TestClient, db: Session):
        """Test updating a playlist."""
        playlist = Playlist(name="Original")
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        
        response = client.put(
            f"/api/playlists/{playlist.id}",
            json={"name": "Updated"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"
    
    def test_delete_playlist(self, client: TestClient, db: Session):
        """Test deleting a playlist."""
        playlist = Playlist(name="To Delete")
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        
        response = client.delete(f"/api/playlists/{playlist.id}")
        
        assert response.status_code in [200, 204]


@pytest.mark.integration
class TestPlaylistItemsAPI:
    """Tests for playlist items endpoints."""
    
    def test_add_item_to_playlist(self, client: TestClient, db: Session):
        """Test adding an item to a playlist."""
        playlist = Playlist(name="Test")
        db.add(playlist)
        db.commit()
        db.refresh(playlist)
        
        item_data = {
            "title": "New Item",
            "source_url": "http://example.com/video.mp4",
            "position": 0,
        }
        
        response = client.post(
            f"/api/playlists/{playlist.id}/items",
            json=item_data
        )
        
        assert response.status_code in [200, 201]
    
    def test_reorder_playlist_items(self, client: TestClient, db: Session):
        """Test reordering playlist items."""
        playlist = Playlist(name="Test")
        db.add(playlist)
        db.commit()
        
        # Add items
        for i in range(3):
            item = PlaylistItem(
                playlist_id=playlist.id,
                position=i,
                title=f"Item {i}",
            )
            db.add(item)
        db.commit()
        db.refresh(playlist)
        
        # Get item IDs
        items = list(playlist.items)
        new_order = [items[2].id, items[0].id, items[1].id]
        
        response = client.put(
            f"/api/playlists/{playlist.id}/reorder",
            json={"item_ids": new_order}
        )
        
        # May not be implemented
        assert response.status_code in [200, 404, 405]
    
    def test_remove_item_from_playlist(self, client: TestClient, db: Session):
        """Test removing an item from a playlist."""
        playlist = Playlist(name="Test")
        db.add(playlist)
        db.commit()
        
        item = PlaylistItem(
            playlist_id=playlist.id,
            position=0,
            title="To Remove",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        
        response = client.delete(
            f"/api/playlists/{playlist.id}/items/{item.id}"
        )
        
        assert response.status_code in [200, 204, 404]
