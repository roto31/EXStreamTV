"""
Unit tests for log lifecycle management.

Tests truncation, archiving, and deletion functionality.
"""

import asyncio
import gzip
from datetime import datetime, timedelta
from pathlib import Path

import pytest


class TestLogLifecycleManager:
    """Tests for LogLifecycleManager."""

    @pytest.fixture
    def log_setup(self, tmp_path):
        """Set up log directories and files."""
        log_dir = tmp_path / "logs"
        archive_dir = tmp_path / "archive"
        log_dir.mkdir(exist_ok=True)

        return {
            "log_dir": log_dir,
            "archive_dir": archive_dir,
            "tmp_path": tmp_path,
        }

    def test_initialization(self, log_setup):
        """Test manager initialization."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager

        manager = LogLifecycleManager(
            log_directories=[log_setup["log_dir"]],
            max_file_size_mb=10,
            archive_after_days=7,
            delete_after_days=30,
            archive_directory=log_setup["archive_dir"],
        )

        assert manager.max_file_size_bytes == 10 * 1024 * 1024
        assert manager.archive_after_days == 7
        assert manager.delete_after_days == 30

    @pytest.mark.asyncio
    async def test_truncation(self, log_setup):
        """Test log file truncation."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager

        log_dir = log_setup["log_dir"]

        # Create a "large" log file (>1KB for testing)
        log_file = log_dir / "large.log"
        content = "X" * 2000  # 2KB of content
        log_file.write_text(content)

        manager = LogLifecycleManager(
            log_directories=[log_dir],
            max_file_size_mb=0.001,  # 1KB threshold for testing
            archive_directory=log_setup["archive_dir"],
        )

        result = await manager.check_and_truncate_logs()

        assert str(log_file) in result["truncated"]
        # File should be smaller now
        assert log_file.stat().st_size < 2000

    def test_lifecycle_status(self, log_setup):
        """Test getting lifecycle status."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager

        log_dir = log_setup["log_dir"]

        # Create some log files
        (log_dir / "app.log").write_text("Application log content")
        (log_dir / "error.log").write_text("Error log content")

        manager = LogLifecycleManager(
            log_directories=[log_dir],
            archive_directory=log_setup["archive_dir"],
        )

        status = manager.get_lifecycle_status()

        assert len(status["active_logs"]) == 2
        assert status["total_active_size_mb"] > 0
        assert "config" in status

    @pytest.mark.asyncio
    async def test_archive_old_logs(self, log_setup):
        """Test archiving old log files."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager
        import os
        import time

        log_dir = log_setup["log_dir"]
        archive_dir = log_setup["archive_dir"]

        # Create an "old" log file
        old_log = log_dir / "old.log"
        old_log.write_text("Old log content that should be archived")

        # Set modification time to 10 days ago
        old_time = time.time() - (10 * 24 * 60 * 60)
        os.utime(old_log, (old_time, old_time))

        manager = LogLifecycleManager(
            log_directories=[log_dir],
            archive_after_days=7,
            archive_directory=archive_dir,
        )

        result = await manager.archive_old_logs()

        assert len(result["archived"]) == 1
        assert archive_dir.exists()
        # Check archive file exists
        archive_files = list(archive_dir.glob("*.log.gz"))
        assert len(archive_files) == 1

    @pytest.mark.asyncio
    async def test_delete_old_archives(self, log_setup):
        """Test deleting old archive files."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager
        import os
        import time

        archive_dir = log_setup["archive_dir"]
        archive_dir.mkdir(exist_ok=True)

        # Create an "old" archive file
        old_archive = archive_dir / "old_20231215.log.gz"
        with gzip.open(old_archive, "wt") as f:
            f.write("Old archived content")

        # Set modification time to 40 days ago
        old_time = time.time() - (40 * 24 * 60 * 60)
        os.utime(old_archive, (old_time, old_time))

        manager = LogLifecycleManager(
            log_directories=[log_setup["log_dir"]],
            delete_after_days=30,
            archive_directory=archive_dir,
        )

        result = await manager.delete_old_archives()

        assert len(result["deleted"]) == 1
        assert not old_archive.exists()


class TestBrowserLogCapture:
    """Tests for BrowserLogCapture."""

    def test_initialization_creates_directory(self, tmp_path):
        """Test that initialization creates parent directory."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "subdir" / "browser.log"
        logger = BrowserLogCapture(log_file)

        assert log_file.parent.exists()

    def test_log_multiple_error_types(self, tmp_path):
        """Test logging different error types."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        # Log different error types
        logger.log_error(error_type="error", message="JS Error")
        logger.log_error(error_type="promise", message="Promise rejection")
        logger.log_error(error_type="network", message="Network error")

        errors = logger.get_recent_errors(10)
        assert len(errors) == 3

        error_types = [e["type"] for e in errors]
        assert "error" in error_types
        assert "promise" in error_types
        assert "network" in error_types

    def test_get_errors_for_troubleshooting(self, tmp_path):
        """Test formatting errors for AI troubleshooting."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        # Log some errors
        for i in range(5):
            logger.log_error(error_type="error", message=f"Test error {i}")

        context = logger.get_errors_for_troubleshooting()

        assert "Browser Console Errors" in context
        assert "Test error" in context

    def test_empty_log_handling(self, tmp_path):
        """Test handling empty log file."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        # Don't log anything
        errors = logger.get_recent_errors(10)
        assert len(errors) == 0

        context = logger.get_errors_for_troubleshooting()
        assert "No recent browser errors found" in context


class TestLoggingSetup:
    """Tests for logging_setup module."""

    def test_setup_logging_basic(self, tmp_path):
        """Test basic logging setup."""
        import logging
        from exstreamtv.utils.logging_setup import setup_logging

        log_file = tmp_path / "test.log"

        logger = setup_logging(
            log_level="DEBUG",
            log_file_name=str(log_file),
            log_to_console=False,
            log_to_file=True,
        )

        assert logger is not None
        assert logger.level == logging.DEBUG

    def test_setup_logging_with_format(self, tmp_path):
        """Test logging setup with custom format."""
        from exstreamtv.utils.logging_setup import setup_logging

        log_file = tmp_path / "test.log"

        logger = setup_logging(
            log_level="INFO",
            log_file_name=str(log_file),
            log_format="%(levelname)s - %(message)s",
        )

        # Log a test message
        logger.info("Test message")

        # Check the format in the file
        content = log_file.read_text()
        assert "INFO" in content
        assert "Test message" in content

    def test_get_logger(self):
        """Test get_logger function."""
        from exstreamtv.utils.logging_setup import get_logger

        logger = get_logger("test.module")
        assert logger.name == "test.module"
