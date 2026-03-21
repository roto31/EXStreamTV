"""
System Monitor - CPU, memory, FD, threads, FFmpeg count during load.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SystemSnapshot:
    """System metrics snapshot."""

    timestamp: datetime
    cpu_percent: float | None = None
    memory_mb: float | None = None
    fd_count: int | None = None
    thread_count: int | None = None
    ffmpeg_count: int | None = None


def take_snapshot() -> SystemSnapshot:
    """Take a system metrics snapshot."""
    s = SystemSnapshot(timestamp=datetime.utcnow())
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        s.cpu_percent = proc.cpu_percent(interval=0.05)
        s.memory_mb = proc.memory_info().rss / (1024 * 1024)
        s.thread_count = proc.num_threads()
        if hasattr(proc, "num_fds"):
            s.fd_count = proc.num_fds()
    except Exception:
        pass
    if s.fd_count is None:
        try:
            fd_dir = f"/proc/{os.getpid()}/fd"
            if os.path.isdir(fd_dir):
                s.fd_count = len(os.listdir(fd_dir))
        except Exception:
            pass
    try:
        import psutil
        s.ffmpeg_count = sum(
            1 for p in psutil.process_iter(["name"])
            if "ffmpeg" in (p.info.get("name") or "").lower()
        )
    except Exception:
        pass
    return s


def check_memory_growth(
    samples: list[SystemSnapshot],
    threshold_percent: float = 20.0,
) -> tuple[bool, str]:
    """
    Fail if memory growth exceeds threshold from first to last sample.
    """
    if len(samples) < 2:
        return True, ""
    first = samples[0]
    last = samples[-1]
    if first.memory_mb is None or last.memory_mb is None:
        return True, ""
    if first.memory_mb <= 0:
        return True, ""
    growth = ((last.memory_mb - first.memory_mb) / first.memory_mb) * 100
    if growth > threshold_percent:
        return False, f"Memory growth {growth:.1f}% exceeds {threshold_percent}%"
    return True, ""
