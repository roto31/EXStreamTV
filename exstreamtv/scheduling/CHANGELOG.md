# Scheduling Component Changelog

All notable changes to the Scheduling component will be documented in this file.

## [2.6.0] - 2026-01-31
### Added - Tunarr Scheduling Features
- **TimeSlotScheduler** (`time_slots.py`) - Time-of-day slot scheduling from Tunarr
  - `TimeSlot` dataclass with start time, duration, and content configuration
  - `TimeSlotSchedule` for managing multiple slots
  - Order modes: ordered, shuffle, random
  - Padding modes: none, filler, loop, next
  - Flex mode for slot extension
  - `TimeSlotOrderMode`, `TimeSlotPaddingMode`, `TimeSlotFlexMode` enums
  - `ScheduledItem` dataclass for scheduled content
- **BalanceScheduler** (`balance.py`) - Weight-based content distribution from Tunarr
  - `ContentSource` dataclass with weight and cooldown
  - `BalanceConfig` for scheduler settings
  - Weight-based source selection
  - Cooldown periods to avoid repetition
  - Consecutive play limits
  - `BalanceStats` for distribution tracking
- Updated `__init__.py` with new exports

## [1.0.6] - 2026-01-14
### Added
- Initial scheduling module ported from StreamTV
- `engine.py` - Schedule execution engine
- `parser.py` - Schedule parsing utilities
