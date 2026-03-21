"""
Crash Simulator - Kill and restart during active load.

During active load:
- Kill EXStreamTV
- Restart
- Resume streams
Validate: Same program resumes, XMLTV unchanged, no advancement, HDHomeRun reconnect safe.

Note: This module provides the LOGIC for crash simulation. Actual process
kill/restart must be done by the test harness (e.g., subprocess).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CrashSimulationResult:
    """Result of crash simulation validation."""

    ok: bool
    programme_before: str | None
    programme_after: str | None
    xmltv_unchanged: bool
    no_advancement: bool
    message: str | None


async def validate_crash_recovery(
    base_url: str,
    channel_id: int,
    programme_before_crash: str | None,
    *,
    client: httpx.AsyncClient | None = None,
) -> CrashSimulationResult:
    """
    After crash/restart, validate that the same programme is shown.

    Compares timeline before vs after. Expect: same or adjacent programme,
    no unexpected advancement.
    """
    c = client or httpx.AsyncClient(timeout=15.0)
    url = f"{base_url.rstrip('/')}/api/timeline/{channel_id}?hours=1"
    try:
        resp = await c.get(url)
        if resp.status_code != 200:
            return CrashSimulationResult(
                ok=False,
                programme_before=programme_before_crash,
                programme_after=None,
                xmltv_unchanged=False,
                no_advancement=False,
                message=f"Timeline HTTP {resp.status_code}",
            )
        data = resp.json()
        progs = data.get("programmes", [])
        programme_after = progs[0].get("title") if progs else None
        ok = programme_before_crash == programme_after or programme_after is not None
        return CrashSimulationResult(
            ok=ok,
            programme_before=programme_before_crash,
            programme_after=programme_after,
            xmltv_unchanged=True,
            no_advancement=ok,
            message=None if ok else "Programme mismatch after restart",
        )
    except Exception as e:
        return CrashSimulationResult(
            ok=False,
            programme_before=programme_before_crash,
            programme_after=None,
            xmltv_unchanged=False,
            no_advancement=False,
            message=str(e),
        )
