"""
Drift Monitor — Detect clock and schedule drift over time.

Run drift check every N seconds for M minutes.
Fail if offset jumps or drifts unexpectedly.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from .clock_validator import (
    ClockValidationResult,
    check_offset_drift,
    validate_clock,
)

logger = logging.getLogger(__name__)


@dataclass
class DriftSample:
    """Single drift check sample."""

    timestamp: datetime
    channel_id: int
    offset: float
    total_cycle: float
    ok: bool
    message: str | None


@dataclass
class DriftMonitorResult:
    """Result of drift monitoring session."""

    channel_id: int
    samples: list[DriftSample] = field(default_factory=list)
    drift_detected: bool = False
    failure_message: str | None = None


async def run_drift_monitor(
    base_url: str,
    channel_ids: list[int],
    *,
    interval_seconds: float = 5.0,
    duration_seconds: float = 600.0,
    client: httpx.AsyncClient | None = None,
) -> dict[int, DriftMonitorResult]:
    """
    Run drift check every interval_seconds for duration_seconds.

    For each channel, validate clock repeatedly and check offset consistency.
    """
    c = client or httpx.AsyncClient(timeout=15.0)
    results: dict[int, DriftMonitorResult] = {ch: DriftMonitorResult(channel_id=ch) for ch in channel_ids}
    start = datetime.utcnow()
    prev_offsets: dict[int, tuple[float, float, datetime]] = {}

    while (datetime.utcnow() - start).total_seconds() < duration_seconds:
        for channel_id in channel_ids:
            res = await validate_clock(base_url, channel_id, client=c)
            sample = DriftSample(
                timestamp=datetime.utcnow(),
                channel_id=channel_id,
                offset=res.current_offset or 0,
                total_cycle=res.total_cycle_duration or 1,
                ok=res.ok,
                message=res.message,
            )
            results[channel_id].samples.append(sample)

            if not res.ok:
                results[channel_id].drift_detected = True
                results[channel_id].failure_message = res.message
                continue

            prev = prev_offsets.get(channel_id)
            if prev:
                offset_before, total, t_before = prev
                elapsed = (sample.timestamp - t_before).total_seconds()
                ok_drift, msg = check_offset_drift(
                    offset_before,
                    sample.offset,
                    elapsed,
                    total,
                    tolerance_seconds=3.0,
                )
                if not ok_drift:
                    results[channel_id].drift_detected = True
                    results[channel_id].failure_message = msg

            prev_offsets[channel_id] = (
                sample.offset,
                sample.total_cycle,
                sample.timestamp,
            )

        await asyncio.sleep(interval_seconds)

    return results
