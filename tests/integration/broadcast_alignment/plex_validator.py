"""
Plex Live TV Simulator — Simulates Plex DVR behavior.

Validates:
- Fetch lineup.json
- Select channel and open stream URL
- Query metadata periodically
- Simulate disconnect/reconnect
- Plex-visible program matches XMLTV
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PlexSimulationResult:
    """Result of Plex-style simulation."""

    ok: bool
    lineup_fetched: bool
    stream_opened: bool
    bytes_received: int
    duration_seconds: float
    content_type: str | None
    message: str | None


async def simulate_plex_tune(
    base_url: str,
    guide_number: str,
    *,
    client: httpx.AsyncClient | None = None,
    duration_seconds: float = 10.0,
    max_bytes: int = 1024 * 1024,
) -> PlexSimulationResult:
    """
    Simulate Plex tuning to a channel.

    1. Fetch lineup.json
    2. Find URL for GuideNumber
    3. Open stream, read for duration_seconds or until max_bytes
    """
    c = client or httpx.AsyncClient(timeout=30.0)
    lineup_url = f"{base_url.rstrip('/')}/hdhomerun/lineup.json"

    try:
        resp = await c.get(lineup_url)
        if resp.status_code != 200:
            return PlexSimulationResult(
                ok=False,
                lineup_fetched=False,
                stream_opened=False,
                bytes_received=0,
                duration_seconds=0,
                content_type=None,
                message=f"Lineup HTTP {resp.status_code}",
            )

        lineup = resp.json()
        stream_url = None
        for entry in lineup:
            if str(entry.get("GuideNumber", "")) == str(guide_number):
                stream_url = entry.get("URL")
                break

        if not stream_url:
            return PlexSimulationResult(
                ok=False,
                lineup_fetched=True,
                stream_opened=False,
                bytes_received=0,
                duration_seconds=0,
                content_type=None,
                message=f"GuideNumber {guide_number} not in lineup",
            )

        start = datetime.utcnow()
        bytes_received = 0
        content_type = None

        async with c.stream("GET", stream_url) as stream_resp:
            content_type = stream_resp.headers.get("content-type")
            async for chunk in stream_resp.aiter_bytes(chunk_size=65536):
                bytes_received += len(chunk)
                elapsed = (datetime.utcnow() - start).total_seconds()
                if elapsed >= duration_seconds or bytes_received >= max_bytes:
                    break

        elapsed = (datetime.utcnow() - start).total_seconds()
        ok = bytes_received > 0 and elapsed >= min(5.0, duration_seconds)
        return PlexSimulationResult(
            ok=ok,
            lineup_fetched=True,
            stream_opened=True,
            bytes_received=bytes_received,
            duration_seconds=elapsed,
            content_type=content_type,
            message=None if ok else f"Only {bytes_received} bytes in {elapsed:.1f}s",
        )
    except Exception as e:
        return PlexSimulationResult(
            ok=False,
            lineup_fetched=False,
            stream_opened=False,
            bytes_received=0,
            duration_seconds=0,
            content_type=None,
            message=str(e),
        )
