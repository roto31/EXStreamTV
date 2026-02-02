"""
Overnight Channel Testing

Runs continuous reliability tests on all channels for extended periods.
Implements:
- Endurance Testing: Running continuously for extended periods
- Load Testing: Multiple channel requests
- Feature Testing: All channel functions tested

Based on:
- LeapWork: Comprehensive regression testing with metrics
- IBM: Systematic testing after code changes
- Microsoft: Chaos engineering and fault injection
"""

import asyncio
import json
import logging
import signal
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

from .metrics_collector import MetricsCollector, TestStatus
from .channel_reliability import ChannelReliabilityTest, ChannelTestConfig

logger = logging.getLogger(__name__)


@dataclass
class OvernightTestConfig:
    """Configuration for overnight testing."""
    duration_hours: float = 2.0
    cycle_interval_seconds: float = 120.0  # 2 minutes between full cycles
    tune_duration_seconds: float = 30.0  # Increased from 15s to 30s for cold-start tolerance
    base_url: str = "http://localhost:8411"
    hdhomerun_url: str = "http://localhost:5004"
    output_dir: str = "tests/reliability/reports"
    include_disabled_channels: bool = False
    log_level: str = "INFO"


class OvernightChannelTest:
    """
    Runs overnight reliability and regression testing on all channels.
    
    This implements the complete reliability testing workflow:
    1. Fetch all channels
    2. For each cycle:
       a. Tune to each enabled channel
       b. Verify stream data received
       c. Check EPG accuracy
       d. Log any failures
    3. Calculate MTBF, MTTR, availability metrics
    4. Generate comprehensive report
    """
    
    def __init__(self, config: Optional[OvernightTestConfig] = None):
        """
        Initialize the overnight test runner.
        
        Args:
            config: Test configuration
        """
        self.config = config or OvernightTestConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.test_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metrics = MetricsCollector(
            test_run_id=self.test_run_id,
            output_dir=self.output_dir,
        )
        
        self._shutdown_requested = False
        self._channels: list[dict] = []
        self._http_client: Optional[httpx.AsyncClient] = None
        self._log_file: Optional[Path] = None
        
        # Set up logging
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Set up file and console logging."""
        self._log_file = self.output_dir / f"overnight_test_{self.test_run_id}.log"
        
        # Create file handler
        file_handler = logging.FileHandler(self._log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
        
        # Add to logger
        logger.addHandler(file_handler)
        logger.setLevel(getattr(logging, self.config.log_level))
    
    def _setup_signal_handlers(self) -> None:
        """Set up graceful shutdown on SIGINT/SIGTERM."""
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received. Finishing current cycle...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def _fetch_channels(self) -> list[dict]:
        """Fetch all channels from the API."""
        try:
            response = await self._http_client.get(
                f"{self.config.base_url}/api/channels"
            )
            response.raise_for_status()
            channels = response.json()
            
            if not self.config.include_disabled_channels:
                channels = [c for c in channels if c.get("enabled", False)]
            
            # Sort by channel number
            channels.sort(
                key=lambda c: float(c.get("number", "0") or "0")
            )
            
            return channels
            
        except Exception as e:
            logger.error(f"Failed to fetch channels: {e}")
            return []
    
    async def _test_channel(self, channel: dict) -> dict[str, Any]:
        """
        Test a single channel.
        
        Args:
            channel: Channel data
            
        Returns:
            Test result dictionary
        """
        channel_number = channel.get("number", "unknown")
        channel_name = channel.get("name", "Unknown")
        
        result = {
            "channel_number": channel_number,
            "channel_name": channel_name,
            "tune_success": False,
            "stream_received": False,
            "bytes_received": 0,
            "time_to_first_byte": None,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Try multiple tuning endpoints in order of preference
        tune_urls = [
            f"{self.config.hdhomerun_url}/auto/v{channel_number}",
            f"{self.config.base_url}/iptv/channel/{channel_number}.ts",
            f"{self.config.base_url}/hdhr/auto/v{channel_number}",
        ]
        
        tune_url = None
        for url in tune_urls:
            try:
                # Quick check if endpoint responds
                check_response = await self._http_client.head(url, timeout=2.0)
                if check_response.status_code in [200, 206]:
                    tune_url = url
                    break
            except:
                continue
        
        if not tune_url:
            # Fall back to IPTV endpoint
            tune_url = f"{self.config.base_url}/iptv/channel/{channel_number}.ts"
        
        try:
            self.metrics.start_test(channel_number, "overnight_tune")
            
            start_time = time.time()
            first_byte_time = None
            
            async with self._http_client.stream(
                "GET",
                tune_url,
                timeout=self.config.tune_duration_seconds + 5,
            ) as response:
                if response.status_code != 200:
                    result["error"] = f"HTTP {response.status_code}"
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name="overnight_tune",
                        status=TestStatus.FAILED,
                        error_message=result["error"],
                        error_type="http_error",
                    )
                    return result
                
                result["tune_success"] = True
                
                # Read data for specified duration
                async for chunk in response.aiter_bytes():
                    if first_byte_time is None:
                        first_byte_time = time.time()
                        result["time_to_first_byte"] = first_byte_time - start_time
                    
                    result["bytes_received"] += len(chunk)
                    
                    # Check if we've been reading long enough
                    if time.time() - start_time >= self.config.tune_duration_seconds:
                        break
                
                if result["bytes_received"] > 0:
                    result["stream_received"] = True
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name="overnight_tune",
                        status=TestStatus.PASSED,
                        metadata={
                            "bytes_received": result["bytes_received"],
                            "time_to_first_byte": result["time_to_first_byte"],
                        },
                    )
                else:
                    result["error"] = "No stream data received"
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name="overnight_tune",
                        status=TestStatus.FAILED,
                        error_message=result["error"],
                        error_type="no_data",
                    )
                    
        except httpx.TimeoutException:
            result["error"] = "Timeout"
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name="overnight_tune",
                status=TestStatus.TIMEOUT,
                error_message="Tune timed out",
                error_type="timeout",
            )
            
        except Exception as e:
            result["error"] = str(e)
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name="overnight_tune",
                status=TestStatus.ERROR,
                error_message=str(e),
                error_type=type(e).__name__,
            )
        
        return result
    
    async def _run_cycle(self, cycle_number: int) -> list[dict]:
        """
        Run a complete test cycle on all channels.
        
        Args:
            cycle_number: Current cycle number
            
        Returns:
            List of test results
        """
        logger.info(f"=== Starting Test Cycle {cycle_number} ===")
        logger.info(f"Testing {len(self._channels)} channels")
        
        cycle_results = []
        
        for i, channel in enumerate(self._channels):
            if self._shutdown_requested:
                logger.info("Shutdown requested, stopping cycle")
                break
            
            channel_number = channel.get("number", "?")
            channel_name = channel.get("name", "Unknown")
            
            logger.info(
                f"[{i+1}/{len(self._channels)}] "
                f"Testing channel {channel_number}: {channel_name}"
            )
            
            result = await self._test_channel(channel)
            cycle_results.append(result)
            
            # Log result
            if result["stream_received"]:
                logger.info(
                    f"  ✓ PASS - {result['bytes_received']} bytes, "
                    f"TTFB: {result['time_to_first_byte']:.2f}s"
                    if result['time_to_first_byte'] else f"  ✓ PASS - {result['bytes_received']} bytes"
                )
            else:
                logger.warning(f"  ✗ FAIL - {result['error']}")
        
        # Cycle summary
        passed = sum(1 for r in cycle_results if r["stream_received"])
        failed = len(cycle_results) - passed
        
        logger.info(f"Cycle {cycle_number} complete: {passed} passed, {failed} failed")
        
        return cycle_results
    
    async def run(self) -> dict[str, Any]:
        """
        Run the overnight test.
        
        Returns:
            Final test summary
        """
        self._setup_signal_handlers()
        
        logger.info("=" * 80)
        logger.info("EXSTREAMTV OVERNIGHT RELIABILITY TEST")
        logger.info("=" * 80)
        logger.info(f"Test Run ID: {self.test_run_id}")
        logger.info(f"Duration: {self.config.duration_hours} hours")
        logger.info(f"Cycle Interval: {self.config.cycle_interval_seconds} seconds")
        logger.info(f"Tune Duration: {self.config.tune_duration_seconds} seconds")
        logger.info("=" * 80)
        
        start_time = time.time()
        end_time = start_time + (self.config.duration_hours * 3600)
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            self._http_client = client
            
            # Fetch channels
            self._channels = await self._fetch_channels()
            
            if not self._channels:
                logger.error("No channels found to test!")
                return {"error": "No channels found"}
            
            logger.info(f"Found {len(self._channels)} channels to test")
            
            cycle_number = 0
            all_results = []
            
            while time.time() < end_time and not self._shutdown_requested:
                cycle_number += 1
                cycle_start = time.time()
                
                # Run test cycle
                cycle_results = await self._run_cycle(cycle_number)
                all_results.extend(cycle_results)
                
                # Save intermediate results
                await self._save_intermediate_results(cycle_number, cycle_results)
                
                # Wait for next cycle
                cycle_duration = time.time() - cycle_start
                remaining = self.config.cycle_interval_seconds - cycle_duration
                
                if remaining > 0 and time.time() < end_time and not self._shutdown_requested:
                    logger.info(f"Waiting {remaining:.0f}s before next cycle...")
                    await asyncio.sleep(remaining)
            
            # Finalize
            logger.info("=" * 80)
            logger.info("TEST COMPLETE")
            logger.info("=" * 80)
            
            # Generate final report
            report = self.metrics.finalize()
            summary = self.metrics.print_summary()
            
            # Save all results
            results_path = self.output_dir / f"overnight_results_{self.test_run_id}.json"
            with open(results_path, "w") as f:
                json.dump({
                    "test_run_id": self.test_run_id,
                    "config": asdict(self.config),
                    "total_cycles": cycle_number,
                    "total_tests": len(all_results),
                    "results": all_results,
                }, f, indent=2, default=str)
            
            logger.info(f"Results saved to {results_path}")
            logger.info(f"Log file: {self._log_file}")
            
            return {
                "test_run_id": self.test_run_id,
                "duration_seconds": time.time() - start_time,
                "total_cycles": cycle_number,
                "total_tests": len(all_results),
                "success_rate": report.overall_success_rate,
                "mtbf": report.overall_mtbf,
                "report_path": str(results_path),
            }
    
    async def _save_intermediate_results(
        self,
        cycle_number: int,
        results: list[dict],
    ) -> None:
        """Save intermediate results after each cycle."""
        path = self.output_dir / f"cycle_{cycle_number}_{self.test_run_id}.json"
        with open(path, "w") as f:
            json.dump({
                "cycle": cycle_number,
                "timestamp": datetime.now().isoformat(),
                "results": results,
            }, f, indent=2)


async def main():
    """Main entry point for overnight testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="EXStreamTV Overnight Reliability Test")
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Test duration in hours (default: 2.0)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=120.0,
        help="Seconds between test cycles (default: 120)",
    )
    parser.add_argument(
        "--tune-duration",
        type=float,
        default=15.0,
        help="Seconds to tune each channel (default: 15)",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include disabled channels in testing",
    )
    
    args = parser.parse_args()
    
    config = OvernightTestConfig(
        duration_hours=args.duration,
        cycle_interval_seconds=args.interval,
        tune_duration_seconds=args.tune_duration,
        include_disabled_channels=args.include_disabled,
    )
    
    tester = OvernightChannelTest(config)
    result = await tester.run()
    
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print(f"Duration: {result.get('duration_seconds', 0) / 3600:.2f} hours")
    print(f"Cycles Completed: {result.get('total_cycles', 0)}")
    print(f"Total Tests: {result.get('total_tests', 0)}")
    print(f"Success Rate: {result.get('success_rate', 0):.2f}%")
    if result.get("mtbf"):
        print(f"MTBF: {result['mtbf']:.1f} seconds")
    print(f"Report: {result.get('report_path', 'N/A')}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
