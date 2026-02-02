"""
Database Backup Manager for scheduled backups and restore.

Ported from Tunarr's backup system with enhancements:
- Scheduled automatic backups (configurable interval)
- Backup rotation (keep N most recent)
- Optional gzip compression
- Manual backup/restore API
- Pre-restore safety backup

This ensures data safety with automatic backups and
easy recovery from failures.
"""

import asyncio
import gzip
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class BackupInfo:
    """Information about a backup file."""
    
    filename: str
    path: Path
    created_at: datetime
    size_bytes: int
    compressed: bool = False
    is_auto: bool = True
    description: Optional[str] = None
    
    @property
    def age_hours(self) -> float:
        """Get age in hours."""
        return (datetime.utcnow() - self.created_at).total_seconds() / 3600
    
    @property
    def size_mb(self) -> float:
        """Get size in megabytes."""
        return self.size_bytes / (1024 * 1024)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "filename": self.filename,
            "path": str(self.path),
            "created_at": self.created_at.isoformat(),
            "age_hours": self.age_hours,
            "size_bytes": self.size_bytes,
            "size_mb": round(self.size_mb, 2),
            "compressed": self.compressed,
            "is_auto": self.is_auto,
            "description": self.description,
        }


@dataclass
class BackupConfig:
    """Configuration for backup manager."""
    
    # Paths
    backup_directory: str = "backups"
    database_path: str = "exstreamtv.db"
    
    # Scheduling
    enabled: bool = True
    interval_hours: int = 24  # Backup every 24 hours
    
    # Retention
    keep_count: int = 7  # Keep last 7 backups
    keep_days: int = 30  # Keep backups for 30 days
    
    # Compression
    compress: bool = True
    
    # Safety
    pre_restore_backup: bool = True  # Backup before restore
    
    # Naming
    filename_prefix: str = "exstreamtv_backup"


