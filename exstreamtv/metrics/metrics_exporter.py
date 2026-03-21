"""
Zero-drift EPG metrics. Delegates to MetricsCollector.
"""

from exstreamtv.monitoring.metrics import get_metrics_collector


def inc_active_mismatch() -> None:
    get_metrics_collector().inc_active_mismatch()


def inc_timeline_rebuild() -> None:
    get_metrics_collector().inc_timeline_rebuild()


def inc_watchdog_interventions() -> None:
    get_metrics_collector().inc_watchdog_interventions()


def inc_xmltv_fallback() -> None:
    get_metrics_collector().inc_xmltv_fallback()


def inc_predictive_warning() -> None:
    get_metrics_collector().inc_predictive_warning()
