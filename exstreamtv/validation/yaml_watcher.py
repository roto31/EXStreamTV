"""File system watcher for YAML files"""

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional dependency: watchdog for file system monitoring
try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    # Create dummy classes for type hints when watchdog is not available
    Observer = None  # type: ignore
    FileSystemEventHandler = object  # type: ignore
    FileSystemEvent = object  # type: ignore
    logger.warning(
        "watchdog module not available. YAML file watching will be disabled. Install with: pip install watchdog"
    )


class YAMLFileHandler(FileSystemEventHandler if WATCHDOG_AVAILABLE else object):
    """Handler for YAML file system events"""

    def __init__(
        self, callback: Callable[[Path, str], None], watch_patterns: set[str] | None = None
    ):
        """
        Initialize handler

        Args:
            callback: Function to call when file changes (file_path, event_type)
            watch_patterns: Set of file patterns to watch (e.g., {'*.yml', '*.yaml'})
        """
        # Re-check if watchdog is available at runtime (in case it was installed after module import)
        try:
            from watchdog.events import FileSystemEventHandler

            watchdog_available = True
        except ImportError:
            watchdog_available = False

        if not watchdog_available:
            raise ImportError(
                "watchdog module is required for YAMLFileHandler. Install with: pip install watchdog"
            )

        # Call super().__init__() if we're actually a FileSystemEventHandler subclass
        if watchdog_available:
            super().__init__()
        self.callback = callback
        self.watch_patterns = watch_patterns or {"*.yml", "*.yaml"}
        self._last_events: dict[str, float] = {}  # Track last event time per file to debounce
        self._debounce_seconds = 0.5  # Debounce rapid file changes

    def _should_handle(self, file_path: Path) -> bool:
        """Check if file matches watch patterns"""
        if not file_path.is_file():
            return False

        # Check if file matches any pattern
        return any(file_path.match(pattern) for pattern in self.watch_patterns)

    def _debounce_event(self, file_path: Path) -> bool:
        """Debounce rapid file changes"""
        file_str = str(file_path)
        current_time = time.time()

        if file_str in self._last_events:
            time_since_last = current_time - self._last_events[file_str]
            if time_since_last < self._debounce_seconds:
                return False  # Skip this event (too soon after last)

        self._last_events[file_str] = current_time
        return True

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_handle(file_path) and self._debounce_event(file_path):
            logger.debug(f"File modified: {file_path}")
            self.callback(file_path, "modified")

    def on_created(self, event: FileSystemEvent):
        """Handle file creation"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_handle(file_path) and self._debounce_event(file_path):
            logger.debug(f"File created: {file_path}")
            self.callback(file_path, "created")

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        if self._should_handle(file_path):
            logger.debug(f"File deleted: {file_path}")
            self.callback(file_path, "deleted")


class YAMLWatcher:
    """Watch YAML files for changes"""

    def __init__(
        self,
        watch_directories: list[Path],
        callback: Callable[[Path, str], None],
        watch_patterns: set[str] | None = None,
    ):
        """
        Initialize watcher

        Args:
            watch_directories: List of directories to watch
            callback: Function to call when file changes (file_path, event_type)
            watch_patterns: Set of file patterns to watch
        """
        # Re-check if watchdog is available at runtime (in case it was installed after module import)
        try:
            from watchdog.events import FileSystemEvent, FileSystemEventHandler
            from watchdog.observers import Observer

            watchdog_available = True
        except ImportError:
            watchdog_available = False

        if not watchdog_available:
            raise ImportError(
                "watchdog module is required for YAMLWatcher. Install with: pip install watchdog"
            )

        self.watch_directories = [Path(d) for d in watch_directories]
        self.callback = callback
        self.watch_patterns = watch_patterns or {"*.yml", "*.yaml"}
        self.observer = Observer()
        self.handler = YAMLFileHandler(callback, watch_patterns)
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """Start watching files"""
        with self._lock:
            if self._running:
                logger.warning("Watcher already running")
                return

            # Schedule watching for each directory
            for directory in self.watch_directories:
                if not directory.exists():
                    logger.warning(f"Watch directory does not exist: {directory}")
                    continue

                self.observer.schedule(self.handler, str(directory), recursive=True)
                logger.info(f"Watching directory: {directory}")

            self.observer.start()
            self._running = True
            logger.info("YAML watcher started")

    def stop(self):
        """Stop watching files"""
        with self._lock:
            if not self._running:
                return

            self.observer.stop()
            self.observer.join(timeout=5.0)
            self._running = False
            logger.info("YAML watcher stopped")

    def is_running(self) -> bool:
        """Check if watcher is running"""
        with self._lock:
            return self._running
