"""
TimelineBuilder for EPG generation.

Builds monotonic programme timeline from playout items and ChannelPlaybackPosition.
Single source of truth: last_item_index and current_item_start_time from DB.
No elapsed-time drift; all derived from persisted anchor.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimelineProgramme:
    """A programme in the timeline with guaranteed monotonic times."""
    start_time: datetime
    stop_time: datetime
    media_item: Any
    playout_item: dict[str, Any]
    title: str = ""
    index: int = 0


@dataclass
class PlaybackAnchor:
    """Anchor for timeline calculation from ChannelPlaybackPosition."""
    playout_start_time: datetime
    last_item_index: int
    current_item_start_time: Optional[datetime] = None
    elapsed_seconds_in_item: int = 0


class TimelineBuilder:
    """
    Builds monotonic programme timeline from playout items.

    Uses last_item_index and current_item_start_time (or playout_start_time + sum of prior durations)
    as single source of truth. Guarantees: start[i] < stop[i], stop[i] == start[i+1], strictly increasing.
    """

    def build(
        self,
        playout_items: List[dict[str, Any]],
        playback_anchor: PlaybackAnchor,
        now: Optional[datetime] = None,
        max_programmes: int = 200,
    ) -> List[TimelineProgramme]:
        """
        Build monotonic timeline from playout items.

        Args:
            playout_items: List of items in playback order. Each item has:
                media_item (with duration), custom_title, etc.
            playback_anchor: Anchor from ChannelPlaybackPosition.
            now: Reference time (default: utcnow).
            max_programmes: Max programmes to emit.

        Returns:
            List of TimelineProgramme with strictly monotonic times.
        """
        if not playout_items:
            return []

        now = now or datetime.utcnow()
        programmes: List[TimelineProgramme] = []

        # Determine start time of current item
        last_idx = max(0, playback_anchor.last_item_index % len(playout_items))
        current_item_start = playback_anchor.current_item_start_time

        if current_item_start is None and playback_anchor.playout_start_time:
            # Fallback: compute from playout_start_time + sum of prior durations
            prior_duration = 0
            for i in range(last_idx):
                item = playout_items[i % len(playout_items)]
                mi = item.get("media_item")
                prior_duration += (mi.duration if mi and hasattr(mi, "duration") else 1800) or 1800
            current_item_start = playback_anchor.playout_start_time + timedelta(seconds=prior_duration)
        elif current_item_start is None:
            current_item_start = now

        # Walk items starting from last_item_index
        idx = last_idx
        prev_stop = current_item_start
        count = 0

        while count < max_programmes:
            item = playout_items[idx % len(playout_items)]
            media_item = item.get("media_item")
            duration = 1800
            if media_item and hasattr(media_item, "duration") and media_item.duration:
                duration = media_item.duration

            start_time = prev_stop
            stop_time = start_time + timedelta(seconds=duration)

            title = item.get("custom_title") or ""
            if not title and media_item and hasattr(media_item, "title"):
                title = media_item.title or ""

            programmes.append(
                TimelineProgramme(
                    start_time=start_time,
                    stop_time=stop_time,
                    media_item=media_item,
                    playout_item=item,
                    title=title,
                    index=len(programmes),
                )
            )
            prev_stop = stop_time
            idx += 1
            count += 1

        return programmes
