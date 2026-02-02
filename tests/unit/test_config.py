"""
Unit tests for configuration module.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from exstreamtv.config import (
    EXStreamTVConfig,
    ServerConfig,
    DatabaseConfig,
    LoggingConfig,
    FFmpegConfig,
    get_config,
    load_config,
)


@pytest.mark.unit
class TestServerConfig:
    """Tests for ServerConfig."""
    
    def test_default_values(self):
        """Test default server configuration values."""
        config = ServerConfig()
        
        assert config.host == "0.0.0.0"
        assert config.port == 8411
        assert config.debug is False
        assert config.log_level == "INFO"
    
    def test_custom_values(self):
        """Test custom server configuration."""
        config = ServerConfig(
            host="127.0.0.1",
            port=9000,
            debug=True,
            log_level="DEBUG"
        )
        
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.debug is True
        assert config.log_level == "DEBUG"
    
    def test_port_validation(self):
        """Test port number validation."""
        # Valid ports
        config = ServerConfig(port=80)
        assert config.port == 80
        
        config = ServerConfig(port=65535)
        assert config.port == 65535


@pytest.mark.unit
class TestDatabaseConfig:
    """Tests for DatabaseConfig."""
    
    def test_default_sqlite(self):
        """Test default SQLite configuration."""
        config = DatabaseConfig()
        
        assert "sqlite" in config.url.lower()
    
    def test_custom_url(self):
        """Test custom database URL."""
        config = DatabaseConfig(url="postgresql://user:pass@localhost/db")
        
        assert "postgresql" in config.url


@pytest.mark.unit
class TestLoggingConfig:
    """Tests for LoggingConfig."""
    
    def test_default_values(self):
        """Test default logging configuration."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert "%(asctime)s" in config.format
    
    def test_custom_level(self):
        """Test custom log level."""
        config = LoggingConfig(level="DEBUG")
        
        assert config.level == "DEBUG"


@pytest.mark.unit
class TestFFmpegConfig:
    """Tests for FFmpegConfig."""
    
    def test_default_values(self):
        """Test default FFmpeg configuration."""
        config = FFmpegConfig()
        
        assert config.path == "ffmpeg"
        assert config.ffprobe_path == "ffprobe"
    
    def test_custom_paths(self):
        """Test custom FFmpeg paths."""
        config = FFmpegConfig(
            path="/usr/local/bin/ffmpeg",
            ffprobe_path="/usr/local/bin/ffprobe"
        )
        
        assert config.path == "/usr/local/bin/ffmpeg"
        assert config.ffprobe_path == "/usr/local/bin/ffprobe"


@pytest.mark.unit
class TestEXStreamTVConfig:
    """Tests for main EXStreamTVConfig class."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = EXStreamTVConfig()
        
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.ffmpeg, FFmpegConfig)
    
    def test_nested_config(self):
        """Test nested configuration access."""
        config = EXStreamTVConfig(
            server=ServerConfig(port=9000),
            database=DatabaseConfig(url="sqlite:///test.db")
        )
        
        assert config.server.port == 9000
        assert "test.db" in config.database.url


@pytest.mark.unit
class TestGetConfig:
    """Tests for config loading functions."""
    
    def test_get_config_returns_config(self):
        """Test that get_config returns an EXStreamTVConfig instance."""
        config = get_config()
        
        assert isinstance(config, EXStreamTVConfig)
    
    def test_get_config_caching(self):
        """Test that get_config returns cached config."""
        config1 = get_config()
        config2 = get_config()
        
        # Should return same instance (cached)
        assert config1 is config2
    
    def test_load_config_creates_new_instance(self):
        """Test that load_config creates a new config."""
        config = load_config()
        
        assert isinstance(config, EXStreamTVConfig)
        assert config.server.port == 8411
