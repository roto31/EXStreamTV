"""
File system media scanner.

Scans local directories for media files.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from exstreamtv.media.scanner.base import (
    MediaScanner,
    ScanProgress,
    ScanResult,
    ScanStatus,
)
from exstreamtv.media.scanner.ffprobe import FFprobeAnalyzer, MediaInfo

logger = logging.getLogger(__name__)


@dataclass
class ScannedFile:
    """A scanned media file."""

    path: Path
    relative_path: Path
    size: int
    modified_time: datetime
    media_info: Optional[MediaInfo] = None

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()


class FileScanner(MediaScanner):
    """
    Scans local file system for media files.

    Features:
    - Recursive directory scanning
    - FFprobe integration for media analysis
    - Progress tracking
    - Cancellation support
    """

    def __init__(
        self,
        library_id: int,
        library_path: str,
        extensions: Optional[Set[str]] = None,
        analyze_media: bool = True,
        max_concurrent: int = 4,
    ):
        super().__init__(library_id, library_path, extensions)
        self.analyze_media = analyze_media
        self.max_concurrent = max_concurrent
        self._ffprobe = FFprobeAnalyzer()

    async def scan(self) -> ScanResult:
        """Perform full library scan."""
        return await self.scan_path(self.library_path)

    async def scan_path(self, path: Path) -> ScanResult:
        """Scan a specific path."""
        self._cancelled = False

        progress = ScanProgress(started_at=datetime.now())
        result = ScanResult(status=ScanStatus.RUNNING, progress=progress)

        try:
            # First pass: count files
            logger.info(f"Counting files in {path}")
            all_files = self._discover_files(path)
            progress.total_files = len(all_files)
            self._notify_progress(progress)

            if not all_files:
                progress.finished_at = datetime.now()
                result.status = ScanStatus.COMPLETED
                result.warnings.append("No media files found")
                return result

            # Second pass: scan files
            logger.info(f"Scanning {len(all_files)} media files")
            scanned_items: List[ScannedFile] = []

            # Process in batches for better performance
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def process_file(file_path: Path) -> Optional[ScannedFile]:
                if self._cancelled:
                    return None

                async with semaphore:
                    return await self._scan_file(file_path)

            tasks = [process_file(f) for f in all_files]

            for i, task in enumerate(asyncio.as_completed(tasks)):
                if self._cancelled:
                    result.status = ScanStatus.CANCELLED
                    break

                try:
                    scanned = await task
                    if scanned:
                        scanned_items.append(scanned)
                        progress.new_items += 1
                except Exception as e:
                    logger.warning(f"Error scanning file: {e}")
                    progress.errors += 1
                    result.errors.append(str(e))

                progress.scanned_files = i + 1
                progress.current_file = str(all_files[min(i, len(all_files) - 1)])
                self._notify_progress(progress)

            progress.finished_at = datetime.now()

            if result.status != ScanStatus.CANCELLED:
                result.status = ScanStatus.COMPLETED

            result.items = scanned_items

            logger.info(
                f"Scan complete: {len(scanned_items)} items, "
                f"{progress.errors} errors in {progress.elapsed_time}"
            )

        except Exception as e:
            logger.exception(f"Scan failed: {e}")
            result = ScanResult.failure(str(e), progress)

        return result

    def _discover_files(self, path: Path) -> List[Path]:
        """Discover all media files in path."""
        files = []

        try:
            for root, dirs, filenames in os.walk(path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for filename in filenames:
                    if filename.startswith("."):
                        continue

                    file_path = Path(root) / filename
                    if self.is_media_file(file_path):
                        files.append(file_path)

        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
        except Exception as e:
            logger.error(f"Error discovering files: {e}")

        return sorted(files)

    async def _scan_file(self, path: Path) -> Optional[ScannedFile]:
        """Scan a single file."""
        try:
            stat = path.stat()

            scanned = ScannedFile(
                path=path,
                relative_path=self.get_relative_path(path),
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime),
            )

            # Analyze with FFprobe if enabled
            if self.analyze_media:
                try:
                    scanned.media_info = await self._ffprobe.analyze(path)
                except Exception as e:
                    logger.debug(f"FFprobe analysis failed for {path}: {e}")

            return scanned

        except Exception as e:
            logger.warning(f"Error scanning {path}: {e}")
            return None

    async def get_file_info(self, path: Path) -> Optional[ScannedFile]:
        """Get info for a single file without full scan."""
        if not path.exists():
            return None

        return await self._scan_file(path)
