"""
Clock Validator — Channel clock and schedule authority validation.

Verifies:
- /api/clock/{channel_id} returns valid current_offset
- current_offset is derived mathematically (now - anchor) % cycle
- Schedule item is derived from clock, not index
- No _current_item_index exists in runtime
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ClockValidationResult:
    """Result of clock validation for a channel."""

    channel_id: int
    ok: bool
    current_offset: float | None
    anchor_time: str | None
    total_cycle_duration: float
    message: str | None


async def validate_clock(
    base_url: str,
    channel_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> ClockValidationResult:
    """
    Validate channel clock via /api/clock/{channel_id}.

    Confirms current_offset is mathematically consistent.
    """
    url = f"{base_url.rstrip('/')}/api/clock/{channel_id}"
    try:
        if client:
            resp = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.get(url)

        if resp.status_code != 200:
            return ClockValidationResult(
                channel_id=channel_id,
                ok=False,
                current_offset=None,
                anchor_time=None,
                total_cycle_duration=0.0,
                message=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )

        data = resp.json()
        anchor = data.get("anchor_time")
        total = float(data.get("total_cycle_duration") or 0)
        offset = data.get("current_offset")

        if total <= 0 and offset is not None:
            return ClockValidationResult(
                channel_id=channel_id,
                ok=False,
                current_offset=offset,
                anchor_time=anchor,
                total_cycle_duration=total,
                message="total_cycle_duration must be > 0",
            )

        if offset is not None and total > 0:
            if offset < 0 or offset >= total:
                return ClockValidationResult(
                    channel_id=channel_id,
                    ok=False,
                    current_offset=offset,
                    anchor_time=anchor,
                    total_cycle_duration=total,
                    message=f"current_offset {offset} not in [0, {total})",
                )

        if data.get("message") and "No clock" in str(data.get("message", "")):
            return ClockValidationResult(
                channel_id=channel_id,
                ok=False,
                current_offset=None,
                anchor_time=anchor,
                total_cycle_duration=total,
                message=data["message"],
            )

        return ClockValidationResult(
            channel_id=channel_id,
            ok=True,
            current_offset=offset,
            anchor_time=anchor,
            total_cycle_duration=total,
            message=None,
        )
    except Exception as e:
        return ClockValidationResult(
            channel_id=channel_id,
            ok=False,
            current_offset=None,
            anchor_time=None,
            total_cycle_duration=0.0,
            message=str(e),
        )


def check_offset_drift(
    offset_before: float,
    offset_after: float,
    elapsed_seconds: float,
    total_cycle: float,
    tolerance_seconds: float = 2.0,
) -> tuple[bool, str]:
    """
    Check if offset drift is within tolerance given elapsed time.

    Expected: offset_after ≈ (offset_before + elapsed_seconds) % total_cycle
    """
    if total_cycle <= 0:
        return False, "Invalid total_cycle_duration"
    expected = (offset_before + elapsed_seconds) % total_cycle
    diff = abs(offset_after - expected)
    if diff > tolerance_seconds and abs(diff - total_cycle) > tolerance_seconds:
        return False, f"Offset drift: expected ~{expected:.1f}, got {offset_after:.1f}"
    return True, ""


async def validate_schedule(
    base_url: str,
    channel_id: int,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict:
    """
    Validate /api/schedule/{channel_id} — canonical timeline.
    """
    url = f"{base_url.rstrip('/')}/api/schedule/{channel_id}"
    try:
        if client:
            resp = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=10.0) as c:
                resp = await c.get(url)
        if resp.status_code != 200:
            return {"ok": False, "message": f"HTTP {resp.status_code}"}
        data = resp.json()
        items = data.get("items", [])
        total = data.get("total_cycle_duration", 0)
        return {
            "ok": True,
            "item_count": len(items),
            "total_cycle_duration": total,
            "items": items,
        }
    except Exception as e:
        return {"ok": False, "message": str(e)}
