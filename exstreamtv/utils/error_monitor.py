"""Error monitoring and detection system"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ErrorPattern:
    """Represents a known error pattern"""

    def __init__(self, name: str, pattern: str, severity: str, category: str, description: str):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.severity = severity  # critical, high, medium, low
        self.category = category  # timeout, connection, ffmpeg, config, etc.
        self.description = description


class ErrorMonitor:
    """Monitors logs for errors and patterns"""

    # Known error patterns
    ERROR_PATTERNS = [
        ErrorPattern(
            name="ffmpeg_timeout",
            pattern=r"FFmpeg timeout.*no data received",
            severity="high",
            category="timeout",
            description="FFmpeg failed to receive data within timeout period",
        ),
        ErrorPattern(
            name="ffmpeg_demuxing_error",
            pattern=r"Error during demuxing.*Input/output error",
            severity="medium",
            category="ffmpeg",
            description="FFmpeg encountered I/O error while demuxing",
        ),
        ErrorPattern(
            name="connection_refused",
            pattern=r"Connection refused|ConnectionRefusedError",
            severity="high",
            category="connection",
            description="Connection to external service refused",
        ),
        ErrorPattern(
            name="http_error",
            pattern=r"HTTP.*(?:404|500|502|503)",
            severity="medium",
            category="connection",
            description="HTTP error from external service",
        ),
        ErrorPattern(
            name="archive_org_redirect",
            pattern=r"302 Found.*archive\.org|Redirect response.*302",
            severity="low",
            category="connection",
            description="Archive.org redirect issue",
        ),
        ErrorPattern(
            name="stream_not_found",
            pattern=r"Could not get stream URL|stream URL.*not found",
            severity="high",
            category="streaming",
            description="Unable to retrieve stream URL",
        ),
        ErrorPattern(
            name="database_error",
            pattern=r"DetachedInstanceError|sqlalchemy.*error",
            severity="medium",
            category="database",
            description="Database session or query error",
        ),
        ErrorPattern(
            name="authentication_error",
            pattern=r"401 Unauthorized|403 Forbidden|authentication failed",
            severity="high",
            category="auth",
            description="Authentication or authorization failure",
        ),
        ErrorPattern(
            name="timeout_general",
            pattern=r"TimeoutError|Timeout|timed out",
            severity="medium",
            category="timeout",
            description="General timeout error",
        ),
        ErrorPattern(
            name="file_not_found",
            pattern=r"FileNotFoundError|No such file",
            severity="high",
            category="filesystem",
            description="Required file not found",
        ),
    ]

    def __init__(self, log_dir: Path | None = None):
        """
        Initialize error monitor

        Args:
            log_dir: Directory containing log files (default: ~/Library/Logs/StreamTV)
        """
        if log_dir is None:
            log_dir = Path.home() / "Library" / "Logs" / "StreamTV"

        self.log_dir = Path(log_dir)
        self.error_counts = defaultdict(int)
        self.last_check_time = None

        logger.info(f"Initialized ErrorMonitor with log_dir={log_dir}")

    async def scan_recent_logs(
        self, minutes: int = 60, max_lines: int = 1000
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        Scan recent log files for errors

        Args:
            minutes: Number of minutes to look back
            max_lines: Maximum number of log lines to scan

        Returns:
            Tuple of (detected_errors, log_lines)
        """
        detected_errors = []
        log_lines = []

        try:
            # Find recent log files
            log_files = self._find_recent_log_files(minutes)

            if not log_files:
                logger.warning("No recent log files found")
                return detected_errors, log_lines

            # Read and parse logs
            for log_file in log_files:
                try:
                    lines = await self._read_log_file(log_file, max_lines)
                    log_lines.extend(lines)
                except Exception as e:
                    logger.exception(f"Error reading log file {log_file}: {e}")

            # Detect errors in log lines
            detected_errors = self._detect_errors(log_lines)

            logger.info(f"Scanned {len(log_lines)} log lines, found {len(detected_errors)} errors")

        except Exception as e:
            logger.exception(f"Error scanning logs: {e}")

        return detected_errors, log_lines

    def _find_recent_log_files(self, minutes: int) -> list[Path]:
        """Find log files modified within the specified time window"""
        if not self.log_dir.exists():
            logger.warning(f"Log directory not found: {self.log_dir}")
            return []

        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_files = []

        try:
            for log_file in self.log_dir.glob("streamtv-*.log"):
                if log_file.is_file():
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime >= cutoff_time:
                        recent_files.append(log_file)

            # Sort by modification time (newest first)
            recent_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        except Exception as e:
            logger.exception(f"Error finding log files: {e}")

        return recent_files

    async def _read_log_file(self, log_file: Path, max_lines: int) -> list[str]:
        """Read log file and return recent lines"""
        lines = []

        try:
            with open(log_file, encoding="utf-8", errors="ignore") as f:
                # Read last N lines efficiently
                lines = f.readlines()
                if len(lines) > max_lines:
                    lines = lines[-max_lines:]

        except Exception as e:
            logger.exception(f"Error reading {log_file}: {e}")

        return lines

    def _detect_errors(self, log_lines: list[str]) -> list[dict[str, Any]]:
        """Detect errors in log lines using known patterns"""
        detected_errors = []

        for i, line in enumerate(log_lines):
            # Check each error pattern
            for pattern in self.ERROR_PATTERNS:
                if pattern.pattern.search(line):
                    # Extract context (surrounding lines)
                    context_start = max(0, i - 2)
                    context_end = min(len(log_lines), i + 3)
                    context_lines = log_lines[context_start:context_end]

                    error = {
                        "pattern_name": pattern.name,
                        "severity": pattern.severity,
                        "category": pattern.category,
                        "description": pattern.description,
                        "line": line.strip(),
                        "line_number": i,
                        "context": "".join(context_lines),
                        "timestamp": self._extract_timestamp(line),
                        "detected_at": datetime.now().isoformat(),
                    }

                    detected_errors.append(error)
                    self.error_counts[pattern.name] += 1

        return detected_errors

    def _extract_timestamp(self, log_line: str) -> str | None:
        """Extract timestamp from log line"""
        # Pattern for StreamTV logs: YYYY-MM-DD HH:MM:SS
        timestamp_pattern = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
        match = re.search(timestamp_pattern, log_line)
        return match.group(1) if match else None

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of detected errors"""
        return {
            "total_errors": sum(self.error_counts.values()),
            "error_counts": dict(self.error_counts),
            "last_check": self.last_check_time.isoformat() if self.last_check_time else None,
        }

    def group_errors_by_category(
        self, errors: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group errors by category"""
        grouped = defaultdict(list)

        for error in errors:
            grouped[error["category"]].append(error)

        return dict(grouped)

    def get_high_priority_errors(self, errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter for high priority errors (critical and high severity)"""
        return [error for error in errors if error["severity"] in ["critical", "high"]]
