"""
Browser Log Capture for EXStreamTV

Captures browser console errors and network failures from the frontend.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class BrowserLogCapture:
    """Captures browser console errors and network failures."""

    def __init__(self, log_file: Path | str | None = None):
        """
        Initialize browser log capture.

        Args:
            log_file: Path to browser log file. Defaults to logs/browser.log
        """
        if log_file is None:
            log_file = Path("logs/browser.log")
        elif isinstance(log_file, str):
            log_file = Path(log_file)

        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log_error(
        self,
        error_type: str,
        message: str,
        stack: str | None = None,
        url: str | None = None,
        line: int | None = None,
        column: int | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Write browser error to log file.

        Args:
            error_type: Type of error (e.g., 'error', 'promise', 'network')
            message: Error message
            stack: Stack trace if available
            url: URL where error occurred
            line: Line number
            column: Column number
            user_agent: Browser user agent
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "stack": stack,
            "url": url,
            "line": line,
            "column": column,
            "user_agent": user_agent,
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write browser log: {e}")

    def get_recent_errors(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent browser errors for AI analysis.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of error dictionaries
        """
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            errors = []
            for line in lines[-limit:]:
                line = line.strip()
                if line:
                    try:
                        errors.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            return errors
        except Exception as e:
            logger.error(f"Failed to read browser logs: {e}")
            return []

    def get_errors_for_troubleshooting(self, max_errors: int = 50) -> str:
        """
        Get browser errors formatted for AI troubleshooting context.

        Args:
            max_errors: Maximum number of errors to include

        Returns:
            Formatted string of browser errors
        """
        errors = self.get_recent_errors(max_errors)

        if not errors:
            return "No recent browser errors found."

        # Group by error type
        error_types: dict[str, list[dict]] = {}
        for error in errors:
            error_type = error.get("type", "unknown")
            if error_type not in error_types:
                error_types[error_type] = []
            error_types[error_type].append(error)

        lines = ["Browser Console Errors:"]
        for error_type, type_errors in error_types.items():
            lines.append(f"\n{error_type.upper()} ({len(type_errors)} occurrences):")
            # Show last 5 unique messages per type
            seen_messages: set[str] = set()
            for error in reversed(type_errors):
                msg = error.get("message", "")[:200]
                if msg and msg not in seen_messages:
                    seen_messages.add(msg)
                    lines.append(f"  - {msg}")
                    if len(seen_messages) >= 5:
                        break

        return "\n".join(lines)

    def clear_logs(self) -> bool:
        """Clear browser log file."""
        try:
            if self.log_file.exists():
                self.log_file.write_text("")
            return True
        except Exception as e:
            logger.error(f"Failed to clear browser logs: {e}")
            return False


# Singleton instance
_browser_logger: BrowserLogCapture | None = None


def get_browser_logger() -> BrowserLogCapture:
    """Get the global BrowserLogCapture instance."""
    global _browser_logger
    if _browser_logger is None:
        from exstreamtv.config import get_config

        config = get_config()
        log_file = config.logging.browser_logs.file
        _browser_logger = BrowserLogCapture(log_file)
    return _browser_logger
