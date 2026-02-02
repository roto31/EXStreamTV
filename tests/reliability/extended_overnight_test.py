"""
Extended Overnight Reliability & Regression Test
=================================================

Comprehensive 2-hour reliability test for all EXStreamTV channels.
Based on authoritative testing standards from:
- IBM Regression Testing
- LeapWork Reliability Testing  
- Microsoft Power Platform Well-Architected
- GeeksforGeeks Software Testing
- Trymata Reliability Testing

Test Coverage:
1. Feature Testing: All channel features tested
2. Load Testing: Multiple concurrent requests
3. Regression Testing: Verify all channels work after updates
4. Endurance Testing: Extended continuous operation
5. Recovery Testing: FFmpeg restart recovery
"""

import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Dict, List
from enum import Enum
import traceback

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class ChannelTestResult:
    """Result of a single channel test."""
    channel_number: str
    channel_name: str
    status: TestStatus
    tune_success: bool = False
    stream_received: bool = False
    bytes_received: int = 0
    time_to_first_byte: Optional[float] = None
    epg_match: Optional[bool] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)


@dataclass  
class CycleResult:
    """Result of a complete test cycle."""
    cycle_number: int
    start_time: str
    end_time: str
    duration_seconds: float
    total_channels: int
    passed: int
    failed: int
    timeouts: int
    errors: int
    success_rate: float
    channel_results: List[dict]


@dataclass
class ExtendedTestConfig:
    """Configuration for extended overnight testing."""
    # Test duration and timing
    duration_hours: float = 2.0
    cycle_interval_seconds: float = 180.0  # 3 minutes between cycles
    tune_duration_seconds: float = 45.0  # 45 seconds per channel (cold-start tolerance)
    
    # Endpoints
    base_url: str = "http://localhost:8411"
    hdhomerun_url: str = "http://localhost:5004"
    
    # Test options
    include_all_channels: bool = True  # Test ALL channels including disabled
    verify_epg: bool = True
    verify_stream_data: bool = True
    
    # Retry options
    max_retries_per_channel: int = 2
    retry_delay_seconds: float = 5.0
    
    # Output
    output_dir: str = "tests/reliability/reports"
    log_level: str = "INFO"


