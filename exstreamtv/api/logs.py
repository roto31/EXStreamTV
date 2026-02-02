"""
Streaming Logs API endpoints
"""

import asyncio
import builtins
import contextlib
import json
import logging
import os
import platform
import re
from datetime import datetime
from pathlib import Path

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["Logs"])

# Get base directory (project root)
BASE_DIR = Path(__file__).parent.parent.parent
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Error patterns to match troubleshooting scripts
ERROR_PATTERNS = {
    "check_python": [
        r"python.*not found",
        r"python.*error",
        r"python.*exception",
        r"no module named",
        r"import.*error",
        r"python.*version",
        r"python.*install",
    ],
    "check_ffmpeg": [
        r"ffmpeg.*not found",
        r"ffmpeg.*error",
        r"ffmpeg.*exception",
        r"ffmpeg.*failed",
        r"ffmpeg.*missing",
        r"codec.*not found",
        r"encoder.*not found",
    ],
    "check_database": [
        r"database.*error",
        r"database.*exception",
        r"sql.*error",
        r"database.*connection",
        r"database.*locked",
        r"database.*corrupt",
        r"sqlite.*error",
    ],
    "check_ports": [
        r"port.*in use",
        r"port.*already",
        r"address.*already",
        r"connection.*refused",
        r"cannot.*bind",
        r"port.*unavailable",
    ],
    "test_connectivity": [
        r"connection.*timeout",
        r"connection.*refused",
        r"network.*error",
        r"dns.*error",
        r"host.*unreachable",
        r"failed.*connect",
        r"youtube.*error",
        r"archive\.org.*error",
        r"nodename.*not known",
        r"servname.*not known",
        r"name resolution",
        r"unable to resolve",
        r"network.*unreachable",
        r"errno.*8",
        r"transport.*error",
    ],
    "repair_database": [
        r"database.*corrupt",
        r"database.*integrity",
        r"database.*repair",
        r"sqlite.*corrupt",
    ],
    "clear_cache": [r"cache.*error", r"cache.*full", r"cache.*corrupt", r"memory.*error"],
}


def match_error_to_scripts(error_message: str) -> list[str]:
    """Match an error message to appropriate troubleshooting scripts"""
    error_lower = error_message.lower()
    matched_scripts = []

    for script_id, patterns in ERROR_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, error_lower, re.IGNORECASE):
                if script_id not in matched_scripts:
                    matched_scripts.append(script_id)
                break

    return matched_scripts


def parse_log_line(line: str) -> dict[str, Any]:
    """Parse a log line and extract information.

    Args:
        line: Raw log line to parse

    Returns:
        dict[str, Any]: Parsed log entry with timestamp, level, logger, message, is_error, matched_scripts
    """
    # Common log formats:
    # 2024-11-30 14:30:45 - streamtv.api.iptv - ERROR - Error message
    # 2024-11-30 14:30:45,123 - streamtv.api.iptv - ERROR - Error message

    timestamp = None
    level = None
    logger_name = None
    message = line

    # Try to parse timestamp and level
    timestamp_match = re.match(r"(\d{4}-\d{2}-\d{2}[\s,]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)", line)
    if timestamp_match:
        timestamp_str = timestamp_match.group(1).replace(",", ".")
        with contextlib.suppress(builtins.BaseException):
            timestamp = datetime.strptime(timestamp_str.split(".")[0], "%Y-%m-%d %H:%M:%S")

    # Try to extract log level
    level_match = re.search(r"\s-\s(DEBUG|INFO|WARNING|ERROR|CRITICAL)\s-", line)
    if level_match:
        level = level_match.group(1)
        # Extract logger name (between timestamp and level)
        parts = line.split(" - ")
        if len(parts) >= 3:
            logger_name = parts[1] if len(parts) > 1 else None
            message = " - ".join(parts[2:]) if len(parts) > 2 else line

    # Check if it's an error
    is_error = (
        level in ["ERROR", "CRITICAL"] or "error" in line.lower() or "exception" in line.lower()
    )

    # Match to troubleshooting scripts if it's an error
    matched_scripts = []
    if is_error:
        matched_scripts = match_error_to_scripts(message)

    return {
        "raw": line,
        "timestamp": timestamp,
        "level": level or "INFO",
        "logger": logger_name,
        "message": message,
        "is_error": is_error,
        "matched_scripts": matched_scripts,
    }


