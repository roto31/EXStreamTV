"""Load Runner - Orchestrates stress modes: Light, Production, Extreme, 24h."""

import logging
from dataclasses import dataclass
from pathlib import Path

import httpx

from .channel_switcher import run_channel_switch_test
from .reconnect_storm import run_reconnect_storm
from .system_monitor import SystemSnapshot, take_snapshot

logger = logging.getLogger(__name__)

STRESS_MODES = {
    "light": {"duration_min": 10, "reconnect_duration": 60, "switch_duration": 60},
    "production": {"duration_min": 30, "reconnect_duration": 90, "switch_duration": 120},
    "extreme": {"duration_min": 120, "reconnect_duration": 120, "switch_duration": 300},
    "24h": {"duration_min": 86400, "reconnect_duration": 300, "switch_duration": 600},
}

try:
    from tests.integration.broadcast_alignment.report_generator import (
        generate_memory_profile_log,
        generate_stress_report_html,
        generate_stress_report_json,
    )
    HAS_REPORT_GEN = True
except ImportError:
    HAS_REPORT_GEN = False


@dataclass
class LoadRunResult:
    mode: str
    passed: bool
    errors: list[str]
    reconnect_result: object | None
    switch_result: object | None
    system_samples: list[SystemSnapshot]


async def run_load(
    base_url: str,
    guide_numbers: list[str],
    mode: str = "light",
    output_dir: Path | str | None = None,
) -> LoadRunResult:
    """Run stress load in given mode."""
    cfg = STRESS_MODES.get(mode, STRESS_MODES["light"])
    errors: list[str] = []
    samples: list[SystemSnapshot] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        samples.append(take_snapshot())
        reconnect_res = None
        if guide_numbers:
            try:
                reconnect_res = await run_reconnect_storm(
                    base_url, guide_numbers[0],
                    duration_seconds=min(cfg["reconnect_duration"], 120),
                    client=client,
                )
                if reconnect_res.errors:
                    errors.extend(reconnect_res.errors[:10])
            except Exception as e:
                errors.append(f"Reconnect storm: {e}")
        samples.append(take_snapshot())
        switch_res = None
        try:
            switch_res = await run_channel_switch_test(
                base_url, guide_numbers or ["100"],
                duration_seconds=min(cfg["switch_duration"], 120),
                client=client,
            )
            if switch_res.errors:
                errors.extend(switch_res.errors[:10])
        except Exception as e:
            errors.append(f"Channel switch: {e}")
        samples.append(take_snapshot())
    result = LoadRunResult(
        mode=mode,
        passed=len(errors) == 0,
        errors=errors,
        reconnect_result=reconnect_res,
        switch_result=switch_res,
        system_samples=samples,
    )
    if HAS_REPORT_GEN and output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        reconnect_count = reconnect_res.cycles_completed if reconnect_res else 0
        switch_count = switch_res.switches_completed if switch_res else 0
        duration = max(
            (s.timestamp - samples[0].timestamp).total_seconds()
            if len(samples) >= 2 and samples[0].timestamp
            else 0,
            reconnect_res.duration_seconds if reconnect_res else 0,
            switch_res.duration_seconds if switch_res else 0,
        )
        metrics = {}
        if samples:
            last = samples[-1]
            metrics = {
                "memory_mb": last.memory_mb,
                "fd_count": last.fd_count,
                "thread_count": last.thread_count,
            }
        mem_samples = [
            {
                "timestamp": s.timestamp.isoformat() if s.timestamp else "",
                "cpu_percent": s.cpu_percent,
                "memory_mb": s.memory_mb,
                "fd_count": s.fd_count,
                "thread_count": s.thread_count,
                "ffmpeg_count": s.ffmpeg_count,
            }
            for s in samples
        ]
        generate_stress_report_json(
            output_dir / "stress_report.json",
            mode=mode,
            duration_seconds=duration,
            reconnect_count=reconnect_count,
            channel_switch_count=switch_count,
            errors=errors,
            metrics=metrics,
        )
        generate_stress_report_html(
            output_dir / "stress_report.html",
            mode=mode,
            duration_seconds=duration,
            reconnect_count=reconnect_count,
            channel_switch_count=switch_count,
            errors=errors,
            metrics=metrics,
        )
        generate_memory_profile_log(output_dir / "memory_profile.log", mem_samples)
    return result
