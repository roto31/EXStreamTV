"""Non-blocking subprocess helpers for async code paths."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger(__name__)


async def subprocess_run_thread(
    cmd: Sequence[str],
    *,
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    """Run subprocess.run in a worker thread (avoids blocking the event loop)."""

    def _inner() -> Any:
        return subprocess.run(
            list(cmd),
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            cwd=cwd,
            env=env,
            check=check,
        )

    return await asyncio.to_thread(_inner)


async def run_exec_text(
    *args: str,
    timeout: float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run program; return (returncode, stdout, stderr) as decoded text."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        if timeout is not None:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        else:
            stdout_b, stderr_b = await proc.communicate()
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        logger.warning("run_exec_text: killed process after timeout: %s", args[:3])
        return 124, "", "timeout"
    out = (stdout_b or b"").decode(errors="replace")
    err = (stderr_b or b"").decode(errors="replace")
    code = proc.returncode if proc.returncode is not None else -1
    return code, out, err


async def run_shell_text(
    cmd: str,
    timeout: float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run shell command (e.g. osascript -e '...')."""
    merged = {**os.environ, **(env or {})}
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=merged,
    )
    try:
        if timeout is not None:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        else:
            stdout_b, stderr_b = await proc.communicate()
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", "timeout"
    out = (stdout_b or b"").decode(errors="replace")
    err = (stderr_b or b"").decode(errors="replace")
    code = proc.returncode if proc.returncode is not None else -1
    return code, out, err


async def run_exec_bytes(
    *args: str,
    timeout: float | None = None,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    try:
        if timeout is not None:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        else:
            stdout_b, stderr_b = await proc.communicate()
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, b"", b"timeout"
    code = proc.returncode if proc.returncode is not None else -1
    return code, stdout_b or b"", stderr_b or b""
