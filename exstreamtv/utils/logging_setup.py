"""Comprehensive logging setup for EXStreamTV with file and console output"""

import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_file_name: str | None = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 10,
    log_format: str | None = None,
    log_directory: Path | None = None,
) -> logging.Logger:
    """
    Set up comprehensive logging for EXStreamTV application.

    This configures logging to write to:
    - Console (stdout) with colored output if available
    - File with rotation

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file_name: Path to log file (can be absolute or relative)
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file
        max_bytes: Maximum size of log file before rotation (default 10MB)
        backup_count: Number of backup files to keep (default 10)
        log_format: Custom log format string
        log_directory: Override log directory (defaults to logs/ in project root)

    Returns:
        Configured root logger
    """
    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Determine log directory
    if log_directory is not None:
        log_dir = log_directory
    elif log_file_name and Path(log_file_name).is_absolute():
        log_dir = Path(log_file_name).parent
        log_file_name = Path(log_file_name).name
    elif log_file_name and "/" in log_file_name:
        # Relative path with directory
        log_dir = Path(log_file_name).parent
        log_file_name = Path(log_file_name).name
    else:
        # Default to logs/ directory in project root
        log_dir = Path("logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    # Generate log file name with timestamp if not provided
    if log_file_name is None:
        timestamp = datetime.now().strftime("%Y-%m-%d")
        log_file_name = f"exstreamtv-{timestamp}.log"

    log_file_path = log_dir / log_file_name

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create detailed formatter with timestamp, name, level, and message
    if log_format:
        detailed_formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    else:
        detailed_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Create simpler formatter for console (optional)
    console_formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )

    # Set up console handler (stdout)
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Set up file handler with rotation
    if log_to_file:
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)

    # Log the initialization
    root_logger.info("=" * 80)
    root_logger.info(f"EXStreamTV Logging initialized - Level: {log_level}")
    root_logger.info(f"Log directory: {log_dir}")
    root_logger.info(f"Log file: {log_file_path}")
    root_logger.info(f"Console logging: {'enabled' if log_to_console else 'disabled'}")
    root_logger.info(f"File logging: {'enabled' if log_to_file else 'disabled'}")
    root_logger.info(f"Max file size: {max_bytes / (1024*1024):.1f} MB, Backups: {backup_count}")
    root_logger.info("=" * 80)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the logger (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_system_info():
    """Log system and environment information at startup"""
    import platform
    import sys
    from pathlib import Path

    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info("SYSTEM INFORMATION")
    logger.info("-" * 80)
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    logger.info(f"Machine: {platform.machine()}")
    logger.info(f"Processor: {platform.processor()}")
    logger.info(f"Working directory: {Path.cwd()}")
    logger.info("=" * 80)


def log_exception(
    logger: logging.Logger, exception: Exception, message: str = "Exception occurred"
):
    """
    Log an exception with full traceback.

    Args:
        logger: Logger instance to use
        exception: Exception to log
        message: Additional context message
    """
    logger.error(f"{message}: {exception!s}", exc_info=True)


# Convenience function for quick setup
def quick_setup(log_level: str = "INFO") -> logging.Logger:
    """
    Quick logging setup with sensible defaults.

    Args:
        log_level: Logging level

    Returns:
        Configured root logger
    """
    return setup_logging(log_level=log_level, log_to_console=True, log_to_file=True)


# Debug log path - configurable via environment variable
import os
DEBUG_LOG_PATH = os.environ.get(
    "EXSTREAMTV_DEBUG_LOG",
    str(Path(__file__).parent.parent.parent / ".cursor" / "debug.log")
)


def debug_log(
    location: str,
    message: str,
    data: dict = None,
    hypothesis_id: str = None,
    session_id: str = "debug-session",
    run_id: str = "run1",
) -> None:
    """
    Write a debug log entry to the debug log file.
    
    This function is used for debugging purposes during development.
    It writes structured JSON log entries to a debug file that can be
    analyzed to understand application behavior.
    
    Args:
        location: Code location identifier (e.g., "module:function:context")
        message: Human-readable description of the log event
        data: Optional dictionary of contextual data
        hypothesis_id: Optional hypothesis identifier for debugging sessions
        session_id: Session identifier (default: "debug-session")
        run_id: Run identifier (default: "run1")
    """
    try:
        import json
        from datetime import datetime as dt
        
        log_entry = {
            "sessionId": session_id,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(dt.now().timestamp() * 1000),
        }
        
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception:
        # Silently ignore debug logging errors to avoid affecting normal operation
        pass
