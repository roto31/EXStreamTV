"""
FFmpeg Process Watchdog.

Monitors FFmpeg processes and kills unresponsive ones to prevent
channel hangs and resource exhaustion.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WatchedProcess:
    """A process being monitored by the watchdog."""
    
    channel_id: str
    process: asyncio.subprocess.Process
    registered_at: datetime = field(default_factory=datetime.utcnow)
    last_output_at: datetime = field(default_factory=datetime.utcnow)
    bytes_output: int = 0
    restart_count: int = 0
    on_timeout: Optional[Callable] = None
    
    @property
    def seconds_since_output(self) -> float:
        """Seconds since last output was received."""
        return (datetime.utcnow() - self.last_output_at).total_seconds()
    
    @property
    def is_running(self) -> bool:
        """Check if process is still running."""
        return self.process.returncode is None


class FFmpegWatchdog:
    """
    Monitors FFmpeg processes and kills unresponsive ones.
    
    Features:
    - Tracks last output time for each process
    - Kills processes that haven't produced output within timeout
    - Triggers callback for restart handling
    - Collects metrics for monitoring
    
    Usage:
        watchdog = FFmpegWatchdog(timeout_seconds=30)
        watchdog.register_process("channel_1", ffmpeg_process)
        
        # In streaming loop:
        async for chunk in process.stdout:
            watchdog.report_output("channel_1")
            yield chunk
        
        # Periodic check (or use check_loop):
        await watchdog.check_all()
    """
    
    def __init__(
        self,
        timeout_seconds: int = 30,
        check_interval: float = 5.0,
    ):
        """
        Initialize the watchdog.
        
        Args:
            timeout_seconds: Kill process if no output for this many seconds
            check_interval: How often to check processes (seconds)
        """
        self._timeout = timeout_seconds
        self._check_interval = check_interval
        self._processes: dict[str, WatchedProcess] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._kills = 0
        self._timeouts = 0
    
    async def register_process(
        self,
        channel_id: str,
        process: asyncio.subprocess.Process,
        on_timeout: Optional[Callable] = None,
    ) -> None:
        """
        Register a process for monitoring.
        
        Args:
            channel_id: Unique identifier for the channel
            process: The FFmpeg subprocess to monitor
            on_timeout: Callback function called when process times out
        """
        async with self._lock:
            # Clean up any existing process for this channel
            if channel_id in self._processes:
                old = self._processes[channel_id]
                if old.is_running:
                    logger.warning(
                        f"Replacing still-running process for channel {channel_id}"
                    )
                    await self._kill_process(old)
            
            self._processes[channel_id] = WatchedProcess(
                channel_id=channel_id,
                process=process,
                on_timeout=on_timeout,
            )
            
            logger.debug(f"Registered FFmpeg process for channel {channel_id}")
    
    def report_output(self, channel_id: str, bytes_count: int = 0) -> None:
        """
        Report that output was received from a process.
        
        Call this each time data is read from the process to reset
        the timeout timer.
        
        Args:
            channel_id: Channel identifier
            bytes_count: Number of bytes received (for metrics)
        """
        if channel_id in self._processes:
            watched = self._processes[channel_id]
            watched.last_output_at = datetime.utcnow()
            watched.bytes_output += bytes_count
    
    async def unregister_process(self, channel_id: str) -> None:
        """
        Unregister a process from monitoring.
        
        Args:
            channel_id: Channel identifier
        """
        async with self._lock:
            if channel_id in self._processes:
                del self._processes[channel_id]
                logger.debug(f"Unregistered FFmpeg process for channel {channel_id}")
    
    async def check_all(self) -> dict[str, Any]:
        """
        Check all registered processes and kill unresponsive ones.
        
        Returns:
            Statistics about the check
        """
        stats = {
            "checked": 0,
            "healthy": 0,
            "killed": 0,
            "already_dead": 0,
        }
        
        async with self._lock:
            for channel_id, watched in list(self._processes.items()):
                stats["checked"] += 1
                
                # Check if process has already exited
                if not watched.is_running:
                    stats["already_dead"] += 1
                    continue
                
                # Check timeout
                if watched.seconds_since_output > self._timeout:
                    logger.warning(
                        f"FFmpeg for channel {channel_id} timed out "
                        f"({watched.seconds_since_output:.1f}s since last output)"
                    )
                    
                    await self._kill_process(watched)
                    stats["killed"] += 1
                    self._kills += 1
                    self._timeouts += 1
                    
                    # Trigger callback
                    if watched.on_timeout:
                        try:
                            if asyncio.iscoroutinefunction(watched.on_timeout):
                                await watched.on_timeout(channel_id)
                            else:
                                watched.on_timeout(channel_id)
                        except Exception as e:
                            logger.error(f"Timeout callback error: {e}")
                else:
                    stats["healthy"] += 1
        
        return stats
    
    async def _kill_process(self, watched: WatchedProcess) -> None:
        """Kill a process."""
        try:
            watched.process.terminate()
            try:
                await asyncio.wait_for(watched.process.wait(), timeout=5.0)
                logger.info(f"Terminated FFmpeg for channel {watched.channel_id}")
            except asyncio.TimeoutError:
                # Force kill
                watched.process.kill()
                await watched.process.wait()
                logger.warning(f"Force killed FFmpeg for channel {watched.channel_id}")
        except Exception as e:
            logger.error(f"Error killing FFmpeg for channel {watched.channel_id}: {e}")
    
    async def start(self) -> None:
        """Start the watchdog check loop."""
        if self._running:
            return
        
        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info(
            f"FFmpeg watchdog started (timeout={self._timeout}s, "
            f"interval={self._check_interval}s)"
        )
    
    async def stop(self) -> None:
        """Stop the watchdog check loop."""
        if not self._running:
            return
        
        self._running = False
        
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("FFmpeg watchdog stopped")
    
    async def _check_loop(self) -> None:
        """Background check loop."""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Watchdog check error: {e}")
                await asyncio.sleep(self._check_interval)
    
    def get_stats(self) -> dict[str, Any]:
        """Get watchdog statistics."""
        return {
            "active_processes": len(self._processes),
            "running": self._running,
            "timeout_seconds": self._timeout,
            "total_kills": self._kills,
            "total_timeouts": self._timeouts,
            "processes": {
                cid: {
                    "seconds_since_output": w.seconds_since_output,
                    "bytes_output": w.bytes_output,
                    "restart_count": w.restart_count,
                    "is_running": w.is_running,
                }
                for cid, w in self._processes.items()
            },
        }


# Global watchdog instance
_watchdog: Optional[FFmpegWatchdog] = None


def get_ffmpeg_watchdog(
    timeout_seconds: int = 30,
    check_interval: float = 5.0,
) -> FFmpegWatchdog:
    """Get the global FFmpeg watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = FFmpegWatchdog(
            timeout_seconds=timeout_seconds,
            check_interval=check_interval,
        )
    return _watchdog
