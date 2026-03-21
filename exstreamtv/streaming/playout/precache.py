"""
Media pre-caching (10s validation gate).

Before entering STREAMING:
- Launch FFmpeg probe with -t 10, null sink output
- Measure runtime_seconds and bytes_processed
- If below threshold: EARLY_EOF, retry, DO NOT advance
"""

import asyncio
import logging
import time
from typing import Optional

from exstreamtv.streaming.playout.exit_classifier import (
    MIN_BYTES_NATURAL_EOF,
    MIN_RUNTIME_NATURAL_EOF,
)
from exstreamtv.streaming.playout.state import ExitClassification

logger = logging.getLogger(__name__)

MIN_PRECACHE_SECONDS = 5
MIN_PRECACHE_BYTES = 1_000_000  # 1MB
PRECACHE_DURATION = 10  # seconds to run FFmpeg for precache probe


async def run_precache_probe(
    ffmpeg_path: str,
    input_url: str,
    seek_offset: float = 0.0,
    extra_args: Optional[list[str]] = None,
) -> tuple[float, int, Optional[int]]:
    """
    Run FFmpeg for PRECACHE_DURATION seconds, capture MPEG-TS output.
    Returns (runtime_seconds, bytes_processed, exit_code).
    """
    cmd = [
        ffmpeg_path,
        "-v", "error",
        "-t", str(PRECACHE_DURATION),
    ]
    if seek_offset > 0:
        cmd.extend(["-ss", str(int(seek_offset))])
    cmd.extend(["-i", input_url, "-f", "mpegts", "-"])
    if extra_args:
        cmd.extend(extra_args)

    from exstreamtv.streaming.ffmpeg_process_manager import (
        get_ffmpeg_process_manager,
    )

    manager = get_ffmpeg_process_manager()
    start = time.monotonic()
    process = await manager.spawn(
        *cmd,
        tag="precache",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    bytes_read = 0
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(
                    process.stdout.read(65536),
                    timeout=PRECACHE_DURATION + 5,
                )
                if not chunk:
                    break
                bytes_read += len(chunk)
                if time.monotonic() - start >= PRECACHE_DURATION:
                    break
            except asyncio.TimeoutError:
                break
            except asyncio.CancelledError:
                logger.info("Precache probe cancelled during shutdown")
                raise
    finally:
        await manager.terminate_process(process)

    runtime = time.monotonic() - start
    return runtime, bytes_read, process.returncode


async def validate_precache(
    ffmpeg_path: str,
    input_url: str,
    seek_offset: float = 0.0,
) -> tuple[bool, float, int, ExitClassification]:
    """
    Run precache probe. Returns (passed, runtime, bytes_proxy, classification).
    Passed=True means we can proceed to STREAMING.

    Probe safety: never run on empty or null URL.
    """
    if not input_url or not isinstance(input_url, str) or not str(input_url).strip():
        logger.warning("Precache skipped: empty or invalid URL")
        return False, 0.0, 0, ExitClassification.EARLY_EOF
    runtime, bytes_proxy, exit_code = await run_precache_probe(
        ffmpeg_path, input_url, seek_offset
    )
    passed = (
        runtime >= MIN_PRECACHE_SECONDS
        and bytes_proxy >= MIN_PRECACHE_BYTES
        and (exit_code == 0 or exit_code is None)
    )
    if passed:
        classification = ExitClassification.NATURAL_EOF
    else:
        classification = ExitClassification.EARLY_EOF
        logger.warning(
            f"Precache failed: runtime={runtime:.1f}s, bytes_proxy={bytes_proxy}, "
            f"exit_code={exit_code}"
        )
    return passed, runtime, bytes_proxy, classification
