"""
XMLTV generation from ChannelClock.

Derived strictly from clock. Zero-drift. No index, no last_item_index.
Strict comparator: start_epoch <= now_epoch < stop_epoch
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from exstreamtv.scheduling.authority import BroadcastScheduleAuthority, get_authority
from exstreamtv.scheduling.canonical_timeline import CanonicalTimelineItem
from exstreamtv.scheduling.clock import ChannelClock, _utc_epoch

logger = logging.getLogger(__name__)


@dataclass
class ClockProgramme:
    """Programme for XMLTV from clock."""

    start_time: datetime
    stop_time: datetime
    title: str
    media_item: Optional[Any] = None
    playout_item: Optional[Any] = None


def build_programmes_from_clock(
    clock: ChannelClock,
    timeline: list[CanonicalTimelineItem],
    now: Optional[datetime] = None,
    duration_hours: float = 24.0,
    max_programmes: int = 200,
) -> list[ClockProgramme]:
    """
    Build programme list from clock + canonical timeline.
    When now is None, uses monotonic-derived now (zero-drift).
    """
    if not timeline:
        return []
    offset = clock.current_offset(now)
    total = clock.total_cycle_duration
    anchor = clock.anchor_time
    anchor_epoch = _utc_epoch(anchor)
    if now is not None:
        now_epoch = _utc_epoch(now)
    else:
        now_epoch = clock._now_epoch()
    elapsed = now_epoch - anchor_epoch
    cycle_index = int(elapsed // total) if total > 0 else 0
    cycle_start = anchor + timedelta(seconds=cycle_index * total)

    cumulative = 0.0
    start_item_idx = 0
    for idx, item in enumerate(timeline):
        duration = item.canonical_duration or 1800.0
        if cumulative + duration > offset:
            start_item_idx = idx
            break
        cumulative += duration

    programmes: list[ClockProgramme] = []
    now_dt = datetime.fromtimestamp(now_epoch, tz=timezone.utc).replace(tzinfo=None) if now is None else now
    end_time = now_dt + timedelta(hours=duration_hours)
    item_start = cycle_start + timedelta(seconds=cumulative)
    idx = start_item_idx
    count = 0

    prev_stop = None
    while count < max_programmes and item_start < end_time:
        item = timeline[idx % len(timeline)]
        duration = item.canonical_duration or 1800.0
        item_stop = item_start + timedelta(seconds=duration)
        # Invariant: non-overlap prev.stop <= next.start
        if prev_stop is not None and item_start < prev_stop:
            raise AssertionError(
                f"Timeline overlap: item_start {item_start} < prev_stop {prev_stop}"
            )
        prev_stop = item_stop
        programme_start = item_start if item_start >= now_dt else now_dt
        programme_stop = min(item_stop, end_time)
        if programme_start < programme_stop:
            programmes.append(
                ClockProgramme(
                    start_time=programme_start,
                    stop_time=programme_stop,
                    title=item.title or item.custom_title or "Unknown",
                    media_item=item.media_item,
                    playout_item=item.playout_item,
                )
            )
            count += 1
        item_start = item_stop
        idx += 1
        if idx >= len(timeline):
            idx = 0
            cycle_index += 1
            cycle_start = anchor + timedelta(seconds=cycle_index * total)
            item_start = cycle_start

    # Invariant: exactly one active programme contains now_epoch
    active = [p for p in programmes if _utc_epoch(p.start_time) <= now_epoch < _utc_epoch(p.stop_time)]
    assert len(active) == 1, f"Single active: expected 1, got {len(active)} for now_epoch={now_epoch}"
    return programmes


async def build_epg_from_clock(
    db_session_factory: Callable[[], Session],
    channels: list,
    now: Optional[datetime] = None,
    duration_hours: float = 24.0,
) -> dict[int, list[ClockProgramme]]:
    """
    Build EPG programmes for channels from clock authority.
    Circuit breaker: on failure, log once per channel and skip (do not retry every request).
    """
    auth = get_authority(db_session_factory)
    result: dict[int, list[ClockProgramme]] = {}

    for channel in channels:
        channel_id = channel.id if hasattr(channel, "id") else channel
        try:
            clock = await auth.ensure_clock(channel_id)
            if not clock:
                result[channel_id] = []
                continue
            timeline = auth.get_timeline(channel_id)
            if not timeline:
                result[channel_id] = []
                continue
            programmes = build_programmes_from_clock(
                clock,
                timeline,
                now=None,  # Zero-drift: use monotonic-derived now
                duration_hours=duration_hours,
                max_programmes=200,
            )
            result[channel_id] = programmes
            if channel_id in getattr(auth, "_epg_failure_logged", set()):
                auth._epg_failure_logged.discard(channel_id)
        except Exception as e:
            result[channel_id] = []
            if channel_id not in getattr(auth, "_epg_failure_logged", set()):
                auth._epg_failure_logged.add(channel_id)
                logger.warning(
                    f"Clock EPG failed for ch={channel_id} (skipping until next rebuild): {e}"
                )

    return result
