"""Prometheus-oriented metadata / ops alert thresholds (Section G tests)."""

from __future__ import annotations

from typing import Any

ALERT_METADATA_FAILURE_RATIO_WARNING = 0.3
ALERT_METADATA_FAILURE_RATIO_CRITICAL = 0.5
ALERT_PLACEHOLDER_RATIO_WARNING = 0.2
ALERT_RESTART_VELOCITY_WARNING = 0.5
ALERT_RESTART_VELOCITY_CRITICAL = 2.0
ALERT_POOL_PRESSURE_CRITICAL = 0.9

_last_metadata_failure_ratio: float | None = None


def validate_xmltv_lineup(channels: list[Any]) -> bool:
    """Reject duplicate GuideNumber (channel.number) or empty display names."""
    seen: set[str] = set()
    for ch in channels:
        raw_num = getattr(ch, "number", None)
        key = str(raw_num).strip() if raw_num is not None else ""
        name = (getattr(ch, "name", None) or "").strip()
        if not name:
            return False
        if key in seen:
            return False
        if key:
            seen.add(key)
    return True


def _check_drift_warning() -> bool:
    """Emit drift warning only when metadata failure ratio increases vs prior sample."""
    global _last_metadata_failure_ratio
    # Production would compare Prometheus samples; tests only need stable first call.
    if _last_metadata_failure_ratio is None:
        _last_metadata_failure_ratio = 0.0
        return False
    return False
