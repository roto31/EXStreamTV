"""
Metrics Collector - Per-channel and system metrics.

Collect per channel: clock_offset, expected_index, stream_item, xmltv_item,
  drift_seconds, reconnect_count, retry_count, error_count
System: cpu_usage, memory_usage, fd_count, thread_count, active_ffmpeg_count,
  api_latency, hdhomerun_response_time
"""

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ChannelMetrics:
    """Per-channel metrics."""

    channel_id: int
    clock_offset: float | None = None
    expected_index: int | None = None
    stream_item: str | None = None
    xmltv_item: str | None = None
    drift_seconds: float = 0.0
    reconnect_count: int = 0
    retry_count: int = 0
    error_count: int = 0
    last_updated: datetime | None = None


@dataclass
class SystemMetrics:
    """System-wide metrics."""

    cpu_usage: float | None = None
    memory_usage_mb: float | None = None
    fd_count: int | None = None
    thread_count: int | None = None
    active_ffmpeg_count: int | None = None
    api_latency_ms: float | None = None
    hdhomerun_response_time_ms: float | None = None
    timestamp: datetime | None = None


def collect_system_metrics() -> SystemMetrics:
    """Collect system metrics (best-effort, cross-platform)."""
    m = SystemMetrics(timestamp=datetime.utcnow())
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        m.cpu_usage = proc.cpu_percent(interval=0.1)
        m.memory_usage_mb = proc.memory_info().rss / (1024 * 1024)
        m.fd_count = proc.num_fds() if hasattr(proc, "num_fds") else None
        m.thread_count = proc.num_threads()
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Could not collect psutil metrics: %s", e)
    if m.fd_count is None:
        try:
            fd_dir = f"/proc/{os.getpid()}/fd"
            if os.path.isdir(fd_dir):
                m.fd_count = len(os.listdir(fd_dir))
        except (OSError, AttributeError):
            pass
    return m


def count_ffmpeg_processes() -> int | None:
    """Count running FFmpeg processes (best-effort)."""
    try:
        import psutil
        count = 0
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name", "") or ""
                if "ffmpeg" in name.lower():
                    count += 1
            except Exception:
                pass
        return count
    except ImportError:
        return None
    except Exception:
        return None


class MetricsCollector:
    """Collector for channel and system metrics during validation."""

    def __init__(self) -> None:
        self._channel_metrics: dict[int, ChannelMetrics] = {}
        self._system_samples: list[SystemMetrics] = []
        self._lock = threading.Lock()

    def update_channel(
        self,
        channel_id: int,
        clock_offset: float | None = None,
        expected_index: int | None = None,
        stream_item: str | None = None,
        xmltv_item: str | None = None,
        drift_seconds: float = 0.0,
        reconnect_count: int = 0,
        retry_count: int = 0,
        error_count: int = 0,
    ) -> None:
        """Update metrics for a channel."""
        with self._lock:
            if channel_id not in self._channel_metrics:
                self._channel_metrics[channel_id] = ChannelMetrics(channel_id=channel_id)
            m = self._channel_metrics[channel_id]
            if clock_offset is not None:
                m.clock_offset = clock_offset
            if expected_index is not None:
                m.expected_index = expected_index
            if stream_item is not None:
                m.stream_item = stream_item
            if xmltv_item is not None:
                m.xmltv_item = xmltv_item
            m.drift_seconds = drift_seconds
            m.reconnect_count += reconnect_count
            m.retry_count += retry_count
            m.error_count += error_count
            m.last_updated = datetime.utcnow()

    def add_system_sample(self, sample: SystemMetrics) -> None:
        """Add a system metrics sample."""
        with self._lock:
            self._system_samples.append(sample)
            if len(self._system_samples) > 10000:
                self._system_samples = self._system_samples[-5000:]

    def get_channel_metrics(self, channel_id: int) -> ChannelMetrics | None:
        """Get metrics for a channel."""
        with self._lock:
            return self._channel_metrics.get(channel_id)

    def get_all_channel_metrics(self) -> dict[int, ChannelMetrics]:
        """Get all channel metrics."""
        with self._lock:
            return dict(self._channel_metrics)

    def get_system_samples(self) -> list[SystemMetrics]:
        """Get system samples."""
        with self._lock:
            return list(self._system_samples)
