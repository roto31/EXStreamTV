"""
Report Generator — alignment_report.json, alignment_report.html,
drift_log.csv, memory_profile.log.
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _json_serial(obj: object) -> str:
    """JSON serializer for datetime and non-serializable objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def generate_alignment_report_json(
    output_path: Path,
    *,
    clock_results: list[dict] | None = None,
    xmltv_results: dict | None = None,
    hdhomerun_result: dict | None = None,
    drift_results: dict | None = None,
    summary: dict | None = None,
) -> None:
    """Generate alignment_report.json."""
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": summary or {},
        "clock_validation": clock_results or [],
        "xmltv_validation": xmltv_results or {},
        "hdhomerun_validation": hdhomerun_result or {},
        "drift_monitor": drift_results or {},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=_json_serial)


def generate_alignment_report_html(
    output_path: Path,
    *,
    clock_results: list[dict] | None = None,
    xmltv_results: dict | None = None,
    hdhomerun_result: dict | None = None,
    drift_results: dict | None = None,
    summary: dict | None = None,
) -> None:
    """Generate alignment_report.html."""
    summary = summary or {}
    passed = summary.get("passed", False)
    status_class = "pass" if passed else "fail"
    status_text = "PASS" if passed else "FAIL"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Broadcast Alignment Report — {status_text}</title>
<style>
body {{ font-family: system-ui; margin: 2em; }}
.pass {{ color: #0a0; }} .fail {{ color: #c00; }}
table {{ border-collapse: collapse; margin: 1em 0; }}
th, td {{ border: 1px solid #ccc; padding: 0.5em 1em; text-align: left; }}
th {{ background: #f5f5f5; }}
pre {{ background: #f5f5f5; padding: 1em; overflow-x: auto; }}
</style>
</head>
<body>
<h1>Broadcast Alignment Report</h1>
<p>Generated: {datetime.utcnow().isoformat()}</p>
<p class="{status_class}"><strong>Status: {status_text}</strong></p>
<pre>{json.dumps(summary, indent=2, default=_json_serial)}</pre>

<h2>Clock Validation</h2>
<pre>{json.dumps(clock_results or [], indent=2, default=_json_serial)}</pre>

<h2>XMLTV Validation</h2>
<pre>{json.dumps(xmltv_results or {}, indent=2, default=_json_serial)}</pre>

<h2>HDHomeRun Validation</h2>
<pre>{json.dumps(hdhomerun_result or {}, indent=2, default=_json_serial)}</pre>

<h2>Drift Monitor</h2>
<pre>{json.dumps(drift_results or {}, indent=2, default=_json_serial)}</pre>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def generate_stress_report_json(
    output_path: Path,
    *,
    mode: str = "",
    duration_seconds: float = 0,
    reconnect_count: int = 0,
    channel_switch_count: int = 0,
    errors: list[str] | None = None,
    metrics: dict | None = None,
) -> None:
    """Generate stress_report.json."""
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "mode": mode,
        "duration_seconds": duration_seconds,
        "reconnect_count": reconnect_count,
        "channel_switch_count": channel_switch_count,
        "errors": errors or [],
        "metrics": metrics or {},
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=_json_serial)


def generate_stress_report_html(
    output_path: Path,
    *,
    mode: str = "",
    duration_seconds: float = 0,
    reconnect_count: int = 0,
    channel_switch_count: int = 0,
    errors: list[str] | None = None,
    metrics: dict | None = None,
) -> None:
    """Generate stress_report.html."""
    errors = errors or []
    metrics = metrics or {}
    passed = len(errors) == 0

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>HDHomeRun Stress Report — {mode}</title>
<style>
body {{ font-family: system-ui; margin: 2em; }}
.pass {{ color: #0a0; }} .fail {{ color: #c00; }}
pre {{ background: #f5f5f5; padding: 1em; overflow-x: auto; }}
</style>
</head>
<body>
<h1>HDHomeRun Stress Report</h1>
<p>Generated: {datetime.utcnow().isoformat()}</p>
<p>Mode: {mode} | Duration: {duration_seconds:.0f}s</p>
<p>Reconnects: {reconnect_count} | Channel switches: {channel_switch_count}</p>
<p class="{'pass' if passed else 'fail'}"><strong>Status: {'PASS' if passed else 'FAIL'}</strong></p>
<h2>Errors</h2>
<pre>{json.dumps(errors, indent=2)}</pre>
<h2>Metrics</h2>
<pre>{json.dumps(metrics, indent=2, default=_json_serial)}</pre>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")


def generate_drift_log_csv(output_path: Path, samples: list[dict]) -> None:
    """Generate drift_log.csv from drift monitor samples."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not samples:
        output_path.write_text("timestamp,channel_id,offset,total_cycle,ok,message\n", encoding="utf-8")
        return
    fieldnames = ["timestamp", "channel_id", "offset", "total_cycle", "ok", "message"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for s in samples:
            w.writerow({k: s.get(k, "") for k in fieldnames})


def generate_memory_profile_log(output_path: Path, samples: list[dict]) -> None:
    """Generate memory_profile.log from system metrics samples."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["timestamp,cpu_percent,memory_mb,fd_count,thread_count,ffmpeg_count\n"]
    for s in samples:
        ts = s.get("timestamp", "")
        cpu = s.get("cpu_percent", "")
        mem = s.get("memory_mb", "")
        fd = s.get("fd_count", "")
        thr = s.get("thread_count", "")
        ff = s.get("ffmpeg_count", "")
        lines.append(f"{ts},{cpu},{mem},{fd},{thr},{ff}\n")
    output_path.write_text("".join(lines), encoding="utf-8")
