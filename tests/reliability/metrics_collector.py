"""
Reliability Metrics Collector

Tracks and calculates key reliability metrics:
- MTBF (Mean Time Between Failures)
- MTTR (Mean Time To Repair)
- Failure Rate
- Availability
- Task Success Rate

Based on reliability testing standards from IBM and Microsoft.
"""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class TestResult:
    """Individual test result."""
    test_name: str
    channel_number: str
    status: TestStatus
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    recovery_time_seconds: Optional[float] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_name": self.test_name,
            "channel_number": self.channel_number,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "recovery_time_seconds": self.recovery_time_seconds,
            "metadata": self.metadata,
        }


@dataclass
class ChannelMetrics:
    """Metrics for a single channel."""
    channel_number: str
    channel_name: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    timeouts: int = 0
    total_uptime_seconds: float = 0.0
    total_downtime_seconds: float = 0.0
    failures: list = field(default_factory=list)
    recovery_times: list = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return ((self.failed + self.errors + self.timeouts) / self.total_tests) * 100
    
    @property
    def availability(self) -> float:
        """Calculate availability as percentage."""
        total_time = self.total_uptime_seconds + self.total_downtime_seconds
        if total_time == 0:
            return 100.0
        return (self.total_uptime_seconds / total_time) * 100
    
    @property
    def mtbf(self) -> Optional[float]:
        """Mean Time Between Failures in seconds."""
        failure_count = self.failed + self.errors + self.timeouts
        if failure_count == 0:
            return None  # No failures
        return self.total_uptime_seconds / failure_count
    
    @property
    def mttr(self) -> Optional[float]:
        """Mean Time To Repair in seconds."""
        if not self.recovery_times:
            return None
        return sum(self.recovery_times) / len(self.recovery_times)


@dataclass
class ReliabilityReport:
    """Overall reliability report."""
    test_run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_channels_tested: int = 0
    total_tests_executed: int = 0
    total_passed: int = 0
    total_failed: int = 0
    total_errors: int = 0
    total_timeouts: int = 0
    channel_metrics: dict = field(default_factory=dict)
    test_results: list = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        """Test run duration in seconds."""
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def overall_success_rate(self) -> float:
        """Overall success rate as percentage."""
        if self.total_tests_executed == 0:
            return 0.0
        return (self.total_passed / self.total_tests_executed) * 100
    
    @property
    def overall_mtbf(self) -> Optional[float]:
        """Overall Mean Time Between Failures."""
        total_uptime = sum(
            m.total_uptime_seconds for m in self.channel_metrics.values()
        )
        total_failures = self.total_failed + self.total_errors + self.total_timeouts
        if total_failures == 0:
            return None
        return total_uptime / total_failures
    
    @property
    def overall_mttr(self) -> Optional[float]:
        """Overall Mean Time To Repair."""
        all_recovery_times = []
        for m in self.channel_metrics.values():
            all_recovery_times.extend(m.recovery_times)
        if not all_recovery_times:
            return None
        return sum(all_recovery_times) / len(all_recovery_times)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "test_run_id": self.test_run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "total_channels_tested": self.total_channels_tested,
            "total_tests_executed": self.total_tests_executed,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "total_errors": self.total_errors,
            "total_timeouts": self.total_timeouts,
            "overall_success_rate": self.overall_success_rate,
            "overall_mtbf": self.overall_mtbf,
            "overall_mttr": self.overall_mttr,
            "channel_metrics": {
                k: asdict(v) for k, v in self.channel_metrics.items()
            },
            "test_results": [r.to_dict() for r in self.test_results],
        }


