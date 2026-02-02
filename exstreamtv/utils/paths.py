"""
Path utilities for EXStreamTV.

Provides centralized path management for debug logs and project directories.
"""

from pathlib import Path
import logging
import json
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Project root is two levels up from this file (utils/paths.py -> utils -> exstreamtv -> root)
_PROJECT_ROOT = Path(__file__).parent.parent.parent


def get_project_root() -> Path:
    """Get the project root directory."""
    return _PROJECT_ROOT


def get_debug_log_path() -> Path:
    """Get the path to the debug log file."""
    return _PROJECT_ROOT / ".cursor" / "debug.log"


def write_debug_log(message: str) -> None:
    """
    Write a raw message to the debug log.
    
    Args:
        message: The message string to write to the log.
    """
    try:
        path = get_debug_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(message + "\n")
    except Exception as e:
        logger.debug(f"Failed to write debug log: {e}")


def debug_log(
    location: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    hypothesis_id: str = "",
    session_id: str = "debug-session",
) -> None:
    """
    Write a structured debug log entry.
    
    Args:
        location: The code location (e.g., "module.py:function_name").
        message: A human-readable message describing the event.
        data: Optional dictionary of additional data to log.
        hypothesis_id: Optional identifier for the hypothesis being tested.
        session_id: Session identifier for grouping related logs.
    """
    try:
        log_entry = {
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": time.time(),
            "sessionId": session_id,
        }
        write_debug_log(json.dumps(log_entry))
    except Exception as e:
        logger.debug(f"Failed to write structured debug log: {e}")


__all__ = [
    "get_project_root",
    "get_debug_log_path",
    "write_debug_log",
    "debug_log",
]
