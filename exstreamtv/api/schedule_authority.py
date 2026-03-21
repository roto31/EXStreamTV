"""
Clock Authority API — Schedule, clock, timeline, and XMLTV endpoints.

All schedule position derived from ChannelClock. No index, no last_item_index.
"""

import logging
from fastapi.responses import RedirectResponse
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.database import Channel, get_db, get_sync_session_factory
from exstreamtv.scheduling import get_authority, build_programmes_from_clock

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Schedule Authority"])


@router.get("/xmltv", include_in_schema=False)
async def get_xmltv_redirect() -> RedirectResponse:
    """
    Redirect to clock-derived XMLTV EPG.

    The EPG is served at /iptv/xmltv.xml (root level for M3U/StreamTV compatibility).
    """
    return RedirectResponse(url="/iptv/xmltv.xml", status_code=302)


async def _get_channel_or_404(channel_id: int, db: AsyncSession) -> Channel:
    """Get channel by ID or raise 404."""
    from sqlalchemy import select
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    ch = result.scalar_one_or_none()
    if not ch:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ch


@router.get("/clock/{channel_id}")
async def get_clock(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Get channel clock state: anchor_time, total_cycle_duration, current_offset.

    Position is derived purely from clock. No index.
    """
    await _get_channel_or_404(channel_id, db)
    factory = get_sync_session_factory()
    auth = get_authority(factory)
    clock = await auth.ensure_clock(channel_id)
    if not clock:
        return {
            "channel_id": channel_id,
            "anchor_time": None,
            "total_cycle_duration": 0.0,
            "current_offset": 0.0,
            "message": "No clock; channel has not started or has no timeline",
        }
    n = now or datetime.utcnow()
    return {
        "channel_id": channel_id,
        "anchor_time": clock.anchor_time.isoformat() if clock.anchor_time else None,
        "total_cycle_duration": clock.total_cycle_duration,
        "current_offset": clock.current_offset(n),
    }


@router.get("/schedule/{channel_id}")
async def get_schedule(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get canonical timeline (schedule) for channel.

    Returns ordered items with canonical_duration. Used by clock for resolution.
    """
    ch = await _get_channel_or_404(channel_id, db)
    factory = get_sync_session_factory()
    auth = get_authority(factory)
    timeline = auth.get_timeline(channel_id)
    if not timeline:
        return {
            "channel_id": channel_id,
            "channel_number": ch.number,
            "channel_name": ch.name,
            "items": [],
            "message": "No timeline; channel has no playout or schedule",
        }
    items = []
    for i, t in enumerate(timeline):
        items.append({
            "index": i,
            "title": t.title or t.custom_title or "Unknown",
            "canonical_duration": t.canonical_duration,
            "source": t.source,
        })
    return {
        "channel_id": channel_id,
        "channel_number": ch.number,
        "channel_name": ch.name,
        "total_cycle_duration": sum(t.canonical_duration or 1800 for t in timeline),
        "item_count": len(items),
        "items": items,
    }


@router.get("/timeline/{channel_id}")
async def get_timeline(
    channel_id: int,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Get current + future programme timeline (clock-derived).

    Programmes from now to now+hours. Aligns with EPG and playback.
    """
    ch = await _get_channel_or_404(channel_id, db)
    factory = get_sync_session_factory()
    auth = get_authority(factory)
    clock = await auth.ensure_clock(channel_id)
    timeline = auth.get_timeline(channel_id)
    if not clock or not timeline:
        return {
            "channel_id": channel_id,
            "channel_number": ch.number,
            "channel_name": ch.name,
            "programmes": [],
            "message": "No clock/timeline; channel has not started or has no schedule",
        }
    now = datetime.utcnow()
    progs = build_programmes_from_clock(
        clock, timeline, now, duration_hours=float(hours), max_programmes=min(500, hours * 4)
    )
    programmes = [
        {
            "start": p.start_time.isoformat(),
            "stop": p.stop_time.isoformat(),
            "title": p.title,
        }
        for p in progs
    ]
    return {
        "channel_id": channel_id,
        "channel_number": ch.number,
        "channel_name": ch.name,
        "programmes": programmes,
    }
