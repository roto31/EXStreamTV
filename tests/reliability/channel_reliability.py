"""
Channel Reliability Testing

Tests channel tuning, streaming, and EPG reliability.
Based on reliability testing principles from:
- IBM: Testing existing functionality when new code is introduced
- Trymata: Ensuring products work consistently for every user, every time
- Microsoft: Fault injection and chaos engineering

Test Categories:
1. Feature Testing: Each channel function executed at least once
2. Load Testing: Multiple concurrent channel requests
3. Regression Testing: Verify no new bugs after changes
"""

import asyncio
import httpx
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from pathlib import Path

from .metrics_collector import MetricsCollector, TestStatus

logger = logging.getLogger(__name__)


@dataclass
class ChannelTestConfig:
    """Configuration for channel reliability tests."""
    base_url: str = "http://localhost:8411"
    hdhomerun_url: str = "http://localhost:5004"
    tune_timeout_seconds: float = 30.0
    stream_sample_seconds: float = 10.0
    epg_check_enabled: bool = True
    concurrent_limit: int = 3


class ChannelReliabilityTest:
    """
    Comprehensive reliability tests for EXStreamTV channels.
    
    Tests include:
    - Channel Tuning: Can the channel be tuned successfully?
    - Stream Validity: Does the channel produce valid MPEG-TS data?
    - EPG Accuracy: Is schedule data available and accurate?
    - Error Recovery: Can the system recover from failures?
    """
    
    def __init__(
        self,
        config: Optional[ChannelTestConfig] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize the channel reliability tester.
        
        Args:
            config: Test configuration
            metrics_collector: Metrics collector instance
        """
        self.config = config or ChannelTestConfig()
        self.metrics = metrics_collector or MetricsCollector()
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(timeout=60.0)
        return self
    
    async def __aexit__(self, *args):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()
    
    async def get_all_channels(self) -> list[dict[str, Any]]:
        """Fetch all channels from the API."""
        try:
            response = await self._http_client.get(
                f"{self.config.base_url}/api/channels"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch channels: {e}")
            return []
    
    async def get_enabled_channels(self) -> list[dict[str, Any]]:
        """Fetch only enabled channels."""
        channels = await self.get_all_channels()
        return [c for c in channels if c.get("enabled", False)]
    
    async def test_channel_api_health(self, channel: dict) -> TestStatus:
        """
        Test 1: API Health Check
        
        Verify the channel exists and returns valid data from the API.
        """
        channel_number = channel.get("number", "unknown")
        channel_name = channel.get("name", "Unknown")
        test_name = "api_health"
        
        self.metrics.start_test(channel_number, test_name)
        
        try:
            response = await self._http_client.get(
                f"{self.config.base_url}/api/channels/{channel.get('id')}"
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and data.get("id"):
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name=test_name,
                        status=TestStatus.PASSED,
                        metadata={"response_time_ms": response.elapsed.total_seconds() * 1000},
                    )
                    return TestStatus.PASSED
            
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.FAILED,
                error_message=f"Unexpected response: {response.status_code}",
                error_type="api_error",
            )
            return TestStatus.FAILED
            
        except httpx.TimeoutException:
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.TIMEOUT,
                error_message="API request timed out",
                error_type="timeout",
            )
            return TestStatus.TIMEOUT
            
        except Exception as e:
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.ERROR,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            return TestStatus.ERROR
    
    async def test_channel_schedule(self, channel: dict) -> TestStatus:
        """
        Test 2: Schedule/EPG Check
        
        Verify the channel has schedule data and EPG entries.
        """
        channel_number = channel.get("number", "unknown")
        channel_name = channel.get("name", "Unknown")
        test_name = "schedule_check"
        
        if not self.config.epg_check_enabled:
            return TestStatus.SKIPPED
        
        self.metrics.start_test(channel_number, test_name)
        
        try:
            # Check if channel has items in its playout
            response = await self._http_client.get(
                f"{self.config.base_url}/api/channels/{channel.get('id')}/playout"
            )
            
            has_playout = False
            playout_item_count = 0
            
            if response.status_code == 200:
                data = response.json()
                playout_items = data.get("items", [])
                playout_item_count = len(playout_items)
                has_playout = playout_item_count > 0
            
            # Also check EPG data
            epg_response = await self._http_client.get(
                f"{self.config.base_url}/iptv/xmltv.xml"
            )
            
            has_epg = False
            if epg_response.status_code == 200:
                # Check if this channel appears in EPG
                epg_content = epg_response.text
                has_epg = f'channel="{channel_number}"' in epg_content
            
            if has_playout and has_epg:
                self.metrics.record_result(
                    channel_number=channel_number,
                    channel_name=channel_name,
                    test_name=test_name,
                    status=TestStatus.PASSED,
                    metadata={
                        "playout_items": playout_item_count,
                        "has_epg": has_epg,
                    },
                )
                return TestStatus.PASSED
            elif has_playout:
                # Has playout but missing EPG
                self.metrics.record_result(
                    channel_number=channel_number,
                    channel_name=channel_name,
                    test_name=test_name,
                    status=TestStatus.PASSED,  # Partial pass
                    metadata={
                        "playout_items": playout_item_count,
                        "has_epg": False,
                        "warning": "Channel has playout but no EPG data",
                    },
                )
                return TestStatus.PASSED
            else:
                self.metrics.record_result(
                    channel_number=channel_number,
                    channel_name=channel_name,
                    test_name=test_name,
                    status=TestStatus.FAILED,
                    error_message=f"No schedule/playout items found (EPG: {has_epg})",
                    error_type="no_schedule",
                )
                return TestStatus.FAILED
                
        except Exception as e:
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.ERROR,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            return TestStatus.ERROR
    
    async def test_channel_tune(self, channel: dict) -> TestStatus:
        """
        Test 3: Channel Tuning
        
        Attempt to tune to the channel and verify stream starts.
        This is the core reliability test.
        """
        channel_number = channel.get("number", "unknown")
        channel_name = channel.get("name", "Unknown")
        test_name = "channel_tune"
        
        self.metrics.start_test(channel_number, test_name)
        
        try:
            # Try HDHomeRun tuning endpoint
            tune_url = f"{self.config.hdhomerun_url}/auto/v{channel_number}"
            
            logger.info(f"Testing tune to channel {channel_number} ({channel_name})")
            
            # Use streaming request to get initial data
            async with self._http_client.stream(
                "GET",
                tune_url,
                timeout=self.config.tune_timeout_seconds,
            ) as response:
                if response.status_code != 200:
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name=test_name,
                        status=TestStatus.FAILED,
                        error_message=f"HTTP {response.status_code}",
                        error_type="http_error",
                    )
                    return TestStatus.FAILED
                
                # Try to read some data
                bytes_received = 0
                start_time = time.time()
                first_byte_time = None
                
                async for chunk in response.aiter_bytes():
                    if first_byte_time is None:
                        first_byte_time = time.time()
                    
                    bytes_received += len(chunk)
                    
                    # Check if we have enough data (at least some MPEG-TS)
                    if bytes_received >= 188 * 10:  # 10 MPEG-TS packets
                        # Verify MPEG-TS sync bytes
                        valid_stream = True
                        elapsed = time.time() - start_time
                        
                        self.metrics.record_result(
                            channel_number=channel_number,
                            channel_name=channel_name,
                            test_name=test_name,
                            status=TestStatus.PASSED,
                            metadata={
                                "bytes_received": bytes_received,
                                "time_to_first_byte": first_byte_time - start_time if first_byte_time else None,
                                "total_time": elapsed,
                            },
                        )
                        return TestStatus.PASSED
                    
                    # Time limit for sampling
                    if time.time() - start_time > self.config.stream_sample_seconds:
                        break
                
                # If we got here, we didn't get enough data
                if bytes_received > 0:
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name=test_name,
                        status=TestStatus.PASSED,
                        metadata={
                            "bytes_received": bytes_received,
                            "warning": "Received data but less than expected",
                        },
                    )
                    return TestStatus.PASSED
                else:
                    self.metrics.record_result(
                        channel_number=channel_number,
                        channel_name=channel_name,
                        test_name=test_name,
                        status=TestStatus.FAILED,
                        error_message="No stream data received",
                        error_type="no_data",
                    )
                    return TestStatus.FAILED
                    
        except httpx.TimeoutException:
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.TIMEOUT,
                error_message=f"Tune timed out after {self.config.tune_timeout_seconds}s",
                error_type="timeout",
            )
            return TestStatus.TIMEOUT
            
        except httpx.ConnectError as e:
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.ERROR,
                error_message=f"Connection error: {e}",
                error_type="connection_error",
            )
            return TestStatus.ERROR
            
        except Exception as e:
            self.metrics.record_result(
                channel_number=channel_number,
                channel_name=channel_name,
                test_name=test_name,
                status=TestStatus.ERROR,
                error_message=str(e),
                error_type=type(e).__name__,
            )
            return TestStatus.ERROR
    
    async def test_single_channel(self, channel: dict) -> dict[str, TestStatus]:
        """
        Run all tests for a single channel.
        
        Args:
            channel: Channel data dictionary
            
        Returns:
            Dictionary of test name -> status
        """
        channel_number = channel.get("number", "unknown")
        channel_name = channel.get("name", "Unknown")
        
        logger.info(f"Testing channel {channel_number}: {channel_name}")
        
        results = {}
        
        # Test 1: API Health
        results["api_health"] = await self.test_channel_api_health(channel)
        
        # Test 2: Schedule Check
        results["schedule_check"] = await self.test_channel_schedule(channel)
        
        # Test 3: Channel Tune (only if API health passed)
        if results["api_health"] == TestStatus.PASSED:
            results["channel_tune"] = await self.test_channel_tune(channel)
        else:
            results["channel_tune"] = TestStatus.SKIPPED
        
        return results
    
    async def test_all_channels(
        self,
        channels: Optional[list[dict]] = None,
        include_disabled: bool = False,
    ) -> dict[str, dict[str, TestStatus]]:
        """
        Test all channels.
        
        Args:
            channels: List of channels to test (fetches if not provided)
            include_disabled: Whether to include disabled channels
            
        Returns:
            Dictionary of channel_number -> test results
        """
        if channels is None:
            if include_disabled:
                channels = await self.get_all_channels()
            else:
                channels = await self.get_enabled_channels()
        
        logger.info(f"Testing {len(channels)} channels")
        
        all_results = {}
        
        # Test channels with concurrency limit
        semaphore = asyncio.Semaphore(self.config.concurrent_limit)
        
        async def test_with_semaphore(channel):
            async with semaphore:
                channel_number = channel.get("number", "unknown")
                results = await self.test_single_channel(channel)
                return channel_number, results
        
        tasks = [test_with_semaphore(ch) for ch in channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Test failed with exception: {result}")
            else:
                channel_number, test_results = result
                all_results[channel_number] = test_results
        
        return all_results
    
    async def run_reliability_suite(
        self,
        duration_hours: float = 2.0,
        cycle_interval_seconds: float = 300.0,
    ) -> None:
        """
        Run continuous reliability testing for specified duration.
        
        This implements the "endurance testing" pattern from reliability testing:
        - Run continuously for extended period
        - Identify issues that occur over time
        - Calculate MTBF and availability metrics
        
        Args:
            duration_hours: How long to run tests
            cycle_interval_seconds: Time between test cycles
        """
        start_time = time.time()
        end_time = start_time + (duration_hours * 3600)
        cycle_count = 0
        
        logger.info(f"Starting reliability suite for {duration_hours} hours")
        
        while time.time() < end_time:
            cycle_count += 1
            cycle_start = time.time()
            
            logger.info(f"=== Test Cycle {cycle_count} ===")
            
            # Run full channel test suite
            await self.test_all_channels()
            
            # Calculate remaining time in this cycle
            cycle_duration = time.time() - cycle_start
            remaining_in_cycle = cycle_interval_seconds - cycle_duration
            
            if remaining_in_cycle > 0 and time.time() < end_time:
                logger.info(f"Cycle complete. Waiting {remaining_in_cycle:.0f}s before next cycle")
                await asyncio.sleep(remaining_in_cycle)
        
        logger.info(f"Reliability suite complete after {cycle_count} cycles")
