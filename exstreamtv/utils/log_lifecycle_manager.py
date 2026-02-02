"""
Log Lifecycle Manager for EXStreamTV

Manages log file lifecycle:
- Truncation: Prevents logs from exceeding max_size
- Archiving: Compresses logs older than archive_after_days
- Deletion: Removes archived logs older than delete_after_days
"""

import asyncio
import gzip
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LogLifecycleManager:
    """
    Manages log file lifecycle:
    - Truncation: Prevents logs from exceeding max_size
    - Archiving: Compresses logs older than archive_after_days
    - Deletion: Removes archived logs older than delete_after_days
    """

    def __init__(
        self,
        log_directories: list[Path],
        max_file_size_mb: int = 50,
        archive_after_days: int = 7,
        delete_after_days: int = 30,
        archive_directory: Path | None = None,
    ):
        """
        Initialize the log lifecycle manager.

        Args:
            log_directories: List of directories containing log files
            max_file_size_mb: Maximum log file size before truncation
            archive_after_days: Days after which to archive logs
            delete_after_days: Days after which to delete archived logs
            archive_directory: Directory for archived logs
        """
        self.log_directories = log_directories
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.archive_after_days = archive_after_days
        self.delete_after_days = delete_after_days
        self.archive_directory = archive_directory or Path("logs/archive")
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the lifecycle management scheduler."""
        if self._running:
            return

        self._running = True

        # Create archive directory
        self.archive_directory.mkdir(parents=True, exist_ok=True)

        # Schedule tasks
        self._tasks.append(
            asyncio.create_task(self._run_periodic(self.check_and_truncate_logs, 3600))
        )  # Every hour
        self._tasks.append(
            asyncio.create_task(self._run_daily(self.archive_old_logs, 3, 0))
        )  # 3 AM
        self._tasks.append(
            asyncio.create_task(self._run_daily(self.delete_old_archives, 4, 0))
        )  # 4 AM

        logger.info("Log lifecycle management started")

    async def stop(self) -> None:
        """Stop the lifecycle management scheduler."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Log lifecycle management stopped")

    async def _run_periodic(self, func, interval_seconds: int) -> None:
        """Run a function periodically."""
        while self._running:
            try:
                await func()
            except Exception as e:
                logger.error(f"Error in periodic task {func.__name__}: {e}")
            await asyncio.sleep(interval_seconds)

    async def _run_daily(self, func, hour: int, minute: int) -> None:
        """Run a function daily at a specific time."""
        while self._running:
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            if self._running:
                try:
                    await func()
                except Exception as e:
                    logger.error(f"Error in daily task {func.__name__}: {e}")

    async def check_and_truncate_logs(self) -> dict[str, Any]:
        """
        Check all log files and truncate if they exceed max size.
        Truncation preserves the most recent entries.
        """
        results: dict[str, Any] = {"truncated": [], "errors": []}

        for log_dir in self.log_directories:
            if not log_dir.exists():
                continue

            for log_file in log_dir.glob("*.log"):
                try:
                    if log_file.stat().st_size > self.max_file_size_bytes:
                        await self._truncate_log_file(log_file)
                        results["truncated"].append(str(log_file))
                        logger.info(f"Truncated log file: {log_file}")
                except Exception as e:
                    results["errors"].append({"file": str(log_file), "error": str(e)})
                    logger.error(f"Error truncating {log_file}: {e}")

        return results

    async def _truncate_log_file(self, log_file: Path) -> None:
        """
        Truncate a log file to max_size, keeping the most recent entries.
        Adds a truncation marker at the beginning.
        """
        target_size = int(self.max_file_size_bytes * 0.8)  # Truncate to 80% of max

        def _do_truncate():
            with open(log_file, "rb") as f:
                f.seek(-target_size, 2)  # Seek from end
                f.readline()  # Skip partial line
                content = f.read()

            truncation_marker = (
                f"--- LOG TRUNCATED AT {datetime.now().isoformat()} ---\n"
                f"--- Previous entries archived or removed to manage file size ---\n\n"
            ).encode("utf-8")

            with open(log_file, "wb") as f:
                f.write(truncation_marker)
                f.write(content)

        await asyncio.get_event_loop().run_in_executor(None, _do_truncate)

    async def archive_old_logs(self) -> dict[str, Any]:
        """
        Archive (compress) log files older than archive_after_days.
        Archives are stored as .log.gz files in the archive directory.
        """
        results: dict[str, Any] = {"archived": [], "errors": []}
        cutoff_date = datetime.now() - timedelta(days=self.archive_after_days)

        self.archive_directory.mkdir(parents=True, exist_ok=True)

        for log_dir in self.log_directories:
            if not log_dir.exists():
                continue

            for log_file in log_dir.glob("*.log"):
                # Skip if it's the main log file (still in use)
                if log_file.name in ["exstreamtv.log", "browser.log"]:
                    continue

                try:
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        archive_name = f"{log_file.stem}_{mtime.strftime('%Y%m%d')}.log.gz"
                        archive_path = self.archive_directory / archive_name

                        def _do_archive():
                            with open(log_file, "rb") as f_in:
                                with gzip.open(archive_path, "wb") as f_out:
                                    shutil.copyfileobj(f_in, f_out)

                            # Clear the original file
                            with open(log_file, "w") as f:
                                f.write(
                                    f"--- Archived to {archive_name} at {datetime.now().isoformat()} ---\n"
                                )

                        await asyncio.get_event_loop().run_in_executor(None, _do_archive)

                        results["archived"].append(
                            {"source": str(log_file), "archive": str(archive_path)}
                        )
                        logger.info(f"Archived log file: {log_file} -> {archive_path}")
                except Exception as e:
                    results["errors"].append({"file": str(log_file), "error": str(e)})
                    logger.error(f"Error archiving {log_file}: {e}")

        return results

    async def delete_old_archives(self) -> dict[str, Any]:
        """
        Delete archived logs older than delete_after_days.
        """
        results: dict[str, Any] = {"deleted": [], "errors": []}
        cutoff_date = datetime.now() - timedelta(days=self.delete_after_days)

        if not self.archive_directory.exists():
            return results

        for archive_file in self.archive_directory.glob("*.log.gz"):
            try:
                mtime = datetime.fromtimestamp(archive_file.stat().st_mtime)
                if mtime < cutoff_date:
                    archive_file.unlink()
                    results["deleted"].append(str(archive_file))
                    logger.info(f"Deleted old archive: {archive_file}")
            except Exception as e:
                results["errors"].append({"file": str(archive_file), "error": str(e)})
                logger.error(f"Error deleting {archive_file}: {e}")

        return results

    def get_lifecycle_status(self) -> dict[str, Any]:
        """Get current status of all managed logs."""
        status: dict[str, Any] = {
            "active_logs": [],
            "archived_logs": [],
            "total_active_size_mb": 0,
            "total_archive_size_mb": 0,
            "config": {
                "max_file_size_mb": self.max_file_size_bytes / (1024 * 1024),
                "archive_after_days": self.archive_after_days,
                "delete_after_days": self.delete_after_days,
            },
        }

        for log_dir in self.log_directories:
            if not log_dir.exists():
                continue

            for log_file in log_dir.glob("*.log"):
                try:
                    stat = log_file.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    status["active_logs"].append(
                        {
                            "path": str(log_file),
                            "size_mb": round(size_mb, 2),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )
                    status["total_active_size_mb"] += size_mb
                except Exception:
                    pass

        if self.archive_directory.exists():
            for archive_file in self.archive_directory.glob("*.log.gz"):
                try:
                    stat = archive_file.stat()
                    size_mb = stat.st_size / (1024 * 1024)
                    status["archived_logs"].append(
                        {
                            "path": str(archive_file),
                            "size_mb": round(size_mb, 2),
                            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        }
                    )
                    status["total_archive_size_mb"] += size_mb
                except Exception:
                    pass

        status["total_active_size_mb"] = round(status["total_active_size_mb"], 2)
        status["total_archive_size_mb"] = round(status["total_archive_size_mb"], 2)

        return status


# Singleton instance
_lifecycle_manager: LogLifecycleManager | None = None


def get_log_lifecycle_manager() -> LogLifecycleManager:
    """Get the global LogLifecycleManager instance."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        from exstreamtv.config import get_config

        config = get_config()

        log_dirs = []
        # Add configured log file directory
        log_file_path = Path(config.logging.file)
        if log_file_path.parent.exists() or log_file_path.parent == Path("logs"):
            log_dirs.append(log_file_path.parent)

        # Add default logs directory
        if Path("logs").exists() or Path("logs") not in log_dirs:
            log_dirs.append(Path("logs"))

        _lifecycle_manager = LogLifecycleManager(
            log_directories=log_dirs,
            max_file_size_mb=config.logging.lifecycle.max_file_size_mb,
            archive_after_days=config.logging.lifecycle.archive_after_days,
            delete_after_days=config.logging.lifecycle.delete_after_days,
            archive_directory=Path(config.logging.lifecycle.archive_directory),
        )
    return _lifecycle_manager
