"""
Monitoring and observability for EXStreamTV.

Provides MetricsCollector and Prometheus exporter for:
- FFmpeg process pool metrics
- Channel health
- System resources (memory, FD, event loop lag)
- DB pool usage
"""

from exstreamtv.monitoring.metrics import MetricsCollector, get_metrics_collector

__all__ = [
    "MetricsCollector",
    "get_metrics_collector",
]
