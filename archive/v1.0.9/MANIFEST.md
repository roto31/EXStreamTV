# EXStreamTV v1.0.9 Archive Manifest

**Release Date**: 2026-01-14  
**Status**: Playout Engine

## Summary

ErsatzTV-compatible playout engine with collection enumerators, schedule modes, and filler system.

## Components at This Version

| Component | Version | Status |
|-----------|---------|--------|
| Playout Engine | 1.0.9 | Created |

## Playout Module Files

### Playout Builder (`builder.py`)
- Build modes: continue, refresh, reset
- Enumerator management and state persistence

### Collection Enumerators (`enumerators.py`)
- ChronologicalEnumerator - Ordered playback
- ShuffledEnumerator - Shuffled with state persistence
- RandomEnumerator - Random with repeat avoidance
- RotatingShuffledEnumerator - Group-based rotation

### Schedule Modes
- ONE - Play one item per schedule slot
- MULTIPLE - Play N items per slot
- DURATION - Play for specified duration
- FLOOD - Fill until target time

### Filler System (`filler.py`)
- FillerManager - Filler content selection
- Pre-roll, mid-roll, post-roll modes
- Tail filler for gap filling
- Pad to minute boundary option

### State Management (`state.py`)
- PlayoutState - Current playout tracking
- PlayoutItem - Individual playout entries
- PlayoutAnchor - Position persistence

## Previous Version

← v1.0.8: ErsatzTV FFmpeg Pipeline

## Next Version

→ v1.2.0: Local Media Libraries
