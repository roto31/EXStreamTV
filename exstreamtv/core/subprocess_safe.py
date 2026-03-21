"""
Safe Async Subprocess — Cancellation-safe subprocess execution.

Ensures no orphan ffprobe/ffmpeg processes on CancelledError.
Uses FFmpegProcessManager for all spawns. Terminates process, waits, re-raises.
"""

import asyncio
import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


class SafeAsyncSubprocess:
    """
    Cancellation-safe subprocess execution.

    On CancelledError: terminate process via FFmpegProcessManager, re-raise.
    Prevents zombie/orphan subprocesses during shutdown.
    """

    @staticmethod
    async def run(
        *cmd: Union[str, bytes],
        timeout: Optional[float] = None,
        name: str = "subprocess",
        env: Optional[dict] = None,
        cwd: Optional[str] = None,
    ) -> tuple[bytes, bytes, int]:
        """
        Run subprocess, return (stdout, stderr, returncode).

        Args:
            *cmd: Command and args (e.g. "ffprobe", "-v", "quiet", ...)
            timeout: Optional timeout in seconds.
            name: Name for logging.
            env: Optional environment dict.
            cwd: Optional working directory.

        Returns:
            (stdout_bytes, stderr_bytes, returncode)

        Raises:
            asyncio.CancelledError: Re-raised after cleaning up process.
            TimeoutError: If timeout exceeded (process killed).
        """
        from exstreamtv.streaming.ffmpeg_process_manager import (
            get_ffmpeg_process_manager,
        )

        str_cmd = [str(c) for c in cmd]
        manager = get_ffmpeg_process_manager()
        process: Optional[asyncio.subprocess.Process] = None
        try:
            process = await manager.spawn(
                *str_cmd,
                tag=name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=dict(env) if env else None,
                cwd=cwd,
            )
            if timeout is not None:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            else:
                stdout, stderr = await process.communicate()
            return (
                stdout or b"",
                stderr or b"",
                process.returncode if process.returncode is not None else -1,
            )
        except asyncio.TimeoutError:
            if process is not None:
                await manager.terminate_process(process)
            raise TimeoutError(f"{name} timed out after {timeout}s") from None
        except asyncio.CancelledError:
            logger.info(f"Cancelled {name}, cleaning up subprocess")
            if process is not None:
                await manager.terminate_process(process)
            raise
        finally:
            if process is not None and process.pid is not None:
                await manager.unregister(process.pid)
