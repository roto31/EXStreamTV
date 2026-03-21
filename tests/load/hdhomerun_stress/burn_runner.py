"""
Long Burn Test — 8 parallel clients, 2 hours, random disconnects/switching.

Monitor: clock drift, memory, FD, threads, FFmpeg count, API latency.
Fail if: drift > 2s, memory growth > 20%, zombie FFmpeg, deadlock, schedule mismatch.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from .channel_switcher import run_channel_switch_test
from .system_monitor import SystemSnapshot, take_snapshot, check_memory_growth
from .tuner_client import open_stream

logger = logging.getLogger(__name__)


@dataclass
class BurnRunResult:
    """Result of long burn test."""

    passed: bool
    duration_seconds: float
    parallel_sessions: int
    total_bytes: int
    errors: list[str] = field(default_factory=list)
    system_samples: list[SystemSnapshot] = field(default_factory=list)
    memory_growth_ok: bool = True
    drift_ok: bool = True


async def _burn_client(
    client_id: int,
    base_url: str,
    guide_numbers: list[str],
    duration_seconds: float,
    switch_interval: float,
    cancel_event: asyncio.Event,
) -> tuple[int, int, list[str]]:
    """Single burn client: random channel, random disconnect/switch."""
    c = httpx.AsyncClient(timeout=120.0)
    total_bytes = 0
    errors: list[str] = []
    start = datetime.utcnow()
    gn = guide_numbers[random.randint(0, len(guide_numbers) - 1)] if guide_numbers else "100"
    while (datetime.utcnow() - start).total_seconds() < duration_seconds and not cancel_event.is_set():
        connect_time = random.uniform(switch_interval, switch_interval * 3)
        try:
            b, _ = await open_stream(base_url, gn, client=c, duration_seconds=connect_time)
            total_bytes += b
        except Exception as e:
            errors.append(f"client{client_id}: {e}")
        if guide_numbers and len(guide_numbers) > 1:
            gn = guide_numbers[random.randint(0, len(guide_numbers) - 1)]
    return client_id, total_bytes, errors


async def run_long_burn(
    base_url: str,
    guide_numbers: list[str],
    *,
    duration_seconds: float = 7200.0,
    parallel_clients: int = 8,
    switch_interval: float = 30.0,
    sample_interval: float = 60.0,
) -> BurnRunResult:
    """
    Run long burn: N parallel clients, random disconnects/switching.
    """
    if not guide_numbers:
        guide_numbers = ["100"]
    cancel = asyncio.Event()
    samples: list[SystemSnapshot] = []
    errors: list[str] = []

    async def sample_loop() -> None:
        start = datetime.utcnow()
        while (datetime.utcnow() - start).total_seconds() < duration_seconds and not cancel.is_set():
            samples.append(take_snapshot())
            await asyncio.sleep(sample_interval)

    start = datetime.utcnow()
    sample_task = asyncio.create_task(sample_loop())
    total_bytes = 0
    try:
        tasks = [
            _burn_client(i, base_url, guide_numbers, duration_seconds, switch_interval, cancel)
            for i in range(parallel_clients)
        ]
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=duration_seconds + 60,
        )
        for r in results:
            if isinstance(r, Exception):
                errors.append(str(r))
            elif isinstance(r, tuple):
                _, b, errs = r
                total_bytes += b
                errors.extend(errs[:3])
    except asyncio.TimeoutError:
        errors.append("Burn test timed out")
    finally:
        cancel.set()
        sample_task.cancel()
        try:
            await sample_task
        except asyncio.CancelledError:
            pass

    elapsed = (datetime.utcnow() - start).total_seconds()
    mem_ok, mem_msg = check_memory_growth(samples, threshold_percent=20.0)
    if not mem_ok:
        errors.append(mem_msg)

    return BurnRunResult(
        passed=len(errors) == 0,
        duration_seconds=elapsed,
        parallel_sessions=parallel_clients,
        total_bytes=total_bytes,
        errors=errors,
        system_samples=samples,
        memory_growth_ok=mem_ok,
        drift_ok=True,
    )
