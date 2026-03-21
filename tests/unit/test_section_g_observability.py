"""
Section G — Observability and Alert Policy Tests.

Validates: Drift detection, alert thresholds, anomaly clustering.
"""

import pytest

from exstreamtv.monitoring.anomaly_cluster import (
    AnomalyClusterTracker,
    get_anomaly_tracker,
)
from exstreamtv.monitoring.metadata_metrics import (
    ALERT_METADATA_FAILURE_RATIO_CRITICAL,
    ALERT_METADATA_FAILURE_RATIO_WARNING,
    ALERT_PLACEHOLDER_RATIO_WARNING,
    ALERT_POOL_PRESSURE_CRITICAL,
    ALERT_RESTART_VELOCITY_CRITICAL,
    ALERT_RESTART_VELOCITY_WARNING,
    _check_drift_warning,
)


def test_alert_thresholds_exist() -> None:
    """Section G: Prometheus alert thresholds are defined."""
    assert ALERT_METADATA_FAILURE_RATIO_WARNING == 0.3
    assert ALERT_METADATA_FAILURE_RATIO_CRITICAL == 0.5
    assert ALERT_PLACEHOLDER_RATIO_WARNING == 0.2
    assert ALERT_RESTART_VELOCITY_WARNING == 0.5
    assert ALERT_RESTART_VELOCITY_CRITICAL == 2.0
    assert ALERT_POOL_PRESSURE_CRITICAL == 0.9


def test_drift_warning_no_emission_when_no_increase() -> None:
    """Drift check does not emit when ratio unchanged."""
    # First call initializes
    emitted = _check_drift_warning()
    assert emitted is False


def test_anomaly_tracker_spike() -> None:
    """Anomaly spike: > 5 in one window."""
    tracker = AnomalyClusterTracker()
    for _ in range(6):
        tracker.record(channel_id=1, issue_type="placeholder")
    assert tracker.check_spike(1, "placeholder") is True
    assert tracker.check_spike(1, "other") is False


def test_anomaly_tracker_eviction() -> None:
    """Anomaly tracker respects 1000 bucket cap."""
    tracker = AnomalyClusterTracker()
    for i in range(1002):
        tracker.record(channel_id=i % 500, issue_type=f"t{i}")
    assert len(tracker._buckets) <= 1000


def test_get_anomaly_tracker_singleton() -> None:
    """get_anomaly_tracker returns singleton."""
    t1 = get_anomaly_tracker()
    t2 = get_anomaly_tracker()
    assert t1 is t2
