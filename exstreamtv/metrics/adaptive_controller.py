"""
Adaptive self-tuning. Deterministic. Never affects scheduling.
Cooldown safeguards prevent rebuild loops.
"""

import time
from collections import deque
from typing import Any

FULL_REBUILD_COOLDOWN_SEC = 900   # 15 min max 1 full rebuild
CHANNEL_REBUILD_WINDOW_SEC = 300  # 5 min
MAX_CHANNEL_REBUILDS_PER_WINDOW = 3

_full_rebuild_timestamps: deque[float] = deque(maxlen=20)
_channel_rebuild_timestamps: deque[tuple[float, int]] = deque(maxlen=100)
_throttle_count: int = 0
_preemptive_count: int = 0
_current_strategy: dict[str, Any] = {}
_adaptive_mode: int = 0  # 0=normal, 1=elevated, 2=high, 3=critical


def _prune_old(timestamps: deque[float], window_sec: float) -> None:
    now = time.monotonic()
    while timestamps and now - timestamps[0] > window_sec:
        timestamps.popleft()


def record_full_rebuild() -> None:
    _full_rebuild_timestamps.append(time.monotonic())


def record_channel_rebuild(channel_id: int) -> None:
    _channel_rebuild_timestamps.append((time.monotonic(), channel_id))


def record_throttle() -> None:
    global _throttle_count
    _throttle_count += 1
    try:
        from exstreamtv.monitoring.metrics import get_metrics_collector
        get_metrics_collector().inc_adaptive_throttled()
    except ImportError:
        pass


def record_preemptive_rebuild() -> None:
    global _preemptive_count
    _preemptive_count += 1
    try:
        from exstreamtv.monitoring.metrics import get_metrics_collector
        get_metrics_collector().inc_preemptive_rebuild()
    except ImportError:
        pass


def get_throttle_count() -> int:
    return _throttle_count


def get_preemptive_count() -> int:
    return _preemptive_count


def can_full_rebuild() -> bool:
    _prune_old(_full_rebuild_timestamps, FULL_REBUILD_COOLDOWN_SEC)
    return len(_full_rebuild_timestamps) == 0


def can_channel_rebuild(channel_id: int) -> bool:
    now = time.monotonic()
    recent = [(t, c) for t, c in _channel_rebuild_timestamps
              if now - t <= CHANNEL_REBUILD_WINDOW_SEC and c == channel_id]
    return len(recent) < MAX_CHANNEL_REBUILDS_PER_WINDOW


def _channel_rebuild_count_total() -> int:
    now = time.monotonic()
    return sum(1 for t, _ in _channel_rebuild_timestamps if now - t <= CHANNEL_REBUILD_WINDOW_SEC)


def determine_adaptive_strategy(
    health_score: float,
    predictive_risk: int,
    recent_metrics: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic strategy selection. Never modifies clock or scheduling.
    """
    global _current_strategy, _adaptive_mode

    if health_score < 50:
        mode = 3
        interval = 20
        scope = "full"
        preemptive = True
        log_level = "aggressive"
    elif predictive_risk > 60 or health_score < 70:
        mode = 2
        interval = 30
        scope = "incremental"
        preemptive = True
        log_level = "aggressive"
    elif predictive_risk >= 30 and predictive_risk <= 60:
        mode = 1
        interval = 45
        scope = "incremental"
        preemptive = False
        log_level = "elevated"
    else:
        mode = 0
        interval = 60
        scope = "channel-only"
        preemptive = False
        log_level = "normal"

    if scope == "full" and not can_full_rebuild():
        scope = "incremental"
        record_throttle()
        import logging
        logging.getLogger(__name__).info("Adaptive throttle: full rebuild deferred (cooldown)")

    if _channel_rebuild_count_total() >= MAX_CHANNEL_REBUILDS_PER_WINDOW * 3:
        if scope == "incremental":
            scope = "channel-only"
        record_throttle()

    _current_strategy = {
        "watchdog_interval_seconds": interval,
        "rebuild_scope": scope,
        "preemptive_rebuild": preemptive,
        "log_level": log_level,
        "adaptive_mode": mode,
    }
    _adaptive_mode = mode
    try:
        from exstreamtv.monitoring.metrics import get_metrics_collector
        get_metrics_collector().set_adaptive_mode(mode)
    except ImportError:
        pass
    return _current_strategy


def get_adaptive_strategy() -> dict[str, Any]:
    return dict(_current_strategy)


def get_watchdog_interval() -> int:
    if not _current_strategy:
        return 60
    s = _current_strategy.get("watchdog_interval_seconds", 60)
    return int(s)


def get_adaptive_mode() -> int:
    return _adaptive_mode


def get_adaptive_mode_label() -> str:
    return ["Normal", "Elevated Monitoring", "High Sensitivity", "Critical Stabilization"][
        min(3, max(0, _adaptive_mode))
    ]
