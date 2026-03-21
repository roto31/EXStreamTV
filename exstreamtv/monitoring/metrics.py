"""
MetricsCollector for EXStreamTV observability.

Tracks FFmpeg processes, channel health, system resources, and DB pool.
Compatible with Prometheus text format (no prometheus_client dependency required).
"""

import asyncio
import logging
import os
import resource
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricsCollector:
    """
    Collects and exposes metrics for Prometheus export.

    Gauges and counters stored as simple dicts; exported as Prometheus text format.
    """

    # FFmpeg process pool
    ffmpeg_processes_active: int = 0
    ffmpeg_spawn_pending: int = 0
    ffmpeg_spawn_rejected_memory_total: int = 0
    ffmpeg_spawn_rejected_fd_total: int = 0
    ffmpeg_spawn_rejected_capacity_total: int = 0

    # Per-channel
    channel_memory_bytes: Dict[str | int, int] = field(default_factory=dict)
    channel_restart_total: Dict[str | int, int] = field(default_factory=dict)
    stream_success_total: Dict[str | int, int] = field(default_factory=dict)
    stream_failure_total: Dict[str | int, int] = field(default_factory=dict)
    circuit_breaker_state: Dict[str | int, str] = field(default_factory=dict)

    # Stability
    pool_acquisition_latency_seconds: float = 0.0
    restart_rate_per_minute: float = 0.0
    health_timeouts_total: int = 0
    playout_rebuild_total: int = 0

    # Zero-drift EPG
    drift_delta_seconds: float = 0.0
    active_mismatch_total: int = 0
    timeline_rebuild_total: int = 0
    watchdog_interventions_total: int = 0
    xmltv_fallback_total: int = 0
    predictive_risk_score: int = 0
    predictive_warning_total: int = 0
    adaptive_mode: int = 0
    adaptive_rebuild_throttled_total: int = 0
    preemptive_rebuild_total: int = 0
    smt_verified_total: int = 0
    smt_failed_total: int = 0
    smt_timeout_total: int = 0

    # System
    system_rss_bytes: int = 0
    fd_usage: int = 0
    event_loop_lag_seconds: float = 0.0

    # DB pool
    db_pool_checked_out: int = 0
    db_pool_size: int = 0

    _lock: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        try:
            self._lock = asyncio.Lock()
        except RuntimeError:
            self._lock = None

    def set_ffmpeg_active(self, count: int) -> None:
        """Update active FFmpeg process count."""
        self.ffmpeg_processes_active = count

    def set_ffmpeg_pending(self, count: int) -> None:
        """Update pending spawn count."""
        self.ffmpeg_spawn_pending = count

    def inc_ffmpeg_rejected(self, reason: str) -> None:
        """Increment spawn rejection counter by reason."""
        if reason == "memory":
            self.ffmpeg_spawn_rejected_memory_total += 1
        elif reason == "fd":
            self.ffmpeg_spawn_rejected_fd_total += 1
        else:
            self.ffmpeg_spawn_rejected_capacity_total += 1

    def inc_channel_restart(self, channel_id: str | int) -> None:
        """Increment restart counter for channel."""
        k = str(channel_id)
        self.channel_restart_total[k] = self.channel_restart_total.get(k, 0) + 1

    def inc_stream_success(self, channel_id: str | int) -> None:
        """Increment stream success counter for channel."""
        k = str(channel_id)
        self.stream_success_total[k] = self.stream_success_total.get(k, 0) + 1

    def inc_stream_failure(self, channel_id: str | int) -> None:
        """Increment stream failure counter for channel."""
        k = str(channel_id)
        self.stream_failure_total[k] = self.stream_failure_total.get(k, 0) + 1

    def set_circuit_breaker_state(self, channel_id: str | int, state: str) -> None:
        """Set circuit breaker state for channel."""
        self.circuit_breaker_state[str(channel_id)] = state

    def set_pool_acquisition_latency(self, seconds: float) -> None:
        self.pool_acquisition_latency_seconds = seconds

    def inc_restart_rate_per_minute(self, rate: float) -> None:
        self.restart_rate_per_minute = rate

    def inc_health_timeouts(self) -> None:
        self.health_timeouts_total += 1

    def inc_playout_rebuild(self) -> None:
        self.playout_rebuild_total += 1

    def set_drift_delta(self, seconds: float) -> None:
        self.drift_delta_seconds = seconds

    def inc_active_mismatch(self) -> None:
        self.active_mismatch_total += 1

    def inc_timeline_rebuild(self) -> None:
        self.timeline_rebuild_total += 1

    def inc_watchdog_interventions(self) -> None:
        self.watchdog_interventions_total += 1

    def inc_xmltv_fallback(self) -> None:
        self.xmltv_fallback_total += 1

    def inc_predictive_warning(self) -> None:
        self.predictive_warning_total += 1

    def set_adaptive_mode(self, mode: int) -> None:
        self.adaptive_mode = mode

    def inc_adaptive_throttled(self) -> None:
        self.adaptive_rebuild_throttled_total += 1

    def inc_preemptive_rebuild(self) -> None:
        self.preemptive_rebuild_total += 1

    def inc_smt_verified(self) -> None:
        self.smt_verified_total += 1

    def inc_smt_failed(self) -> None:
        self.smt_failed_total += 1

    def inc_smt_timeout(self) -> None:
        self.smt_timeout_total += 1

    def set_channel_memory(self, channel_id: str | int, bytes_val: int) -> None:
        """Set memory usage for channel."""
        self.channel_memory_bytes[str(channel_id)] = bytes_val

    def set_db_pool(self, checked_out: int, size: int) -> None:
        """Set DB pool metrics."""
        self.db_pool_checked_out = checked_out
        self.db_pool_size = size

    def update_system_metrics(self) -> None:
        """Update system metrics (RSS, FD, event loop lag)."""
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            self.system_rss_bytes = proc.memory_info().rss
        except Exception:
            pass

        try:
            self.fd_usage = len(os.listdir("/proc/self/fd"))
        except (FileNotFoundError, OSError):
            try:
                soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
                self.fd_usage = 0  # Cannot get on some platforms
            except Exception:
                pass

    def update_event_loop_lag(self, lag_seconds: float) -> None:
        """Update event loop lag measurement."""
        self.event_loop_lag_seconds = lag_seconds

    def to_prometheus_text(self) -> str:
        """Export metrics in Prometheus exposition format."""
        self.update_system_metrics()
        lines: list[str] = []

        def gauge(name: str, value: float | int, labels: Optional[dict] = None) -> None:
            lbl = ""
            if labels:
                parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
                lbl = "{" + ",".join(parts) + "}"
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name}{lbl} {value}")

        def counter(name: str, value: int, labels: Optional[dict] = None) -> None:
            lbl = ""
            if labels:
                parts = [f'{k}="{v}"' for k, v in sorted(labels.items())]
                lbl = "{" + ",".join(parts) + "}"
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name}{lbl} {value}")

        gauge("exstreamtv_ffmpeg_processes_active", self.ffmpeg_processes_active)
        gauge("exstreamtv_ffmpeg_spawn_pending", self.ffmpeg_spawn_pending)
        counter("exstreamtv_ffmpeg_spawn_rejected_total", self.ffmpeg_spawn_rejected_memory_total, {"reason": "memory"})
        counter("exstreamtv_ffmpeg_spawn_rejected_total", self.ffmpeg_spawn_rejected_fd_total, {"reason": "fd"})
        counter("exstreamtv_ffmpeg_spawn_rejected_total", self.ffmpeg_spawn_rejected_capacity_total, {"reason": "capacity"})
        gauge("exstreamtv_system_rss_bytes", self.system_rss_bytes)
        gauge("exstreamtv_fd_usage", self.fd_usage)
        gauge("exstreamtv_event_loop_lag_seconds", self.event_loop_lag_seconds)
        gauge("exstreamtv_db_pool_checked_out", self.db_pool_checked_out)
        gauge("exstreamtv_db_pool_size", self.db_pool_size)
        gauge("exstreamtv_pool_acquisition_latency_seconds", self.pool_acquisition_latency_seconds)
        gauge("exstreamtv_restart_rate_per_minute", self.restart_rate_per_minute)
        counter("exstreamtv_health_timeouts_total", self.health_timeouts_total)
        counter("exstreamtv_playout_rebuild_total", self.playout_rebuild_total)
        gauge("exstreamtv_drift_delta_seconds", self.drift_delta_seconds)
        counter("exstreamtv_active_mismatch_total", self.active_mismatch_total)
        counter("exstreamtv_timeline_rebuild_total", self.timeline_rebuild_total)
        counter("exstreamtv_watchdog_interventions_total", self.watchdog_interventions_total)
        counter("exstreamtv_xmltv_fallback_total", self.xmltv_fallback_total)
        gauge("exstreamtv_predictive_risk_score", self.predictive_risk_score)
        counter("exstreamtv_predictive_warning_total", self.predictive_warning_total)
        gauge("exstreamtv_adaptive_mode", self.adaptive_mode)
        counter("exstreamtv_adaptive_rebuild_throttled_total", self.adaptive_rebuild_throttled_total)
        counter("exstreamtv_preemptive_rebuild_total", self.preemptive_rebuild_total)
        counter("exstreamtv_smt_verified_total", self.smt_verified_total)
        counter("exstreamtv_smt_failed_total", self.smt_failed_total)
        counter("exstreamtv_smt_timeout_total", self.smt_timeout_total)
        _state_val = {"closed": 0, "half_open": 1, "open": 2}
        for ch_id, state in self.circuit_breaker_state.items():
            gauge("exstreamtv_circuit_breaker_state", _state_val.get(state, -1), {"channel_id": str(ch_id)})

        for ch_id, val in self.channel_restart_total.items():
            counter("exstreamtv_channel_restart_total", val, {"channel_id": str(ch_id)})
        for ch_id, val in self.stream_success_total.items():
            counter("exstreamtv_stream_success_total", val, {"channel_id": str(ch_id)})
        for ch_id, val in self.stream_failure_total.items():
            counter("exstreamtv_stream_failure_total", val, {"channel_id": str(ch_id)})
        for ch_id, val in self.channel_memory_bytes.items():
            gauge("exstreamtv_channel_memory_bytes", val, {"channel_id": str(ch_id)})

        return "\n".join(lines) + "\n"


_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global MetricsCollector."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
