"""Alignment Runner - Orchestrates Broadcast Alignment Validation Harness."""

import logging
from pathlib import Path

import httpx

from .clock_validator import validate_clock, validate_schedule
from .drift_monitor import run_drift_monitor
from .hdhomerun_validator import validate_hdhomerun_protocol
from .metrics_collector import collect_system_metrics, count_ffmpeg_processes
from .plex_validator import simulate_plex_tune
from .report_generator import (
    generate_alignment_report_html,
    generate_alignment_report_json,
    generate_drift_log_csv,
    generate_memory_profile_log,
)
from .stream_probe import probe_stream
from .xmltv_validator import fetch_and_validate_xmltv

logger = logging.getLogger(__name__)


async def run_alignment_validation(
    base_url: str = "http://127.0.0.1:8411",
    channel_ids: list[int] | None = None,
    guide_numbers: list[str] | None = None,
    output_dir: Path | None = None,
    run_drift_monitor_full: bool = False,
    drift_interval_seconds: float = 5.0,
    drift_duration_seconds: float = 60.0,
) -> dict:
    """Run full alignment validation; generate reports including drift_log.csv, memory_profile.log."""
    output_dir = output_dir or Path("reports/alignment")
    output_dir.mkdir(parents=True, exist_ok=True)
    drift_samples: list[dict] = []
    memory_samples: list[dict] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        errors: list[str] = []
        clock_results: list[dict] = []
        schedule_results: list[dict] = []
        hdh = await validate_hdhomerun_protocol(base_url, client=client)
        hdhomerun_result = {
            "discover": {"ok": hdh.discover.ok, "message": hdh.discover.message},
            "lineup": {"ok": hdh.lineup.ok, "message": hdh.lineup.message},
            "device_id": hdh.device_id,
            "guide_numbers": hdh.guide_numbers,
        }
        if not hdh.discover.ok:
            errors.append("HDHomeRun discover failed")
        guide_numbers = guide_numbers or hdh.guide_numbers or ["100"]
        channel_ids = channel_ids or [int(g) for g in guide_numbers if g.isdigit()]

        for ch_id in channel_ids[:10]:
            cr = await validate_clock(base_url, ch_id, client=client)
            clock_results.append({"channel_id": ch_id, "ok": cr.ok, "message": cr.message})
            sch = await validate_schedule(base_url, ch_id, client=client)
            schedule_results.append({"channel_id": ch_id, **sch})

        xmltv_results = await fetch_and_validate_xmltv(base_url, guide_numbers, client=client)
        for ch, xr in xmltv_results.items():
            if not xr.ok:
                errors.append(f"XMLTV ch={ch}: {xr.message}")

        for gn in guide_numbers[:5]:
            pr = await simulate_plex_tune(base_url, gn, client=client, duration_seconds=8.0)
            if not pr.ok:
                errors.append(f"Plex ch={gn}: {pr.message}")

        for gn in guide_numbers[:5]:
            sr = await probe_stream(base_url, gn, duration_seconds=15.0, client=client)
            if not sr.ok:
                errors.append(f"Stream ch={gn}: {sr.message}")

        m = collect_system_metrics()
        ff = count_ffmpeg_processes()
        memory_samples.append({
            "timestamp": m.timestamp.isoformat() if m.timestamp else "",
            "cpu_percent": m.cpu_usage,
            "memory_mb": m.memory_usage_mb,
            "fd_count": m.fd_count,
            "thread_count": m.thread_count,
            "ffmpeg_count": ff,
        })

        if run_drift_monitor_full:
            drift_res = await run_drift_monitor(
                base_url, channel_ids[:5],
                interval_seconds=drift_interval_seconds,
                duration_seconds=drift_duration_seconds,
                client=client,
            )
            for ch_id, dr in drift_res.items():
                for s in dr.samples:
                    drift_samples.append({
                        "timestamp": s.timestamp.isoformat(),
                        "channel_id": ch_id,
                        "offset": s.offset,
                        "total_cycle": s.total_cycle,
                        "ok": s.ok,
                        "message": s.message or "",
                    })
                if dr.drift_detected:
                    errors.append(f"Drift ch={ch_id}: {dr.failure_message}")

        summary = {
            "passed": len(errors) == 0,
            "errors": errors,
            "clock_validated": sum(1 for r in clock_results if r.get("ok")),
            "clock_total": len(clock_results),
            "schedule_validated": sum(1 for r in schedule_results if r.get("ok")),
        }
        generate_alignment_report_json(
            output_dir / "alignment_report.json",
            clock_results=clock_results,
            hdhomerun_result=hdhomerun_result,
            summary=summary,
        )
        generate_alignment_report_html(
            output_dir / "alignment_report.html",
            clock_results=clock_results,
            hdhomerun_result=hdhomerun_result,
            summary=summary,
        )
        generate_drift_log_csv(output_dir / "drift_log.csv", drift_samples)
        generate_memory_profile_log(output_dir / "memory_profile.log", memory_samples)
        return summary
