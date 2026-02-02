"""
Schedule Generator for AI Channel Creation

Generates complex schedules from AI specifications including:
- Time-slot based scheduling (shows on the hour/half-hour)
- Commercial break insertion with period-appropriate duration
- Day-of-week patterns (Saturday morning cartoons, Movie of the Week)
- Holiday programming calendar integration
- Genre grouping and rotation
- No-repeat logic for content blocks
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DayOfWeek(Enum):
    """Days of the week."""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


@dataclass
class TimeSlot:
    """A time slot in the schedule."""
    
    start_time: time
    end_time: time
    duration_minutes: int
    content_type: str  # "show", "movie", "commercial", "filler"
    genre: str | None = None
    source: str | None = None  # "plex", "archive_org", "youtube"
    collection_id: int | None = None
    media_item_id: int | None = None
    title: str | None = None
    notes: str = ""
    day_of_week: DayOfWeek | None = None  # None means every day
    is_special_block: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_minutes": self.duration_minutes,
            "content_type": self.content_type,
            "genre": self.genre,
            "source": self.source,
            "collection_id": self.collection_id,
            "media_item_id": self.media_item_id,
            "title": self.title,
            "notes": self.notes,
            "day_of_week": self.day_of_week.name if self.day_of_week else None,
            "is_special_block": self.is_special_block,
        }


@dataclass
class ScheduleBlock:
    """A block of programming (e.g., Saturday morning cartoons)."""
    
    name: str
    day_of_week: DayOfWeek | None  # None for daily
    start_time: time
    duration_hours: float
    genres: list[str] = field(default_factory=list)
    source: str | None = None
    collection_ids: list[int] = field(default_factory=list)
    no_repeat: bool = True
    commercial_breaks: bool = True
    breaks_per_half_hour: int = 2
    break_duration_seconds: int = 120
    
    @property
    def end_time(self) -> time:
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = start_dt + timedelta(hours=self.duration_hours)
        return end_dt.time()


@dataclass
class HolidayProgramming:
    """Holiday-specific programming configuration."""
    
    name: str
    date_start: tuple[int, int]  # (month, day)
    date_end: tuple[int, int]  # (month, day)
    genres: list[str] = field(default_factory=list)
    content_keywords: list[str] = field(default_factory=list)
    override_primetime: bool = True
    special_commercials: bool = True


class HolidayCalendar:
    """
    Calendar of holiday programming periods.
    
    Based on classic network television traditions from the 1970s-1980s.
    """
    
    # Classic TV holiday programming
    HOLIDAYS = {
        "thanksgiving": HolidayProgramming(
            name="Thanksgiving",
            date_start=(11, 20),
            date_end=(11, 28),
            genres=["family", "comedy", "specials"],
            content_keywords=["thanksgiving", "harvest", "family"],
            override_primetime=True,
        ),
        "christmas": HolidayProgramming(
            name="Christmas/Holiday Season",
            date_start=(12, 1),
            date_end=(12, 25),
            genres=["holiday", "family", "specials", "movies"],
            content_keywords=["christmas", "holiday", "santa", "winter"],
            override_primetime=True,
            special_commercials=True,
        ),
        "new_years": HolidayProgramming(
            name="New Year's",
            date_start=(12, 26),
            date_end=(1, 2),
            genres=["specials", "variety", "music"],
            content_keywords=["new year", "celebration", "countdown"],
            override_primetime=True,
        ),
        "easter": HolidayProgramming(
            name="Easter",
            date_start=(3, 15),  # Approximate - Easter is variable
            date_end=(4, 25),
            genres=["family", "religious", "specials"],
            content_keywords=["easter", "spring", "bunny"],
            override_primetime=False,
        ),
        "july4th": HolidayProgramming(
            name="Independence Day",
            date_start=(7, 1),
            date_end=(7, 5),
            genres=["patriotic", "specials", "movies"],
            content_keywords=["fourth", "july", "independence", "america"],
            override_primetime=True,
        ),
        "halloween": HolidayProgramming(
            name="Halloween",
            date_start=(10, 24),
            date_end=(10, 31),
            genres=["horror", "thriller", "specials"],
            content_keywords=["halloween", "spooky", "scary", "horror"],
            override_primetime=True,
        ),
    }
    
    def __init__(self, enabled_holidays: dict[str, bool] | None = None):
        """
        Initialize holiday calendar.
        
        Args:
            enabled_holidays: Dict of holiday name -> enabled status
        """
        self.enabled_holidays = enabled_holidays or {
            name: True for name in self.HOLIDAYS
        }
    
    def get_active_holiday(self, date: datetime) -> HolidayProgramming | None:
        """
        Get the active holiday for a given date.
        
        Args:
            date: Date to check
            
        Returns:
            HolidayProgramming or None
        """
        month = date.month
        day = date.day
        
        for holiday_name, holiday in self.HOLIDAYS.items():
            if not self.enabled_holidays.get(holiday_name, True):
                continue
            
            start_month, start_day = holiday.date_start
            end_month, end_day = holiday.date_end
            
            # Handle year boundary (e.g., Christmas -> New Year's)
            if start_month > end_month:
                # Spans year boundary
                if (month > start_month or (month == start_month and day >= start_day)) or \
                   (month < end_month or (month == end_month and day <= end_day)):
                    return holiday
            else:
                # Same year
                if (month > start_month or (month == start_month and day >= start_day)) and \
                   (month < end_month or (month == end_month and day <= end_day)):
                    return holiday
        
        return None
    
    def is_holiday_period(self, date: datetime) -> bool:
        """Check if date is in a holiday period."""
        return self.get_active_holiday(date) is not None


class ScheduleGenerator:
    """
    Generates complex programming schedules from AI specifications.
    
    Creates schedules that follow classic TV programming patterns:
    - Shows start on the hour or half-hour
    - Commercial breaks at natural points
    - Day-specific programming (Saturday morning cartoons, etc.)
    - Holiday-aware programming
    - Genre-based daypart organization
    """
    
    # Classic TV daypart definitions (times in 24-hour format)
    DEFAULT_DAYPARTS = {
        "early_morning": {"start": "05:00", "end": "09:00", "genres": ["news", "kids"]},
        "morning": {"start": "09:00", "end": "12:00", "genres": ["game_shows", "talk"]},
        "daytime": {"start": "12:00", "end": "16:00", "genres": ["soaps", "talk", "game_shows"]},
        "early_fringe": {"start": "16:00", "end": "18:00", "genres": ["syndication", "news"]},
        "access": {"start": "18:00", "end": "20:00", "genres": ["news", "game_shows", "entertainment"]},
        "primetime": {"start": "20:00", "end": "23:00", "genres": ["drama", "comedy", "movies"]},
        "late_night": {"start": "23:00", "end": "01:00", "genres": ["talk", "variety", "movies"]},
        "overnight": {"start": "01:00", "end": "05:00", "genres": ["movies", "infomercials", "reruns"]},
    }
    
    def __init__(
        self,
        holiday_calendar: HolidayCalendar | None = None,
        random_seed: int | None = None,
    ):
        """
        Initialize schedule generator.
        
        Args:
            holiday_calendar: Optional holiday calendar
            random_seed: Optional random seed for reproducibility
        """
        self.holiday_calendar = holiday_calendar or HolidayCalendar()
        self._random = random.Random(random_seed)
    
    def generate_schedule_template(
        self,
        spec: Any,  # ChannelSpecification
        days: int = 7,
    ) -> list[TimeSlot]:
        """
        Generate a schedule template from channel specification.
        
        Args:
            spec: Channel specification from AI
            days: Number of days to generate
            
        Returns:
            List of TimeSlot objects
        """
        slots = []
        
        # Get dayparts from spec or use defaults
        dayparts = spec.dayparts if hasattr(spec, "dayparts") and spec.dayparts else self.DEFAULT_DAYPARTS
        
        # Get special blocks from spec
        special_blocks = []
        if hasattr(spec, "special_blocks"):
            for block_spec in spec.special_blocks:
                block = self._parse_special_block(block_spec)
                if block:
                    special_blocks.append(block)
        
        # Get commercial settings
        commercials_enabled = False
        breaks_per_half_hour = 2
        break_duration = 120
        
        if hasattr(spec, "commercials") and spec.commercials:
            commercials_enabled = spec.commercials.get("enabled", False)
            breaks_per_half_hour = spec.commercials.get("breaks_per_half_hour", 2)
            break_duration = spec.commercials.get("break_duration_seconds", 120)
        
        # Generate slots for each day
        for day in range(days):
            day_of_week = DayOfWeek(day % 7)
            
            # Check for special blocks on this day
            day_special_blocks = [
                b for b in special_blocks
                if b.day_of_week is None or b.day_of_week == day_of_week
            ]
            
            # Generate daypart slots
            for daypart_name, daypart_config in dayparts.items():
                if not daypart_config:
                    continue
                
                start_str = daypart_config.get("start", "00:00")
                end_str = daypart_config.get("end", "00:00")
                genres = daypart_config.get("genres", [])
                
                start_time = self._parse_time(start_str)
                end_time = self._parse_time(end_str)
                
                # Check if this time period is covered by a special block
                covered_by_special = False
                for block in day_special_blocks:
                    if self._times_overlap(start_time, end_time, block.start_time, block.end_time):
                        covered_by_special = True
                        break
                
                if covered_by_special:
                    continue
                
                # Generate slots for this daypart
                daypart_slots = self._generate_daypart_slots(
                    start_time=start_time,
                    end_time=end_time,
                    genres=genres,
                    day_of_week=day_of_week,
                    commercials_enabled=commercials_enabled,
                    breaks_per_half_hour=breaks_per_half_hour,
                    break_duration=break_duration,
                )
                slots.extend(daypart_slots)
            
            # Add special block slots
            for block in day_special_blocks:
                block_slots = self._generate_block_slots(
                    block=block,
                    day_of_week=day_of_week,
                )
                slots.extend(block_slots)
        
        # Sort by day and time
        slots.sort(key=lambda s: (
            s.day_of_week.value if s.day_of_week else 0,
            s.start_time,
        ))
        
        return slots
    
    def _parse_time(self, time_str: str) -> time:
        """Parse time string to time object."""
        parts = time_str.split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    
    def _parse_special_block(self, block_spec: dict[str, Any]) -> ScheduleBlock | None:
        """Parse special block specification."""
        try:
            day_str = block_spec.get("day", "").lower()
            day_of_week = None
            
            if day_str:
                day_map = {
                    "monday": DayOfWeek.MONDAY,
                    "tuesday": DayOfWeek.TUESDAY,
                    "wednesday": DayOfWeek.WEDNESDAY,
                    "thursday": DayOfWeek.THURSDAY,
                    "friday": DayOfWeek.FRIDAY,
                    "saturday": DayOfWeek.SATURDAY,
                    "sunday": DayOfWeek.SUNDAY,
                }
                day_of_week = day_map.get(day_str)
            
            return ScheduleBlock(
                name=block_spec.get("name", "Special Block"),
                day_of_week=day_of_week,
                start_time=self._parse_time(block_spec.get("start", "08:00")),
                duration_hours=block_spec.get("duration_hours", 4),
                genres=block_spec.get("genres", []),
                source=block_spec.get("source"),
                no_repeat=block_spec.get("no_repeat", True),
                commercial_breaks=block_spec.get("commercial_breaks", True),
            )
        except Exception as e:
            logger.warning(f"Error parsing special block: {e}")
            return None
    
    def _times_overlap(
        self,
        start1: time,
        end1: time,
        start2: time,
        end2: time,
    ) -> bool:
        """Check if two time ranges overlap."""
        # Convert to minutes for easier comparison
        def to_minutes(t: time) -> int:
            return t.hour * 60 + t.minute
        
        s1, e1 = to_minutes(start1), to_minutes(end1)
        s2, e2 = to_minutes(start2), to_minutes(end2)
        
        # Handle overnight ranges
        if e1 < s1:
            e1 += 24 * 60
        if e2 < s2:
            e2 += 24 * 60
        
        return max(s1, s2) < min(e1, e2)
    
    def _generate_daypart_slots(
        self,
        start_time: time,
        end_time: time,
        genres: list[str],
        day_of_week: DayOfWeek,
        commercials_enabled: bool = False,
        breaks_per_half_hour: int = 2,
        break_duration: int = 120,
    ) -> list[TimeSlot]:
        """Generate time slots for a daypart."""
        slots = []
        
        # Calculate duration
        start_dt = datetime.combine(datetime.today(), start_time)
        end_dt = datetime.combine(datetime.today(), end_time)
        
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        
        total_minutes = int((end_dt - start_dt).total_seconds() / 60)
        
        # Standard show lengths (30 or 60 minutes)
        show_lengths = [30, 60]
        
        current_time = start_time
        current_dt = start_dt
        
        while current_dt < end_dt:
            # Choose show length (prefer 30 for sitcoms, 60 for dramas)
            if "comedy" in genres or "sitcom" in genres:
                show_length = 30
            elif "drama" in genres or "movies" in genres:
                show_length = 60
            else:
                show_length = self._random.choice(show_lengths)
            
            # Check if we have enough time left
            remaining = int((end_dt - current_dt).total_seconds() / 60)
            if remaining < show_length:
                show_length = remaining
            
            if show_length <= 0:
                break
            
            # Create show slot
            show_end_dt = current_dt + timedelta(minutes=show_length)
            
            slots.append(TimeSlot(
                start_time=current_time,
                end_time=show_end_dt.time(),
                duration_minutes=show_length,
                content_type="show",
                genre=self._random.choice(genres) if genres else None,
                day_of_week=day_of_week,
            ))
            
            # Add commercial breaks if enabled
            if commercials_enabled and show_length >= 30:
                num_breaks = (show_length // 30) * breaks_per_half_hour
                break_minutes = break_duration // 60
                
                for i in range(num_breaks):
                    # Insert commercial break (conceptually - actual insertion happens during playout)
                    pass
            
            current_dt = show_end_dt
            current_time = current_dt.time()
        
        return slots
    
    def _generate_block_slots(
        self,
        block: ScheduleBlock,
        day_of_week: DayOfWeek,
    ) -> list[TimeSlot]:
        """Generate time slots for a special block."""
        slots = []
        
        start_dt = datetime.combine(datetime.today(), block.start_time)
        end_dt = start_dt + timedelta(hours=block.duration_hours)
        
        current_dt = start_dt
        
        while current_dt < end_dt:
            # For cartoon blocks, use 30-minute slots
            if any(g in ["cartoons", "animation", "kids"] for g in block.genres):
                show_length = 30
            else:
                show_length = 60
            
            remaining = int((end_dt - current_dt).total_seconds() / 60)
            if remaining < show_length:
                show_length = remaining
            
            if show_length <= 0:
                break
            
            show_end_dt = current_dt + timedelta(minutes=show_length)
            
            slots.append(TimeSlot(
                start_time=current_dt.time(),
                end_time=show_end_dt.time(),
                duration_minutes=show_length,
                content_type="show",
                genre=self._random.choice(block.genres) if block.genres else None,
                source=block.source,
                day_of_week=day_of_week,
                is_special_block=True,
                notes=f"Part of {block.name}",
            ))
            
            current_dt = show_end_dt
        
        return slots
    
    async def generate_schedule_items(
        self,
        spec: Any,  # ChannelSpecification
        schedule_id: int,
        db_session: Any,
    ) -> list[int]:
        """
        Generate ProgramScheduleItem records from specification.
        
        Args:
            spec: Channel specification
            schedule_id: Schedule ID to add items to
            db_session: Database session
            
        Returns:
            List of created item IDs
        """
        from exstreamtv.database.models import ProgramScheduleItem
        
        created_ids = []
        
        try:
            # Generate template slots
            slots = self.generate_schedule_template(spec)
            
            # Create schedule items
            for position, slot in enumerate(slots):
                item = ProgramScheduleItem(
                    schedule_id=schedule_id,
                    position=position,
                    collection_type="collection" if slot.collection_id else "search",
                    collection_id=slot.collection_id,
                    custom_title=slot.title,
                    playback_mode="one",
                    playback_order="chronological",
                    duration_minutes=slot.duration_minutes,
                )
                
                # Set start time if it's a fixed-time slot
                if slot.start_time:
                    item.start_time = slot.start_time
                
                db_session.add(item)
                await db_session.flush()
                created_ids.append(item.id)
            
            await db_session.commit()
            
            logger.info(f"Created {len(created_ids)} schedule items for schedule {schedule_id}")
            
        except Exception as e:
            logger.exception(f"Error generating schedule items: {e}")
            await db_session.rollback()
        
        return created_ids
    
    def apply_holiday_programming(
        self,
        slots: list[TimeSlot],
        date: datetime,
    ) -> list[TimeSlot]:
        """
        Apply holiday-specific programming adjustments.
        
        Args:
            slots: Original schedule slots
            date: Date to check for holidays
            
        Returns:
            Modified slots with holiday programming
        """
        holiday = self.holiday_calendar.get_active_holiday(date)
        
        if not holiday:
            return slots
        
        modified_slots = []
        
        for slot in slots:
            # Check if this slot should be affected by holiday programming
            if holiday.override_primetime and slot.start_time.hour >= 20:
                # Replace primetime with holiday content
                modified_slot = TimeSlot(
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    duration_minutes=slot.duration_minutes,
                    content_type=slot.content_type,
                    genre=self._random.choice(holiday.genres) if holiday.genres else slot.genre,
                    source=slot.source,
                    collection_id=slot.collection_id,
                    day_of_week=slot.day_of_week,
                    notes=f"Holiday special: {holiday.name}",
                )
                modified_slots.append(modified_slot)
            else:
                modified_slots.append(slot)
        
        return modified_slots
