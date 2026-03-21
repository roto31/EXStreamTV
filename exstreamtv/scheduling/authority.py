"""
BroadcastScheduleAuthority — Orchestrator for clock-based scheduling.

Clock is sole schedule authority. Versioned cache, overlap prevention, active assertion.
"""

import asyncio
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from exstreamtv.core.async_guard import AsyncCancellationGuard
from exstreamtv.core.shutdown_state import is_shutting_down

from exstreamtv.scheduling.canonical_timeline import (
    CanonicalTimelineItem,
    build_from_playout,
    build_from_yaml,
)
from exstreamtv.scheduling.authoritative_time import now_epoch, now_datetime_utc
from exstreamtv.scheduling.clock import ChannelClock, _utc_epoch
from exstreamtv.scheduling.parser import ScheduleParser

logger = logging.getLogger(__name__)


def _authoritative_now() -> datetime:
    """Scheduling now. Monotonic-derived. No wall-clock."""
    return now_datetime_utc()


def _timeline_version_hash(session: Session, channel_id: int, channel_number: str) -> str:
    """Compute version hash from playout/schedule updated_at."""
    from exstreamtv.database.models import Playout, ProgramSchedule
    from sqlalchemy import select
    stmt = select(Playout).where(
        Playout.channel_id == channel_id,
        Playout.is_active == True,
    )
    playout = session.execute(stmt).scalar_one_or_none()
    parts = []
    if playout:
        parts.append(str(getattr(playout, "updated_at", None) or ""))
        if getattr(playout, "program_schedule_id", None):
            sched = session.get(ProgramSchedule, playout.program_schedule_id)
            if sched:
                parts.append(str(getattr(sched, "updated_at", None) or ""))
    schedule_file = ScheduleParser.find_schedule_file(channel_number)
    if schedule_file and schedule_file.exists():
        parts.append(str(schedule_file.stat().st_mtime))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


