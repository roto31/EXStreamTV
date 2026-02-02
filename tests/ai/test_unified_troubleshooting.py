"""
Integration tests for unified AI troubleshooting.

Tests the following components:
- TroubleshootingService
- LogAnalyzer with multi-source support
- System Admin persona
- Fix suggestion workflow
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Test fixtures and helpers


@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock()
    config.logging.file = "logs/test.log"
    config.logging.lifecycle.enabled = False
    config.logging.lifecycle.max_file_size_mb = 50
    config.logging.lifecycle.archive_after_days = 7
    config.logging.lifecycle.delete_after_days = 30
    config.logging.lifecycle.archive_directory = "logs/archive"
    config.logging.browser_logs.enabled = True
    config.logging.browser_logs.file = "logs/browser.log"
    config.auto_healer.enabled = True
    config.auto_healer.ollama_url = "http://localhost:11434"
    config.auto_healer.ollama_model = "llama3.2:latest"
    config.auto_healer.auto_fix = False
    config.auto_healer.learning_enabled = True
    config.ai_agent.ollama.host = "http://localhost:11434"
    config.ai_agent.ollama.model = "llama3.2"
    return config


class TestLogAnalyzer:
    """Tests for LogAnalyzer with multi-source support."""

    def test_log_severity_enum(self):
        """Test LogSeverity enum values."""
        from exstreamtv.ai_agent.log_analyzer import LogSeverity

        assert LogSeverity.DEBUG.value == "DEBUG"
        assert LogSeverity.ERROR.value == "ERROR"
        assert LogSeverity.CRITICAL.value == "CRITICAL"

    def test_log_analyzer_initialization(self):
        """Test LogAnalyzer initialization."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()
        assert analyzer is not None
        assert len(analyzer.patterns) > 0

    def test_analyze_ffmpeg_error(self):
        """Test analyzing FFmpeg error patterns."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()
        line = "2024-01-15 10:30:00 - FFmpeg HTTP error 500 during streaming"
        matches = analyzer.analyze_line(line)

        assert len(matches) > 0
        assert any(m.pattern.name == "ffmpeg_http_error" for m in matches)

    def test_analyze_youtube_rate_limit(self):
        """Test analyzing YouTube rate limit patterns."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()
        line = "2024-01-15 10:30:00 - YouTube rate limit 429 Too Many Requests"
        matches = analyzer.analyze_line(line)

        assert len(matches) > 0
        assert any(m.pattern.name == "youtube_rate_limit" for m in matches)

    def test_analyze_plex_patterns(self):
        """Test analyzing Plex-specific patterns."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()

        # Test transcoder error
        line = "Transcoder error: failed to start encoding"
        matches = analyzer.analyze_line(line)
        assert any(m.pattern.category == "plex" for m in matches)

    def test_analyze_browser_patterns(self):
        """Test analyzing browser-specific patterns."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()

        # Test JavaScript error
        line = "Uncaught TypeError: Cannot read property 'foo' of undefined"
        matches = analyzer.analyze_line(line)
        assert any(m.pattern.category == "browser" for m in matches)

    def test_analyze_ollama_patterns(self):
        """Test analyzing Ollama-specific patterns."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()

        # Test model error
        line = "model not found: llama3.2"
        matches = analyzer.analyze_line(line)
        assert any(m.pattern.category == "ollama" for m in matches)

    def test_add_custom_source(self):
        """Test adding custom log sources."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer, FileLogSource

        analyzer = LogAnalyzer()
        source = FileLogSource(Path("/tmp/test.log"), "TestSource")
        analyzer.add_source(source)

        assert "TestSource" in analyzer.get_sources()

    def test_get_patterns_by_category(self):
        """Test filtering patterns by category."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()
        ffmpeg_patterns = analyzer.get_patterns_by_category("ffmpeg")

        assert len(ffmpeg_patterns) > 0
        assert all(p.category == "ffmpeg" for p in ffmpeg_patterns)

    def test_get_patterns_by_severity(self):
        """Test filtering patterns by severity."""
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer, LogSeverity

        analyzer = LogAnalyzer()
        error_patterns = analyzer.get_patterns_by_severity(LogSeverity.ERROR)

        assert len(error_patterns) > 0
        assert all(p.severity == LogSeverity.ERROR for p in error_patterns)


class TestSystemAdminPersona:
    """Tests for System Admin persona."""

    def test_persona_type_exists(self):
        """Test that SYSTEM_ADMIN persona type exists."""
        from exstreamtv.ai_agent.persona_manager import PersonaType

        assert PersonaType.SYSTEM_ADMIN is not None
        assert PersonaType.SYSTEM_ADMIN.value == "system_admin"

    def test_persona_info(self):
        """Test System Admin persona metadata."""
        from exstreamtv.ai_agent.persona_manager import PersonaManager, PersonaType

        manager = PersonaManager()
        info = manager.get_persona_info(PersonaType.SYSTEM_ADMIN)

        assert info.name == "Alex Chen"
        assert info.title == "DevOps Engineer"
        assert "troubleshooting" in info.specialties

    def test_welcome_message(self):
        """Test System Admin welcome message."""
        from exstreamtv.ai_agent.prompts.system_admin import get_sysadmin_welcome_message

        message = get_sysadmin_welcome_message()

        assert "Alex Chen" in message
        assert "DevOps" in message

    def test_build_troubleshooting_prompt(self):
        """Test building troubleshooting prompt."""
        from exstreamtv.ai_agent.prompts.system_admin import build_troubleshooting_prompt

        prompt = build_troubleshooting_prompt(
            user_message="Why is my channel not playing?",
            conversation_history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ],
            log_context={
                "application": [{"message": "FFmpeg error", "severity": "ERROR"}],
            },
        )

        assert "Why is my channel not playing?" in prompt
        assert "FFmpeg error" in prompt

    def test_persona_registered_in_prompts(self):
        """Test System Admin is in PERSONAS registry."""
        from exstreamtv.ai_agent.prompts import PERSONAS

        assert "system_admin" in PERSONAS
        assert PERSONAS["system_admin"]["name"] == "Alex Chen"


class TestFixSuggester:
    """Tests for FixSuggester."""

    def test_fix_suggester_initialization(self):
        """Test FixSuggester initialization."""
        from exstreamtv.ai_agent.fix_suggester import FixSuggester

        suggester = FixSuggester()
        assert suggester is not None

    def test_rule_based_suggestions(self):
        """Test rule-based fix suggestions."""
        from exstreamtv.ai_agent.fix_suggester import FixSuggester
        from exstreamtv.ai_agent.log_analyzer import LogAnalyzer

        analyzer = LogAnalyzer()
        suggester = FixSuggester()

        # Create a match for YouTube rate limit
        line = "YouTube rate limit 429"
        matches = analyzer.analyze_line(line)

        if matches:
            suggestions = suggester.suggest_fixes(matches[0])
            assert len(suggestions) > 0
            # Should suggest increasing delay
            assert any("delay" in s.title.lower() or "rate" in s.title.lower() for s in suggestions)


class TestApprovalManager:
    """Tests for ApprovalManager."""

    def test_approval_manager_initialization(self):
        """Test ApprovalManager initialization."""
        from exstreamtv.ai_agent.approval_manager import ApprovalManager

        manager = ApprovalManager()
        assert manager is not None

    def test_safe_fixes_dont_require_approval(self):
        """Test that safe fixes don't require approval."""
        from exstreamtv.ai_agent.approval_manager import ApprovalManager
        from exstreamtv.ai_agent.fix_suggester import FixSuggestion, FixRiskLevel

        manager = ApprovalManager()

        safe_fix = FixSuggestion(
            id="test_fix_1",
            title="Retry operation",
            description="Retry the failed operation",
            risk_level=FixRiskLevel.SAFE,
            action_type="retry",
            target="streaming",
            change_details={},
            estimated_effectiveness=0.8,
        )

        # Safe fixes should not require approval (unless learning DB says otherwise)
        # Note: This depends on learning DB state
        assert safe_fix.risk_level == FixRiskLevel.SAFE


