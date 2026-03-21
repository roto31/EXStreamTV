"""
FFmpeg Process Manager — Centralized, cancellation-safe, process-group-aware lifecycle.

Sole owner of FFmpeg/ffprobe subprocess spawning. Guarantees:
- Process group isolation per invocation (preexec_fn=os.setsid)
- Explicit terminate -> wait(5s) -> kill fallback
- Cancellation-safe cleanup (never bypass on CancelledError)
- Defensive sweep after shutdown_all

Do not spawn ffmpeg/ffprobe directly. Use FFmpegProcessManager.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

TERMINATE_WAIT_SECONDS = 5.0


@dataclass
class ManagedProcess:
    """Tracked FFmpeg/ffprobe process with process group ID."""

    process: asyncio.subprocess.Process
    pgid: Optional[int]
    tag: str = ""

    async def terminate_and_wait(self) -> None:
        """SIGTERM to process group, wait 5s, SIGKILL if needed."""
        proc = self.process
        if proc.returncode is not None:
            return
        try:
            if self.pgid is not None and sys.platform != "win32":
                try:
                    os.killpg(self.pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            else:
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=TERMINATE_WAIT_SECONDS)
            except asyncio.TimeoutError:
                if proc.returncode is None:
                    if self.pgid is not None and sys.platform != "win32":
                        try:
                            os.killpg(self.pgid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    proc.kill()
                    await proc.wait()
            logger.debug(
                f"FFmpegProcessManager: process {proc.pid} exited with {proc.returncode}"
            )
        except Exception as e:
            logger.warning(f"FFmpegProcessManager: error terminating {proc.pid}: {e}")


class FFmpegProcessManager:
    """
    Centralized FFmpeg/ffprobe spawn and lifecycle control.

    All ffmpeg and ffprobe subprocesses must be spawned through this manager.
    shutdown_all() must be called during application shutdown.
    """

    _instance: Optional["FFmpegProcessManager"] = None

    def __init__(self) -> None:
        self._registry: dict[int, ManagedProcess] = {}
        self._registry_lock = asyncio.Lock()
        self._shutting_down = False

    @classmethod
    def get_instance(cls) -> "FFmpegProcessManager":
        if cls._instance is None:
            cls._instance = FFmpegProcessManager()
        return cls._instance

    def _preexec_setsid(self) -> None:
        """Create new process group. Unix only."""
        if sys.platform != "win32":
            os.setsid()

    async def spawn(
        self,
        *cmd: str,
        tag: str = "",
        stdout: int = asyncio.subprocess.PIPE,
        stderr: int = asyncio.subprocess.PIPE,
        stdin: int = asyncio.subprocess.DEVNULL,
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
    ) -> asyncio.subprocess.Process:
        """
        Spawn ffmpeg/ffprobe in its own process group. Register for shutdown.
        """
        if self._shutting_down:
            raise RuntimeError("FFmpegProcessManager: shutting down, spawn rejected")

        preexec = self._preexec_setsid if sys.platform != "win32" else None
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=stdout,
            stderr=stderr,
            stdin=stdin,
            env=dict(os.environ) if env is None else {**os.environ, **env},
            cwd=cwd,
            preexec_fn=preexec,
        )
        pgid: Optional[int] = None
        if sys.platform != "win32" and process.pid:
            try:
                pgid = os.getpgid(process.pid)
            except OSError:
                pass

        managed = ManagedProcess(process=process, pgid=pgid, tag=str(tag))
        async with self._registry_lock:
            self._registry[process.pid] = managed
        logger.debug(
            f"FFmpegProcessManager: spawned PID {process.pid} pgid={pgid} tag={tag}"
        )
        return process

    async def unregister(self, pid: int) -> None:
        """Unregister process after caller has awaited wait()."""
        async with self._registry_lock:
            self._registry.pop(pid, None)

    async def terminate_process(self, process: asyncio.subprocess.Process) -> None:
        """Terminate process using contract (SIGTERM -> wait -> SIGKILL). Unregister."""
        if process.pid is None:
            return
        managed: Optional[ManagedProcess] = None
        async with self._registry_lock:
            managed = self._registry.pop(process.pid, None)
        if managed:
            await managed.terminate_and_wait()
        elif process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=TERMINATE_WAIT_SECONDS)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

    async def shutdown_all(self) -> None:
        """Terminate all registered processes, then defensive sweep."""
        self._shutting_down = True
        to_terminate: list[ManagedProcess] = []
        async with self._registry_lock:
            to_terminate = list(self._registry.values())
            self._registry.clear()

        for managed in to_terminate:
            try:
                await managed.terminate_and_wait()
            except Exception as e:
                logger.warning(
                    f"FFmpegProcessManager: shutdown error {managed.process.pid}: {e}"
                )

        self._defensive_sweep()

    def _is_our_descendant(self, pid: int) -> bool:
        """Return True if pid is a descendant of our process."""
        try:
            import psutil
        except ImportError:
            return False
        our_pid = os.getpid()
        try:
            p = psutil.Process(pid)
            while True:
                ppid = p.ppid()
                if ppid == our_pid:
                    return True
                if ppid <= 1:
                    return False
                p = psutil.Process(ppid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def _defensive_sweep(self) -> None:
        """Kill any remaining ffmpeg/ffprobe that are our descendants."""
        try:
            import psutil
        except ImportError:
            return

        killed = 0
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if "ffmpeg" not in name and "ffprobe" not in name:
                    continue
                if self._is_our_descendant(proc.pid):
                    proc.kill()
                    killed += 1
                    logger.info(f"FFmpegProcessManager: defensive kill PID {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            logger.warning(
                f"FFmpegProcessManager: defensive sweep killed {killed} process(es)"
            )

    async def get_active_count(self) -> int:
        """Return number of registered processes."""
        async with self._registry_lock:
            return len(self._registry)


def get_ffmpeg_process_manager() -> FFmpegProcessManager:
    """Get the global FFmpegProcessManager instance."""
    return FFmpegProcessManager.get_instance()


async def shutdown_ffmpeg_process_manager() -> None:
    """Shutdown the global manager. Call during app lifespan shutdown."""
    mgr = FFmpegProcessManager.get_instance()
    await mgr.shutdown_all()