class BroadcastScheduleAuthority:
    """
    Central scheduling authority. Versioned timeline cache. Overlap prevention.
    """

    def __init__(self, db_session_factory: Callable[[], Session]):
        self._db_session_factory = db_session_factory
        self._clocks: dict[int, ChannelClock] = {}
        self._timelines: dict[int, list[CanonicalTimelineItem]] = {}
        self._timeline_versions: dict[int, str] = {}
        self._anchor_times: dict[int, datetime] = {}
        self._timeline_locks: dict[int, asyncio.Lock] = {}
        self._epg_failure_logged: set[int] = set()

    def get_timeline(self, channel_id: int) -> list[CanonicalTimelineItem]:
        """Get cached canonical timeline. Auto-invalidate if version mismatch."""
        cached = self._timelines.get(channel_id, [])
        if not cached:
            return []
        session = self._db_session_factory()
        try:
            ch_num = self._get_channel_number(channel_id)
            current_ver = _timeline_version_hash(session, channel_id, ch_num)
            stored_ver = self._timeline_versions.get(channel_id)
            if stored_ver != current_ver:
                self.invalidate_timeline(channel_id)
                logger.info(f"Timeline version mismatch ch={channel_id}, invalidated")
                return []
        finally:
            session.close()
        return cached

    def invalidate_timeline(self, channel_id: int) -> None:
        """Clear cached timeline and clock for channel."""
        self._timelines.pop(channel_id, None)
        self._clocks.pop(channel_id, None)
        self._timeline_versions.pop(channel_id, None)
        self._anchor_times.pop(channel_id, None)
        logger.debug(f"Invalidated timeline cache for channel {channel_id}")

    def invalidate_all_timelines(self) -> None:
        """Clear all cached timelines and clocks."""
        self._timelines.clear()
        self._clocks.clear()
        self._timeline_versions.clear()
        self._anchor_times.clear()
        logger.debug("Invalidated all timeline caches")

    def get_clock(self, channel_id: int) -> Optional[ChannelClock]:
        """Get ChannelClock for channel. Returns None if not initialized."""
        return self._clocks.get(channel_id)

    def _get_timeline_lock(self, channel_id: int) -> asyncio.Lock:
        """Per-channel lock to prevent concurrent ensure_clock for same channel."""
        if channel_id not in self._timeline_locks:
            self._timeline_locks[channel_id] = asyncio.Lock()
        return self._timeline_locks[channel_id]

    async def ensure_clock(
        self,
        channel_id: int,
        anchor_time: Optional[datetime] = None,
    ) -> Optional[ChannelClock]:
        """
        Ensure ChannelClock exists for channel. Build timeline if needed.
        Uses anchor_time from ChannelPlaybackPosition if not provided.
        Locked per-channel to prevent concurrent builds.
        """
        if is_shutting_down():
            raise asyncio.CancelledError("Shutdown in progress")
        if channel_id in self._clocks:
            return self._clocks[channel_id]
        async with AsyncCancellationGuard.safe_lock(
            self._get_timeline_lock(channel_id),
            name=f"timeline_lock:{channel_id}",
        ):
            if channel_id in self._clocks:
                return self._clocks[channel_id]
            timeline = self._timelines.get(channel_id)
            if not timeline:
                timeline = await self.load_timeline_async(channel_id)
                if not timeline:
                    return None
                self._timelines[channel_id] = timeline
                session = self._db_session_factory()
                try:
                    ch_num = self._get_channel_number(channel_id)
                    self._timeline_versions[channel_id] = _timeline_version_hash(
                        session, channel_id, ch_num
                    )
                finally:
                    session.close()
            total = sum(t.canonical_duration or 1800 for t in timeline)
            if total <= 0:
                total = 1800 * len(timeline) or 1800
            if os.environ.get("EXSTREAMTV_VALIDATE_DURATIONS") == "1":
                assert total > 0, f"total_cycle_duration must be > 0 for channel {channel_id}"
            existing_anchor = self._get_anchor_from_db(channel_id)
            anchor = anchor_time or existing_anchor or _authoritative_now()
            if not existing_anchor and not anchor_time:
                self.persist_anchor(channel_id, anchor)
            clock = ChannelClock(
                channel_id=channel_id,
                anchor_time=anchor,
                total_cycle_duration=total,
            )
            self._clocks[channel_id] = clock
            # Invariant: exactly one active item
            resolved = clock.resolve_item_and_seek(timeline, now=None)
            assert resolved is not None or not timeline, (
                f"ch={channel_id}: resolve must return item when timeline non-empty"
            )
            return self._clocks[channel_id]

    def _get_channel_number(self, channel_id: int) -> str:
        """Get channel number from DB."""
        from exstreamtv.database.models import Channel
        session = self._db_session_factory()
        try:
            ch = session.get(Channel, channel_id)
            return str(ch.number) if ch and ch.number else str(channel_id)
        finally:
            session.close()

    def _get_anchor_from_db(self, channel_id: int) -> Optional[datetime]:
        """Load playout_start_time from ChannelPlaybackPosition."""
        from exstreamtv.database.models import ChannelPlaybackPosition

        session = self._db_session_factory()
        try:
            pos = session.query(ChannelPlaybackPosition).filter(
                ChannelPlaybackPosition.channel_id == channel_id
            ).first()
            if pos and pos.playout_start_time:
                return pos.playout_start_time
            return None
        finally:
            session.close()

    async def load_timeline_async(self, channel_id: int) -> list[CanonicalTimelineItem]:
        """Load timeline asynchronously. Call before ensure_clock."""
        channel_number = self._get_channel_number(channel_id)
        schedule_file = ScheduleParser.find_schedule_file(channel_number)
        if schedule_file and schedule_file.exists():
            try:
                timeline = await build_from_yaml(
                    channel_id,
                    schedule_file,
                    self._db_session_factory,
                    max_items=2000,
                )
                if timeline:
                    self._timelines[channel_id] = timeline
                    return timeline
            except Exception as e:
                logger.warning(f"YAML timeline failed for ch={channel_id}: {e}")
        timeline = await build_from_playout(
            channel_id,
            self._db_session_factory,
            max_items=2000,
            skip_resolution=True,
        )
        if timeline:
            self._timelines[channel_id] = timeline
        return timeline

    def persist_anchor(self, channel_id: int, anchor_time: datetime) -> None:
        """Persist anchor_time to ChannelPlaybackPosition. Only anchor, no index."""
        from exstreamtv.database.models import ChannelPlaybackPosition

        session = self._db_session_factory()
        try:
            from exstreamtv.database.models import Channel
            pos = session.query(ChannelPlaybackPosition).filter(
                ChannelPlaybackPosition.channel_id == channel_id
            ).first()
            if pos:
                pos.playout_start_time = anchor_time
                pos.last_played_at = _authoritative_now()
            else:
                ch = session.get(Channel, channel_id)
                if ch:
                    pos = ChannelPlaybackPosition(
                        channel_id=channel_id,
                        channel_number=str(getattr(ch, "number", channel_id)),
                        playout_start_time=anchor_time,
                        last_played_at=_authoritative_now(),
                    )
                    session.add(pos)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.warning(f"Failed to persist anchor for ch={channel_id}: {e}")
        finally:
            session.close()


# Singleton access
_authority: Optional[BroadcastScheduleAuthority] = None


def get_authority(db_session_factory: Callable[[], Session]) -> BroadcastScheduleAuthority:
    """Get or create BroadcastScheduleAuthority singleton."""
    global _authority
    if _authority is None:
        _authority = BroadcastScheduleAuthority(db_session_factory)
    return _authority
