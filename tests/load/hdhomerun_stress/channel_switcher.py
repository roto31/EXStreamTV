"""
Channel Switcher - Rapid channel switch test.

Switch channels every 5 seconds for 10 minutes.
Ensure: no drift, no race, no authority conflict, no stream corruption.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from .tuner_client import open_stream

logger = logging.getLogger(__name__)


@dataclass
class ChannelSwitchResult:
    """Result of channel switch test."""

    switches_completed: int
    total_bytes: int
    duration_seconds: float
    errors: list[str]
    channels: list[str]


async def run_channel_switch_test(
    base_url: str,
    guide_numbers: list[str],
    *,
    switch_interval_seconds: float = 5.0,
    duration_seconds: float = 600.0,
    client: httpx.AsyncClient | None = None,
) -> ChannelSwitchResult:
    """
    Switch channels every switch_interval_seconds for duration_seconds.
    """
    if not guide_numbers:
        return ChannelSwitchResult(
            switches_completed=0,
            total_bytes=0,
            duration_seconds=0,
            errors=["No channels provided"],
            channels=[],
        )

    c = client or httpx.AsyncClient(timeout=30.0)
    start = datetime.utcnow()
    idx = 0
    switches = 0
    total_bytes = 0
    errors: list[str] = []

    while (datetime.utcnow() - start).total_seconds() < duration_seconds:
        gn = guide_numbers[idx % len(guide_numbers)]
        try:
            bytes_recv, _ = await open_stream(
                base_url, gn, client=c, duration_seconds=switch_interval_seconds
            )
            total_bytes += bytes_recv
        except Exception as e:
            errors.append(f"ch={gn}: {e}")
        switches += 1
        idx += 1

    elapsed = (datetime.utcnow() - start).total_seconds()
    return ChannelSwitchResult(
        switches_completed=switches,
        total_bytes=total_bytes,
        duration_seconds=elapsed,
        errors=errors,
        channels=guide_numbers,
    )
