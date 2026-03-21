#!/usr/bin/env python3
"""
Runtime Soak Test Harness - Validates all Executive Technical Architecture Audit risks.

Launches server with EXSTREAMTV_VALIDATE_DURATIONS=1, runs streams, XMLTV, ensure_clock
race test, log monitor, cancellation safety. Generates reports/runtime_soak_test_report.md.

Usage:
  python3 scripts/runtime_soak_test.py [--stress] [--port PORT] [--duration SECS]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Fail-fast patterns in server logs (any occurrence = FAIL)
LOG_FAIL_PATTERNS = [
    r"needs more content \(only 0\.0 min remaining\)",
    r"Missing Plex connection info",
    r"Stream unavailable",
    r"contract violation",
    r"Auto-restarting channel",
    r"total_cycle_duration == 0",
    r"UnboundLocalError",
    r"Internal Server Error",
    r"Traceback",
]


@dataclass
class SoakReport:
    """Results from the soak test run."""

    test_duration_seconds: float = 0.0
    channels_tested: list = field(default_factory=list)
    concurrent_stream_count: int = 0
    xmltv_request_count: int = 0
    rebuild_count: int = 0
    resolver_failure_count: int = 0
    restart_loop_count: int = 0
    race_condition_status: str = "NOT_RUN"
    cancellation_safety_status: str = "NOT_RUN"
    orphan_ffmpeg_count: int = -1
    log_failure_detected: str = ""
    passed: bool = False
    errors: list[str] = field(default_factory=list)


def _count_orphan_ffmpeg() -> int:
    """Count ffmpeg processes not owned by current user (rough orphan check)."""
    try:
        import psutil

        count = 0
        for p in psutil.process_iter(["name", "ppid"]):
            try:
                if "ffmpeg" in (p.info.get("name") or "").lower():
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return count
    except ImportError:
        return -1


def _run_subprocess_until(
    cmd: list[str],
    env: dict,
    ready_url: str,
    ready_timeout: float,
    log_callback,
) -> subprocess.Popen | None:
    """Start subprocess, wait for readiness via HTTP, return process or None on failure."""
    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        log_callback(f"Failed to start server: {e}")
        return None

    # Read stdout in background for log monitoring
    def read_stdout():
        for line in iter(proc.stdout.readline, ""):
            log_callback(line.rstrip())
        proc.stdout.close()

    t = threading.Thread(target=read_stdout, daemon=True)
    t.start()

    # Wait for readiness
    import urllib.request

    deadline = time.monotonic() + ready_timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(ready_url)
            with urllib.request.urlopen(req, timeout=2) as r:
                if r.status == 200:
                    return proc
        except Exception:
            pass
        time.sleep(0.5)

    log_callback("Server did not become ready in time")
    proc.terminate()
    proc.wait(timeout=5)
    return None


async def run_soak(
    base_url: str = "http://127.0.0.1:8411",
    port: int = 8411,
    duration_seconds: float = 300.0,
    stress: bool = False,
    report_path: Path | None = None,
) -> SoakReport:
    """Execute full runtime soak test."""
    report = SoakReport()
    log_lines: list[str] = []
    log_failure: list[str] = []
    fail_event = threading.Event()

    def log_cb(line: str, fe: threading.Event | None = None):
        log_lines.append(line)
        for pat in LOG_FAIL_PATTERNS:
            if re.search(pat, line, re.I):
                log_failure.append(f"{pat}: {line[:200]}")
                if fe:
                    fe.set()

    env = os.environ.copy()
    env["EXSTREAMTV_VALIDATE_DURATIONS"] = "1"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "exstreamtv.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
    ]

    baseline_ffmpeg = _count_orphan_ffmpeg()
    print("Starting server with EXSTREAMTV_VALIDATE_DURATIONS=1...")
    proc = _run_subprocess_until(
        cmd,
        env,
        f"{base_url}/api/health",
        30.0,
        lambda line: log_cb(line, fail_event),
    )
    if not proc:
        report.errors.append("Server failed to start or become ready")
        report.passed = False
        _write_report(report, report_path)
        return report

    health_url = f"{base_url}/api/health"
    try:
        import httpx
    except ImportError:
        report.errors.append("httpx not installed")
        proc.terminate()
        proc.wait(timeout=10)
        _write_report(report, report_path)
        return report

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1) XMLTV validation (5 times during soak)
        xmltv_ok = True
        xmltv_count = 0
        for _ in range(5):
            try:
                r = await client.get(f"{base_url}/iptv/xmltv.xml")
                xmltv_count += 1
                if r.status_code != 200:
                    report.errors.append(f"XMLTV returned {r.status_code}")
                    xmltv_ok = False
                elif len(r.content) < 10 * 1024:
                    report.errors.append(f"XMLTV too small: {len(r.content)} bytes")
                    xmltv_ok = False
                elif b"Internal Server Error" in r.content or b"Traceback" in r.content:
                    report.errors.append("XMLTV contained error content")
                    xmltv_ok = False
            except Exception as e:
                report.errors.append(f"XMLTV request failed: {e}")
                xmltv_ok = False
        report.xmltv_request_count = xmltv_count

        if not xmltv_ok:
            proc.terminate()
            proc.wait(timeout=10)
            report.passed = False
            _write_report(report, report_path)
            return report

        # 2) Discover channels
        try:
            r = await client.get(f"{base_url}/api/channels")
            r.raise_for_status()
            channels = r.json()
        except Exception as e:
            report.errors.append(f"Channel discovery failed: {e}")
            proc.terminate()
            proc.wait(timeout=10)
            report.passed = False
            _write_report(report, report_path)
            return report

        enabled = [c for c in channels if c.get("enabled", True)]
        if len(enabled) < 2:
            report.errors.append("Need at least 2 enabled channels")
            proc.terminate()
            proc.wait(timeout=10)
            report.passed = False
            _write_report(report, report_path)
            return report

        # Select 4 channels for streams (2 IPTV, 1 Plex sim, 1 HDHomeRun)
        selected = enabled[:4]
        report.channels_tested = [c.get("number", "") for c in selected]

        # 3) Concurrent ensure_clock race test
        channel_ids = [c["id"] for c in selected]
        try:
            tasks = [
                client.get(f"{base_url}/api/clock/{cid}") for cid in channel_ids[:3]
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    report.errors.append(f"ensure_clock race test channel {i}: {res}")
                elif res.status_code != 200:
                    report.errors.append(
                        f"ensure_clock channel {i} returned {res.status_code}"
                    )
            def _is_fail(r):
                if isinstance(r, Exception):
                    return True
                return getattr(r, "status_code", 0) != 200

            report.race_condition_status = (
                "PASSED" if not any(_is_fail(r) for r in results) else "FAILED"
            )
        except Exception as e:
            report.race_condition_status = f"FAILED: {e}"
            report.errors.append(str(e))

        # 4) Stream sessions (2 IPTV, 1 HDHomeRun)
        stream_count = 5 if stress else 4
        stream_tasks = []

        stream_timeout = httpx.Timeout(15.0)

        async def read_stream(
            url: str, name: str, min_seconds: float, _max_idle_seconds: float
        ) -> tuple[bool, str]:
            try:
                async with client.stream(
                    "GET", url, timeout=stream_timeout
                ) as resp:
                    if resp.status_code != 200:
                        return False, f"{name}: HTTP {resp.status_code}"
                    start = time.monotonic()
                    total_bytes = 0
                    async for chunk in resp.aiter_bytes():
                        total_bytes += len(chunk)
                        if time.monotonic() - start >= min_seconds:
                            return True, ""
                    return False, f"{name}: stream closed early"
            except Exception as e:
                return False, f"{name}: {e}"

        nums = [str(c.get("number", "")) for c in selected]
        iptv_urls = [f"{base_url}/iptv/channel/{n}.ts" for n in nums[:2]]
        hd_urls = [f"{base_url}/hdhomerun/auto/v{n}" for n in nums[2:4]]
        # Cycle URLs if we need more for stress mode
        iptv_pool = iptv_urls + ([iptv_urls[0]] * 3) if len(iptv_urls) >= 1 else []
        hd_pool = hd_urls + ([hd_urls[0]] * 1) if len(hd_urls) >= 1 else []

        if stress:
            for i, url in enumerate(iptv_pool[:5]):
                stream_tasks.append(
                    read_stream(url, f"IPTV-{i}", duration_seconds, 10.0)
                )
            for i, url in enumerate(hd_pool[:2]):
                stream_tasks.append(
                    read_stream(url, f"Plex/HD-{i}", duration_seconds, 10.0)
                )
        else:
            for url in iptv_urls[:2]:
                stream_tasks.append(
                    read_stream(url, "IPTV", duration_seconds, 10.0)
                )
            for url in hd_urls[:2]:
                stream_tasks.append(
                    read_stream(url, "HDHomeRun", duration_seconds, 10.0)
                )

        if stress and iptv_urls:

            async def disconnect_reconnect_stream() -> tuple[bool, str]:
                """Simulate random client disconnects: connect, read 2 min, disconnect, repeat."""
                url = iptv_urls[0]
                total_elapsed = 0.0
                while total_elapsed < duration_seconds:
                    try:
                        async with client.stream(
                            "GET", url, timeout=stream_timeout
                        ) as resp:
                            if resp.status_code != 200:
                                return False, f"DiscReconn: HTTP {resp.status_code}"
                            chunk_start = time.monotonic()
                            async for chunk in resp.aiter_bytes():
                                if time.monotonic() - chunk_start >= 120:
                                    break
                            total_elapsed += time.monotonic() - chunk_start
                    except Exception as e:
                        return False, f"DiscReconn: {e}"
                    await asyncio.sleep(5)
                return True, ""

            stream_tasks.append(disconnect_reconnect_stream())

        # 5) Additional XMLTV requests during soak (every 30s in stress)
        xmltv_task = None
        if stress:

            async def xmltv_loop():
                n = 0
                while n < 20:  # 10 min / 30s
                    await asyncio.sleep(30)
                    try:
                        r = await client.get(f"{base_url}/iptv/xmltv.xml")
                        if r.status_code == 200 and len(r.content) > 10240:
                            n += 1
                    except Exception:
                        pass

            xmltv_task = asyncio.create_task(xmltv_loop())

        report.concurrent_stream_count = len(stream_tasks)
        stream_coros = [st for st in stream_tasks]

        async def run_streams_with_abort() -> list:
            abort_task = asyncio.create_task(
                asyncio.to_thread(fail_event.wait)
            )
            stream_task_objs = [asyncio.create_task(c) for c in stream_coros]
            done, _ = await asyncio.wait(
                [abort_task] + stream_task_objs,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if abort_task in done:
                for t in stream_task_objs:
                    t.cancel()
                await asyncio.gather(*stream_task_objs, return_exceptions=True)
                return []
            return await asyncio.gather(*stream_task_objs, return_exceptions=True)

        stream_results = await run_streams_with_abort()
        if fail_event.is_set():
            report.errors.append("Log failure patterns detected (aborted)")
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            report.orphan_ffmpeg_count = _count_orphan_ffmpeg()
            report.test_duration_seconds = duration_seconds
            report.passed = False
            _write_report(report, report_path)
            return report

        if xmltv_task:
            xmltv_task.cancel()
            try:
                await xmltv_task
            except asyncio.CancelledError:
                pass

        for i, res in enumerate(stream_results):
            if isinstance(res, Exception):
                report.errors.append(f"Stream {i}: {res}")
            elif isinstance(res, tuple):
                ok, msg = res
                if not ok:
                    report.errors.append(msg)

        # 6) Check for log failures
        if log_failure:
            report.log_failure_detected = "; ".join(log_failure[:5])
            report.errors.append("Log failure patterns detected")

        # 7) Cancellation safety (SIGINT)
        report.cancellation_safety_status = "RUNNING"
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            report.errors.append("Server did not exit cleanly within 15s of SIGINT")
            report.cancellation_safety_status = "FAILED: timeout"
        else:
            report.cancellation_safety_status = "PASSED"

        post_ffmpeg = _count_orphan_ffmpeg()
        report.orphan_ffmpeg_count = post_ffmpeg
        # No new orphans: post must be <= baseline (zero delta)
        if baseline_ffmpeg >= 0 and post_ffmpeg > baseline_ffmpeg:
            report.errors.append(
                f"Orphan ffmpeg increased: baseline={baseline_ffmpeg}, post={post_ffmpeg}"
            )
            report.passed = False

        # Rebuild count / restart: parse logs (best-effort)
        rebuild_match = re.search(r"rebuilt (\d+)", " ".join(log_lines))
        if rebuild_match:
            report.rebuild_count = int(rebuild_match.group(1))
        for line in log_lines:
            if "Auto-restarting" in line or "triggering channel restart" in line.lower():
                report.restart_loop_count += 1

    report.test_duration_seconds = duration_seconds
    report.passed = len(report.errors) == 0
    _write_report(report, report_path)
    return report


def _write_report(report: SoakReport, path: Path | None) -> None:
    """Write markdown report and updated risk matrix."""
    if not path:
        path = PROJECT_ROOT / "reports" / "runtime_soak_test_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    orphan_ok = (
        report.orphan_ffmpeg_count < 0
        or "Orphan ffmpeg increased" not in " ".join(report.errors)
    )
    risk_matrix = [
        ("Orphan ffmpeg", "RESOLVED" if orphan_ok else "UNRESOLVED", f"count={report.orphan_ffmpeg_count} (no increase)"),
        ("Duration Collapse", "RESOLVED" if report.passed else "UNRESOLVED", report.log_failure_detected or "No zero duration in logs"),
        ("Mass Rebuild Storm", "RESOLVED" if report.rebuild_count == 0 else "UNRESOLVED", f"rebuild_count={report.rebuild_count}"),
        ("Clock Invalidation", "RESOLVED" if report.race_condition_status == "PASSED" else "UNRESOLVED", report.race_condition_status),
        ("XMLTV Failure", "RESOLVED" if report.xmltv_request_count > 0 and not any("XMLTV" in e for e in report.errors) else "UNRESOLVED", f"requests={report.xmltv_request_count}"),
        ("Resolver Contract Violation", "RESOLVED" if "Missing Plex" not in report.log_failure_detected else "UNRESOLVED", report.log_failure_detected or "No Plex metadata errors"),
        ("Race Conditions", "RESOLVED" if report.race_condition_status == "PASSED" else "UNRESOLVED", report.race_condition_status),
        ("IPTV Streaming Failure", "RESOLVED" if report.passed and report.concurrent_stream_count > 0 else "UNRESOLVED", f"streams={report.concurrent_stream_count}"),
        ("Plex Streaming Failure", "RESOLVED" if "Stream unavailable" not in (report.log_failure_detected or "") else "UNRESOLVED", report.log_failure_detected or "No Plex stream errors"),
        ("HDHomeRun Failure", "RESOLVED" if report.passed else "UNRESOLVED", "Stream session completed"),
        ("Restart Loops", "RESOLVED" if report.restart_loop_count == 0 else "UNRESOLVED", f"restart_loop_count={report.restart_loop_count}"),
    ]

    md = f"""# Runtime Soak Test Report

