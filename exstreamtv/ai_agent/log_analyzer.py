"""
Real-time log parsing and pattern detection.

Provides unified log source abstraction for analyzing logs from multiple sources:
- EXStreamTV application logs
- Plex Media Server logs
- Browser console logs
- Ollama AI logs
"""

import contextlib
import logging
import re
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from re import Pattern
from typing import Any

logger = logging.getLogger(__name__)


class LogSeverity(Enum):
    """Log severity levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(ABC):
    """Abstract base class for log sources."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable source name."""
        pass

    @abstractmethod
    def get_log_lines(self, from_position: int = 0) -> list[tuple[str, int]]:
        """
        Return (line, position) tuples from the log source.

        Args:
            from_position: Start position in the log

        Returns:
            List of (line_content, new_position) tuples
        """
        pass

    @abstractmethod
    def parse_timestamp(self, line: str) -> datetime | None:
        """
        Extract timestamp from log line.

        Args:
            line: Log line to parse

        Returns:
            Extracted datetime or None
        """
        pass


class FileLogSource(LogSource):
    """Log source from a file."""

    def __init__(self, file_path: Path, name: str | None = None):
        self._file_path = file_path
        self._name = name or file_path.stem
        self._last_position = 0

    @property
    def source_name(self) -> str:
        return self._name

    @property
    def file_path(self) -> Path:
        return self._file_path

    def get_log_lines(self, from_position: int = 0) -> list[tuple[str, int]]:
        if not self._file_path.exists():
            return []

        lines = []
        try:
            with open(self._file_path, encoding="utf-8", errors="ignore") as f:
                f.seek(from_position)
                for line in f:
                    lines.append((line.strip(), f.tell()))
                self._last_position = f.tell()
        except Exception as e:
            logger.error(f"Error reading {self._file_path}: {e}")

        return lines

    def parse_timestamp(self, line: str) -> datetime | None:
        """Default timestamp parsing for standard log format."""
        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})", line)
        if timestamp_match:
            try:
                return datetime.strptime(timestamp_match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                with contextlib.suppress(ValueError):
                    return datetime.strptime(timestamp_match.group(1), "%Y-%m-%dT%H:%M:%S")
        return None


class ApplicationLogSource(FileLogSource):
    """EXStreamTV application logs."""

    def __init__(self, file_path: Path | None = None):
        if file_path is None:
            from exstreamtv.config import get_config

            config = get_config()
            file_path = Path(config.logging.file)
        super().__init__(file_path, "EXStreamTV")


class PlexLogSource(FileLogSource):
    """Plex Media Server logs."""

    def __init__(self, file_path: Path | None = None):
        if file_path is None:
            # Auto-detect Plex logs directory
            from exstreamtv.api.logs import get_plex_logs_directory, get_plex_log_files

            logs_dir = get_plex_logs_directory()
            if logs_dir:
                log_files = get_plex_log_files()
                if log_files:
                    file_path = log_files[0]  # Most recent
        if file_path is None:
            file_path = Path("/dev/null")  # Fallback
        super().__init__(file_path, "Plex Media Server")

    def parse_timestamp(self, line: str) -> datetime | None:
        """Parse Plex log timestamp format: [YYYY-MM-DD HH:MM:SS.mmm]."""
        timestamp_match = re.match(
            r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]", line
        )
        if timestamp_match:
            try:
                ts_str = timestamp_match.group(1)
                if "." in ts_str:
                    return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
                return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return None


class OllamaLogSource(FileLogSource):
    """Ollama server logs."""

    def __init__(self, file_path: Path | None = None):
        if file_path is None:
            from exstreamtv.api.logs import get_ollama_logs_directory

            logs_dir = get_ollama_logs_directory()
            if logs_dir:
                log_files = list(logs_dir.glob("*.log"))
                if log_files:
                    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                    file_path = log_files[0]
        if file_path is None:
            file_path = Path("/dev/null")
        super().__init__(file_path, "Ollama")

    def parse_timestamp(self, line: str) -> datetime | None:
        """Parse Ollama JSON log timestamp."""
        try:
            if line.strip().startswith("{"):
                import json

                data = json.loads(line)
                ts = data.get("time") or data.get("timestamp")
                if ts:
                    # ISO format
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            pass
        return super().parse_timestamp(line)