def get_log_file_path() -> Path:
    """Get the log file path from config, with fallbacks"""
    from ..config import get_config
    config = get_config()

    log_file = getattr(getattr(config, 'logging', None), 'file', 'server.log') or 'server.log'

    # List of possible log file locations to check
    possible_paths = []

    # Try absolute path first
    if Path(log_file).is_absolute():
        possible_paths.append(Path(log_file))
    else:
        # Try relative to BASE_DIR
        possible_paths.append(BASE_DIR / log_file)
        # Try in current directory
        possible_paths.append(Path(log_file))
        # Try in parent directory
        possible_paths.append(BASE_DIR.parent / log_file)

    # Also check for common log file names
    common_names = ["server.log", "streamtv.log", "app.log", "application.log"]
    for name in common_names:
        possible_paths.append(BASE_DIR / name)
        possible_paths.append(BASE_DIR.parent / name)

    # Return the first existing file, or the first path if none exist
    for path in possible_paths:
        if path.exists():
            return path

    # Return the primary expected path (will be created when logging starts)
    return BASE_DIR / log_file


def get_plex_logs_directory() -> Path | None:
    """Get Plex logs directory path from config.

    Returns:
        Path | None: Path to Plex logs directory, or None if not configured
    """
    """Get Plex Media Server logs directory, auto-detecting based on OS if not configured"""
    from ..config import get_config
    config = get_config()

    # If explicitly configured, use that
    plex_config = getattr(config, 'plex', None)
    logs_path = getattr(plex_config, 'logs_path', None) if plex_config else None
    if logs_path:
        path = Path(logs_path)
        if path.exists():
            return path
        logger.warning(f"Configured Plex logs path does not exist: {path}")

    # Auto-detect based on OS
    system = platform.system()
    home = Path.home()

    possible_paths = []

    if system == "Darwin":  # macOS
        possible_paths = [
            home / "Library" / "Logs" / "Plex Media Server",
            Path("/Users/Shared/Plex Media Server/Logs"),
        ]
    elif system == "Linux":
        possible_paths = [
            Path("/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs"),
            Path("/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs"),
            home / ".local" / "share" / "Plex Media Server" / "Logs",
            Path("/opt/plexmediaserver/Library/Application Support/Plex Media Server/Logs"),
        ]
    elif system == "Windows":
        local_appdata = os.getenv("LOCALAPPDATA", "")
        if local_appdata:
            possible_paths = [
                Path(local_appdata) / "Plex Media Server" / "Logs",
            ]
        # Also try common Windows paths
        possible_paths.extend(
            [
                Path("C:/Users")
                / os.getenv("USERNAME", "")
                / "AppData"
                / "Local"
                / "Plex Media Server"
                / "Logs",
            ]
        )

    # Check each possible path
    for path in possible_paths:
        if path.exists() and path.is_dir():
            logger.info(f"Found Plex logs directory: {path}")
            return path

    logger.warning(
        "Could not find Plex Media Server logs directory. Please configure plex.logs_path in config.yaml"
    )
    return None


def get_plex_log_files() -> list[Path]:
    """Get list of Plex log files, sorted by modification time (newest first).

    Returns:
        list[Path]: List of Plex log file paths, sorted by modification time (newest first)
    """
    logs_dir = get_plex_logs_directory()
    if not logs_dir:
        return []

    log_files = []
    for file in logs_dir.iterdir():
        if file.is_file() and (file.suffix == ".log" or "Plex Media Server" in file.name):
            log_files.append(file)

    # Sort by modification time, newest first
    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return log_files


