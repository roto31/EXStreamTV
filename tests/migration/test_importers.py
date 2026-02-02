"""
Importer Tests

Tests for ErsatzTV and StreamTV importers.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime


class TestErsatzTVImporter:
    """Test ErsatzTV importer class."""
    
    def test_importer_initialization(self, tmp_path):
        """Test importer can be initialized."""
        from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
        
        db_path = tmp_path / "ersatztv.db"
        db_path.touch()
        
        importer = ErsatzTVImporter(db_path, dry_run=True)
        
        assert importer.source_db_path == db_path
        assert importer.dry_run is True
        assert importer.stats.channels == 0
    
    def test_validate_missing_database(self, tmp_path):
        """Test validation fails for missing database."""
        from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
        
        db_path = tmp_path / "nonexistent.db"
        
        importer = ErsatzTVImporter(db_path)
        result = importer.validate()
        
        assert result.is_valid is False
        assert any("not found" in err.lower() for err in result.errors)
    
    def test_validate_empty_database(self, tmp_path):
        """Test validation of empty database."""
        from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
        
        db_path = tmp_path / "ersatztv.db"
        conn = sqlite3.connect(str(db_path))
        conn.close()
        
        importer = ErsatzTVImporter(db_path)
        result = importer.validate()
        
        # Should still be valid but with warnings about missing tables
        assert result.is_valid is True
        assert len(result.warnings) > 0
    
    def test_validate_with_tables(self, tmp_path):
        """Test validation of database with expected tables."""
        from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
        
        db_path = tmp_path / "ersatztv.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create expected tables
        cursor.execute("CREATE TABLE Channels (Id INTEGER PRIMARY KEY, Number TEXT, Name TEXT)")
        cursor.execute("CREATE TABLE FFmpegProfiles (Id INTEGER PRIMARY KEY, Name TEXT)")
        cursor.execute("CREATE TABLE Playouts (Id INTEGER PRIMARY KEY, ChannelId INTEGER)")
        cursor.execute("CREATE TABLE ProgramSchedules (Id INTEGER PRIMARY KEY, Name TEXT)")
        
        # Add some data
        cursor.execute("INSERT INTO Channels VALUES (1, '1', 'Test Channel')")
        cursor.execute("INSERT INTO FFmpegProfiles VALUES (1, 'Default')")
        
        conn.commit()
        conn.close()
        
        importer = ErsatzTVImporter(db_path)
        result = importer.validate()
        
        assert result.is_valid is True
        assert result.counts.get("channels", 0) == 1
        assert result.counts.get("ffmpegprofiles", 0) == 1
    
    def test_migration_stats_to_dict(self):
        """Test MigrationStats conversion to dictionary."""
        from exstreamtv.importers.ersatztv_importer import MigrationStats
        
        stats = MigrationStats()
        stats.channels = 10
        stats.playouts = 5
        stats.errors = 1
        
        stats_dict = stats.to_dict()
        
        assert stats_dict["channels"] == 10
        assert stats_dict["playouts"] == 5
        assert stats_dict["errors"] == 1
    
    def test_id_maps_initialization(self, tmp_path):
        """Test that ID maps are properly initialized."""
        from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
        
        db_path = tmp_path / "ersatztv.db"
        db_path.touch()
        
        importer = ErsatzTVImporter(db_path)
        
        assert "ffmpeg_profiles" in importer.id_maps
        assert "channels" in importer.id_maps
        assert "playouts" in importer.id_maps
        assert "decos" in importer.id_maps


class TestStreamTVImporter:
    """Test StreamTV importer class."""
    
    def test_importer_initialization(self, tmp_path):
        """Test importer can be initialized."""
        from exstreamtv.importers.streamtv_importer import StreamTVImporter
        
        db_path = tmp_path / "streamtv.db"
        db_path.touch()
        
        importer = StreamTVImporter(db_path, dry_run=True)
        
        assert importer.source_db_path == db_path
        assert importer.dry_run is True
        assert importer.stats.channels == 0
    
    def test_validate_missing_database(self, tmp_path):
        """Test validation fails for missing database."""
        from exstreamtv.importers.streamtv_importer import StreamTVImporter
        
        db_path = tmp_path / "nonexistent.db"
        
        importer = StreamTVImporter(db_path)
        result = importer.validate()
        
        assert result["is_valid"] is False
        assert any("not found" in err.lower() for err in result["errors"])
    
    def test_validate_with_tables(self, tmp_path):
        """Test validation of database with expected tables."""
        from exstreamtv.importers.streamtv_importer import StreamTVImporter
        
        db_path = tmp_path / "streamtv.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create expected tables
        cursor.execute("CREATE TABLE channels (id INTEGER PRIMARY KEY, name TEXT, number TEXT)")
        cursor.execute("CREATE TABLE playlists (id INTEGER PRIMARY KEY, name TEXT)")
        cursor.execute("CREATE TABLE media_items (id INTEGER PRIMARY KEY, title TEXT)")
        
        # Add some data
        cursor.execute("INSERT INTO channels VALUES (1, 'Test Channel', '1')")
        cursor.execute("INSERT INTO playlists VALUES (1, 'Test Playlist')")
        
        conn.commit()
        conn.close()
        
        importer = StreamTVImporter(db_path)
        result = importer.validate()
        
        assert result["is_valid"] is True
        assert result["counts"].get("channels", 0) == 1
        assert result["counts"].get("playlists", 0) == 1
    
    def test_migration_stats_to_dict(self):
        """Test StreamTVMigrationStats conversion to dictionary."""
        from exstreamtv.importers.streamtv_importer import StreamTVMigrationStats
        
        stats = StreamTVMigrationStats()
        stats.channels = 5
        stats.playlists = 10
        stats.youtube_sources = 100
        
        stats_dict = stats.to_dict()
        
        assert stats_dict["channels"] == 5
        assert stats_dict["playlists"] == 10
        assert stats_dict["youtube_sources"] == 100
    
    def test_id_maps_initialization(self, tmp_path):
        """Test that ID maps are properly initialized."""
        from exstreamtv.importers.streamtv_importer import StreamTVImporter
        
        db_path = tmp_path / "streamtv.db"
        db_path.touch()
        
        importer = StreamTVImporter(db_path)
        
        assert "channels" in importer.id_maps
        assert "playlists" in importer.id_maps
        assert "media_items" in importer.id_maps


class TestErsatzTVValidator:
    """Test ErsatzTV validator."""
    
    def test_validator_initialization(self, tmp_path):
        """Test validator can be initialized."""
        from exstreamtv.importers.validators import ErsatzTVValidator
        
        db_path = tmp_path / "ersatztv.db"
        
        validator = ErsatzTVValidator(db_path)
        
        assert validator.db_path == db_path
    
    def test_validate_source_missing_file(self, tmp_path):
        """Test validation of missing source file."""
        from exstreamtv.importers.validators import ErsatzTVValidator
        
        db_path = tmp_path / "missing.db"
        
        validator = ErsatzTVValidator(db_path)
        result = validator.validate_source()
        
        assert result.is_valid is False
        assert len(result.errors) > 0
    
    def test_validate_source_with_database(self, tmp_path):
        """Test validation of valid database."""
        from exstreamtv.importers.validators import ErsatzTVValidator
        
        db_path = tmp_path / "ersatztv.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create minimal tables
        cursor.execute("CREATE TABLE Channels (Id INTEGER PRIMARY KEY, Number TEXT, Name TEXT)")
        cursor.execute("INSERT INTO Channels VALUES (1, '1', 'Test')")
        
        conn.commit()
        conn.close()
        
        validator = ErsatzTVValidator(db_path)
        result = validator.validate_source()
        
        assert result.is_valid is True
        assert "channels" in result.counts


class TestIntegration:
    """Integration tests for migration workflow."""
    
    def test_full_ersatztv_validation_workflow(self, tmp_path):
        """Test complete ErsatzTV validation workflow."""
        from exstreamtv.importers.ersatztv_importer import ErsatzTVImporter
        
        # Create a mock ErsatzTV database
        db_path = tmp_path / "ersatztv.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create tables with realistic structure
        cursor.execute("""
            CREATE TABLE Channels (
                Id INTEGER PRIMARY KEY,
                UniqueId TEXT,
                Number TEXT,
                Name TEXT,
                FFmpegProfileId INTEGER,
                StreamingMode INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE FFmpegProfiles (
                Id INTEGER PRIMARY KEY,
                Name TEXT,
                HardwareAccelerationKind INTEGER,
                VideoFormat INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE Playouts (
                Id INTEGER PRIMARY KEY,
                ChannelId INTEGER,
                ProgramScheduleId INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE ProgramSchedules (
                Id INTEGER PRIMARY KEY,
                Name TEXT
            )
        """)
        
        # Add test data
        cursor.execute("INSERT INTO FFmpegProfiles VALUES (1, 'Default', 0, 0)")
        cursor.execute("INSERT INTO Channels VALUES (1, 'uuid-1', '1', 'Channel One', 1, 0)")
        cursor.execute("INSERT INTO ProgramSchedules VALUES (1, 'Daily Schedule')")
        cursor.execute("INSERT INTO Playouts VALUES (1, 1, 1)")
        
        conn.commit()
        conn.close()
        
        # Run validation
        importer = ErsatzTVImporter(db_path, dry_run=True)
        result = importer.validate()
        
        assert result.is_valid is True
        assert result.counts.get("channels", 0) == 1
        assert result.counts.get("ffmpegprofiles", 0) == 1
        assert result.counts.get("playouts", 0) == 1
    
    def test_full_streamtv_validation_workflow(self, tmp_path):
        """Test complete StreamTV validation workflow."""
        from exstreamtv.importers.streamtv_importer import StreamTVImporter
        
        # Create a mock StreamTV database
        db_path = tmp_path / "streamtv.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE channels (
                id INTEGER PRIMARY KEY,
                name TEXT,
                number TEXT,
                enabled INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE playlists (
                id INTEGER PRIMARY KEY,
                name TEXT,
                description TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE media_items (
                id INTEGER PRIMARY KEY,
                title TEXT,
                source TEXT,
                url TEXT
            )
        """)
        
        # Add test data
        cursor.execute("INSERT INTO channels VALUES (1, 'Test Channel', '1', 1)")
        cursor.execute("INSERT INTO playlists VALUES (1, 'Test Playlist', 'Description')")
        cursor.execute("INSERT INTO media_items VALUES (1, 'Test Video', 'youtube', 'https://...')")
        
        conn.commit()
        conn.close()
        
        # Run validation
        importer = StreamTVImporter(db_path, dry_run=True)
        result = importer.validate()
        
        assert result["is_valid"] is True
        assert result["counts"].get("channels", 0) == 1
        assert result["counts"].get("playlists", 0) == 1
        assert result["counts"].get("media_items", 0) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
