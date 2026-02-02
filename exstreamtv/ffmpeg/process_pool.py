"""
FFmpeg Process Pool

Manages a pool of FFmpeg processes for efficient resource utilization.
Prevents spawning too many concurrent transcoding processes.
"""

import asyncio
import os
import signal
import time
from asyncio.subprocess import Process
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class ProcessState(str, Enum):
    """State of an FFmpeg process."""
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ProcessInfo:
    """Information about a managed FFmpeg process."""
    id: str
    pid: int
    state: ProcessState
    started_at: float
    channel_id: Optional[int] = None
    source_url: Optional[str] = None
    command: List[str] = field(default_factory=list)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    output_bytes: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def uptime_seconds(self) -> float:
        """Get process uptime in seconds."""
        return time.time() - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "pid": self.pid,
            "state": self.state.value,
            "started_at": self.started_at,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "channel_id": self.channel_id,
            "source_url": self.source_url,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "output_bytes": self.output_bytes,
            "error_count": len(self.errors),
        }


@dataclass
class PoolConfig:
    """FFmpeg process pool configuration."""
    
    # Maximum concurrent FFmpeg processes
    max_processes: int = 4
    
    # Process startup timeout
    startup_timeout: float = 30.0
    
    # Grace period for stopping processes
    stop_timeout: float = 10.0
    
    # Enable process resource monitoring
    enable_monitoring: bool = True
    
    # Monitoring interval in seconds
    monitor_interval: float = 5.0
    
    # Maximum process age before restart (0 = disabled)
    max_age_seconds: int = 0
    
    # Restart on error
    restart_on_error: bool = True
    
    # Maximum restart attempts
    max_restarts: int = 3


