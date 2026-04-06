"""
Process Pool Manager for EXStreamTV streaming stability.

The sole gatekeeper for FFmpeg subprocess spawning. Implements:
- Global process cap (memory, FD, and config based)
- Startup rate limiter (token bucket) to prevent thundering herd
- Zombie detection and long-run guard
- Memory and FD guards before spawn
- Prometheus-style metrics integration
"""

import asyncio
import logging
import os
import platform
import resource
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProcessState(str, Enum):
    """State of an FFmpeg process in the pool."""
    SPAWNING = "spawning"
    RUNNING = "running"
    RELEASING = "releasing"


@dataclass
class ProcessRegistryEntry:
    """Registry entry for a managed FFmpeg process."""
    channel_id: int | str
    pid: int
    process: "asyncio.subprocess.Process"  # Actual Process for terminate/wait
    state: ProcessState
    start_time: float
    restart_count: int = 0
    bytes_output: int = 0


class SpawnRejectedError(Exception):
    """Raised when spawn is rejected (memory, FD, or capacity)."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Spawn rejected: {reason}")


def _get_ulimit_nofile() -> int:
    """Get process ulimit for open files."""
    try:
        soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
        return soft
    except (ValueError, OSError):
        return 1024


def _get_open_fd_count() -> int:
    """Get current open file descriptor count (Unix)."""
    try:
        return len(os.listdir("/proc/self/fd"))
    except (FileNotFoundError, OSError):
        return 0


def _compute_max_processes(config: Any) -> int:
    """
    Compute safe max_processes from config and system limits.
    Formula: min(config, memory-based, FD-based).
    On macOS (no /proc/self/fd), fd-based limit can be overly restrictive
    when ulimit is low; use a generous fallback in that case.
    """
    max_from_config = getattr(
        getattr(config, "ffmpeg", None), "max_processes", None
    ) or 150

    max_from_memory = 150
    try:
        import psutil
        mem = psutil.virtual_memory()
        max_from_memory = int(mem.total / (150 * 1024 * 1024))  # 150MB per FFmpeg
    except ImportError:
        pass

    ulimit_nofile = _get_ulimit_nofile()
    fd_reserve = getattr(
        getattr(config, "ffmpeg", None), "fd_guard_reserve", 100
    )
    fd_per_process = 50
    max_from_fd = max(1, (ulimit_nofile - fd_reserve) // fd_per_process)

    # On macOS we cannot verify fd usage (/proc/self/fd doesn't exist). When
    # ulimit is low (e.g. 256 in some launch contexts), max_from_fd becomes 3,
    # starving 36+ channels. Use a sensible floor when fd limit is unrealistically low.
    fd_count = _get_open_fd_count()
    if (platform.system() == "Darwin" or fd_count == 0) and max_from_fd < 15:
        max_from_fd = 50  # Fallback when fd formula would over-restrict

    result = min(max_from_config, max_from_memory, max_from_fd)
    return max(1, result)


class TokenBucket:
    """Simple token bucket for rate limiting."""
    def __init__(self, rate: float, capacity: int = 10):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_update
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
                self._last_update = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                # Need to wait
                wait_time = (1 - self.tokens) / self.rate
                self.tokens = 0
            await asyncio.sleep(wait_time)


class ProcessPoolManager:
    """
    Sole gatekeeper for FFmpeg process spawning.

    ChannelManager/ChannelStream call acquire_process() before spawn and
    release_process() when done. Implements guards and rate limiting.
    """

    def __init__(self, config: Optional[Any] = None):
        self._config = config
        self._max_processes = _compute_max_processes(config or _default_config())
        self._spawn_semaphore = asyncio.Semaphore(self._max_processes)
        self._registry: Dict[int | str, ProcessRegistryEntry] = {}
        self._registry_lock = asyncio.Lock()
        rate = getattr(
            getattr(config, "ffmpeg", None), "spawns_per_second", 5
        ) if config else 5
        self._startup_rate_limiter = TokenBucket(rate=rate, capacity=10)
        self._long_run_hours = getattr(
            getattr(config, "ffmpeg", None), "long_run_hours", 24.0
        ) if config else 24.0
        self._memory_threshold = getattr(
            getattr(config, "ffmpeg", None), "memory_guard_threshold", 0.85
        ) if config else 0.85
        self._fd_reserve = getattr(
            getattr(config, "ffmpeg", None), "fd_guard_reserve", 100
        ) if config else 100
        self._shutting_down = False
        self._zombie_task: Optional[asyncio.Task] = None
        self._spawn_rejected_memory = 0
        self._spawn_rejected_fd = 0
        self._spawn_rejected_capacity = 0
        self._spawn_timeout_total = 0

    async def start(self) -> None:
        """Start the process pool manager (e.g. zombie check task)."""
        self._zombie_task = asyncio.create_task(self._zombie_check_loop())
        # Issue 7.2: Store reference to prevent GC and enable inspection
        self._zombie_task.add_done_callback(lambda t: logger.debug("Zombie check loop ended"))
        logger.info(
            f"ProcessPoolManager started (max_processes={self._max_processes})"
        )

    async def stop(self) -> None:
        """Stop the pool and terminate all processes."""
        self._shutting_down = True
        if self._zombie_task:
            self._zombie_task.cancel()
            try:
                await self._zombie_task
            except asyncio.CancelledError:
                pass
        from exstreamtv.streaming.ffmpeg_process_manager import (
            get_ffmpeg_process_manager,
        )

        manager = get_ffmpeg_process_manager()
        async with self._registry_lock:
            for channel_id, entry in list(self._registry.items()):
                try:
                    await manager.terminate_process(entry.process)
                except Exception as e:
                    logger.warning(f"Error terminating process {entry.pid}: {e}")
            self._registry.clear()
        logger.info("ProcessPoolManager stopped")

    def _check_guards(self) -> None:
        """Check memory and FD guards; raise SpawnRejectedError if over limits."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent / 100.0 >= self._memory_threshold:
                self._spawn_rejected_memory += 1
                raise SpawnRejectedError("memory")
        except ImportError:
            pass

        fd_count = _get_open_fd_count()
        ulimit = _get_ulimit_nofile()
        if ulimit > 0 and fd_count >= (ulimit - self._fd_reserve):
            self._spawn_rejected_fd += 1
            raise SpawnRejectedError("fd")

    async def acquire_process(
        self,
        channel_id: int | str,
        ffmpeg_cmd: List[str],
        *,
        timeout_seconds: float = 90.0,
        max_attempts: int = 5,
    ) -> "asyncio.subprocess.Process":
        """
        Acquire a slot, rate-limit, run guards, spawn FFmpeg, register.
        Bounded: timeout, max_attempts, exponential backoff. No infinite wait.
        """
        if self._shutting_down:
            raise SpawnRejectedError("shutting_down")

        attempt = 0
        last_error: Optional[Exception] = None

        while attempt < max_attempts:
            attempt += 1
            try:
                async def _acquire_inner() -> None:
                    async with self._registry_lock:
                        is_cold = len(self._registry) == 0
                    if not is_cold:
                        await self._startup_rate_limiter.acquire()
                    await self._spawn_semaphore.acquire()

                to = 5.0 if attempt == 1 else timeout_seconds
                await asyncio.wait_for(_acquire_inner(), timeout=to)
            except asyncio.TimeoutError:
                self._spawn_timeout_total += 1
                last_error = SpawnRejectedError("timeout")
                # Immediate raise on 1st timeout so caller can POOL_BYPASS (prevents cascade)
                if attempt == 1:
                    raise last_error
                if attempt < max_attempts:
                    backoff = min(2.0**attempt, 60.0)
                    logger.warning(
                        f"ProcessPoolManager acquire timeout (attempt {attempt}/{max_attempts}), "
                        f"backoff {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise last_error
                continue

            try:
                self._check_guards()
            except SpawnRejectedError as e:
                self._spawn_semaphore.release()
                if e.reason in ("memory", "fd"):
                    raise
                last_error = e
                if attempt < max_attempts:
                    backoff = min(2.0**attempt, 60.0)
                    await asyncio.sleep(backoff)
                    continue
                raise

            try:
                # Do not spawn ffmpeg directly. Use FFmpegProcessManager.
                from exstreamtv.streaming.ffmpeg_process_manager import (
                    get_ffmpeg_process_manager,
                )

                manager = get_ffmpeg_process_manager()
                process = await manager.spawn(
                    *ffmpeg_cmd,
                    tag=str(channel_id),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except Exception as e:
                self._spawn_semaphore.release()
                raise

            entry = ProcessRegistryEntry(
            channel_id=channel_id,
            pid=process.pid,
            process=process,
            state=ProcessState.RUNNING,
            start_time=time.time(),
        )
        async with self._registry_lock:
            self._registry[channel_id] = entry

        logger.info(
            f"ProcessPoolManager: spawned FFmpeg for channel {channel_id} (PID {process.pid})"
        )
        return process

    async def release_process(self, channel_id: int | str) -> None:
        """Terminate process for channel if running, unregister, release semaphore."""
        async with self._registry_lock:
            entry = self._registry.pop(channel_id, None)
        if entry is None:
            return
        entry.state = ProcessState.RELEASING
        try:
            from exstreamtv.streaming.ffmpeg_process_manager import (
                get_ffmpeg_process_manager,
            )

            await get_ffmpeg_process_manager().terminate_process(entry.process)
        except Exception as e:
            logger.warning(f"Error releasing process for channel {channel_id}: {e}")
        finally:
            self._spawn_semaphore.release()

    async def _zombie_check_loop(self) -> None:
        """Background task: detect zombies and long-running processes."""
        while not self._shutting_down:
            try:
                await asyncio.sleep(30)
                await self._check_zombies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Zombie check error: {e}")

    async def _check_zombies(self) -> None:
        """Check for exited (zombie) or overly long-running processes."""
        long_run_sec = self._long_run_hours * 3600
        now = time.time()
        to_release: List[int | str] = []
        async with self._registry_lock:
            for channel_id, entry in list(self._registry.items()):
                proc = entry.process
                if proc.returncode is not None:
                    to_release.append(channel_id)
                    logger.info(f"ProcessPoolManager: zombie process {entry.pid} for channel {channel_id}")
                elif (now - entry.start_time) > long_run_sec:
                    to_release.append(channel_id)
                    logger.info(
                        f"ProcessPoolManager: long-run process {entry.pid} "
                        f"for channel {channel_id} (> {self._long_run_hours}h)"
                    )
        for cid in to_release:
            await self.release_process(cid)

    def get_metrics(self) -> Dict[str, Any]:
        """Return metrics for Prometheus/observability."""
        async def _gather():
            async with self._registry_lock:
                active = len(self._registry)
            return {
                "exstreamtv_ffmpeg_processes_active": active,
                "exstreamtv_ffmpeg_max_processes": self._max_processes,
                "exstreamtv_ffmpeg_spawn_rejected_memory_total": self._spawn_rejected_memory,
                "exstreamtv_ffmpeg_spawn_rejected_fd_total": self._spawn_rejected_fd,
                "exstreamtv_ffmpeg_spawn_rejected_capacity_total": self._spawn_rejected_capacity,
                "exstreamtv_ffmpeg_spawn_timeout_total": self._spawn_timeout_total,
            }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(_gather())
                # Cannot block on future in async context; return sync fallback
                return {
                    "exstreamtv_ffmpeg_max_processes": self._max_processes,
                    "exstreamtv_ffmpeg_spawn_rejected_memory_total": self._spawn_rejected_memory,
                    "exstreamtv_ffmpeg_spawn_rejected_fd_total": self._spawn_rejected_fd,
                    "exstreamtv_ffmpeg_spawn_rejected_capacity_total": self._spawn_rejected_capacity,
                    "exstreamtv_ffmpeg_spawn_timeout_total": self._spawn_timeout_total,
                }
        except RuntimeError:
            pass
        return {
            "exstreamtv_ffmpeg_max_processes": self._max_processes,
            "exstreamtv_ffmpeg_spawn_rejected_memory_total": self._spawn_rejected_memory,
            "exstreamtv_ffmpeg_spawn_rejected_fd_total": self._spawn_rejected_fd,
            "exstreamtv_ffmpeg_spawn_rejected_capacity_total": self._spawn_rejected_capacity,
            "exstreamtv_ffmpeg_spawn_timeout_total": self._spawn_timeout_total,
        }

    async def get_active_count(self) -> int:
        """Return number of active (registered) processes."""
        async with self._registry_lock:
            return len(self._registry)


def _default_config() -> Any:
    """Return a minimal config object with defaults."""
    class _C:
        class ffmpeg:
            max_processes = 150
            spawns_per_second = 5
            long_run_hours = 24.0
            memory_guard_threshold = 0.85
            fd_guard_reserve = 100
    return _C()


# Global instance
_process_pool_manager: Optional[ProcessPoolManager] = None


def get_process_pool_manager(config: Optional[Any] = None) -> ProcessPoolManager:
    """Get or create the global ProcessPoolManager."""
    global _process_pool_manager
    if _process_pool_manager is None:
        from exstreamtv.config import get_config
        cfg = config or get_config()
        _process_pool_manager = ProcessPoolManager(cfg)
    return _process_pool_manager


async def shutdown_process_pool_manager() -> None:
    """Shutdown the global ProcessPoolManager."""
    global _process_pool_manager
    if _process_pool_manager is not None:
        await _process_pool_manager.stop()
        _process_pool_manager = None
