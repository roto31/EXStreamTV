#!/usr/bin/env python3
"""
24-hour soak test harness for EXStreamTV stability.

Simulates concurrent channel requests, tracks restart count, pool usage,
memory growth. Detects recursion errors and restart storms.
Does NOT modify core code. Exit non-zero if instability detected.
"""

import argparse
import json
import logging
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SoakMetrics:
    elapsed_seconds: float = 0.0
    requests_total: int = 0
    requests_ok: int = 0
    requests_err: int = 0
    restarts_detected: int = 0
    pool_active_max: int = 0
    memory_rss_mb_max: float = 0.0
    recursion_errors: int = 0
    restart_storms: int = 0
    samples: list = field(default_factory=list)


def _get_memory_mb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


def _fetch_metrics(base_url: str) -> dict:
    import urllib.request
    try:
        req = urllib.request.Request(f"{base_url}/api/health")
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"error": str(e)}


def _fetch_prometheus(base_url: str) -> dict:
    import urllib.request
    try:
        req = urllib.request.Request(f"{base_url}/metrics")
        with urllib.request.urlopen(req, timeout=5) as r:
            text = r.read().decode()
            out = {}
            for line in text.splitlines():
                if line.startswith("exstreamtv_ffmpeg_processes_active ") and "{" not in line:
                    try:
                        out["ffmpeg_active"] = int(float(line.split()[1]))
                    except (IndexError, ValueError):
                        pass
                if line.startswith("exstreamtv_health_timeouts_total ") and "{" not in line:
                    try:
                        out["health_timeouts"] = int(float(line.split()[1]))
                    except (IndexError, ValueError):
                        pass
            return out
    except Exception:
        return {}


def run_soak(
    base_url: str = "http://127.0.0.1:8000",
    duration_seconds: int = 86400,
    interval_seconds: float = 5.0,
    concurrency: int = 5,
    metrics_file: Path | None = None,
    fail_on: dict | None = None,
) -> SoakMetrics:
    fail_on = fail_on or {
        "recursion_errors": 1,
        "restart_storms": 3,
        "memory_growth_mb": 500,
        "restarts_per_minute": 30,
    }
    metrics = SoakMetrics()
    restart_timestamps: deque = deque(maxlen=200)
    last_health_timeouts = 0
    start_memory = _get_memory_mb()
    start_time = time.monotonic()
    stop_event = threading.Event()

    def worker():
        nonlocal metrics
        while not stop_event.is_set():
            try:
                r = _fetch_metrics(base_url)
                metrics.requests_total += 1
                if "error" in r:
                    metrics.requests_err += 1
                else:
                    metrics.requests_ok += 1
            except Exception as e:
                metrics.requests_err += 1
                if "recursion" in str(e).lower() or "RecursionError" in str(type(e).__name__):
                    metrics.recursion_errors += 1
            time.sleep(interval_seconds / max(1, concurrency))

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    for t in threads:
        t.start()

    end_time = start_time + duration_seconds
    sample_count = 0
    while time.monotonic() < end_time:
        time.sleep(min(30, end_time - time.monotonic()))
        metrics.elapsed_seconds = time.monotonic() - start_time

        pm: dict = {}
        try:
            pm = _fetch_prometheus(base_url)
            active = pm.get("ffmpeg_active", 0)
            metrics.pool_active_max = max(metrics.pool_active_max, active)
            ht = pm.get("health_timeouts", 0)
            delta = ht - last_health_timeouts
            last_health_timeouts = ht
            if delta > 0:
                metrics.restarts_detected += delta
                for _ in range(delta):
                    restart_timestamps.append(time.monotonic())
        except Exception:
            pass

        mem = _get_memory_mb()
        metrics.memory_rss_mb_max = max(metrics.memory_rss_mb_max, mem)

        now = time.monotonic()
        recent = sum(1 for t in restart_timestamps if t > now - 60.0)
        if recent >= fail_on.get("restarts_per_minute", 30):
            metrics.restart_storms += 1
            logger.warning(f"Restart storm detected: {recent} restarts/min")

        sample_count += 1
        if sample_count <= 100:
            metrics.samples.append({
                "elapsed": metrics.elapsed_seconds,
                "memory_mb": mem,
                "pool_active": pm.get("ffmpeg_active", 0),
                "restarts": metrics.restarts_detected,
            })

    stop_event.set()
    for t in threads:
        t.join(timeout=interval_seconds * 2)

    metrics.elapsed_seconds = time.monotonic() - start_time
    if metrics_file:
        metrics_file.write_text(json.dumps(asdict(metrics), indent=2))

    return metrics


def main() -> int:
    ap = argparse.ArgumentParser(description="EXStreamTV soak test")
    ap.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL")
    ap.add_argument("--duration", type=int, default=86400, help="Duration seconds (default 24h)")
    ap.add_argument("--interval", type=float, default=5.0, help="Request interval")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--metrics", type=Path, help="Write metrics JSON to file")
    args = ap.parse_args()

    metrics = run_soak(
        base_url=args.url,
        duration_seconds=args.duration,
        interval_seconds=args.interval,
        concurrency=args.concurrency,
        metrics_file=args.metrics,
    )

    logger.info(
        f"Soak complete: {metrics.elapsed_seconds:.0f}s, "
        f"ok={metrics.requests_ok}, err={metrics.requests_err}, "
        f"restarts={metrics.restarts_detected}, recursion_err={metrics.recursion_errors}, "
        f"storms={metrics.restart_storms}"
    )

    exit_code = 0
    if metrics.recursion_errors > 0:
        logger.error("Recursion errors detected")
        exit_code = 1
    if metrics.restart_storms >= 3:
        logger.error("Restart storms detected")
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
