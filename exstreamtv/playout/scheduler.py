"""
Playout scheduler for determining what plays when.

Ported from ErsatzTV PlayoutModeScheduler*.cs files.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from exstreamtv.playout.enumerators import CollectionEnumerator
from exstreamtv.playout.state import PlayoutItem, PlayoutState


class ScheduleMode(Enum):
    """
    Schedule item playback mode.

    Ported from ErsatzTV PlayoutMode.
    """

    ONE = "one"  # Play one item, then move to next schedule item
    MULTIPLE = "multiple"  # Play N items, then move to next
    DURATION = "duration"  # Play items for a duration, then move to next
    FLOOD = "flood"  # Play until a specific time


@dataclass
class ScheduleItem:
    """
    A schedule item defining what to play and when.

    Ported from ErsatzTV ProgramScheduleItem.
    """

    id: int
    schedule_id: int
    index: int
    start_type: str = "dynamic"  # dynamic, fixed
    start_time: Optional[datetime] = None  # For fixed start

    # Content source
    collection_id: Optional[int] = None
    playlist_id: Optional[int] = None
    multi_collection_id: Optional[int] = None

    # Playback mode
    playout_mode: ScheduleMode = ScheduleMode.ONE
    playout_count: int = 1  # For MULTIPLE mode
    playout_duration: Optional[timedelta] = None  # For DURATION mode
    flood_end_time: Optional[datetime] = None  # For FLOOD mode

    # Filler
    pre_roll_filler_id: Optional[int] = None
    mid_roll_filler_id: Optional[int] = None
    post_roll_filler_id: Optional[int] = None
    tail_filler_id: Optional[int] = None
    fallback_filler_id: Optional[int] = None

    # Options
    custom_title: Optional[str] = None
    guide_mode: str = "normal"  # normal, filler, ignore
    offline_tail: bool = False


@dataclass
class ScheduleResult:
    """Result of scheduling items."""

    items: List[PlayoutItem] = field(default_factory=list)
    next_schedule_item_index: int = 0
    new_anchors: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    finished: bool = False
    error: Optional[str] = None


class PlayoutScheduler:
    """
    Main scheduler that determines playout items.

    Ported from ErsatzTV PlayoutModeScheduler* classes.
    """

    def __init__(
        self,
        schedule_items: List[ScheduleItem],
        enumerators: Optional[Dict[int, CollectionEnumerator]] = None,
    ):
        self.schedule_items = schedule_items
        self.enumerators = enumerators or {}
        self._current_index = 0

    def schedule_items_for_range(
        self,
        start: datetime,
        end: datetime,
        state: PlayoutState,
    ) -> ScheduleResult:
        """
        Schedule playout items for a time range.

        Args:
            start: Start of range.
            end: End of range.
            state: Current playout state.

        Returns:
            ScheduleResult with items and state updates.
        """
        result = ScheduleResult()
        current_time = start
        schedule_index = state.schedule_item_index

        while current_time < end and schedule_index < len(self.schedule_items):
            schedule_item = self.schedule_items[schedule_index]

            # Get items for this schedule item
            items_result = self._schedule_item(
                schedule_item,
                current_time,
                end,
                state,
            )

            result.items.extend(items_result.items)

            if items_result.items:
                last_item = items_result.items[-1]
                current_time = last_item.finish

            # Update anchor state
            result.new_anchors.update(items_result.new_anchors)

            # Move to next schedule item
            if not items_result.finished:
                schedule_index = (schedule_index + 1) % len(self.schedule_items)
            else:
                break

        result.next_schedule_item_index = schedule_index
        return result

    def _schedule_item(
        self,
        schedule_item: ScheduleItem,
        start: datetime,
        end: datetime,
        state: PlayoutState,
    ) -> ScheduleResult:
        """Schedule items based on the schedule item's mode."""
        mode = schedule_item.playout_mode

        if mode == ScheduleMode.ONE:
            return self._schedule_one(schedule_item, start, state)
        elif mode == ScheduleMode.MULTIPLE:
            return self._schedule_multiple(schedule_item, start, state)
        elif mode == ScheduleMode.DURATION:
            return self._schedule_duration(schedule_item, start, state)
        elif mode == ScheduleMode.FLOOD:
            return self._schedule_flood(schedule_item, start, end, state)
        else:
            return ScheduleResult(error=f"Unknown mode: {mode}")

    def _schedule_one(
        self,
        schedule_item: ScheduleItem,
        start: datetime,
        state: PlayoutState,
    ) -> ScheduleResult:
        """Schedule one item from the collection."""
        result = ScheduleResult()

        collection_id = schedule_item.collection_id
        if not collection_id or collection_id not in self.enumerators:
            result.error = f"No enumerator for collection {collection_id}"
            return result

        enumerator = self.enumerators[collection_id]
        media_item = enumerator.get_next()

        if media_item:
            duration = getattr(media_item, "duration", timedelta(hours=1))

            playout_item = PlayoutItem(
                id=len(state.items) + len(result.items) + 1,
                playout_id=state.playout_id,
                media_item_id=getattr(media_item, "id", 0),
                start=start,
                finish=start + duration,
                custom_title=schedule_item.custom_title,
                collection_key=str(collection_id),
            )
            result.items.append(playout_item)

            # Save enumerator state
            result.new_anchors[collection_id] = enumerator.get_state()

        return result

    def _schedule_multiple(
        self,
        schedule_item: ScheduleItem,
        start: datetime,
        state: PlayoutState,
    ) -> ScheduleResult:
        """Schedule multiple items from the collection."""
        result = ScheduleResult()
        current_time = start
        count = schedule_item.playout_count or 1

        collection_id = schedule_item.collection_id
        if not collection_id or collection_id not in self.enumerators:
            result.error = f"No enumerator for collection {collection_id}"
            return result

        enumerator = self.enumerators[collection_id]

        for _ in range(count):
            media_item = enumerator.get_next()
            if not media_item:
                break

            duration = getattr(media_item, "duration", timedelta(hours=1))

            playout_item = PlayoutItem(
                id=len(state.items) + len(result.items) + 1,
                playout_id=state.playout_id,
                media_item_id=getattr(media_item, "id", 0),
                start=current_time,
                finish=current_time + duration,
                custom_title=schedule_item.custom_title,
                collection_key=str(collection_id),
            )
            result.items.append(playout_item)
            current_time = playout_item.finish

        # Save enumerator state
        result.new_anchors[collection_id] = enumerator.get_state()

        return result

    def _schedule_duration(
        self,
        schedule_item: ScheduleItem,
        start: datetime,
        state: PlayoutState,
    ) -> ScheduleResult:
        """Schedule items for a specified duration."""
        result = ScheduleResult()
        current_time = start
        target_duration = schedule_item.playout_duration or timedelta(hours=1)
        target_end = start + target_duration

        collection_id = schedule_item.collection_id
        if not collection_id or collection_id not in self.enumerators:
            result.error = f"No enumerator for collection {collection_id}"
            return result

        enumerator = self.enumerators[collection_id]

        while current_time < target_end:
            media_item = enumerator.get_next()
            if not media_item:
                break

            duration = getattr(media_item, "duration", timedelta(hours=1))

            # Trim last item if it would exceed target
            if current_time + duration > target_end:
                duration = target_end - current_time

            playout_item = PlayoutItem(
                id=len(state.items) + len(result.items) + 1,
                playout_id=state.playout_id,
                media_item_id=getattr(media_item, "id", 0),
                start=current_time,
                finish=current_time + duration,
                custom_title=schedule_item.custom_title,
                collection_key=str(collection_id),
            )
            result.items.append(playout_item)
            current_time = playout_item.finish

        # Save enumerator state
        result.new_anchors[collection_id] = enumerator.get_state()

        return result

    def _schedule_flood(
        self,
        schedule_item: ScheduleItem,
        start: datetime,
        end: datetime,
        state: PlayoutState,
    ) -> ScheduleResult:
        """Schedule items until a specific end time."""
        result = ScheduleResult()
        current_time = start
        flood_end = schedule_item.flood_end_time or end

        collection_id = schedule_item.collection_id
        if not collection_id or collection_id not in self.enumerators:
            result.error = f"No enumerator for collection {collection_id}"
            return result

        enumerator = self.enumerators[collection_id]

        while current_time < flood_end:
            media_item = enumerator.get_next()
            if not media_item:
                break

            duration = getattr(media_item, "duration", timedelta(hours=1))

            playout_item = PlayoutItem(
                id=len(state.items) + len(result.items) + 1,
                playout_id=state.playout_id,
                media_item_id=getattr(media_item, "id", 0),
                start=current_time,
                finish=current_time + duration,
                custom_title=schedule_item.custom_title,
                collection_key=str(collection_id),
            )
            result.items.append(playout_item)
            current_time = playout_item.finish

        # Save enumerator state
        result.new_anchors[collection_id] = enumerator.get_state()
        result.finished = current_time >= flood_end

        return result
