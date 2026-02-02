"""
Playout state management.

Tracks the current state of a playout including position in schedule,
current item, and anchor points.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum


class PlayoutScheduleKind(Enum):
    """Type of playout schedule."""

    CLASSIC = "classic"
    TEMPLATE = "template"
    BLOCK = "block"
    EXTERNAL_JSON = "external_json"


@dataclass
class PlayoutAnchor:
    """
    Anchor point for schedule synchronization.

    Ported from ErsatzTV PlayoutProgramScheduleAnchor.
    """

    id: int
    playout_id: int
    collection_id: Optional[int] = None
    collection_type: Optional[str] = None  # collection, multi_collection, smart_collection
    anchor_date: Optional[datetime] = None
    enumerator_state: Optional[Dict[str, Any]] = None

    @property
    def is_checkpoint(self) -> bool:
        """Check if this is a checkpoint anchor (has date)."""
        return self.anchor_date is not None


@dataclass
class PlayoutItem:
    """
    A single item in a playout.

    Ported from ErsatzTV PlayoutItem.
    """

    id: int
    playout_id: int
    media_item_id: int
    start: datetime
    finish: datetime
    in_point: timedelta = timedelta(0)
    out_point: Optional[timedelta] = None
    guide_group: Optional[int] = None
    filler_kind: Optional[str] = None  # pre_roll, mid_roll, post_roll, tail, fallback
    custom_title: Optional[str] = None
    guide_start: Optional[datetime] = None
    guide_finish: Optional[datetime] = None
    block_key: Optional[str] = None
    collection_key: Optional[str] = None

    @property
    def duration(self) -> timedelta:
        """Calculate item duration."""
        return self.finish - self.start

    @property
    def media_duration(self) -> timedelta:
        """Calculate actual media duration (considering in/out points)."""
        if self.out_point:
            return self.out_point - self.in_point
        return self.duration


@dataclass
class PlayoutState:
    """
    Current state of a playout.

    Ported from ErsatzTV PlayoutBuilderState.
    """

    playout_id: int
    channel_id: int
    schedule_kind: PlayoutScheduleKind = PlayoutScheduleKind.CLASSIC

    # Current position
    current_time: datetime = field(default_factory=datetime.now)
    index: int = 0

    # Items
    items: List[PlayoutItem] = field(default_factory=list)
    anchors: List[PlayoutAnchor] = field(default_factory=list)

    # Scheduling state
    schedule_item_index: int = 0
    collection_enumerator_index: int = 0
    in_flood_mode: bool = False
    flood_start_time: Optional[datetime] = None

    # Filler state
    filler_items: List[PlayoutItem] = field(default_factory=list)
    needs_filler: bool = False
    filler_duration_remaining: timedelta = timedelta(0)

    def get_current_item(self) -> Optional[PlayoutItem]:
        """Get the currently playing item."""
        now = datetime.now()
        for item in self.items:
            if item.start <= now < item.finish:
                return item
        return None

    def get_next_item(self) -> Optional[PlayoutItem]:
        """Get the next item to play."""
        now = datetime.now()
        future_items = [item for item in self.items if item.start > now]
        return min(future_items, key=lambda x: x.start) if future_items else None

    def get_items_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> List[PlayoutItem]:
        """Get all items within a time range."""
        return [
            item for item in self.items
            if item.start < end and item.finish > start
        ]

    def add_item(self, item: PlayoutItem) -> None:
        """Add an item to the playout."""
        self.items.append(item)
        self.items.sort(key=lambda x: x.start)

    def remove_old_items(self, before: datetime) -> int:
        """Remove items that finished before the given time."""
        original_count = len(self.items)
        self.items = [item for item in self.items if item.finish > before]
        return original_count - len(self.items)

    def get_anchor_for_collection(self, collection_id: int) -> Optional[PlayoutAnchor]:
        """Get anchor for a specific collection."""
        for anchor in self.anchors:
            if anchor.collection_id == collection_id:
                return anchor
        return None

    def update_anchor(self, collection_id: int, enumerator_state: Dict[str, Any]) -> None:
        """Update or create anchor for a collection."""
        anchor = self.get_anchor_for_collection(collection_id)
        if anchor:
            anchor.enumerator_state = enumerator_state
        else:
            self.anchors.append(
                PlayoutAnchor(
                    id=len(self.anchors) + 1,
                    playout_id=self.playout_id,
                    collection_id=collection_id,
                    enumerator_state=enumerator_state,
                )
            )
