"""
Filler content management for playout gaps.

Ported from ErsatzTV filler system.
"""

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class FillerMode(Enum):
    """Mode for filler content insertion."""

    NONE = "none"  # No filler
    PRE_ROLL = "pre_roll"  # Before main content
    MID_ROLL = "mid_roll"  # During main content (breaks)
    POST_ROLL = "post_roll"  # After main content
    TAIL = "tail"  # Fill remaining time
    FALLBACK = "fallback"  # When no content available
    PAD = "pad"  # Pad to exact duration


@dataclass
class FillerItem:
    """A filler content item."""

    id: int
    media_item_id: int
    duration: timedelta
    title: Optional[str] = None
    weight: int = 1  # For weighted random selection


@dataclass
class FillerPreset:
    """
    A preset collection of filler content.

    Ported from ErsatzTV FillerPreset.
    """

    id: int
    name: str
    filler_mode: FillerMode = FillerMode.TAIL
    filler_duration: Optional[timedelta] = None  # For fixed-duration modes
    collection_id: Optional[int] = None  # Source collection for filler
    items: List[FillerItem] = field(default_factory=list)
    pad_to_nearest_minute: int = 0  # 0 = disabled, otherwise pad to this minute boundary
    allow_watermarks: bool = False
    count: Optional[int] = None  # Max items for PRE_ROLL/POST_ROLL

    @property
    def total_duration(self) -> timedelta:
        """Get total duration of all filler items."""
        return sum((item.duration for item in self.items), timedelta(0))


class FillerManager:
    """
    Manages filler content selection and insertion.

    Ported from ErsatzTV filler logic.
    """

    def __init__(self, presets: Optional[List[FillerPreset]] = None):
        self.presets: Dict[int, FillerPreset] = {}
        if presets:
            for preset in presets:
                self.presets[preset.id] = preset

    def add_preset(self, preset: FillerPreset) -> None:
        """Add a filler preset."""
        self.presets[preset.id] = preset

    def get_preset(self, preset_id: int) -> Optional[FillerPreset]:
        """Get a filler preset by ID."""
        return self.presets.get(preset_id)

    def select_filler(
        self,
        preset_id: int,
        target_duration: timedelta,
        mode: Optional[FillerMode] = None,
    ) -> List[FillerItem]:
        """
        Select filler items to fill the target duration.

        Args:
            preset_id: ID of the filler preset to use.
            target_duration: Duration to fill.
            mode: Override filler mode.

        Returns:
            List of filler items to use.
        """
        preset = self.presets.get(preset_id)
        if not preset or not preset.items:
            return []

        actual_mode = mode or preset.filler_mode
        selected: List[FillerItem] = []
        remaining = target_duration

        if actual_mode == FillerMode.NONE:
            return []

        if actual_mode in (FillerMode.PRE_ROLL, FillerMode.POST_ROLL):
            # Select up to count items
            count = preset.count or 1
            available = preset.items.copy()
            random.shuffle(available)
            for item in available[:count]:
                if remaining > timedelta(0):
                    selected.append(item)
                    remaining -= item.duration

        elif actual_mode in (FillerMode.TAIL, FillerMode.PAD, FillerMode.FALLBACK):
            # Fill until target duration is met
            available = preset.items.copy()

            while remaining > timedelta(0) and available:
                # Try to find exact fit
                exact_fits = [
                    item for item in available
                    if item.duration <= remaining
                ]

                if not exact_fits:
                    break

                # Select weighted random
                weights = [item.weight for item in exact_fits]
                total_weight = sum(weights)
                r = random.uniform(0, total_weight)
                cumulative = 0

                for item in exact_fits:
                    cumulative += item.weight
                    if r <= cumulative:
                        selected.append(item)
                        remaining -= item.duration
                        break

        return selected

    def calculate_gap_duration(
        self,
        current_end: datetime,
        next_start: datetime,
    ) -> timedelta:
        """Calculate duration of gap between items."""
        if next_start <= current_end:
            return timedelta(0)
        return next_start - current_end

    def get_pad_target(
        self,
        current_duration: timedelta,
        pad_to_minute: int,
    ) -> timedelta:
        """
        Calculate target duration for padding to minute boundary.

        Args:
            current_duration: Current total duration.
            pad_to_minute: Pad to this minute boundary (e.g., 15 = 15-minute blocks).

        Returns:
            Target duration for padding.
        """
        if pad_to_minute <= 0:
            return current_duration

        current_minutes = current_duration.total_seconds() / 60
        target_minutes = (
            (current_minutes // pad_to_minute) + 1
        ) * pad_to_minute

        return timedelta(minutes=target_minutes)

    def create_filler_schedule(
        self,
        main_items: List[Any],  # PlayoutItem
        preset_id: int,
        start_time: datetime,
        target_end: Optional[datetime] = None,
    ) -> List[Any]:
        """
        Create a complete schedule with filler inserted.

        Args:
            main_items: Main content items.
            preset_id: Filler preset to use.
            start_time: Start time of schedule.
            target_end: Optional target end time to fill to.

        Returns:
            Combined list of main and filler items.
        """
        preset = self.presets.get(preset_id)
        if not preset:
            return main_items

        result = []
        current_time = start_time

        for item in main_items:
            # Handle pre-roll
            if preset.filler_mode == FillerMode.PRE_ROLL:
                pre_roll = self.select_filler(
                    preset_id,
                    preset.filler_duration or timedelta(minutes=5),
                    FillerMode.PRE_ROLL,
                )
                for filler in pre_roll:
                    # Would create PlayoutItem here
                    current_time += filler.duration

            result.append(item)
            current_time += item.duration

            # Handle post-roll
            if preset.filler_mode == FillerMode.POST_ROLL:
                post_roll = self.select_filler(
                    preset_id,
                    preset.filler_duration or timedelta(minutes=2),
                    FillerMode.POST_ROLL,
                )
                for filler in post_roll:
                    current_time += filler.duration

        # Handle tail filler
        if target_end and current_time < target_end:
            tail_duration = target_end - current_time
            tail_filler = self.select_filler(
                preset_id,
                tail_duration,
                FillerMode.TAIL,
            )
            for filler in tail_filler:
                current_time += filler.duration

        return result