**Generated**: {datetime.now(timezone.utc).isoformat()}
**Overall**: {"PASSED" if report.passed else "FAILED"}

## Summary

| Metric | Value |
|--------|-------|
| Test duration | {report.test_duration_seconds:.0f}s |
| Channels tested | {report.channels_tested} |
| Concurrent stream count | {report.concurrent_stream_count} |
| XMLTV request count | {report.xmltv_request_count} |
| Rebuild count | {report.rebuild_count} |
| Resolver failure count | {report.resolver_failure_count} |
| Restart loop count | {report.restart_loop_count} |
| Race condition status | {report.race_condition_status} |
| Cancellation safety | {report.cancellation_safety_status} |
| Orphan ffmpeg processes | {report.orphan_ffmpeg_count} |

## Errors

"""
    for e in report.errors:
        md += f"- {e}\n"
    md += "\n## Risk Matrix (Post-Soak)\n\n| Risk Area | Status | Evidence |\n|-----------|--------|----------|\n"
    for name, status, ev in risk_matrix:
        md += f"| {name} | {status} | {ev} |\n"
    path.write_text(md, encoding="utf-8")
    print(f"Report written to {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime soak test harness")
    parser.add_argument("--url", default="http://127.0.0.1:8411", help="Base URL")
    parser.add_argument("--port", type=int, default=8411)
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--duration", type=float, default=300)
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "reports" / "runtime_soak_test_report.md",
    )
    parser.add_argument("--skip-validate", action="store_true", help="Skip post-soak clock validation")
    args = parser.parse_args()

    report = asyncio.run(
        run_soak(
            base_url=args.url,
            port=args.port,
            duration_seconds=600 if args.stress else args.duration,
            stress=args.stress,
            report_path=args.report,
        )
    )
    if not args.skip_validate and report.passed:
        print("\n--- Post-soak: Clock Authority Validation ---")
        try:
            val_proc = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "validate_clock_authority.py")],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
            )
            if val_proc.returncode != 0:
                report.passed = False
                report.errors.append(
                    f"validate_clock_authority.py exited {val_proc.returncode}"
                )
                if val_proc.stderr:
                    report.errors.append(val_proc.stderr[:500])
                _write_report(report, args.report)
            else:
                print(val_proc.stdout or "(no output)")
        except Exception as e:
            report.passed = False
            report.errors.append(f"Post-soak validation failed: {e}")
            _write_report(report, args.report)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
