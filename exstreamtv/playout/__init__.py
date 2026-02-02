"""
EXStreamTV Playout Engine

ErsatzTV-style continuous playout scheduling system.

Features:
- Continuous 24/7 channel playouts
- Multiple schedule modes (one, duration, flood, multiple)
- Collection enumerators (chronological, shuffled, random)
- Filler content management
- Playout anchors for schedule synchronization
"""

from exstreamtv.playout.builder import PlayoutBuilder, PlayoutBuildMode, PlayoutBuildResult
from exstreamtv.playout.enumerators import (
    ChronologicalEnumerator,
    CollectionEnumerator,
    RandomEnumerator,
    ShuffledEnumerator,
)
from exstreamtv.playout.filler import FillerManager, FillerMode
from exstreamtv.playout.scheduler import PlayoutScheduler, ScheduleMode
from exstreamtv.playout.state import PlayoutState

__all__ = [
    # Builder
    "PlayoutBuilder",
    "PlayoutBuildMode",
    "PlayoutBuildResult",
    # Enumerators
    "CollectionEnumerator",
    "ChronologicalEnumerator",
    "ShuffledEnumerator",
    "RandomEnumerator",
    # Filler
    "FillerManager",
    "FillerMode",
    # Scheduler
    "PlayoutScheduler",
    "ScheduleMode",
    # State
    "PlayoutState",
]
