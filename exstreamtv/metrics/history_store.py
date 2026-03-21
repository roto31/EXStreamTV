"""
In-memory metrics history for predictive analysis. No DB. Ring buffers.
"""

from collections import deque
from typing import Any

_drift_history: deque[float] = deque(maxlen=60)
_mismatch_hourly: deque[int] = deque(maxlen=24)
_rebuild_hourly: deque[int] = deque(maxlen=24)
_interventions_hourly: deque[int] = deque(maxlen=24)
_current_hour: int | None = None
_prev_mismatch: int = 0
_prev_rebuild: int = 0
_prev_interventions: int = 0


def record_sample(
    drift_delta: float,
    active_mismatch_total: int,
    timeline_rebuild_total: int,
    watchdog_interventions_total: int,
) -> None:
    """Call every 60s. Rolls hourly buckets when hour changes."""
    import time
    global _current_hour, _prev_mismatch, _prev_rebuild, _prev_interventions
    hour = int(time.time() // 3600)

    _drift_history.append(drift_delta)

    if _current_hour is not None and hour != _current_hour:
        _mismatch_hourly.append(max(0, active_mismatch_total - _prev_mismatch))
        _rebuild_hourly.append(max(0, timeline_rebuild_total - _prev_rebuild))
        _interventions_hourly.append(max(0, watchdog_interventions_total - _prev_interventions))
    elif _current_hour is None:
        _current_hour = hour
    _current_hour = hour
    _prev_mismatch = active_mismatch_total
    _prev_rebuild = timeline_rebuild_total
    _prev_interventions = watchdog_interventions_total


def get_history() -> dict[str, Any]:
    """Snapshot for analyze_health_trend."""
    return {
        "drift_deltas_60m": list(_drift_history),
        "mismatch_by_hour": list(_mismatch_hourly)[-24:],
        "rebuild_by_hour": list(_rebuild_hourly)[-24:],
        "interventions_by_hour": list(_interventions_hourly)[-24:],
    }