class BrowserLogSource(LogSource):
    """Browser console logs from API."""

    def __init__(self):
        self._name = "Browser"

    @property
    def source_name(self) -> str:
        return self._name

    def get_log_lines(self, from_position: int = 0) -> list[tuple[str, int]]:
        """Get browser log lines from the browser logger."""
        try:
            from exstreamtv.utils.browser_logger import get_browser_logger

            browser_logger = get_browser_logger()
            errors = browser_logger.get_recent_errors(100)

            lines = []
            for i, error in enumerate(errors[from_position:], start=from_position):
                line = f"[{error.get('timestamp', '')}] {error.get('type', 'ERROR').upper()} - {error.get('message', '')}"
                lines.append((line, i + 1))

            return lines
        except Exception as e:
            logger.error(f"Error reading browser logs: {e}")
            return []

    def parse_timestamp(self, line: str) -> datetime | None:
        """Parse browser log timestamp."""
        timestamp_match = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
        if timestamp_match:
            try:
                return datetime.fromisoformat(timestamp_match.group(1))
            except ValueError:
                pass
        return None


@dataclass
class LogPattern:
    """Pattern for matching log entries."""

    name: str
    pattern: Pattern[str]
    severity: LogSeverity
    category: str  # e.g., "authentication", "streaming", "ffmpeg", "youtube", "archive_org"
    description: str
    action_required: bool = False
    priority: int = 5  # 1-10, higher is more urgent


@dataclass
class LogMatch:
    """A matched log entry."""

    pattern: LogPattern
    timestamp: datetime
    message: str
    context: dict[str, Any]
    line_number: int | None = None


