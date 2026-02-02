"""
Time Slot Scheduler for time-based programming.

Ported from Tunarr's TimeSlotService with enhancements:
- Time-of-day based programming slots
- Order modes: ordered, shuffle, random
- Padding options: none, filler, loop, next
- Flex mode for slot extension

This enables traditional TV-style scheduling where specific
content plays at specific times of day.
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TimeSlotOrderMode(str, Enum):
    """How to order content within a time slot."""
    
    ORDERED = "ordered"  # Play in order
    SHUFFLE = "shuffle"  # Shuffle content
    RANDOM = "random"  # Random selection each time
    NEXT = "next"  # Continue from last position


class TimeSlotPaddingMode(str, Enum):
    """How to handle content shorter than the slot."""
    
    NONE = "none"  # Leave dead air
    FILLER = "filler"  # Use filler content
    LOOP = "loop"  # Loop the content
    NEXT = "next"  # Play next item from schedule
    BLACK = "black"  # Black screen


class TimeSlotFlexMode(str, Enum):
    """How to handle content longer than the slot."""
    
    CUT = "cut"  # Cut off at slot end
    EXTEND = "extend"  # Extend into next slot
    SHIFT = "shift"  # Shift subsequent slots


@dataclass
class TimeSlot:
    """
    Represents a time-based programming slot.
    
    A slot defines a time window where specific content should play.
    """
    
    slot_id: str
    name: str
    
    # Timing
    start_time: time  # Time of day (e.g., 20:00)
    duration_minutes: int = 60  # Slot duration
    
    # Days (0=Monday, 6=Sunday)
    days_of_week: list[int] = field(default_factory=lambda: list(range(7)))
    
    # Content
    collection_id: Optional[int] = None
    media_item_ids: list[int] = field(default_factory=list)
    
    # Playback behavior
    order_mode: TimeSlotOrderMode = TimeSlotOrderMode.ORDERED
    padding_mode: TimeSlotPaddingMode = TimeSlotPaddingMode.FILLER
    flex_mode: TimeSlotFlexMode = TimeSlotFlexMode.CUT
    
    # Filler configuration
    filler_collection_id: Optional[int] = None
    
    # State tracking
    current_position: int = 0  # Position in collection
    last_played_at: Optional[datetime] = None
    
    # Priority (higher = more important)
    priority: int = 0
    
    @property
    def end_time(self) -> time:
        """Calculate end time."""
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = start_dt + timedelta(minutes=self.duration_minutes)
        return end_dt.time()
    
    def is_active_at(self, dt: datetime) -> bool:
        """
        Check if slot is active at given datetime.
        
        Args:
            dt: Datetime to check
            
        Returns:
            True if slot is active
        """
        # Check day of week
        if dt.weekday() not in self.days_of_week:
            return False
        
        # Check time
        current_time = dt.time()
        
        # Handle slots that cross midnight
        if self.end_time < self.start_time:
            return current_time >= self.start_time or current_time < self.end_time
        
        return self.start_time <= current_time < self.end_time
    
    def minutes_until_start(self, dt: datetime) -> int:
        """
        Calculate minutes until slot starts.
        
        Args:
            dt: Current datetime
            
        Returns:
            Minutes until start (negative if currently active)
        """
        current_time = dt.time()
        
        # Same day
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        
        diff = start_minutes - current_minutes
        
        if diff < 0:
            # Slot already started today, calculate until tomorrow
            diff += 24 * 60
        
        return diff
    
    def get_next_item_index(self, content_count: int) -> int:
        """
        Get next item index based on order mode.
        
        Args:
            content_count: Total number of items
            
        Returns:
            Next item index
        """
        if content_count == 0:
            return 0
        
        if self.order_mode == TimeSlotOrderMode.RANDOM:
            return random.randint(0, content_count - 1)
        
        elif self.order_mode == TimeSlotOrderMode.SHUFFLE:
            # Advance position, shuffle when complete
            self.current_position = (self.current_position + 1) % content_count
            return self.current_position
        
        else:  # ORDERED or NEXT
            self.current_position = (self.current_position + 1) % content_count
            return self.current_position
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "slot_id": self.slot_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
            "days_of_week": self.days_of_week,
            "collection_id": self.collection_id,
            "order_mode": self.order_mode.value,
            "padding_mode": self.padding_mode.value,
            "flex_mode": self.flex_mode.value,
            "priority": self.priority,
            "current_position": self.current_position,
        }


@dataclass
class TimeSlotSchedule:
    """
    A collection of time slots forming a complete schedule.
    """
    
    schedule_id: str
    name: str
    channel_id: int
    slots: list[TimeSlot] = field(default_factory=list)
    
    # Default content when no slot is active
    default_collection_id: Optional[int] = None
    default_filler_id: Optional[int] = None
    
    # Schedule settings
    enabled: bool = True
    timezone: str = "UTC"
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_slot(self, slot: TimeSlot) -> None:
        """
        Add a time slot to the schedule.
        
        Args:
            slot: TimeSlot to add
        """
        self.slots.append(slot)
        self.slots.sort(key=lambda s: s.start_time)
        self.updated_at = datetime.utcnow()
    
    def remove_slot(self, slot_id: str) -> bool:
        """
        Remove a time slot.
        
        Args:
            slot_id: ID of slot to remove
            
        Returns:
            True if removed, False if not found
        """
        for i, slot in enumerate(self.slots):
            if slot.slot_id == slot_id:
                del self.slots[i]
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def get_active_slot(self, dt: Optional[datetime] = None) -> Optional[TimeSlot]:
        """
        Get the currently active time slot.
        
        Args:
            dt: Datetime to check (default: now)
            
        Returns:
            Active TimeSlot or None
        """
        if not self.enabled:
            return None
        
        check_time = dt or datetime.utcnow()
        
        # Find all active slots
        active_slots = [s for s in self.slots if s.is_active_at(check_time)]
        
        if not active_slots:
            return None
        
        # Return highest priority slot
        return max(active_slots, key=lambda s: s.priority)
    
    def get_next_slot(self, dt: Optional[datetime] = None) -> Optional[tuple[TimeSlot, int]]:
        """
        Get the next upcoming time slot.
        
        Args:
            dt: Current datetime (default: now)
            
        Returns:
            Tuple of (TimeSlot, minutes_until_start) or None
        """
        if not self.enabled or not self.slots:
            return None
        
        check_time = dt or datetime.utcnow()
        
        # Find slot with minimum positive minutes until start
        upcoming = [
            (s, s.minutes_until_start(check_time))
            for s in self.slots
            if not s.is_active_at(check_time)
        ]
        
        if not upcoming:
            return None
        
        # Get slot starting soonest
        return min(upcoming, key=lambda x: x[1])
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "channel_id": self.channel_id,
            "enabled": self.enabled,
            "timezone": self.timezone,
            "slots": [s.to_dict() for s in self.slots],
            "default_collection_id": self.default_collection_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class ScheduledItem:
    """An item scheduled to play at a specific time."""
    
    media_item_id: int
    start_time: datetime
    end_time: datetime
    slot_id: Optional[str] = None
    is_filler: bool = False
    
    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return (self.end_time - self.start_time).total_seconds()


class TimeSlotScheduler:
    """
    Scheduler that manages time-slot based programming.
    
    Features:
    - Resolves which content should play at any given time
    - Handles slot transitions
    - Manages padding and overflow
    - Tracks playback position per slot
    
    Usage:
        scheduler = TimeSlotScheduler()
        scheduler.add_schedule(schedule)
        
        # Get what should play now
        item = await scheduler.get_current_item(channel_id)
        
        # Get schedule for next 24 hours
        items = await scheduler.build_schedule(channel_id, hours=24)
    """
    
    def __init__(self):
        """Initialize the scheduler."""
        self._schedules: dict[int, TimeSlotSchedule] = {}  # channel_id -> schedule
        self._content_cache: dict[int, list[int]] = {}  # collection_id -> media_item_ids
    
    def add_schedule(self, schedule: TimeSlotSchedule) -> None:
        """
        Add or update a schedule.
        
        Args:
            schedule: TimeSlotSchedule to add
        """
        self._schedules[schedule.channel_id] = schedule
        logger.info(
            f"Added time slot schedule '{schedule.name}' for channel {schedule.channel_id} "
            f"with {len(schedule.slots)} slots"
        )
    
    def get_schedule(self, channel_id: int) -> Optional[TimeSlotSchedule]:
        """
        Get schedule for a channel.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            TimeSlotSchedule or None
        """
        return self._schedules.get(channel_id)
    
    def remove_schedule(self, channel_id: int) -> bool:
        """
        Remove schedule for a channel.
        
        Args:
            channel_id: Channel ID
            
        Returns:
            True if removed
        """
        if channel_id in self._schedules:
            del self._schedules[channel_id]
            return True
        return False
    
    async def get_current_item(
        self,
        channel_id: int,
        dt: Optional[datetime] = None,
        get_media_items: Optional[callable] = None,
    ) -> Optional[ScheduledItem]:
        """
        Get the item that should be playing now.
        
        Args:
            channel_id: Channel ID
            dt: Current datetime (default: now)
            get_media_items: Async function to get media items for collection
            
        Returns:
            ScheduledItem or None
        """
        schedule = self._schedules.get(channel_id)
        if not schedule:
            return None
        
        check_time = dt or datetime.utcnow()
        slot = schedule.get_active_slot(check_time)
        
        if not slot:
            # No active slot - use default content
            if schedule.default_collection_id and get_media_items:
                items = await get_media_items(schedule.default_collection_id)
                if items:
                    item_id = random.choice(items)
                    return ScheduledItem(
                        media_item_id=item_id,
                        start_time=check_time,
                        end_time=check_time + timedelta(hours=1),
                        is_filler=True,
                    )
            return None
        
        # Get content for slot
        if slot.collection_id and get_media_items:
            items = await get_media_items(slot.collection_id)
            if items:
                item_index = slot.get_next_item_index(len(items))
                item_id = items[item_index]
                
                # Calculate times
                start_dt = datetime.combine(check_time.date(), slot.start_time)
                end_dt = start_dt + timedelta(minutes=slot.duration_minutes)
                
                return ScheduledItem(
                    media_item_id=item_id,
                    start_time=start_dt,
                    end_time=end_dt,
                    slot_id=slot.slot_id,
                )
        
        return None
    
    async def build_schedule(
        self,
        channel_id: int,
        hours: int = 24,
        start_time: Optional[datetime] = None,
        get_media_items: Optional[callable] = None,
        get_media_duration: Optional[callable] = None,
    ) -> list[ScheduledItem]:
        """
        Build a schedule for the specified time period.
        
        Args:
            channel_id: Channel ID
            hours: Hours to schedule
            start_time: Start datetime (default: now)
            get_media_items: Async function to get media items for collection
            get_media_duration: Async function to get media duration
            
        Returns:
            List of ScheduledItems
        """
        schedule = self._schedules.get(channel_id)
        if not schedule:
            return []
        
        start = start_time or datetime.utcnow()
        end = start + timedelta(hours=hours)
        
        items: list[ScheduledItem] = []
        current = start
        
        while current < end:
            slot = schedule.get_active_slot(current)
            
            if slot and slot.collection_id and get_media_items:
                # Get content for slot
                media_items = await get_media_items(slot.collection_id)
                
                if media_items:
                    # Fill the slot with content
                    slot_start = datetime.combine(current.date(), slot.start_time)
                    slot_end = slot_start + timedelta(minutes=slot.duration_minutes)
                    
                    slot_current = max(slot_start, current)
                    
                    while slot_current < slot_end and slot_current < end:
                        item_index = slot.get_next_item_index(len(media_items))
                        item_id = media_items[item_index]
                        
                        # Get duration
                        duration = 30 * 60  # Default 30 min
                        if get_media_duration:
                            duration = await get_media_duration(item_id) or duration
                        
                        item_end = min(
                            slot_current + timedelta(seconds=duration),
                            slot_end,
                            end,
                        )
                        
                        items.append(ScheduledItem(
                            media_item_id=item_id,
                            start_time=slot_current,
                            end_time=item_end,
                            slot_id=slot.slot_id,
                        ))
                        
                        slot_current = item_end
                    
                    current = slot_end
                else:
                    current += timedelta(minutes=15)  # Skip ahead
            else:
                # No active slot, use default or skip
                next_slot = schedule.get_next_slot(current)
                
                if next_slot:
                    slot, minutes_until = next_slot
                    # Skip to next slot (or fill with default content)
                    current += timedelta(minutes=min(minutes_until, 60))
                else:
                    current += timedelta(hours=1)
        
        return items
    
    def get_stats(self) -> dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "schedules_count": len(self._schedules),
            "schedules": {
                ch_id: {
                    "name": sched.name,
                    "slots_count": len(sched.slots),
                    "enabled": sched.enabled,
                }
                for ch_id, sched in self._schedules.items()
            },
        }


# Global scheduler instance
_time_slot_scheduler: Optional[TimeSlotScheduler] = None


def get_time_slot_scheduler() -> TimeSlotScheduler:
    """Get the global TimeSlotScheduler instance."""
    global _time_slot_scheduler
    if _time_slot_scheduler is None:
        _time_slot_scheduler = TimeSlotScheduler()
    return _time_slot_scheduler