class MetricsCollector:
    """
    Collects and calculates reliability metrics during test runs.
    
    Key metrics tracked (per IBM/Microsoft standards):
    - MTBF: Mean Time Between Failures
    - MTTR: Mean Time To Repair
    - Failure Rate: Frequency of failures over time
    - Availability: Uptime percentage
    - Task Success Rate: Percentage of successful operations
    """
    
    def __init__(
        self,
        test_run_id: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ):
        """
        Initialize the metrics collector.
        
        Args:
            test_run_id: Unique identifier for this test run
            output_dir: Directory to save reports
        """
        self.test_run_id = test_run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = output_dir or Path("tests/reliability/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.report = ReliabilityReport(
            test_run_id=self.test_run_id,
            start_time=datetime.now(),
        )
        
        self._current_test_start: dict[str, datetime] = {}
    
    def start_test(self, channel_number: str, test_name: str) -> None:
        """Mark the start of a test."""
        key = f"{channel_number}:{test_name}"
        self._current_test_start[key] = datetime.now()
    
    def record_result(
        self,
        channel_number: str,
        channel_name: str,
        test_name: str,
        status: TestStatus,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        recovery_time: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> TestResult:
        """
        Record a test result.
        
        Args:
            channel_number: Channel being tested
            channel_name: Name of the channel
            test_name: Name of the test
            status: Test result status
            error_message: Error message if failed
            error_type: Type of error
            recovery_time: Time to recover from failure
            metadata: Additional metadata
            
        Returns:
            TestResult object
        """
        key = f"{channel_number}:{test_name}"
        start_time = self._current_test_start.pop(key, datetime.now())
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        result = TestResult(
            test_name=test_name,
            channel_number=channel_number,
            status=status,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            error_message=error_message,
            error_type=error_type,
            recovery_time_seconds=recovery_time,
            metadata=metadata or {},
        )
        
        self.report.test_results.append(result)
        self.report.total_tests_executed += 1
        
        # Update overall counts
        if status == TestStatus.PASSED:
            self.report.total_passed += 1
        elif status == TestStatus.FAILED:
            self.report.total_failed += 1
        elif status == TestStatus.ERROR:
            self.report.total_errors += 1
        elif status == TestStatus.TIMEOUT:
            self.report.total_timeouts += 1
        
        # Update channel-specific metrics
        if channel_number not in self.report.channel_metrics:
            self.report.channel_metrics[channel_number] = ChannelMetrics(
                channel_number=channel_number,
                channel_name=channel_name,
            )
            self.report.total_channels_tested += 1
        
        metrics = self.report.channel_metrics[channel_number]
        metrics.total_tests += 1
        
        if status == TestStatus.PASSED:
            metrics.passed += 1
            metrics.total_uptime_seconds += duration
        elif status == TestStatus.FAILED:
            metrics.failed += 1
            metrics.total_downtime_seconds += duration
            metrics.failures.append({
                "time": end_time.isoformat(),
                "error": error_message,
                "type": error_type,
            })
        elif status == TestStatus.ERROR:
            metrics.errors += 1
            metrics.total_downtime_seconds += duration
        elif status == TestStatus.TIMEOUT:
            metrics.timeouts += 1
            metrics.total_downtime_seconds += duration
        
        if recovery_time:
            metrics.recovery_times.append(recovery_time)
        
        return result
    
    def finalize(self) -> ReliabilityReport:
        """Finalize the report and save to disk."""
        self.report.end_time = datetime.now()
        
        # Save report as JSON
        report_path = self.output_dir / f"reliability_report_{self.test_run_id}.json"
        with open(report_path, "w") as f:
            json.dump(self.report.to_dict(), f, indent=2)
        
        logger.info(f"Reliability report saved to {report_path}")
        
        return self.report
    
    def print_summary(self) -> str:
        """Print a human-readable summary."""
        lines = [
            "=" * 80,
            "EXSTREAMTV RELIABILITY TEST REPORT",
            "=" * 80,
            f"Test Run ID: {self.report.test_run_id}",
            f"Duration: {self.report.duration_seconds:.1f} seconds",
            f"Start: {self.report.start_time.isoformat()}",
            f"End: {self.report.end_time.isoformat() if self.report.end_time else 'In progress'}",
            "",
            "OVERALL METRICS:",
            "-" * 40,
            f"Total Channels Tested: {self.report.total_channels_tested}",
            f"Total Tests Executed: {self.report.total_tests_executed}",
            f"Passed: {self.report.total_passed}",
            f"Failed: {self.report.total_failed}",
            f"Errors: {self.report.total_errors}",
            f"Timeouts: {self.report.total_timeouts}",
            f"Success Rate: {self.report.overall_success_rate:.2f}%",
        ]
        
        if self.report.overall_mtbf:
            lines.append(f"Overall MTBF: {self.report.overall_mtbf:.1f} seconds")
        if self.report.overall_mttr:
            lines.append(f"Overall MTTR: {self.report.overall_mttr:.1f} seconds")
        
        lines.extend([
            "",
            "CHANNEL-LEVEL METRICS:",
            "-" * 80,
            f"{'Channel':<10} {'Name':<30} {'Tests':<8} {'Pass%':<8} {'MTBF':<12} {'Avail%':<8}",
            "-" * 80,
        ])
        
        for ch_num, metrics in sorted(
            self.report.channel_metrics.items(),
            key=lambda x: float(x[0]) if x[0].replace('.', '').isdigit() else 0
        ):
            mtbf_str = f"{metrics.mtbf:.0f}s" if metrics.mtbf else "N/A"
            lines.append(
                f"{ch_num:<10} {metrics.channel_name[:30]:<30} "
                f"{metrics.total_tests:<8} {metrics.success_rate:.1f}%   "
                f"{mtbf_str:<12} {metrics.availability:.1f}%"
            )
        
        # List failures
        failed_channels = [
            (ch_num, m) for ch_num, m in self.report.channel_metrics.items()
            if m.failed > 0 or m.errors > 0 or m.timeouts > 0
        ]
        
        if failed_channels:
            lines.extend([
                "",
                "FAILURES DETECTED:",
                "-" * 80,
            ])
            for ch_num, metrics in failed_channels:
                lines.append(f"Channel {ch_num} ({metrics.channel_name}):")
                for failure in metrics.failures:
                    lines.append(f"  - {failure['time']}: {failure['error']}")
        
        lines.append("=" * 80)
        
        summary = "\n".join(lines)
        print(summary)
        
        # Also save summary to file
        summary_path = self.output_dir / f"reliability_summary_{self.test_run_id}.txt"
        with open(summary_path, "w") as f:
            f.write(summary)
        
        return summary