class FFmpegProcessPool:
    """
    Manages a pool of FFmpeg transcoding processes.
    
    Features:
    - Limits concurrent processes
    - Queue for pending requests
    - Process health monitoring
    - Graceful shutdown
    - Resource tracking
    """
    
    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()
        
        # Active processes
        self._processes: Dict[str, tuple[Process, ProcessInfo]] = {}
        
        # Process queue
        self._queue: asyncio.Queue = asyncio.Queue()
        
        # Semaphore for limiting concurrent processes
        self._semaphore = asyncio.Semaphore(self.config.max_processes)
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Monitoring task
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Shutdown flag
        self._shutting_down = False
        
        # Process counter for unique IDs
        self._counter = 0
        
        # Callbacks
        self._on_process_started: Optional[Callable] = None
        self._on_process_stopped: Optional[Callable] = None
        self._on_process_error: Optional[Callable] = None
    
    async def start(self) -> None:
        """Start the process pool."""
        if self.config.enable_monitoring:
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"FFmpeg process pool started (max {self.config.max_processes} processes)")
    
    async def stop(self) -> None:
        """Stop the process pool and all processes."""
        self._shutting_down = True
        
        # Cancel monitoring
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop all processes
        await self.stop_all()
        
        logger.info("FFmpeg process pool stopped")
    
    async def spawn(
        self,
        command: List[str],
        channel_id: Optional[int] = None,
        source_url: Optional[str] = None,
        wait: bool = True,
    ) -> Optional[str]:
        """
        Spawn a new FFmpeg process.
        
        Args:
            command: FFmpeg command and arguments
            channel_id: Associated channel ID
            source_url: Source URL being processed
            wait: Wait for semaphore if pool is full
            
        Returns:
            Process ID if started, None if pool full and not waiting
        """
        if self._shutting_down:
            return None
        
        # Wait for available slot
        if wait:
            await self._semaphore.acquire()
        else:
            if not self._semaphore.locked():
                self._semaphore.acquire_nowait()
            else:
                return None
        
        try:
            # Generate unique ID
            async with self._lock:
                self._counter += 1
                process_id = f"ffmpeg_{self._counter}"
            
            # Start process
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            info = ProcessInfo(
                id=process_id,
                pid=process.pid,
                state=ProcessState.RUNNING,
                started_at=time.time(),
                channel_id=channel_id,
                source_url=source_url,
                command=command,
            )
            
            async with self._lock:
                self._processes[process_id] = (process, info)
            
            logger.info(f"Started FFmpeg process {process_id} (PID {process.pid})")
            
            if self._on_process_started:
                asyncio.create_task(self._on_process_started(info))
            
            return process_id
        
        except Exception as e:
            self._semaphore.release()
            logger.error(f"Failed to start FFmpeg process: {e}")
            return None
    
    async def stop_process(self, process_id: str, force: bool = False) -> bool:
        """
        Stop a specific FFmpeg process.
        
        Args:
            process_id: Process ID to stop
            force: Use SIGKILL instead of SIGTERM
            
        Returns:
            True if process was stopped
        """
        async with self._lock:
            if process_id not in self._processes:
                return False
            
            process, info = self._processes[process_id]
            info.state = ProcessState.STOPPING
        
        try:
            if force:
                process.kill()
            else:
                process.terminate()
            
            # Wait for process to exit
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=self.config.stop_timeout,
                )
            except asyncio.TimeoutError:
                # Force kill if didn't stop
                process.kill()
                await process.wait()
            
            async with self._lock:
                if process_id in self._processes:
                    _, info = self._processes.pop(process_id)
                    info.state = ProcessState.STOPPED
                    self._semaphore.release()
            
            logger.info(f"Stopped FFmpeg process {process_id}")
            
            if self._on_process_stopped:
                asyncio.create_task(self._on_process_stopped(info))
            
            return True
        
        except Exception as e:
            logger.error(f"Error stopping process {process_id}: {e}")
            return False
    
    async def stop_all(self) -> int:
        """Stop all FFmpeg processes."""
        async with self._lock:
            process_ids = list(self._processes.keys())
        
        stopped = 0
        for pid in process_ids:
            if await self.stop_process(pid):
                stopped += 1
        
        return stopped
    
    async def stop_for_channel(self, channel_id: int) -> int:
        """Stop all processes for a specific channel."""
        async with self._lock:
            process_ids = [
                pid for pid, (_, info) in self._processes.items()
                if info.channel_id == channel_id
            ]
        
        stopped = 0
        for pid in process_ids:
            if await self.stop_process(pid):
                stopped += 1
        
        return stopped
    
    async def get_process(self, process_id: str) -> Optional[ProcessInfo]:
        """Get information about a process."""
        async with self._lock:
            if process_id in self._processes:
                _, info = self._processes[process_id]
                return info
        return None
    
    async def get_all_processes(self) -> List[ProcessInfo]:
        """Get information about all processes."""
        async with self._lock:
            return [info for _, info in self._processes.values()]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        async with self._lock:
            processes = [info for _, info in self._processes.values()]
        
        running = sum(1 for p in processes if p.state == ProcessState.RUNNING)
        total_memory = sum(p.memory_mb for p in processes)
        total_cpu = sum(p.cpu_percent for p in processes)
        
        return {
            "max_processes": self.config.max_processes,
            "active_processes": len(processes),
            "running_processes": running,
            "available_slots": self.config.max_processes - len(processes),
            "total_memory_mb": round(total_memory, 1),
            "total_cpu_percent": round(total_cpu, 1),
            "queue_size": self._queue.qsize(),
        }
    
    async def wait_for_process(
        self,
        process_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[int]:
        """
        Wait for a process to complete.
        
        Returns:
            Exit code, or None if timeout/not found
        """
        async with self._lock:
            if process_id not in self._processes:
                return None
            process, _ = self._processes[process_id]
        
        try:
            if timeout:
                return await asyncio.wait_for(process.wait(), timeout=timeout)
            else:
                return await process.wait()
        except asyncio.TimeoutError:
            return None
        finally:
            async with self._lock:
                if process_id in self._processes:
                    self._processes.pop(process_id)
                    self._semaphore.release()
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while not self._shutting_down:
            try:
                await asyncio.sleep(self.config.monitor_interval)
                await self._update_process_stats()
                await self._check_process_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
    
    async def _update_process_stats(self) -> None:
        """Update resource usage stats for all processes."""
        try:
            import psutil
        except ImportError:
            return
        
        async with self._lock:
            for process_id, (proc, info) in self._processes.items():
                try:
                    ps_proc = psutil.Process(proc.pid)
                    info.cpu_percent = ps_proc.cpu_percent()
                    info.memory_mb = ps_proc.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    
    async def _check_process_health(self) -> None:
        """Check health of all processes and handle failures."""
        async with self._lock:
            items = list(self._processes.items())
        
        for process_id, (process, info) in items:
            # Check if process is still running
            if process.returncode is not None:
                async with self._lock:
                    if process_id in self._processes:
                        self._processes.pop(process_id)
                        self._semaphore.release()
                        info.state = ProcessState.STOPPED
                
                if process.returncode != 0:
                    info.state = ProcessState.ERROR
                    logger.warning(
                        f"FFmpeg process {process_id} exited with code {process.returncode}"
                    )
                    
                    if self._on_process_error:
                        asyncio.create_task(
                            self._on_process_error(info, process.returncode)
                        )
            
            # Check max age
            elif (self.config.max_age_seconds > 0 and
                  info.uptime_seconds > self.config.max_age_seconds):
                logger.info(
                    f"Restarting FFmpeg process {process_id} due to max age"
                )
                await self.stop_process(process_id)
    
    def on_process_started(self, callback: Callable) -> None:
        """Register callback for process start events."""
        self._on_process_started = callback
    
    def on_process_stopped(self, callback: Callable) -> None:
        """Register callback for process stop events."""
        self._on_process_stopped = callback
    
    def on_process_error(self, callback: Callable) -> None:
        """Register callback for process error events."""
        self._on_process_error = callback


# Global process pool instance
_process_pool: Optional[FFmpegProcessPool] = None


async def get_process_pool() -> FFmpegProcessPool:
    """Get or create the global FFmpeg process pool."""
    global _process_pool
    
    if _process_pool is None:
        _process_pool = FFmpegProcessPool()
        await _process_pool.start()
    
    return _process_pool


async def shutdown_process_pool() -> None:
    """Shutdown the global process pool."""
    global _process_pool
    
    if _process_pool is not None:
        await _process_pool.stop()
        _process_pool = None
