"""
Base media scanner classes.

Ported from ErsatzTV Scanner concepts.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ScanStatus(Enum):
    """Status of a scan operation."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ScanProgress:
    """Progress information for a scan operation."""

    total_files: int = 0
    scanned_files: int = 0
    new_items: int = 0
    updated_items: int = 0
    removed_items: int = 0
    errors: int = 0
    current_file: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.total_files == 0:
            return 0.0
        return (self.scanned_files / self.total_files) * 100

    @property
    def elapsed_time(self) -> Optional[timedelta]:
        """Calculate elapsed time."""
        if not self.started_at:
            return None
        end = self.finished_at or datetime.now()
        return end - self.started_at

    @property
    def estimated_remaining(self) -> Optional[timedelta]:
        """Estimate remaining time."""
        if not self.started_at or self.scanned_files == 0:
            return None

        elapsed = self.elapsed_time
        if not elapsed:
            return None

        rate = self.scanned_files / elapsed.total_seconds()
        remaining_files = self.total_files - self.scanned_files

        if rate > 0:
            return timedelta(seconds=remaining_files / rate)
        return None


@dataclass
class ScanResult:
    """Result of a scan operation."""

    status: ScanStatus = ScanStatus.PENDING
    progress: ScanProgress = field(default_factory=ScanProgress)
    items: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def success(cls, items: List[Any], progress: ScanProgress) -> "ScanResult":
        """Create successful result."""
        return cls(
            status=ScanStatus.COMPLETED,
            progress=progress,
            items=items,
        )

    @classmethod
    def failure(cls, error: str, progress: Optional[ScanProgress] = None) -> "ScanResult":
        """Create failure result."""
        return cls(
            status=ScanStatus.FAILED,
            progress=progress or ScanProgress(),
            errors=[error],
        )


class MediaScanner(ABC):
    """
    Abstract base class for media scanners.

    Ported from ErsatzTV IMediaScanner concept.
    """

    def __init__(
        self,
        library_id: int,
        library_path: str,
        extensions: Optional[Set[str]] = None,
    ):
        self.library_id = library_id
        self.library_path = Path(library_path)
        self.extensions = extensions or {
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
            ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".m2ts",
        }
        self._cancelled = False
        self._progress_callbacks: List[Callable[[ScanProgress], None]] = []

    def add_progress_callback(self, callback: Callable[[ScanProgress], None]) -> None:
        """Add a callback for progress updates."""
        self._progress_callbacks.append(callback)

    def _notify_progress(self, progress: ScanProgress) -> None:
        """Notify all progress callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def cancel(self) -> None:
        """Cancel the current scan."""
        self._cancelled = True

    @abstractmethod
    async def scan(self) -> ScanResult:
        """
        Perform a full library scan.

        Returns:
            ScanResult with discovered media items.
        """
        pass

    @abstractmethod
    async def scan_path(self, path: Path) -> ScanResult:
        """
        Scan a specific path within the library.

        Args:
            path: Path to scan.

        Returns:
            ScanResult with discovered media items.
        """
        pass

    def is_media_file(self, path: Path) -> bool:
        """Check if a file is a supported media file."""
        return path.suffix.lower() in self.extensions

    def get_relative_path(self, path: Path) -> Path:
        """Get path relative to library root."""
        try:
            return path.relative_to(self.library_path)
        except ValueError:
            return path