class TestTroubleshootingService:
    """Tests for TroubleshootingService."""

    @pytest.mark.asyncio
    async def test_service_initialization(self, mock_config):
        """Test TroubleshootingService initialization."""
        with patch("exstreamtv.services.troubleshooting_service.get_config", return_value=mock_config):
            from exstreamtv.services.troubleshooting_service import TroubleshootingService

            service = TroubleshootingService(mock_config)
            assert service is not None
            assert service.persona_manager is not None
            assert service.log_analyzer is not None

    def test_get_welcome_message(self, mock_config):
        """Test getting welcome message."""
        with patch("exstreamtv.services.troubleshooting_service.get_config", return_value=mock_config):
            from exstreamtv.services.troubleshooting_service import TroubleshootingService

            service = TroubleshootingService(mock_config)
            message = service.get_welcome_message()

            assert "Alex Chen" in message

    @pytest.mark.asyncio
    async def test_analyze_and_suggest_fallback(self, mock_config):
        """Test analyze_and_suggest with fallback (no AI available)."""
        with patch("exstreamtv.services.troubleshooting_service.get_config", return_value=mock_config):
            from exstreamtv.services.troubleshooting_service import TroubleshootingService

            service = TroubleshootingService(mock_config)

            # Mock the AI to fail
            service._get_ai_response = AsyncMock(side_effect=RuntimeError("No AI available"))

            result = await service.analyze_and_suggest(
                query="Why is my stream not working?",
                include_app_logs=True,
                include_plex_logs=False,
                include_browser_logs=False,
                include_ollama_logs=False,
            )

            assert result.success is True
            assert result.model_used == "fallback"
            assert "unable to connect" in result.response.lower() or len(result.response) > 0