def parse_plex_log_line(line: str) -> dict[str, Any]:
    """Parse a Plex log line into structured data.

    Args:
        line: Raw Plex log line to parse

    Returns:
        dict[str, Any]: Parsed log entry with timestamp, level, logger, message, is_error
    """
    # Plex log format: [timestamp] LEVEL - message
    # Example: [2024-01-01 12:00:00.000] ERROR - Error message here

    parsed = {"raw": line, "timestamp": None, "level": "INFO", "message": line, "is_error": False}

    # Try to extract timestamp and level
    timestamp_match = re.match(r"\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]", line)
    if timestamp_match:
        try:
            timestamp_str = timestamp_match.group(1)
            # Parse timestamp (handle with or without microseconds)
            if "." in timestamp_str:
                parsed["timestamp"] = datetime.strptime(
                    timestamp_str, "%Y-%m-%d %H:%M:%S.%f"
                ).isoformat()
            else:
                parsed["timestamp"] = datetime.strptime(
                    timestamp_str, "%Y-%m-%d %H:%M:%S"
                ).isoformat()
        except ValueError:
            pass

    # Extract log level
    level_match = re.search(r"\b(ERROR|WARN|WARNING|INFO|DEBUG|CRITICAL|FATAL)\b", line)
    if level_match:
        level = level_match.group(1).upper()
        if level == "WARN":
            level = "WARNING"
        parsed["level"] = level
        parsed["is_error"] = level in ["ERROR", "CRITICAL", "FATAL"]

    # Extract message (everything after timestamp and level)
    if timestamp_match:
        remaining = line[timestamp_match.end() :].strip()
        # Remove level if present
        if level_match:
            remaining = re.sub(
                r"\b(ERROR|WARN|WARNING|INFO|DEBUG|CRITICAL|FATAL)\b\s*-\s*", "", remaining, count=1
            )
        parsed["message"] = remaining
    else:
        parsed["message"] = line

    return parsed


# Note: The /logs page route is handled in main.py to avoid conflicts


@router.get("")
async def logs_root() -> dict[str, Any]:
    """Get logs API summary.
    
    Returns available log endpoints and current log file status.
    """
    log_file = get_log_file_path()
    plex_logs_dir = get_plex_logs_directory()
    ollama_logs_dir = get_ollama_logs_directory()
    
    return {
        "message": "Logs API",
        "endpoints": [
            {"path": "/api/logs/entries", "description": "Get log entries as JSON"},
            {"path": "/api/logs/stream", "description": "Stream logs in real-time (SSE)"},
            {"path": "/api/logs/clear", "description": "Clear the log file"},
            {"path": "/api/logs/plex/logs/directory", "description": "Plex logs directory info"},
            {"path": "/api/logs/plex/logs/files", "description": "List Plex log files"},
            {"path": "/api/logs/plex/logs/entries", "description": "Get Plex log entries"},
            {"path": "/api/logs/browser/entries", "description": "Get browser log entries"},
            {"path": "/api/logs/ollama/directory", "description": "Ollama logs directory info"},
            {"path": "/api/logs/ollama/entries", "description": "Get Ollama log entries"},
            {"path": "/api/logs/lifecycle/status", "description": "Log lifecycle status"},
        ],
        "status": {
            "log_file": str(log_file),
            "log_file_exists": log_file.exists(),
            "plex_logs_available": plex_logs_dir is not None,
            "ollama_logs_available": ollama_logs_dir is not None,
        }
    }


@router.get("/{entry_id}", response_class=HTMLResponse)
async def log_entry_detail(entry_id: str, request: Request) -> HTMLResponse:
    """Log entry detail page with context and self-heal option.

    Args:
        entry_id: Base64-encoded log entry ID
        request: FastAPI request object

    Returns:
        HTMLResponse: Log entry detail page

    Raises:
        HTTPException: If log entry ID is invalid
    """
    import base64

    try:
        # Decode entry_id (it's base64 encoded log line)
        decoded = base64.b64decode(entry_id).decode("utf-8")

        # Parse the log entry
        parsed = parse_log_line(decoded)

        # Get surrounding context (lines before and after)
        log_file = get_log_file_path()
        context_lines = []
        target_line_index = None

        if log_file.exists():
            try:
                with open(log_file, encoding="utf-8", errors="ignore") as f:
                    all_lines = f.readlines()

                    # Find the line index
                    for i, line in enumerate(all_lines):
                        if line.strip() == decoded.strip():
                            target_line_index = i
                            # Get 20 lines before and after for context
                            start = max(0, i - 20)
                            end = min(len(all_lines), i + 21)
                            context_lines = [
                                {
                                    "line_number": j + 1,
                                    "content": all_lines[j].strip(),
                                    "is_target": j == i,
                                    "parsed": parse_log_line(all_lines[j].strip()),
                                }
                                for j in range(start, end)
                            ]
                            break
            except Exception as e:
                logger.exception(f"Error reading context: {e}")

        return templates.TemplateResponse(
            "log_detail.html",
            {
                "request": request,
                "title": f"Log Entry Detail - {parsed.get('level', 'INFO')}",
                "entry": parsed,
                "raw_line": decoded,
                "context_lines": context_lines,
                "target_line_index": target_line_index,
            },
        )
    except Exception as e:
        logger.exception(f"Error decoding log entry: {e}")
        raise HTTPException(status_code=400, detail="Invalid log entry ID")


