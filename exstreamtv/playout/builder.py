"""
Playout builder for creating complete playouts.

Ported from ErsatzTV PlayoutBuilder.cs.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from exstreamtv.playout.enumerators import (
    ChronologicalEnumerator,
    CollectionEnumerator,
    RandomEnumerator,
    ShuffledEnumerator,
)
from exstreamtv.playout.filler import FillerManager, FillerPreset
from exstreamtv.playout.scheduler import PlayoutScheduler, ScheduleItem
from exstreamtv.playout.state import PlayoutAnchor, PlayoutItem, PlayoutState

logger = logging.getLogger(__name__)


class PlayoutBuildMode(Enum):
    """Mode for building/rebuilding playout."""

    CONTINUE = "continue"  # Continue from current position
    REFRESH = "refresh"  # Rebuild from current time
    RESET = "reset"  # Complete rebuild from scratch


@dataclass
class PlayoutBuildResult:
    """Result of building a playout."""

    items: List[PlayoutItem] = field(default_factory=list)
    anchors: List[PlayoutAnchor] = field(default_factory=list)
    items_to_remove: List[int] = field(default_factory=list)
    clear_all: bool = False
    success: bool = True
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "PlayoutBuildResult":
        """Create empty result."""
        return cls()

    @classmethod
    def failure(cls, error: str) -> "PlayoutBuildResult":
        """Create failure result."""
        return cls(success=False, error=error)


class PlayoutBuilder:
    """
    Builds playout schedules for channels.

    Ported from ErsatzTV PlayoutBuilder.cs.
    """

    def __init__(
        self,
        filler_manager: Optional[FillerManager] = None,
        trim_start: bool = True,
    ):
        self.filler_manager = filler_manager or FillerManager()
        self.trim_start = trim_start
        self._enumerators: Dict[int, CollectionEnumerator] = {}

    async def build(
        self,
        state: PlayoutState,
        schedule_items: List[ScheduleItem],
        collections: Dict[int, List[Any]],  # collection_id -> media items
        start: datetime,
        finish: datetime,
        mode: PlayoutBuildMode = PlayoutBuildMode.CONTINUE,
    ) -> PlayoutBuildResult:
        """
        Build playout items for the specified time range.

        Args:
            state: Current playout state.
            schedule_items: Schedule items defining what to play.
            collections: Media item collections.
            start: Start of build range.
            finish: End of build range.
            mode: Build mode (continue, refresh, reset).

        Returns:
            PlayoutBuildResult with items and state updates.
        """
        logger.info(
            f"Building playout {state.playout_id} from {start} to {finish} "
            f"(mode: {mode.value})"
        )

        result = PlayoutBuildResult()

        try:
            # Validate inputs
            if not schedule_items:
                return PlayoutBuildResult.failure("No schedule items provided")

            if not collections:
                return PlayoutBuildResult.failure("No collections provided")

            # Handle build mode
            if mode == PlayoutBuildMode.RESET:
                result.clear_all = True
                state.items.clear()
                state.anchors.clear()
                state.schedule_item_index = 0

            elif mode == PlayoutBuildMode.REFRESH:
                # Remove future items
                result.items_to_remove = [
                    item.id for item in state.items
                    if item.start >= start
                ]
                state.items = [
                    item for item in state.items
                    if item.start < start
                ]

            # Initialize enumerators for collections
            self._initialize_enumerators(collections, state)

            # Create scheduler
            scheduler = PlayoutScheduler(schedule_items, self._enumerators)

            # Schedule items for the range
            schedule_result = scheduler.schedule_items_for_range(
                start, finish, state
            )

            if schedule_result.error:
                result.warnings.append(schedule_result.error)

            result.items = schedule_result.items

            # Update anchors
            for collection_id, enumerator_state in schedule_result.new_anchors.items():
                state.update_anchor(collection_id, enumerator_state)

            result.anchors = state.anchors

            # Update state
            state.schedule_item_index = schedule_result.next_schedule_item_index

            logger.info(f"Built {len(result.items)} playout items")

        except Exception as e:
            logger.exception(f"Error building playout: {e}")
            result.success = False
            result.error = str(e)

        return result

    def _initialize_enumerators(
        self,
        collections: Dict[int, List[Any]],
        state: PlayoutState,
    ) -> None:
        """Initialize or restore collection enumerators."""
        for collection_id, items in collections.items():
            # Check for existing anchor state
            anchor = state.get_anchor_for_collection(collection_id)
            enumerator_state = anchor.enumerator_state if anchor else None

            # Create appropriate enumerator
            # Default to shuffled for variety
            self._enumerators[collection_id] = ShuffledEnumerator(
                items=items,
                state=enumerator_state,
            )

    def create_enumerator(
        self,
        collection_id: int,
        items: List[Any],
        enumerator_type: str = "shuffled",
        state: Optional[Dict[str, Any]] = None,
    ) -> CollectionEnumerator:
        """
        Create an enumerator for a collection.

        Args:
            collection_id: Collection ID.
            items: Items in the collection.
            enumerator_type: Type of enumerator (chronological, shuffled, random).
            state: Optional saved state to restore.

        Returns:
            CollectionEnumerator instance.
        """
        if enumerator_type == "chronological":
            enumerator = ChronologicalEnumerator(items, state=state)
        elif enumerator_type == "random":
            enumerator = RandomEnumerator(items, state=state)
        else:  # default to shuffled
            enumerator = ShuffledEnumerator(items, state=state)

        self._enumerators[collection_id] = enumerator
        return enumerator

    def get_current_item(
        self,
        state: PlayoutState,
        at_time: Optional[datetime] = None,
    ) -> Optional[PlayoutItem]:
        """
        Get the item that should be playing at a specific time.

        Args:
            state: Playout state.
            at_time: Time to check (defaults to now).

        Returns:
            PlayoutItem or None.
        """
        check_time = at_time or datetime.now()

        for item in state.items:
            if item.start <= check_time < item.finish:
                return item

        return None

    def get_upcoming_items(
        self,
        state: PlayoutState,
        count: int = 10,
        after: Optional[datetime] = None,
    ) -> List[PlayoutItem]:
        """
        Get upcoming playout items.

        Args:
            state: Playout state.
            count: Maximum number of items to return.
            after: Start time (defaults to now).

        Returns:
            List of upcoming PlayoutItem.
        """
        check_time = after or datetime.now()

        upcoming = [
            item for item in state.items
            if item.start >= check_time
        ]

        upcoming.sort(key=lambda x: x.start)

        return upcoming[:count]

    def calculate_time_until_next(
        self,
        state: PlayoutState,
        at_time: Optional[datetime] = None,
    ) -> Optional[timedelta]:
        """
        Calculate time until the next item starts.

        Args:
            state: Playout state.
            at_time: Reference time (defaults to now).

        Returns:
            timedelta or None if no next item.
        """
        check_time = at_time or datetime.now()
        current = self.get_current_item(state, check_time)

        if current:
            return current.finish - check_time

        next_item = state.get_next_item()
        if next_item:
            return next_item.start - check_time

        return None
