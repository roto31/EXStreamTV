"""
ChannelClock — Sole schedule authority.

Zero-drift mode: uses time.monotonic() to derive now_epoch.
Position: current_offset = (now_epoch - anchor_epoch) % total_cycle_duration
Strict comparator: start_epoch <= now_epoch < stop_epoch
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from exstreamtv.scheduling.canonical_timeline import CanonicalTimelineItem

logger = logging.getLogger(__name__)

DRIFT_THRESHOLD_SECONDS = 2.0


@dataclass
class ResolvedPosition:
    """Result of resolving clock position to timeline item."""

    item: CanonicalTimelineItem
    seek_seconds: float
    offset_into_cycle: float
    item_index: int  # For logging only; not authoritative


def _utc_epoch(dt: datetime) -> float:
    """Convert datetime to UTC epoch seconds."""
    if dt.tzinfo:
        return dt.timestamp()
    return datetime(*dt.timetuple()[:6], tzinfo=timezone.utc).timestamp()


class ChannelClock:
    """
    Clock as sole schedule authority. Zero-drift mode.

    Uses monotonic reference to eliminate DST/NTP/manual clock drift.
    anchor_wall_epoch: UTC epoch when cycle started.
    anchor_monotonic: time.monotonic() at creation.
    """

    def __init__(
        self,
        channel_id: int,
        anchor_time: datetime,
        total_cycle_duration: float,
    ):
        self.channel_id = channel_id
        self._anchor_time = anchor_time
        self._anchor_wall_epoch = _utc_epoch(anchor_time)
        self._anchor_monotonic = time.monotonic()
        self._total_cycle_duration = max(0.001, total_cycle_duration)

    @property
    def anchor_time(self) -> datetime:
        return self._anchor_time

    @property
    def total_cycle_duration(self) -> float:
        return self._total_cycle_duration

    def _now_epoch(self) -> float:
        """Derive now as UTC epoch using monotonic. Immune to clock jumps."""
        delta = time.monotonic() - self._anchor_monotonic
        return self._anchor_wall_epoch + delta

    def check_drift(self) -> float:
        """Return abs(system_time - monotonic_derived). Drift-safe reset if > threshold."""
        derived = self._now_epoch()
        system_epoch = time.time()
        drift = abs(system_epoch - derived)
        if drift > DRIFT_THRESHOLD_SECONDS:
            logger.warning(
                f"Clock drift ch={self.channel_id}: {drift:.1f}s. Resetting anchor (T preserved)."
            )
            self._anchor_wall_epoch = derived
            self._anchor_monotonic = time.monotonic()
        return drift

    def current_offset(self, now: Optional[datetime] = None) -> float:
        """
        Compute current offset into the cycle (seconds).
        Uses monotonic-derived now when now is None.
        """
        if now is not None:
            now_epoch = _utc_epoch(now)
        else:
            now_epoch = self._now_epoch()
        elapsed = now_epoch - self._anchor_wall_epoch
        return elapsed % self._total_cycle_duration

    def resolve_item_and_seek(
        self,
        timeline: list[CanonicalTimelineItem],
        now: Optional[datetime] = None,
    ) -> Optional[ResolvedPosition]:
        """
        Resolve clock position to timeline item and seek offset.
        Uses monotonic-derived now when now is None (zero-drift).
        """
        if not timeline:
            return None
        offset = self.current_offset(now)
        cumulative = 0.0
        for idx, item in enumerate(timeline):
            duration = item.canonical_duration or 1800.0
            if cumulative + duration > offset:
                seek = offset - cumulative
                seek = max(0.0, min(seek, max(0, duration - 10)))  # Leave 10s buffer
                return ResolvedPosition(
                    item=item,
                    seek_seconds=seek,
                    offset_into_cycle=offset,
                    item_index=idx,
                )
            cumulative += duration
        item = timeline[-1]
        duration = item.canonical_duration or 1800.0
        seek = max(0.0, duration - 10)
        return ResolvedPosition(
            item=item,
            seek_seconds=seek,
            offset_into_cycle=offset,
            item_index=len(timeline) - 1,
        )
