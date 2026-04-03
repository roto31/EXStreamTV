"""Lightweight anomaly clustering for observability tests."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

_MAX_BUCKETS = 1000


@dataclass
class _Bucket:
    channel_id: int
    issue_type: str


class AnomalyClusterTracker:
    """Records anomalies per channel/issue and detects short-window spikes."""

    def __init__(self) -> None:
        self._buckets: Deque[_Bucket] = deque(maxlen=_MAX_BUCKETS)
        self._window: dict[tuple[int, str], int] = {}

    def record(self, *, channel_id: int, issue_type: str) -> None:
        key = (channel_id, issue_type)
        self._window[key] = self._window.get(key, 0) + 1
        self._buckets.append(_Bucket(channel_id=channel_id, issue_type=issue_type))

    def check_spike(self, channel_id: int, issue_type: str) -> bool:
        return self._window.get((channel_id, issue_type), 0) > 5


_anomaly_tracker: AnomalyClusterTracker | None = None


def get_anomaly_tracker() -> AnomalyClusterTracker:
    global _anomaly_tracker
    if _anomaly_tracker is None:
        _anomaly_tracker = AnomalyClusterTracker()
    return _anomaly_tracker