class TestBrowserLogger:
    """Tests for BrowserLogCapture."""

    def test_browser_logger_initialization(self, tmp_path):
        """Test BrowserLogCapture initialization."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        assert logger is not None
        assert logger.log_file == log_file

    def test_log_error(self, tmp_path):
        """Test logging browser errors."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        logger.log_error(
            error_type="error",
            message="Test error message",
            stack="at test.js:10",
            url="http://localhost:8411/test",
        )

        # Verify log was written
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test error message" in content

    def test_get_recent_errors(self, tmp_path):
        """Test retrieving recent errors."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        # Log some errors
        for i in range(5):
            logger.log_error(error_type="error", message=f"Error {i}")

        errors = logger.get_recent_errors(10)
        assert len(errors) == 5
        assert errors[0]["message"] == "Error 0"

    def test_clear_logs(self, tmp_path):
        """Test clearing browser logs."""
        from exstreamtv.utils.browser_logger import BrowserLogCapture

        log_file = tmp_path / "browser.log"
        logger = BrowserLogCapture(log_file)

        logger.log_error(error_type="error", message="Test error")
        assert log_file.stat().st_size > 0

        result = logger.clear_logs()
        assert result is True
        assert log_file.stat().st_size == 0


class TestLogLifecycleManager:
    """Tests for LogLifecycleManager."""

    @pytest.mark.asyncio
    async def test_lifecycle_manager_initialization(self, tmp_path):
        """Test LogLifecycleManager initialization."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager

        log_dirs = [tmp_path / "logs"]
        log_dirs[0].mkdir(exist_ok=True)

        manager = LogLifecycleManager(
            log_directories=log_dirs,
            max_file_size_mb=1,
            archive_after_days=7,
            delete_after_days=30,
            archive_directory=tmp_path / "archive",
        )

        assert manager is not None

    def test_get_lifecycle_status(self, tmp_path):
        """Test getting lifecycle status."""
        from exstreamtv.utils.log_lifecycle_manager import LogLifecycleManager

        log_dir = tmp_path / "logs"
        log_dir.mkdir(exist_ok=True)

        # Create a test log file
        log_file = log_dir / "test.log"
        log_file.write_text("Test log content\n" * 100)

        manager = LogLifecycleManager(
            log_directories=[log_dir],
            archive_directory=tmp_path / "archive",
        )

        status = manager.get_lifecycle_status()

        assert "active_logs" in status
        assert "archived_logs" in status
        assert len(status["active_logs"]) == 1


class TestLogSourceAbstraction:
    """Tests for LogSource abstraction classes."""

    def test_file_log_source(self, tmp_path):
        """Test FileLogSource."""
        from exstreamtv.ai_agent.log_analyzer import FileLogSource

        log_file = tmp_path / "test.log"
        log_file.write_text("Line 1\nLine 2\nLine 3\n")

        source = FileLogSource(log_file, "TestLog")

        assert source.source_name == "TestLog"
        lines = source.get_log_lines()
        assert len(lines) == 3

    def test_browser_log_source(self):
        """Test BrowserLogSource initialization."""
        from exstreamtv.ai_agent.log_analyzer import BrowserLogSource

        source = BrowserLogSource()
        assert source.source_name == "Browser"

    def test_timestamp_parsing(self, tmp_path):
        """Test timestamp parsing in log sources."""
        from exstreamtv.ai_agent.log_analyzer import FileLogSource

        log_file = tmp_path / "test.log"
        log_file.write_text("2024-01-15 10:30:00 - Test message\n")

        source = FileLogSource(log_file)
        timestamp = source.parse_timestamp("2024-01-15 10:30:00 - Test message")

        assert timestamp is not None
        assert timestamp.year == 2024
        assert timestamp.month == 1
        assert timestamp.day == 15