@router.get("/entries")
async def get_log_entries(
    lines: int = 500, filter_level: str | None = None
) -> dict[str, Any]:
    """Get log entries as JSON.

    Args:
        lines: Number of recent log lines to retrieve
        filter_level: Optional log level filter (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        dict[str, Any]: Dictionary with entries, total_lines, showing, and optional error info

    Raises:
        HTTPException: If log file reading fails
    """
    log_file = get_log_file_path()

    if not log_file.exists():
        # Check if any log files exist in common locations
        checked_paths = [
            BASE_DIR / "server.log",
            BASE_DIR / "streamtv.log",
            BASE_DIR / "app.log",
            BASE_DIR.parent / "server.log",
            BASE_DIR.parent / "streamtv.log",
        ]

        existing_logs = [str(p) for p in checked_paths if p.exists()]

        # Try to create an empty log file if it doesn't exist
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_file.touch()
            logger.info(f"Created log file at {log_file}")
        except Exception as e:
            logger.warning(f"Could not create log file at {log_file}: {e}")
            message = f"Log file not found at: {log_file}"
            if existing_logs:
                message += "\n\nFound log files at:\n" + "\n".join(
                    f"  • {path}" for path in existing_logs
                )
                message += "\n\nPlease update config.yaml to point to one of these files, or the log file will be created when the first log entry is written."
            else:
                message += "\n\nThe log file will be created automatically when the first log entry is written."

            return {
                "entries": [
                    {
                        "raw": message,
                        "timestamp": None,
                        "level": "WARNING",
                        "logger": "logs",
                        "message": message,
                        "is_error": False,
                        "matched_scripts": [],
                    }
                ],
                "error": f"Log file not found at: {log_file}",
                "log_path": str(log_file),
                "checked_paths": [str(p) for p in checked_paths],
                "existing_logs": existing_logs,
            }

    try:
        # Read last N lines
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

        # Parse lines
        entries = []
        for line in recent_lines:
            parsed = parse_log_line(line.strip())
            if filter_level and parsed["level"] != filter_level:
                continue
            entries.append(parsed)

        return {"entries": entries, "total_lines": len(all_lines), "showing": len(entries)}
    except Exception as e:
        logger.exception(f"Error reading log file: {e}")
        raise HTTPException(status_code=500, detail=f"Error reading log file: {e!s}")


@router.get("/stream")
async def stream_logs() -> StreamingResponse:
    """Stream logs in real-time (SSE).

    Returns:
        StreamingResponse: Server-sent events stream of log entries
    """
    log_file = get_log_file_path()

    if not log_file.exists():

        async def error_generator():
            yield f"data: {json.dumps({'error': f'Log file not found at: {log_file}', 'log_path': str(log_file)})}\n\n"

        return StreamingResponse(error_generator(), media_type="text/event-stream")

    async def log_generator():
        import json

        # Read existing logs first
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            f.seek(0, 2)  # Seek to end
            last_position = f.tell()

        while True:
            try:
                with open(log_file, encoding="utf-8", errors="ignore") as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    last_position = f.tell()

                    for line in new_lines:
                        if line.strip():
                            parsed = parse_log_line(line.strip())
                            yield f"data: {json.dumps(parsed)}\n\n"

                await asyncio.sleep(0.5)  # Check every 500ms
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(1)

    return StreamingResponse(log_generator(), media_type="text/event-stream")


