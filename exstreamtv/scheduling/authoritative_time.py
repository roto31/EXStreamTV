"""
Authoritative time: monotonic-derived epoch. Zero wall-clock dependency.

Single source of truth for scheduling. Immune to DST, NTP, manual changes.
"""

import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from datetime import datetime

_anchor_wall_epoch: Optional[float] = None
_anchor_monotonic: Optional[float] = None


def _ensure_anchor() -> None:
    global _anchor_wall_epoch, _anchor_monotonic
    if _anchor_wall_epoch is None:
        _anchor_wall_epoch = time.time()
        _anchor_monotonic = time.monotonic()


def now_epoch() -> float:
    """Authoritative now as UTC epoch. Monotonic-derived."""
    _ensure_anchor()
    delta = time.monotonic() - _anchor_monotonic
    return _anchor_wall_epoch + delta


def now_datetime_utc() -> "datetime":
    """Authoritative now as naive UTC datetime. For scheduling compatibility."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(now_epoch(), tz=timezone.utc).replace(tzinfo=None)


def reset_anchor() -> None:
    """Reset anchor so T_new(now)==T_old(now). Zero jump."""
    global _anchor_wall_epoch, _anchor_monotonic
    old_derived = now_epoch()
    _anchor_wall_epoch = time.time()
    _anchor_monotonic = time.monotonic()
    new_derived = now_epoch()
    if abs(new_derived - old_derived) > 0.01:
        _anchor_wall_epoch = old_derived - (time.monotonic() - _anchor_monotonic)