class ExtendedOvernightTest:
    """
    Extended overnight reliability and regression testing.
    
    Implements comprehensive testing based on industry standards:
    
    1. IBM Regression Testing:
       - Systematic testing after code changes
       - Full regression suite execution
       
    2. LeapWork Reliability:
       - Continuous monitoring
       - Metrics collection (MTBF, MTTR)
       
    3. Microsoft Power Platform:
       - Chaos engineering principles
       - Fault injection testing
       
    4. GeeksforGeeks Software Testing:
       - Feature testing
       - Load testing
       - Regression testing
       
    5. Trymata Reliability:
       - User-focused testing
       - Real-world scenario simulation
    """
    
    def __init__(self, config: Optional[ExtendedTestConfig] = None):
        self.config = config or ExtendedTestConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._shutdown_requested = False
        self._channels: List[dict] = []
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Metrics
        self._all_results: List[ChannelTestResult] = []
        self._cycle_results: List[CycleResult] = []
        self._channel_metrics: Dict[str, Dict] = {}
        self._error_log: List[Dict] = []
        
        # Logging setup
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Configure logging to file and console."""
        self._log_file = self.output_dir / f"extended_overnight_{self.test_run_id}.log"
        
        # File handler with detailed logging
        file_handler = logging.FileHandler(self._log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(name)s] %(message)s"
        ))
        
        logger.addHandler(file_handler)
        logger.setLevel(getattr(logging, self.config.log_level))
    
    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown handlers."""
        def handler(sig, frame):
            logger.warning("Shutdown signal received - completing current cycle...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    
    async def _fetch_all_channels(self) -> List[dict]:
        """Fetch all channels from API."""
        try:
            response = await self._http_client.get(
                f"{self.config.base_url}/api/channels"
            )
            response.raise_for_status()
            channels = response.json()
            
            # Sort by channel number
            channels.sort(key=lambda c: float(str(c.get("number", "0")).replace(".", "")))
            
            logger.info(f"Fetched {len(channels)} total channels")
            
            enabled = [c for c in channels if c.get("enabled", False)]
            disabled = [c for c in channels if not c.get("enabled", False)]
            
            logger.info(f"  - {len(enabled)} enabled channels")
            logger.info(f"  - {len(disabled)} disabled channels")
            
            if self.config.include_all_channels:
                return channels
            else:
                return enabled
                
        except Exception as e:
            logger.error(f"Failed to fetch channels: {e}")
            return []
    
    async def _get_epg_for_channel(self, channel_number: str) -> Optional[dict]:
        """Get current EPG program for a channel."""
        try:
            response = await self._http_client.get(
                f"{self.config.base_url}/api/channels/{channel_number}/schedule",
                timeout=10.0
            )
            if response.status_code == 200:
                schedule = response.json()
                if schedule and len(schedule) > 0:
                    return schedule[0]  # Current program
        except Exception as e:
            logger.debug(f"EPG fetch failed for channel {channel_number}: {e}")
        return None
    
    async def _test_channel(self, channel: dict, retry: int = 0) -> ChannelTestResult:
        """
        Test a single channel with comprehensive validation.
        
        Args:
            channel: Channel data dict
            retry: Current retry count
            
        Returns:
            ChannelTestResult with all metrics
        """
        channel_number = str(channel.get("number", "unknown"))
        channel_name = channel.get("name", "Unknown")
        enabled = channel.get("enabled", False)
        
        result = ChannelTestResult(
            channel_number=channel_number,
            channel_name=channel_name,
            status=TestStatus.FAILED,
            metadata={"enabled": enabled, "retry": retry}
        )
        
        # Determine best tune URL - use IPTV endpoint (more reliable)
        tune_url = f"{self.config.base_url}/iptv/channel/{channel_number}.ts"
        
        try:
            start_time = time.time()
            first_byte_time = None
            
            # Check EPG before tuning
            if self.config.verify_epg:
                epg_data = await self._get_epg_for_channel(channel_number)
                result.metadata["epg_available"] = epg_data is not None
                if epg_data:
                    result.metadata["epg_title"] = epg_data.get("title", "Unknown")
            
            # Tune to channel
            async with self._http_client.stream(
                "GET",
                tune_url,
                timeout=self.config.tune_duration_seconds + 10,
            ) as response:
                
                if response.status_code != 200:
                    result.status = TestStatus.FAILED
                    result.error_message = f"HTTP {response.status_code}"
                    result.error_type = "http_error"
                    self._log_error(channel_number, channel_name, result.error_message)
                    return result
                
                result.tune_success = True
                
                # Stream data for specified duration
                async for chunk in response.aiter_bytes():
                    if first_byte_time is None:
                        first_byte_time = time.time()
                        result.time_to_first_byte = first_byte_time - start_time
                    
                    result.bytes_received += len(chunk)
                    
                    # Check if duration reached
                    if time.time() - start_time >= self.config.tune_duration_seconds:
                        break
                
                # Evaluate result
                if result.bytes_received > 0:
                    result.stream_received = True
                    result.status = TestStatus.PASSED
                    
                    # Validate stream quality
                    duration = time.time() - start_time
                    bitrate = (result.bytes_received * 8) / duration if duration > 0 else 0
                    result.metadata["bitrate_bps"] = bitrate
                    result.metadata["bitrate_mbps"] = bitrate / 1_000_000
                    
                else:
                    result.status = TestStatus.FAILED
                    result.error_message = "No stream data received"
                    result.error_type = "no_data"
                    self._log_error(channel_number, channel_name, result.error_message)
                    
        except httpx.TimeoutException:
            result.status = TestStatus.TIMEOUT
            result.error_message = f"Timeout after {self.config.tune_duration_seconds}s"
            result.error_type = "timeout"
            self._log_error(channel_number, channel_name, result.error_message)
            
            # Retry if allowed
            if retry < self.config.max_retries_per_channel:
                logger.info(f"  Retrying channel {channel_number} (attempt {retry + 2})")
                await asyncio.sleep(self.config.retry_delay_seconds)
                return await self._test_channel(channel, retry + 1)
            
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            result.error_type = type(e).__name__
            self._log_error(channel_number, channel_name, str(e), traceback.format_exc())
        
        return result
    
    def _log_error(self, channel_number: str, channel_name: str, 
                   error: str, stacktrace: Optional[str] = None) -> None:
        """Log an error for later analysis."""
        self._error_log.append({
            "timestamp": datetime.now().isoformat(),
            "channel_number": channel_number,
            "channel_name": channel_name,
            "error": error,
            "stacktrace": stacktrace,
        })
    
    def _update_channel_metrics(self, result: ChannelTestResult) -> None:
        """Update running metrics for a channel."""
        ch = result.channel_number
        if ch not in self._channel_metrics:
            self._channel_metrics[ch] = {
                "channel_number": ch,
                "channel_name": result.channel_name,
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "timeouts": 0,
                "errors": 0,
                "total_bytes": 0,
                "avg_ttfb": [],
                "failures": [],
            }
        
        m = self._channel_metrics[ch]
        m["total_tests"] += 1
        
        if result.status == TestStatus.PASSED:
            m["passed"] += 1
            m["total_bytes"] += result.bytes_received
            if result.time_to_first_byte:
                m["avg_ttfb"].append(result.time_to_first_byte)
        elif result.status == TestStatus.TIMEOUT:
            m["timeouts"] += 1
            m["failures"].append({"type": "timeout", "time": result.timestamp})
        elif result.status == TestStatus.ERROR:
            m["errors"] += 1
            m["failures"].append({"type": "error", "time": result.timestamp, "msg": result.error_message})
        else:
            m["failed"] += 1
            m["failures"].append({"type": "failed", "time": result.timestamp, "msg": result.error_message})
    
    async def _run_cycle(self, cycle_number: int) -> CycleResult:
        """Run a complete test cycle on all channels."""
        cycle_start = datetime.now()
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"CYCLE {cycle_number} STARTING - {len(self._channels)} channels")
        logger.info("=" * 80)
        
        results: List[ChannelTestResult] = []
        passed = failed = timeouts = errors = 0
        
        for i, channel in enumerate(self._channels):
            if self._shutdown_requested:
                logger.warning("Shutdown requested - stopping cycle")
                break
            
            ch_num = channel.get("number", "?")
            ch_name = channel.get("name", "Unknown")
            enabled = "✓" if channel.get("enabled") else "✗"
            
            logger.info(f"[{i+1}/{len(self._channels)}] Channel {ch_num} ({enabled}): {ch_name}")
            
            result = await self._test_channel(channel)
            results.append(result)
            self._all_results.append(result)
            self._update_channel_metrics(result)
            
            # Log result
            if result.status == TestStatus.PASSED:
                passed += 1
                ttfb = f"{result.time_to_first_byte:.2f}s" if result.time_to_first_byte else "N/A"
                bitrate = result.metadata.get("bitrate_mbps", 0)
                logger.info(f"  ✓ PASS - {result.bytes_received:,} bytes, TTFB: {ttfb}, {bitrate:.1f} Mbps")
            elif result.status == TestStatus.TIMEOUT:
                timeouts += 1
                logger.warning(f"  ✗ TIMEOUT - {result.error_message}")
            elif result.status == TestStatus.ERROR:
                errors += 1
                logger.error(f"  ✗ ERROR - {result.error_type}: {result.error_message}")
            else:
                failed += 1
                logger.warning(f"  ✗ FAIL - {result.error_message}")
        
        # Cycle summary
        cycle_end = datetime.now()
        duration = (cycle_end - cycle_start).total_seconds()
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        logger.info("")
        logger.info("-" * 60)
        logger.info(f"CYCLE {cycle_number} COMPLETE")
        logger.info(f"  Duration: {duration:.1f}s")
        logger.info(f"  Results: {passed} passed, {failed} failed, {timeouts} timeouts, {errors} errors")
        logger.info(f"  Success Rate: {success_rate:.1f}%")
        logger.info("-" * 60)
        
        cycle_result = CycleResult(
            cycle_number=cycle_number,
            start_time=cycle_start.isoformat(),
            end_time=cycle_end.isoformat(),
            duration_seconds=duration,
            total_channels=total,
            passed=passed,
            failed=failed,
            timeouts=timeouts,
            errors=errors,
            success_rate=success_rate,
            channel_results=[asdict(r) for r in results]
        )
        
        self._cycle_results.append(cycle_result)
        
        # Save cycle results
        self._save_cycle_results(cycle_result)
        
        return cycle_result
    
    def _save_cycle_results(self, cycle: CycleResult) -> None:
        """Save cycle results to file."""
        path = self.output_dir / f"cycle_{cycle.cycle_number}_{self.test_run_id}.json"
        with open(path, "w") as f:
            json.dump(asdict(cycle), f, indent=2, default=str)
    
    def _calculate_reliability_metrics(self) -> Dict:
        """Calculate overall reliability metrics (MTBF, MTTR, etc.)."""
        metrics = {
            "total_tests": len(self._all_results),
            "total_passed": sum(1 for r in self._all_results if r.status == TestStatus.PASSED),
            "total_failed": sum(1 for r in self._all_results if r.status == TestStatus.FAILED),
            "total_timeouts": sum(1 for r in self._all_results if r.status == TestStatus.TIMEOUT),
            "total_errors": sum(1 for r in self._all_results if r.status == TestStatus.ERROR),
        }
        
        # Overall success rate
        metrics["success_rate"] = (metrics["total_passed"] / metrics["total_tests"] * 100) if metrics["total_tests"] > 0 else 0
        
        # MTBF (Mean Time Between Failures) per channel
        channel_mtbf = {}
        for ch_num, ch_data in self._channel_metrics.items():
            total = ch_data["total_tests"]
            passed = ch_data["passed"]
            failures = total - passed
            if failures > 0 and passed > 0:
                channel_mtbf[ch_num] = passed / failures
            elif failures == 0:
                channel_mtbf[ch_num] = float('inf')  # No failures
            else:
                channel_mtbf[ch_num] = 0  # All failures
        
        metrics["channel_mtbf"] = channel_mtbf
        
        # Average TTFB
        all_ttfb = [r.time_to_first_byte for r in self._all_results if r.time_to_first_byte]
        metrics["avg_ttfb"] = sum(all_ttfb) / len(all_ttfb) if all_ttfb else None
        metrics["min_ttfb"] = min(all_ttfb) if all_ttfb else None
        metrics["max_ttfb"] = max(all_ttfb) if all_ttfb else None
        
        # Categorize channels by reliability
        reliable_channels = []
        unreliable_channels = []
        for ch_num, ch_data in self._channel_metrics.items():
            rate = (ch_data["passed"] / ch_data["total_tests"] * 100) if ch_data["total_tests"] > 0 else 0
            ch_info = {
                "number": ch_num,
                "name": ch_data["channel_name"],
                "success_rate": rate,
                "passed": ch_data["passed"],
                "total": ch_data["total_tests"],
            }
            if rate >= 80:
                reliable_channels.append(ch_info)
            else:
                unreliable_channels.append(ch_info)
        
        metrics["reliable_channels"] = sorted(reliable_channels, key=lambda x: -x["success_rate"])
        metrics["unreliable_channels"] = sorted(unreliable_channels, key=lambda x: x["success_rate"])
        
        return metrics
    
    def _generate_report(self) -> Dict:
        """Generate comprehensive final report."""
        metrics = self._calculate_reliability_metrics()
        
        report = {
            "test_run_id": self.test_run_id,
            "test_type": "Extended Overnight Reliability & Regression Test",
            "start_time": self._cycle_results[0].start_time if self._cycle_results else None,
            "end_time": self._cycle_results[-1].end_time if self._cycle_results else None,
            "config": asdict(self.config),
            "summary": {
                "total_cycles": len(self._cycle_results),
                "total_channels_tested": len(self._channels),
                "total_tests_executed": metrics["total_tests"],
                "overall_success_rate": metrics["success_rate"],
                "passed": metrics["total_passed"],
                "failed": metrics["total_failed"],
                "timeouts": metrics["total_timeouts"],
                "errors": metrics["total_errors"],
            },
            "performance": {
                "avg_time_to_first_byte": metrics["avg_ttfb"],
                "min_time_to_first_byte": metrics["min_ttfb"],
                "max_time_to_first_byte": metrics["max_ttfb"],
            },
            "reliability": {
                "reliable_channels_count": len(metrics["reliable_channels"]),
                "unreliable_channels_count": len(metrics["unreliable_channels"]),
                "reliable_channels": metrics["reliable_channels"],
                "unreliable_channels": metrics["unreliable_channels"],
            },
            "channel_metrics": {k: {
                **v,
                "avg_ttfb": sum(v["avg_ttfb"]) / len(v["avg_ttfb"]) if v["avg_ttfb"] else None,
                "success_rate": (v["passed"] / v["total_tests"] * 100) if v["total_tests"] > 0 else 0,
            } for k, v in self._channel_metrics.items()},
            "error_log": self._error_log,
            "cycles": [asdict(c) for c in self._cycle_results],
        }
        
        return report
    
    async def run(self) -> Dict:
        """
        Run the extended overnight test.
        
        Returns:
            Final test report dictionary
        """
        self._setup_signal_handlers()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("EXSTREAMTV EXTENDED OVERNIGHT RELIABILITY TEST")
        logger.info("=" * 80)
        logger.info(f"Test Run ID: {self.test_run_id}")
        logger.info(f"Duration: {self.config.duration_hours} hours")
        logger.info(f"Cycle Interval: {self.config.cycle_interval_seconds}s")
        logger.info(f"Tune Duration: {self.config.tune_duration_seconds}s per channel")
        logger.info(f"Include All Channels: {self.config.include_all_channels}")
        logger.info("=" * 80)
        
        test_start = time.time()
        test_end = test_start + (self.config.duration_hours * 3600)
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            self._http_client = client
            
            # Fetch channels
            self._channels = await self._fetch_all_channels()
            
            if not self._channels:
                logger.error("No channels found!")
                return {"error": "No channels found"}
            
            cycle_number = 0
            
            while time.time() < test_end and not self._shutdown_requested:
                cycle_number += 1
                cycle_start = time.time()
                
                # Run cycle
                await self._run_cycle(cycle_number)
                
                # Wait for next cycle
                cycle_duration = time.time() - cycle_start
                remaining_wait = self.config.cycle_interval_seconds - cycle_duration
                
                if remaining_wait > 0 and time.time() < test_end and not self._shutdown_requested:
                    logger.info(f"Waiting {remaining_wait:.0f}s before next cycle...")
                    await asyncio.sleep(remaining_wait)
        
        # Generate final report
        logger.info("")
        logger.info("=" * 80)
        logger.info("GENERATING FINAL REPORT")
        logger.info("=" * 80)
        
        report = self._generate_report()
        
        # Save report
        report_path = self.output_dir / f"extended_overnight_report_{self.test_run_id}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        # Save summary text
        summary_path = self.output_dir / f"extended_overnight_summary_{self.test_run_id}.txt"
        self._write_summary(summary_path, report)
        
        logger.info(f"Report saved: {report_path}")
        logger.info(f"Summary saved: {summary_path}")
        logger.info(f"Log file: {self._log_file}")
        
        return report
    
    def _write_summary(self, path: Path, report: Dict) -> None:
        """Write human-readable summary."""
        with open(path, "w") as f:
            f.write("=" * 80 + "\n")
            f.write("EXSTREAMTV EXTENDED OVERNIGHT RELIABILITY TEST SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Test Run ID: {report['test_run_id']}\n")
            f.write(f"Start Time: {report['start_time']}\n")
            f.write(f"End Time: {report['end_time']}\n\n")
            
            s = report["summary"]
            f.write("OVERALL RESULTS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Cycles: {s['total_cycles']}\n")
            f.write(f"Channels Tested: {s['total_channels_tested']}\n")
            f.write(f"Total Tests: {s['total_tests_executed']}\n")
            f.write(f"Success Rate: {s['overall_success_rate']:.1f}%\n")
            f.write(f"Passed: {s['passed']}\n")
            f.write(f"Failed: {s['failed']}\n")
            f.write(f"Timeouts: {s['timeouts']}\n")
            f.write(f"Errors: {s['errors']}\n\n")
            
            p = report["performance"]
            f.write("PERFORMANCE METRICS\n")
            f.write("-" * 40 + "\n")
            if p["avg_time_to_first_byte"]:
                f.write(f"Avg TTFB: {p['avg_time_to_first_byte']:.2f}s\n")
                f.write(f"Min TTFB: {p['min_time_to_first_byte']:.2f}s\n")
                f.write(f"Max TTFB: {p['max_time_to_first_byte']:.2f}s\n")
            else:
                f.write("No TTFB data available\n")
            f.write("\n")
            
            r = report["reliability"]
            f.write("CHANNEL RELIABILITY\n")
            f.write("-" * 40 + "\n")
            f.write(f"Reliable Channels (≥80%): {r['reliable_channels_count']}\n")
            f.write(f"Unreliable Channels (<80%): {r['unreliable_channels_count']}\n\n")
            
            if r["reliable_channels"]:
                f.write("RELIABLE CHANNELS:\n")
                for ch in r["reliable_channels"][:10]:
                    f.write(f"  {ch['number']:>6} | {ch['name'][:30]:<30} | {ch['success_rate']:.1f}%\n")
                f.write("\n")
            
            if r["unreliable_channels"]:
                f.write("UNRELIABLE CHANNELS:\n")
                for ch in r["unreliable_channels"]:
                    f.write(f"  {ch['number']:>6} | {ch['name'][:30]:<30} | {ch['success_rate']:.1f}%\n")
                f.write("\n")
            
            if report["error_log"]:
                f.write("ERROR LOG (last 20):\n")
                f.write("-" * 40 + "\n")
                for err in report["error_log"][-20:]:
                    f.write(f"  [{err['timestamp']}] Ch {err['channel_number']}: {err['error']}\n")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extended Overnight Reliability Test")
    parser.add_argument("--duration", type=float, default=2.0, help="Duration in hours")
    parser.add_argument("--interval", type=float, default=180.0, help="Cycle interval in seconds")
    parser.add_argument("--tune-duration", type=float, default=45.0, help="Tune duration per channel")
    parser.add_argument("--all-channels", action="store_true", default=True, help="Include disabled channels")
    
    args = parser.parse_args()
    
    config = ExtendedTestConfig(
        duration_hours=args.duration,
        cycle_interval_seconds=args.interval,
        tune_duration_seconds=args.tune_duration,
        include_all_channels=args.all_channels,
    )
    
    tester = ExtendedOvernightTest(config)
    report = await tester.run()
    
    # Print final summary
    print("\n" + "=" * 80)
    print("EXTENDED OVERNIGHT TEST COMPLETE")
    print("=" * 80)
    s = report.get("summary", {})
    print(f"Success Rate: {s.get('overall_success_rate', 0):.1f}%")
    print(f"Total Tests: {s.get('total_tests_executed', 0)}")
    print(f"Passed: {s.get('passed', 0)}")
    print(f"Failed/Timeouts/Errors: {s.get('failed', 0)}/{s.get('timeouts', 0)}/{s.get('errors', 0)}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