@router.get("/clear")
async def clear_logs() -> dict[str, Any]:
    """Clear the log file.

    Returns:
        dict[str, Any]: Success status and message

    Raises:
        HTTPException: If log file clearing fails
    """
    log_file = get_log_file_path()

    try:
        if log_file.exists():
            log_file.write_text("")
        return {"success": True, "message": "Log file cleared"}
    except Exception as e:
        logger.exception(f"Error clearing log file: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing log file: {e!s}")


# Plex Logs Endpoints


@router.get("/plex/logs/directory", response_model=None)
async def get_plex_logs_directory_info() -> dict[str, Any] | JSONResponse:
    """Get information about Plex logs directory.

    Returns:
        dict[str, Any] | JSONResponse: Directory info or error response if not found
    """
    logs_dir = get_plex_logs_directory()
    if not logs_dir:
        return JSONResponse(
            {
                "found": False,
                "message": "Plex logs directory not found. Please configure plex.logs_path in config.yaml",
                "possible_locations": {
                    "macOS": "~/Library/Logs/Plex Media Server",
                    "Linux": "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Logs",
                    "Windows": "%LOCALAPPDATA%\\Plex Media Server\\Logs",
                },
            }
        )

    log_files = get_plex_log_files()
    return {
        "found": True,
        "directory": str(logs_dir),
        "log_files_count": len(log_files),
        "log_files": [
            {"name": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
            for f in log_files[:10]
        ],
    }


@router.get("/plex/logs/files")
async def list_plex_log_files() -> dict[str, list[dict[str, Any]]]:
    """List available Plex log files.

    Returns:
        dict[str, list[dict[str, Any]]]: Dictionary with files list containing name, path, size, modified
    """
    log_files = get_plex_log_files()
    return {
        "files": [
            {
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in log_files
        ]
    }


@router.get("/plex/logs/entries", response_model=None)
async def get_plex_log_entries(
    lines: int = 500, filter_level: str = "", log_file: str | None = None
) -> dict[str, Any] | JSONResponse:
    """Get Plex log entries.

    Args:
        lines: Number of recent log lines to retrieve
        filter_level: Optional log level filter
        log_file: Specific log file to read (defaults to most recent)

    Returns:
        dict[str, Any] | JSONResponse: Log entries or error response
    """
    logs_dir = get_plex_logs_directory()
    if not logs_dir:
        return JSONResponse(
            {
                "error": "Plex logs directory not found",
                "entries": [],
                "message": "Please configure plex.logs_path in config.yaml or ensure Plex is installed",
            },
            status_code=404,
        )

    # Determine which log file to read
    log_files = get_plex_log_files()
    if not log_files:
        return JSONResponse(
            {"error": "No Plex log files found", "entries": [], "directory": str(logs_dir)},
            status_code=404,
        )

    # Use specified file or default to most recent
    if log_file:
        target_file = logs_dir / log_file
        if not target_file.exists():
            return JSONResponse(
                {"error": f"Log file not found: {log_file}", "entries": []}, status_code=404
            )
    else:
        target_file = log_files[0]  # Most recent

    try:
        entries = []
        with open(target_file, encoding="utf-8", errors="ignore") as f:
            # Read last N lines
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue

                parsed = parse_plex_log_line(line)

                # Apply level filter
                if filter_level and parsed["level"] != filter_level:
                    continue

                entries.append(parsed)

        return {
            "entries": entries,
            "file": target_file.name,
            "total_lines": len(entries),
            "log_path": str(logs_dir),
        }
    except Exception as e:
        logger.exception(f"Error reading Plex logs: {e}")
        return JSONResponse(
            {"error": f"Error reading Plex logs: {e!s}", "entries": [], "log_path": str(logs_dir)},
            status_code=500,
        )


@router.get("/plex/logs", response_class=HTMLResponse)
async def plex_logs_page(request: Request) -> HTMLResponse:
    """Plex logs viewer page.

    Args:
        request: FastAPI request object

    Returns:
        HTMLResponse: Plex logs viewer page
    """
    return templates.TemplateResponse("plex_logs.html", {"request": request})


# Browser Log Endpoints


@router.post("/browser")
async def report_browser_error(request: Request) -> dict[str, Any]:
    """Receive browser console errors from frontend.

    Args:
        request: FastAPI request object with error data

    Returns:
        dict[str, Any]: Success status
    """
    from ..utils.browser_logger import get_browser_logger

    try:
        body = await request.json()
        browser_logger = get_browser_logger()

        browser_logger.log_error(
            error_type=body.get("type", "error"),
            message=body.get("message", ""),
            stack=body.get("stack"),
            url=body.get("url"),
            line=body.get("line"),
            column=body.get("col"),
            user_agent=request.headers.get("user-agent"),
        )

        return {"success": True}
    except Exception as e:
        logger.warning(f"Failed to log browser error: {e}")
        return {"success": False, "error": str(e)}


@router.get("/browser/entries")
async def get_browser_log_entries(limit: int = 100) -> dict[str, Any]:
    """Get browser log entries.

    Args:
        limit: Maximum number of entries to return

    Returns:
        dict[str, Any]: Browser log entries
    """
    from ..utils.browser_logger import get_browser_logger

    browser_logger = get_browser_logger()
    errors = browser_logger.get_recent_errors(limit)

    return {"entries": errors, "count": len(errors)}


@router.delete("/browser/clear")
async def clear_browser_logs() -> dict[str, Any]:
    """Clear browser logs.

    Returns:
        dict[str, Any]: Success status
    """
    from ..utils.browser_logger import get_browser_logger

    browser_logger = get_browser_logger()
    success = browser_logger.clear_logs()

    return {"success": success}


# Ollama Log Endpoints


def get_ollama_logs_directory() -> Path | None:
    """Get Ollama logs directory path.

    Returns:
        Path | None: Path to Ollama logs directory, or None if not found
    """
    home = Path.home()

    # Ollama logs location varies by platform
    possible_paths = [
        home / ".ollama" / "logs",
        Path("/var/log/ollama"),
        home / "Library" / "Logs" / "Ollama",  # macOS alternative
    ]

    for path in possible_paths:
        if path.exists() and path.is_dir():
            return path

    return None


def parse_ollama_log_line(line: str) -> dict[str, Any]:
    """Parse Ollama log line format.

    Args:
        line: Raw log line

    Returns:
        dict[str, Any]: Parsed log entry
    """
    parsed = {"raw": line, "timestamp": None, "level": "INFO", "message": line, "is_error": False}

    # Ollama uses structured JSON logs or simple text format
    try:
        # Try JSON parsing first
        if line.strip().startswith("{"):
            data = json.loads(line)
            parsed["timestamp"] = data.get("time") or data.get("timestamp")
            parsed["level"] = data.get("level", "INFO").upper()
            parsed["message"] = data.get("msg") or data.get("message") or line
            parsed["is_error"] = parsed["level"] in ["ERROR", "FATAL", "CRITICAL"]
            return parsed
    except json.JSONDecodeError:
        pass

    # Fallback: Simple text parsing
    level_match = re.search(r"\b(ERROR|WARN|WARNING|INFO|DEBUG|FATAL)\b", line, re.IGNORECASE)
    if level_match:
        level = level_match.group(1).upper()
        if level == "WARN":
            level = "WARNING"
        parsed["level"] = level
        parsed["is_error"] = level in ["ERROR", "FATAL"]

    return parsed


def get_ollama_logs_context(max_lines: int = 100) -> str:
    """Get Ollama logs for AI troubleshooting context.

    Args:
        max_lines: Maximum number of lines to include

    Returns:
        str: Formatted Ollama logs
    """
    logs_dir = get_ollama_logs_directory()
    if not logs_dir:
        return "Ollama logs directory not found."

    # Find the most recent log file
    log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("server.log"))
    if not log_files:
        return "No Ollama log files found."

    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    target_file = log_files[0]

    try:
        with open(target_file, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            recent_lines = lines[-max_lines:] if len(lines) > max_lines else lines

        # Filter for errors and warnings
        error_lines = []
        warning_lines = []
        for line in recent_lines:
            parsed = parse_ollama_log_line(line.strip())
            if parsed["level"] in ["ERROR", "FATAL", "CRITICAL"]:
                error_lines.append(line.strip())
            elif parsed["level"] == "WARNING":
                warning_lines.append(line.strip())

        context_lines = error_lines[-30:] + warning_lines[-20:]

        if not context_lines:
            return f"Ollama logs: No recent errors or warnings found in {target_file.name}."

        return f"Ollama Logs ({target_file.name}, recent errors/warnings):\n" + "\n".join(
            context_lines[-50:]
        )
    except Exception as e:
        logger.warning(f"Error reading Ollama logs: {e}")
        return f"Error reading Ollama logs: {e!s}"


@router.get("/ollama/directory")
async def get_ollama_logs_directory_info() -> dict[str, Any]:
    """Get information about Ollama logs directory.

    Returns:
        dict[str, Any]: Directory info
    """
    logs_dir = get_ollama_logs_directory()
    if not logs_dir:
        return {
            "found": False,
            "message": "Ollama logs directory not found",
            "possible_locations": ["~/.ollama/logs/", "/var/log/ollama/"],
        }

    log_files = list(logs_dir.glob("*.log"))
    return {
        "found": True,
        "directory": str(logs_dir),
        "log_files_count": len(log_files),
        "log_files": [
            {"name": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
            for f in sorted(log_files, key=lambda f: f.stat().st_mtime, reverse=True)[:10]
        ],
    }


@router.get("/ollama/entries")
async def get_ollama_log_entries(lines: int = 200, filter_level: str = "") -> dict[str, Any]:
    """Get Ollama log entries.

    Args:
        lines: Number of lines to return
        filter_level: Optional level filter

    Returns:
        dict[str, Any]: Log entries
    """
    logs_dir = get_ollama_logs_directory()
    if not logs_dir:
        return {"error": "Ollama logs directory not found", "entries": []}

    log_files = list(logs_dir.glob("*.log"))
    if not log_files:
        return {"error": "No Ollama log files found", "entries": []}

    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    target_file = log_files[0]

    try:
        entries = []
        with open(target_file, encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            for line in recent_lines:
                line = line.strip()
                if not line:
                    continue

                parsed = parse_ollama_log_line(line)

                if filter_level and parsed["level"] != filter_level.upper():
                    continue

                entries.append(parsed)

        return {
            "entries": entries,
            "file": target_file.name,
            "total_lines": len(entries),
            "log_path": str(logs_dir),
        }
    except Exception as e:
        logger.error(f"Error reading Ollama logs: {e}")
        return {"error": f"Error reading Ollama logs: {e!s}", "entries": []}


# Log Lifecycle Endpoints


@router.get("/lifecycle/status")
async def get_lifecycle_status() -> dict[str, Any]:
    """Get log lifecycle management status.

    Returns:
        dict[str, Any]: Lifecycle status
    """
    from ..utils.log_lifecycle_manager import get_log_lifecycle_manager

    manager = get_log_lifecycle_manager()
    return manager.get_lifecycle_status()


@router.post("/lifecycle/archive-now")
async def trigger_archive() -> dict[str, Any]:
    """Manually trigger log archiving.

    Returns:
        dict[str, Any]: Archive results
    """
    from ..utils.log_lifecycle_manager import get_log_lifecycle_manager

    manager = get_log_lifecycle_manager()
    return await manager.archive_old_logs()


@router.post("/lifecycle/cleanup-now")
async def trigger_cleanup() -> dict[str, Any]:
    """Manually trigger old archive deletion.

    Returns:
        dict[str, Any]: Cleanup results
    """
    from ..utils.log_lifecycle_manager import get_log_lifecycle_manager

    manager = get_log_lifecycle_manager()
    return await manager.delete_old_archives()


@router.post("/lifecycle/truncate-now")
async def trigger_truncation() -> dict[str, Any]:
    """Manually trigger log truncation check.

    Returns:
        dict[str, Any]: Truncation results
    """
    from ..utils.log_lifecycle_manager import get_log_lifecycle_manager

    manager = get_log_lifecycle_manager()
    return await manager.check_and_truncate_logs()
