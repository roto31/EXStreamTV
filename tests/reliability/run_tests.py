#!/usr/bin/env python3
"""
EXStreamTV Reliability and Regression Test Runner

Main entry point for running all reliability and regression tests.

Usage:
    # Run overnight channel test (2 hours)
    python -m tests.reliability.run_tests overnight --duration 2
    
    # Run platform-wide regression test suite
    python -m tests.reliability.run_tests platform
    
    # Run basic regression test suite
    python -m tests.reliability.run_tests regression
    
    # Run sanity tests only
    python -m tests.reliability.run_tests sanity
    
    # Run single channel test
    python -m tests.reliability.run_tests channel 102
    
    # Run platform reliability monitoring
    python -m tests.reliability.run_tests monitor --duration 1
    
    # Run tests for specific subsystem
    python -m tests.reliability.run_tests subsystem --name api
    
    # Run StreamTV import tests
    python -m tests.reliability.run_tests streamtv-import --source-db /path/to/db
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.reliability.overnight_test import OvernightChannelTest, OvernightTestConfig
from tests.reliability.regression_suite import RegressionTestSuite, Priority
from tests.reliability.channel_reliability import ChannelReliabilityTest, ChannelTestConfig
from tests.reliability.metrics_collector import MetricsCollector
from tests.reliability.platform_regression_suite import PlatformRegressionSuite, Subsystem
from tests.reliability.platform_reliability import PlatformReliabilityMonitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def run_overnight_test(args: argparse.Namespace) -> int:
    """Run overnight reliability testing."""
    config = OvernightTestConfig(
        duration_hours=args.duration,
        cycle_interval_seconds=args.interval,
        tune_duration_seconds=args.tune_time,
        include_disabled_channels=args.include_disabled,
    )
    
    tester = OvernightChannelTest(config)
    result = await tester.run()
    
    # Return exit code based on success rate
    success_rate = result.get("success_rate", 0)
    if success_rate >= 95:
        return 0  # Excellent
    elif success_rate >= 80:
        return 1  # Acceptable with warnings
    else:
        return 2  # Failures detected


async def run_regression_tests(args: argparse.Namespace) -> int:
    """Run regression test suite."""
    async with RegressionTestSuite() as suite:
        if args.sanity_only:
            results = await suite.run_sanity_tests()
        else:
            results = await suite.run_all()
        
        # Generate report
        output_path = Path("tests/reliability/reports")
        output_path.mkdir(parents=True, exist_ok=True)
        report_file = output_path / f"regression_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        suite.generate_report(report_file)
        
        # Return exit code
        failed = sum(1 for r in results if not r.passed)
        return 0 if failed == 0 else 1


async def run_channel_test(args: argparse.Namespace) -> int:
    """Run test on specific channel(s)."""
    config = ChannelTestConfig(
        tune_timeout_seconds=args.timeout,
        stream_sample_seconds=args.sample_time,
    )
    
    metrics = MetricsCollector()
    
    async with ChannelReliabilityTest(config, metrics) as tester:
        if args.channel_number:
            # Test specific channel
            channels = await tester.get_all_channels()
            target = [c for c in channels if str(c.get("number")) == str(args.channel_number)]
            
            if not target:
                logger.error(f"Channel {args.channel_number} not found")
                return 1
            
            results = await tester.test_single_channel(target[0])
        else:
            # Test all enabled channels
            results = await tester.test_all_channels()
        
        # Print summary
        report = metrics.finalize()
        metrics.print_summary()
        
        return 0 if report.overall_success_rate >= 80 else 1


async def run_streamtv_import_test(args: argparse.Namespace) -> int:
    """Test StreamTV import functionality."""
    from tests.reliability.streamtv_import_test import StreamTVImportTest
    
    source_path = Path(args.source_db) if args.source_db else None
    
    tester = StreamTVImportTest(source_db_path=source_path)
    result = await tester.run_full_test()
    tester.print_report()
    
    return 0 if not result.issues else 1


async def run_platform_regression(args: argparse.Namespace) -> int:
    """Run platform-wide regression tests."""
    async with PlatformRegressionSuite() as suite:
        if args.subsystem:
            subsystem = Subsystem(args.subsystem)
            results = await suite.run_by_subsystem(subsystem)
        elif args.sanity_only:
            results = await suite.run_sanity_tests()
        else:
            results = await suite.run_all()
        
        # Generate reports
        output_path = Path("tests/reliability/reports")
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = output_path / f"platform_regression_{timestamp}.txt"
        json_file = output_path / f"platform_regression_{timestamp}.json"
        
        suite.generate_report(report_file)
        suite.save_json_report(json_file)
        
        # Return exit code
        failed = sum(1 for r in results if not r.passed)
        return 0 if failed == 0 else 1


async def run_platform_monitor(args: argparse.Namespace) -> int:
    """Run platform reliability monitoring."""
    async with PlatformReliabilityMonitor(
        check_interval_seconds=args.interval,
    ) as monitor:
        summary = await monitor.run_continuous(duration_hours=args.duration)
        
        # Generate reports
        output_path = Path("tests/reliability/reports")
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = output_path / f"platform_reliability_{timestamp}.json"
        
        monitor.print_report()
        monitor.save_report(report_file)
        
        # Return based on availability
        return 0 if summary['availability_pct'] >= 80 else 1


async def run_subsystem_tests(args: argparse.Namespace) -> int:
    """Run tests for a specific subsystem."""
    try:
        subsystem = Subsystem(args.name)
    except ValueError:
        logger.error(f"Unknown subsystem: {args.name}")
        logger.info(f"Available subsystems: {[s.value for s in Subsystem]}")
        return 1
    
    async with PlatformRegressionSuite() as suite:
        results = await suite.run_by_subsystem(subsystem)
        
        # Generate report
        output_path = Path("tests/reliability/reports")
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = output_path / f"subsystem_{args.name}_{timestamp}.txt"
        
        suite.generate_report(report_file)
        
        failed = sum(1 for r in results if not r.passed)
        return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="EXStreamTV Reliability and Regression Test Runner"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Test type to run")
    
    # Platform-wide regression test command
    platform_parser = subparsers.add_parser(
        "platform",
        help="Run platform-wide regression tests (all subsystems)",
    )
    platform_parser.add_argument(
        "--sanity-only",
        action="store_true",
        help="Run only sanity (Priority 1) tests",
    )
    platform_parser.add_argument(
        "--subsystem",
        help="Run tests for specific subsystem only",
    )
    
    # Platform reliability monitoring
    monitor_parser = subparsers.add_parser(
        "monitor",
        help="Run continuous platform reliability monitoring",
    )
    monitor_parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Monitoring duration in hours (default: 1)",
    )
    monitor_parser.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="Seconds between health checks (default: 60)",
    )
    
    # Subsystem-specific tests
    subsystem_parser = subparsers.add_parser(
        "subsystem",
        help="Run tests for a specific subsystem",
    )
    subsystem_parser.add_argument(
        "--name",
        required=True,
        help="Subsystem name (core, api, database, streaming, media, ai_agent, tasks, ffmpeg, integration, webui)",
    )
    
    # Overnight test command
    overnight_parser = subparsers.add_parser(
        "overnight",
        help="Run overnight channel reliability test",
    )
    overnight_parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Test duration in hours (default: 2)",
    )
    overnight_parser.add_argument(
        "--interval",
        type=float,
        default=120.0,
        help="Seconds between test cycles (default: 120)",
    )
    overnight_parser.add_argument(
        "--tune-time",
        type=float,
        default=15.0,
        help="Seconds to tune each channel (default: 15)",
    )
    overnight_parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include disabled channels",
    )
    
    # Regression test command (basic)
    regression_parser = subparsers.add_parser(
        "regression",
        help="Run basic regression test suite",
    )
    regression_parser.add_argument(
        "--sanity-only",
        action="store_true",
        help="Run only sanity (Priority 1) tests",
    )
    
    # Sanity test command (alias)
    sanity_parser = subparsers.add_parser(
        "sanity",
        help="Run sanity tests only",
    )
    
    # Channel test command
    channel_parser = subparsers.add_parser(
        "channel",
        help="Test specific channel(s)",
    )
    channel_parser.add_argument(
        "channel_number",
        nargs="?",
        help="Channel number to test (tests all if not specified)",
    )
    channel_parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Tune timeout in seconds (default: 30)",
    )
    channel_parser.add_argument(
        "--sample-time",
        type=float,
        default=10.0,
        help="Stream sample time in seconds (default: 10)",
    )
    
    # StreamTV import test command
    streamtv_parser = subparsers.add_parser(
        "streamtv-import",
        help="Test StreamTV import functionality",
    )
    streamtv_parser.add_argument(
        "--source-db",
        help="Path to StreamTV database file",
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Run appropriate test
    if args.command == "platform":
        return asyncio.run(run_platform_regression(args))
    elif args.command == "monitor":
        return asyncio.run(run_platform_monitor(args))
    elif args.command == "subsystem":
        return asyncio.run(run_subsystem_tests(args))
    elif args.command == "overnight":
        return asyncio.run(run_overnight_test(args))
    elif args.command == "regression":
        return asyncio.run(run_regression_tests(args))
    elif args.command == "sanity":
        args.sanity_only = True
        return asyncio.run(run_regression_tests(args))
    elif args.command == "channel":
        return asyncio.run(run_channel_test(args))
    elif args.command == "streamtv-import":
        return asyncio.run(run_streamtv_import_test(args))
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
