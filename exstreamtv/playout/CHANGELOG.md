# Playout Engine Component Changelog

All notable changes to the Playout Engine component will be documented in this file.

## [2.5.0] - 2026-01-17
### Changed
- No changes to playout module in this release

## [1.0.9] - 2026-01-14
### Added
- **Playout Builder** (`builder.py`)
  - Build modes: continue, refresh, reset
  - Enumerator management and state persistence

- **Collection Enumerators** (`enumerators.py`)
  - ChronologicalEnumerator - Ordered playback
  - ShuffledEnumerator - Shuffled with state persistence
  - RandomEnumerator - Random with repeat avoidance
  - RotatingShuffledEnumerator - Group-based rotation

- **Schedule Modes**
  - ONE - Play one item per schedule slot
  - MULTIPLE - Play N items per slot
  - DURATION - Play for specified duration
  - FLOOD - Fill until target time

- **Filler System** (`filler.py`)
  - FillerManager - Filler content selection
  - Pre-roll, mid-roll, post-roll modes
  - Tail filler for gap filling
  - Pad to minute boundary option

- **State Management** (`state.py`)
  - PlayoutState - Current playout tracking
  - PlayoutItem - Individual playout entries
  - PlayoutAnchor - Position persistence