class DatabaseBackupManager:
    """
    Manages database backups with scheduling and rotation.
    
    Features:
    - Scheduled automatic backups
    - Manual backup/restore
    - Backup rotation and cleanup
    - Gzip compression
    - Pre-restore safety backups
    
    Usage:
        manager = DatabaseBackupManager()
        await manager.start()  # Start scheduled backups
        
        # Manual backup
        backup = await manager.create_backup(description="Before migration")
        
        # Restore
        await manager.restore_backup(backup.path)
        
        # List backups
        backups = manager.list_backups()
    """
    
    def __init__(self, config: Optional[BackupConfig] = None):
        """
        Initialize backup manager.
        
        Args:
            config: Backup configuration
        """
        self._config = config or BackupConfig()
        self._backup_dir = Path(self._config.backup_directory)
        self._db_path = Path(self._config.database_path)
        self._running = False
        self._backup_task: Optional[asyncio.Task] = None
        self._last_backup: Optional[datetime] = None
        
        # Ensure backup directory exists
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"DatabaseBackupManager initialized: "
            f"directory={self._backup_dir}, "
            f"interval={self._config.interval_hours}h"
        )
    
    async def start(self) -> None:
        """Start scheduled backups."""
        if not self._config.enabled:
            logger.info("Scheduled backups are disabled")
            return
        
        if self._running:
            return
        
        self._running = True
        self._backup_task = asyncio.create_task(self._backup_loop())
        
        logger.info(
            f"Backup scheduler started: "
            f"interval={self._config.interval_hours}h, "
            f"keep={self._config.keep_count} backups"
        )
    
    async def stop(self) -> None:
        """Stop scheduled backups."""
        if not self._running:
            return
        
        self._running = False
        
        if self._backup_task:
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Backup scheduler stopped")
    
    async def _backup_loop(self) -> None:
        """Background backup loop."""
        while self._running:
            try:
                # Check if backup is needed
                if self._should_backup():
                    await self.create_backup(is_auto=True)
                    await self._cleanup_old_backups()
                
                # Wait for next check (check every hour)
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Backup loop error: {e}")
                await asyncio.sleep(3600)  # Wait and retry
    
    def _should_backup(self) -> bool:
        """Check if a backup is needed."""
        if self._last_backup is None:
            return True
        
        elapsed = (datetime.utcnow() - self._last_backup).total_seconds() / 3600
        return elapsed >= self._config.interval_hours
    
    async def create_backup(
        self,
        description: Optional[str] = None,
        is_auto: bool = False,
        compress: Optional[bool] = None,
    ) -> BackupInfo:
        """
        Create a database backup.
        
        Args:
            description: Optional description
            is_auto: Whether this is an automatic backup
            compress: Override compression setting
            
        Returns:
            BackupInfo for the created backup
            
        Raises:
            FileNotFoundError: If database doesn't exist
            IOError: If backup fails
        """
        if not self._db_path.exists():
            raise FileNotFoundError(f"Database not found: {self._db_path}")
        
        use_compress = compress if compress is not None else self._config.compress
        
        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        prefix = "auto_" if is_auto else "manual_"
        ext = ".db.gz" if use_compress else ".db"
        filename = f"{self._config.filename_prefix}_{prefix}{timestamp}{ext}"
        backup_path = self._backup_dir / filename
        
        try:
            # Create backup
            if use_compress:
                await self._create_compressed_backup(backup_path)
            else:
                await self._create_uncompressed_backup(backup_path)
            
            # Create info
            info = BackupInfo(
                filename=filename,
                path=backup_path,
                created_at=datetime.utcnow(),
                size_bytes=backup_path.stat().st_size,
                compressed=use_compress,
                is_auto=is_auto,
                description=description,
            )
            
            self._last_backup = info.created_at
            
            logger.info(
                f"Backup created: {filename} "
                f"({info.size_mb:.2f} MB)"
            )
            
            return info
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Clean up partial backup
            if backup_path.exists():
                backup_path.unlink()
            raise IOError(f"Backup failed: {e}") from e
    
    async def _create_compressed_backup(self, backup_path: Path) -> None:
        """Create a gzip-compressed backup."""
        def _compress():
            with open(self._db_path, "rb") as f_in:
                with gzip.open(backup_path, "wb", compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        await asyncio.get_event_loop().run_in_executor(None, _compress)
    
    async def _create_uncompressed_backup(self, backup_path: Path) -> None:
        """Create an uncompressed backup."""
        def _copy():
            shutil.copy2(self._db_path, backup_path)
        
        await asyncio.get_event_loop().run_in_executor(None, _copy)
    
    async def restore_backup(
        self,
        backup_path: Path | str,
        create_safety_backup: Optional[bool] = None,
    ) -> bool:
        """
        Restore database from backup.
        
        Args:
            backup_path: Path to backup file
            create_safety_backup: Create safety backup before restore
            
        Returns:
            True if restore succeeded
            
        Raises:
            FileNotFoundError: If backup doesn't exist
            IOError: If restore fails
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        # Create safety backup if configured
        do_safety = (
            create_safety_backup 
            if create_safety_backup is not None 
            else self._config.pre_restore_backup
        )
        
        if do_safety and self._db_path.exists():
            logger.info("Creating safety backup before restore")
            await self.create_backup(
                description="Safety backup before restore",
                is_auto=False,
            )
        
        try:
            is_compressed = backup_path.suffix == ".gz"
            
            if is_compressed:
                await self._restore_compressed_backup(backup_path)
            else:
                await self._restore_uncompressed_backup(backup_path)
            
            logger.info(f"Database restored from: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise IOError(f"Restore failed: {e}") from e
    
    async def _restore_compressed_backup(self, backup_path: Path) -> None:
        """Restore from a compressed backup."""
        def _decompress():
            with gzip.open(backup_path, "rb") as f_in:
                with open(self._db_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        
        await asyncio.get_event_loop().run_in_executor(None, _decompress)
    
    async def _restore_uncompressed_backup(self, backup_path: Path) -> None:
        """Restore from an uncompressed backup."""
        def _copy():
            shutil.copy2(backup_path, self._db_path)
        
        await asyncio.get_event_loop().run_in_executor(None, _copy)
    
    def list_backups(self) -> list[BackupInfo]:
        """
        List all available backups.
        
        Returns:
            List of BackupInfo, sorted by date (newest first)
        """
        backups = []
        
        for path in self._backup_dir.glob(f"{self._config.filename_prefix}_*"):
            if path.is_file():
                try:
                    # Parse timestamp from filename
                    # Format: prefix_auto/manual_YYYYMMDD_HHMMSS.db(.gz)
                    parts = path.stem.split("_")
                    if len(parts) >= 4:
                        date_str = parts[-2]
                        time_str = parts[-1].replace(".db", "")
                        timestamp = datetime.strptime(
                            f"{date_str}_{time_str}",
                            "%Y%m%d_%H%M%S"
                        )
                    else:
                        timestamp = datetime.fromtimestamp(path.stat().st_mtime)
                    
                    is_auto = "auto" in path.name
                    
                    backups.append(BackupInfo(
                        filename=path.name,
                        path=path,
                        created_at=timestamp,
                        size_bytes=path.stat().st_size,
                        compressed=path.suffix == ".gz",
                        is_auto=is_auto,
                    ))
                    
                except Exception as e:
                    logger.warning(f"Error parsing backup {path}: {e}")
        
        # Sort by date, newest first
        backups.sort(key=lambda b: b.created_at, reverse=True)
        
        return backups
    
    async def _cleanup_old_backups(self) -> int:
        """
        Clean up old backups based on retention policy.
        
        Returns:
            Number of backups deleted
        """
        backups = self.list_backups()
        
        # Only clean up auto backups
        auto_backups = [b for b in backups if b.is_auto]
        
        if not auto_backups:
            return 0
        
        deleted = 0
        
        # Keep only keep_count most recent
        for backup in auto_backups[self._config.keep_count:]:
            try:
                backup.path.unlink()
                deleted += 1
                logger.debug(f"Deleted old backup: {backup.filename}")
            except Exception as e:
                logger.warning(f"Failed to delete backup {backup.filename}: {e}")
        
        # Also delete backups older than keep_days
        cutoff = datetime.utcnow() - timedelta(days=self._config.keep_days)
        
        for backup in auto_backups:
            if backup.created_at < cutoff and backup.path.exists():
                try:
                    backup.path.unlink()
                    deleted += 1
                    logger.debug(f"Deleted expired backup: {backup.filename}")
                except Exception as e:
                    logger.warning(f"Failed to delete backup {backup.filename}: {e}")
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old backups")
        
        return deleted
    
    async def delete_backup(self, backup_path: Path | str) -> bool:
        """
        Delete a specific backup.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            True if deleted
        """
        path = Path(backup_path)
        
        if not path.exists():
            return False
        
        try:
            path.unlink()
            logger.info(f"Deleted backup: {path.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup {path}: {e}")
            return False
    
    def get_stats(self) -> dict[str, Any]:
        """Get backup manager statistics."""
        backups = self.list_backups()
        
        total_size = sum(b.size_bytes for b in backups)
        auto_count = sum(1 for b in backups if b.is_auto)
        manual_count = len(backups) - auto_count
        
        return {
            "running": self._running,
            "enabled": self._config.enabled,
            "backup_directory": str(self._backup_dir),
            "database_path": str(self._db_path),
            "interval_hours": self._config.interval_hours,
            "keep_count": self._config.keep_count,
            "keep_days": self._config.keep_days,
            "compress": self._config.compress,
            "total_backups": len(backups),
            "auto_backups": auto_count,
            "manual_backups": manual_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "last_backup": self._last_backup.isoformat() if self._last_backup else None,
            "newest_backup": backups[0].to_dict() if backups else None,
        }


# Global backup manager instance
_backup_manager: Optional[DatabaseBackupManager] = None


def get_backup_manager(
    config: Optional[BackupConfig] = None,
) -> DatabaseBackupManager:
    """Get the global DatabaseBackupManager instance."""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = DatabaseBackupManager(config)
    return _backup_manager


async def init_backup_manager(
    config: Optional[BackupConfig] = None,
    start: bool = True,
) -> DatabaseBackupManager:
    """Initialize and optionally start the backup manager."""
    manager = get_backup_manager(config)
    if start:
        await manager.start()
    return manager
