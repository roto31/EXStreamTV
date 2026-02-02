"""
EXStreamTV Scheduling Module

Schedule parsing, time slots, and content balancing.

Components:
- ScheduleEngine: Schedule execution engine
- ScheduleParser: Schedule parsing utilities
- TimeSlotScheduler: Tunarr-style time-based scheduling (NEW)
- BalanceScheduler: Weighted content distribution (NEW)
"""

from .engine import ScheduleEngine
from .parser import ParsedSchedule, ScheduleParser

# New components from Tunarr integration
from .time_slots import (
    TimeSlot,
    TimeSlotSchedule,
    TimeSlotScheduler,
    TimeSlotOrderMode,
    TimeSlotPaddingMode,
    TimeSlotFlexMode,
    ScheduledItem,
    get_time_slot_scheduler,
)
from .balance import (
    BalanceScheduler,
    BalanceConfig,
    BalanceStats,
    ContentSource,
    get_balance_scheduler,
)

__all__ = [
    # Original components
    "ParsedSchedule",
    "ScheduleEngine",
    "ScheduleParser",
    # Time slot scheduling (Tunarr)
    "TimeSlot",
    "TimeSlotSchedule",
    "TimeSlotScheduler",
    "TimeSlotOrderMode",
    "TimeSlotPaddingMode",
    "TimeSlotFlexMode",
    "ScheduledItem",
    "get_time_slot_scheduler",
    # Balance scheduling (Tunarr)
    "BalanceScheduler",
    "BalanceConfig",
    "BalanceStats",
    "ContentSource",
    "get_balance_scheduler",
]
