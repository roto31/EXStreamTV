"""Tuner Client - HDHomeRun stream client for stress testing."""

import asyncio
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


async def open_stream(
    base_url: str,
    guide_number: str,
    *,
    client: httpx.AsyncClient | None = None,
    duration_seconds: float = 60.0,
) -> tuple[int, float]:
    """Open HDHomeRun stream and consume for duration_seconds."""
    url = f"{base_url.rstrip('/')}/hdhomerun/auto/v{guide_number}"
    c = client or httpx.AsyncClient(timeout=120.0)
    start = datetime.utcnow()
    total = 0
    try:
        async with c.stream("GET", url) as resp:
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                total += len(chunk)
                if (datetime.utcnow() - start).total_seconds() >= duration_seconds:
                    break
    except (asyncio.CancelledError, Exception):
        pass
    return total, (datetime.utcnow() - start).total_seconds()


async def connect_disconnect_cycle(
    base_url: str,
    guide_number: str,
    connect_seconds: float = 5.0,
    *,
    client: httpx.AsyncClient | None = None,
) -> tuple[int, float]:
    """Connect, read for connect_seconds, disconnect."""
    return await open_stream(base_url, guide_number, client=client, duration_seconds=connect_seconds)