class LogAnalyzer:
    """Analyze logs in real-time for error patterns from multiple sources."""

    def __init__(self, log_file: Path | None = None):
        """
        Initialize log analyzer.

        Args:
            log_file: Path to log file (if None, uses default from config).
        """
        self.log_file = log_file
        self.patterns: list[LogPattern] = []
        self._load_default_patterns()
        self._last_position: int = 0
        self._match_callbacks: list[Callable[[LogMatch], None]] = []
        self._sources: dict[str, LogSource] = {}

    def _load_default_patterns(self) -> None:
        """Load default error patterns."""
        # FFmpeg errors
        self.patterns.extend([
            LogPattern(
                name="ffmpeg_http_error",
                pattern=re.compile(r"FFmpeg.*HTTP error (\d+)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="ffmpeg",
                description="FFmpeg HTTP error",
                action_required=True,
                priority=8,
            ),
            LogPattern(
                name="ffmpeg_timeout",
                pattern=re.compile(r"FFmpeg.*timeout|timed out", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="ffmpeg",
                description="FFmpeg timeout",
                action_required=True,
                priority=7,
            ),
            LogPattern(
                name="ffmpeg_demux_error",
                pattern=re.compile(
                    r"FFmpeg.*demux.*error|Unable to find a valid device",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.ERROR,
                category="ffmpeg",
                description="FFmpeg demuxing error",
                action_required=True,
                priority=8,
            ),
        ])

        # YouTube errors
        self.patterns.extend([
            LogPattern(
                name="youtube_rate_limit",
                pattern=re.compile(
                    r"YouTube.*rate limit|429|Too Many Requests",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.WARNING,
                category="youtube",
                description="YouTube rate limit",
                action_required=True,
                priority=7,
            ),
            LogPattern(
                name="youtube_auth_error",
                pattern=re.compile(
                    r"YouTube.*(?:401|403|Unauthorized|Forbidden)",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.ERROR,
                category="youtube",
                description="YouTube authentication error",
                action_required=True,
                priority=9,
            ),
            LogPattern(
                name="youtube_format_unavailable",
                pattern=re.compile(
                    r"Requested format is not available|no streamable formats",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.ERROR,
                category="youtube",
                description="YouTube format unavailable",
                action_required=True,
                priority=6,
            ),
        ])

        # Archive.org errors
        self.patterns.extend([
            LogPattern(
                name="archive_org_500",
                pattern=re.compile(
                    r"Archive\.org.*(?:500|Internal Server Error)",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.ERROR,
                category="archive_org",
                description="Archive.org 500 error",
                action_required=True,
                priority=7,
            ),
            LogPattern(
                name="archive_org_403",
                pattern=re.compile(r"Archive\.org.*(?:403|Forbidden)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="archive_org",
                description="Archive.org 403 error",
                action_required=True,
                priority=8,
            ),
            LogPattern(
                name="archive_org_cdn_error",
                pattern=re.compile(
                    r"Archive\.org.*CDN.*(?:error|failed|unavailable)",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.WARNING,
                category="archive_org",
                description="Archive.org CDN error",
                action_required=True,
                priority=6,
            ),
        ])

        # Streaming errors
        self.patterns.extend([
            LogPattern(
                name="cannot_tune_channel",
                pattern=re.compile(
                    r"cannot tune channel|Could not tune channel",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.ERROR,
                category="streaming",
                description="Channel tuning failure",
                action_required=True,
                priority=9,
            ),
            LogPattern(
                name="stream_startup_delay",
                pattern=re.compile(
                    r"stream.*startup.*delay|took.*seconds to start",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.WARNING,
                category="streaming",
                description="Stream startup delay",
                action_required=False,
                priority=5,
            ),
        ])

        # Authentication errors
        self.patterns.extend([
            LogPattern(
                name="cookie_error",
                pattern=re.compile(
                    r"cookie.*(?:error|failed|invalid|expired|not found)",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.WARNING,
                category="authentication",
                description="Cookie error",
                action_required=True,
                priority=7,
            ),
            LogPattern(
                name="auth_required",
                pattern=re.compile(
                    r"API key required|authentication required|access_token not set",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.WARNING,
                category="authentication",
                description="Authentication required",
                action_required=False,
                priority=4,
            ),
        ])

        # Network errors
        self.patterns.extend([
            LogPattern(
                name="network_timeout",
                pattern=re.compile(
                    r"network.*timeout|connection.*timeout|timed out",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.ERROR,
                category="network",
                description="Network timeout",
                action_required=True,
                priority=6,
            ),
            LogPattern(
                name="connection_refused",
                pattern=re.compile(r"connection.*refused|Connection refused", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="network",
                description="Connection refused",
                action_required=True,
                priority=7,
            ),
        ])

        # Validation errors
        self.patterns.append(
            LogPattern(
                name="yaml_validation_error",
                pattern=re.compile(
                    r"YAML.*validation.*(?:error|failed|invalid)",
                    re.IGNORECASE,
                ),
                severity=LogSeverity.WARNING,
                category="validation",
                description="YAML validation error",
                action_required=False,
                priority=5,
            )
        )

        # Plex patterns
        self.patterns.extend([
            LogPattern(
                name="plex_transcoder_error",
                pattern=re.compile(r"Transcoder.*(?:error|failed)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="plex",
                description="Plex transcoder error",
                action_required=True,
                priority=8,
            ),
            LogPattern(
                name="plex_playback_error",
                pattern=re.compile(r"Playback.*(?:error|failed)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="plex",
                description="Plex playback error",
                action_required=True,
                priority=8,
            ),
            LogPattern(
                name="plex_database_error",
                pattern=re.compile(r"(?:database|sqlite).*(?:error|corrupt|locked)", re.IGNORECASE),
                severity=LogSeverity.CRITICAL,
                category="plex",
                description="Plex database error",
                action_required=True,
                priority=9,
            ),
            LogPattern(
                name="plex_library_scan_error",
                pattern=re.compile(r"(?:library|scan).*(?:error|failed)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="plex",
                description="Plex library scan error",
                action_required=True,
                priority=6,
            ),
        ])

        # Browser patterns
        self.patterns.extend([
            LogPattern(
                name="browser_js_error",
                pattern=re.compile(r"Uncaught.*Error|TypeError|ReferenceError", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="browser",
                description="Browser JavaScript error",
                action_required=True,
                priority=7,
            ),
            LogPattern(
                name="browser_network_error",
                pattern=re.compile(r"Failed to fetch|NetworkError|net::ERR", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="browser",
                description="Browser network error",
                action_required=True,
                priority=7,
            ),
            LogPattern(
                name="browser_promise_rejection",
                pattern=re.compile(r"Unhandled.*rejection|Promise.*reject", re.IGNORECASE),
                severity=LogSeverity.WARNING,
                category="browser",
                description="Unhandled promise rejection",
                action_required=False,
                priority=5,
            ),
        ])

        # Ollama patterns
        self.patterns.extend([
            LogPattern(
                name="ollama_model_error",
                pattern=re.compile(r"model.*(?:not found|failed|error)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="ollama",
                description="Ollama model error",
                action_required=True,
                priority=8,
            ),
            LogPattern(
                name="ollama_memory_error",
                pattern=re.compile(r"out of memory|CUDA.*error|GPU.*error", re.IGNORECASE),
                severity=LogSeverity.CRITICAL,
                category="ollama",
                description="Ollama memory/GPU error",
                action_required=True,
                priority=9,
            ),
            LogPattern(
                name="ollama_connection_error",
                pattern=re.compile(r"connection.*(?:refused|failed|timeout)", re.IGNORECASE),
                severity=LogSeverity.ERROR,
                category="ollama",
                description="Ollama connection error",
                action_required=True,
                priority=7,
            ),
        ])

    def add_pattern(self, pattern: LogPattern) -> None:
        """Add a custom log pattern."""
        self.patterns.append(pattern)

    def analyze_line(self, line: str, line_number: int | None = None) -> list[LogMatch]:
        """
        Analyze a single log line.

        Returns:
            List of LogMatch objects for patterns that matched.
        """
        matches = []

        # Extract timestamp if present
        timestamp = datetime.now()
        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})", line)
        if timestamp_match:
            try:
                timestamp = datetime.strptime(timestamp_match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                with contextlib.suppress(ValueError):
                    timestamp = datetime.strptime(
                        timestamp_match.group(1), "%Y-%m-%dT%H:%M:%S"
                    )

        # Check against all patterns
        for pattern in self.patterns:
            match = pattern.pattern.search(line)
            if match:
                context: dict[str, Any] = {
                    "groups": match.groups(),
                    "groupdict": match.groupdict(),
                    "full_match": match.group(0),
                }

                # Extract HTTP status code if present
                if "http" in line.lower() or "error" in line.lower():
                    status_match = re.search(r"\b(\d{3})\b", line)
                    if status_match:
                        context["status_code"] = int(status_match.group(1))

                matches.append(
                    LogMatch(
                        pattern=pattern,
                        timestamp=timestamp,
                        message=line.strip(),
                        context=context,
                        line_number=line_number,
                    )
                )

        # Notify callbacks
        for match in matches:
            for callback in self._match_callbacks:
                try:
                    callback(match)
                except Exception as e:
                    logger.error(f"Error in log match callback: {e}", exc_info=True)

        return matches

    def analyze_file(
        self,
        file_path: Path | None = None,
        from_position: int | None = None,
    ) -> list[LogMatch]:
        """
        Analyze log file from a specific position.

        Args:
            file_path: Path to log file (uses self.log_file if None).
            from_position: Start position in file (uses last position if None).

        Returns:
            List of LogMatch objects.
        """
        if file_path is None:
            file_path = self.log_file

        if file_path is None or not file_path.exists():
            return []

        if from_position is None:
            from_position = self._last_position

        matches = []

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                f.seek(from_position)

                line_number = 0
                for line in f:
                    line_number += 1
                    line_matches = self.analyze_line(line, line_number)
                    matches.extend(line_matches)

                self._last_position = f.tell()

        except Exception as e:
            logger.error(f"Error analyzing log file: {e}", exc_info=True)

        return matches

    def add_match_callback(self, callback: Callable[[LogMatch], None]) -> None:
        """Add callback for log matches."""
        self._match_callbacks.append(callback)

    def remove_match_callback(self, callback: Callable[[LogMatch], None]) -> None:
        """Remove match callback."""
        if callback in self._match_callbacks:
            self._match_callbacks.remove(callback)

    def get_patterns_by_category(self, category: str) -> list[LogPattern]:
        """Get all patterns for a category."""
        return [p for p in self.patterns if p.category == category]

    def get_patterns_by_severity(self, severity: LogSeverity) -> list[LogPattern]:
        """Get all patterns for a severity level."""
        return [p for p in self.patterns if p.severity == severity]

    def add_source(self, source: LogSource) -> None:
        """
        Add a log source for analysis.

        Args:
            source: LogSource instance to add
        """
        self._sources[source.source_name] = source
        logger.debug(f"Added log source: {source.source_name}")

    def remove_source(self, source_name: str) -> bool:
        """
        Remove a log source.

        Args:
            source_name: Name of source to remove

        Returns:
            True if removed, False if not found
        """
        if source_name in self._sources:
            del self._sources[source_name]
            return True
        return False

    def get_sources(self) -> dict[str, LogSource]:
        """Get all registered log sources."""
        return self._sources.copy()

    def analyze_all_sources(self) -> list[LogMatch]:
        """
        Analyze all registered log sources.

        Returns:
            List of LogMatch objects from all sources
        """
        all_matches: list[LogMatch] = []

        for source_name, source in self._sources.items():
            try:
                lines = source.get_log_lines()
                for line, position in lines:
                    matches = self.analyze_line(line, position)
                    # Tag matches with source
                    for match in matches:
                        match.context["source"] = source_name
                    all_matches.extend(matches)
            except Exception as e:
                logger.error(f"Error analyzing source {source_name}: {e}")

        # Sort by priority (highest first)
        all_matches.sort(key=lambda m: m.pattern.priority, reverse=True)

        return all_matches

    def get_context_for_troubleshooting(
        self,
        include_app: bool = True,
        include_plex: bool = True,
        include_browser: bool = True,
        include_ollama: bool = True,
        max_matches_per_source: int = 20,
    ) -> dict[str, list[LogMatch]]:
        """
        Get categorized log matches for AI troubleshooting.

        Args:
            include_app: Include EXStreamTV application logs
            include_plex: Include Plex logs
            include_browser: Include browser logs
            include_ollama: Include Ollama logs
            max_matches_per_source: Maximum matches per source

        Returns:
            Dict of source name to list of matches
        """
        results: dict[str, list[LogMatch]] = {}

        if include_app:
            try:
                app_source = ApplicationLogSource()
                lines = app_source.get_log_lines()
                matches = []
                for line, pos in lines[-500:]:  # Last 500 lines
                    matches.extend(self.analyze_line(line, pos))
                results["application"] = matches[:max_matches_per_source]
            except Exception as e:
                logger.warning(f"Error analyzing application logs: {e}")

        if include_plex:
            try:
                plex_source = PlexLogSource()
                if plex_source.file_path.exists():
                    lines = plex_source.get_log_lines()
                    matches = []
                    for line, pos in lines[-500:]:
                        matches.extend(self.analyze_line(line, pos))
                    results["plex"] = matches[:max_matches_per_source]
            except Exception as e:
                logger.warning(f"Error analyzing Plex logs: {e}")

        if include_browser:
            try:
                browser_source = BrowserLogSource()
                lines = browser_source.get_log_lines()
                matches = []
                for line, pos in lines:
                    matches.extend(self.analyze_line(line, pos))
                results["browser"] = matches[:max_matches_per_source]
            except Exception as e:
                logger.warning(f"Error analyzing browser logs: {e}")

        if include_ollama:
            try:
                ollama_source = OllamaLogSource()
                if ollama_source.file_path.exists():
                    lines = ollama_source.get_log_lines()
                    matches = []
                    for line, pos in lines[-300:]:
                        matches.extend(self.analyze_line(line, pos))
                    results["ollama"] = matches[:max_matches_per_source]
            except Exception as e:
                logger.warning(f"Error analyzing Ollama logs: {e}")

        return results

    def format_matches_for_ai(self, matches: dict[str, list[LogMatch]]) -> str:
        """
        Format log matches as context for AI troubleshooting.

        Args:
            matches: Dict of source to matches from get_context_for_troubleshooting

        Returns:
            Formatted string for AI context
        """
        lines = ["=== Log Analysis Results ===\n"]

        for source, source_matches in matches.items():
            if not source_matches:
                continue

            lines.append(f"\n--- {source.upper()} LOGS ---")
            lines.append(f"Found {len(source_matches)} issues:\n")

            for match in source_matches:
                lines.append(
                    f"[{match.pattern.severity.value}] {match.pattern.description}"
                )
                lines.append(f"  Pattern: {match.pattern.name}")
                lines.append(f"  Message: {match.message[:200]}")
                if match.pattern.action_required:
                    lines.append("  ** Action Required **")
                lines.append("")

        if not any(matches.values()):
            lines.append("No critical issues found in logs.")

        return "\n".join(lines)
