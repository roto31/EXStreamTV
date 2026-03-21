"""Reconnect Storm - Rapid connect/disconnect cycles."""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime

import httpx

from .tuner_client import connect_disconnect_cycle

logger = logging.getLogger(__name__)


@dataclass
class ReconnectStormResult:
    cycles_completed: int
    total_bytes: int
    duration_seconds: float
    errors: list[str]


async def run_reconnect_storm(
    base_url: str,
    guide_number: str,
    duration_seconds: float = 60.0,
    min_connect_sec: float = 3.0,
    max_connect_sec: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> ReconnectStormResult:
    """Run rapid connect/disconnect cycles."""
    c = client or httpx.AsyncClient(timeout=30.0)
    start = datetime.utcnow()
    cycles = 0
    total_bytes = 0
    errors: list[str] = []
    while (datetime.utcnow() - start).total_seconds() < duration_seconds:
        connect_time = random.uniform(min_connect_sec, max_connect_sec)
        try:
            b, _ = await connect_disconnect_cycle(base_url, guide_number, connect_time, client=c)
            total_bytes += b
        except Exception as e:
            errors.append(str(e))
        cycles += 1
    return ReconnectStormResult(
        cycles_completed=cycles,
        total_bytes=total_bytes,
        duration_seconds=(datetime.utcnow() - start).total_seconds(),
        errors=errors,
    )
