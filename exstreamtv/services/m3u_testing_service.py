"""Background service for periodic M3U stream testing"""

import asyncio
import contextlib
import logging
from datetime import datetime

from ..config import config
from ..database.models import M3UStreamSource, M3UStreamTest
from ..database.session import SessionLocal
from ..importers.m3u_discovery import M3UStreamTester

logger = logging.getLogger(__name__)


class M3UTestingService:
    """Scheduled testing of M3U streams"""

    def __init__(self, db_session=None):
        self.db = db_session or SessionLocal()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the testing service"""
        if self._running:
            logger.warning("M3U testing service is already running")
            return

        if not config.m3u.enabled or not config.m3u.enable_testing_service:
            logger.info("M3U testing service is disabled")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_periodic_tests())
        logger.info("M3U testing service started")

    async def stop(self) -> None:
        """Stop the testing service"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        logger.info("M3U testing service stopped")

    async def _run_periodic_tests(self) -> None:
        """Run periodic tests in background"""
        interval_hours = config.m3u.testing_interval_hours
        interval_seconds = interval_hours * 3600

        logger.info(f"M3U testing service: Running tests every {interval_hours} hours")

        while self._running:
            try:
                # Run tests
                await self.test_all_streams()

                # Wait for next interval
                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in M3U testing service: {e}", exc_info=True)
                # Wait a bit before retrying
                await asyncio.sleep(60)

    async def test_all_streams(self) -> None:
        """Test all active streams"""
        logger.info("Starting periodic M3U stream testing...")

        streams = self.db.query(M3UStreamSource).filter(M3UStreamSource.is_active).all()

        if not streams:
            logger.info("No active streams to test")
            return

        tester = M3UStreamTester(self.db)

        try:
            for stream in streams:
                try:
                    logger.info(f"Testing stream: {stream.name} ({stream.url})")

                    result = await tester.test_stream(stream.url)

                    # Update stream
                    stream.last_tested = datetime.utcnow()
                    stream.reliability_score = result.get("reliability_percentage")
                    stream.total_channels = result.get("total_channels", 0)
                    stream.working_channels = result.get("working_channels", 0)

                    # Create test record
                    test_record = M3UStreamTest(
                        stream_source_id=stream.id,
                        test_result="success" if result.get("success") else "failure",
                        channels_tested=result.get("channels_tested", 0),
                        channels_working=result.get("working_channels", 0),
                        reliability_percentage=result.get("reliability_percentage"),
                        test_duration=result.get("test_duration"),
                        error_message=result.get("error_message"),
                    )
                    self.db.add(test_record)

                    # Mark as inactive if reliability is too low
                    if result.get("reliability_percentage", 0) < 20:
                        stream.is_active = False
                        logger.warning(
                            f"Stream {stream.name} marked as inactive (reliability < 20%)"
                        )

                    self.db.commit()

                    logger.info(
                        f"✓ Tested {stream.name}: "
                        f"{result.get('reliability_percentage', 0):.1f}% reliability "
                        f"({result.get('working_channels', 0)}/{result.get('total_channels', 0)} channels)"
                    )

                except Exception as e:
                    logger.error(f"Error testing stream {stream.name}: {e}", exc_info=True)
                    self.db.rollback()
                    continue

            logger.info(f"Completed testing {len(streams)} streams")

        finally:
            await tester.close()

    async def test_stream_source(self, stream_id: int) -> None:
        """Test a single stream source"""
        stream = self.db.query(M3UStreamSource).filter(M3UStreamSource.id == stream_id).first()

        if not stream:
            raise ValueError(f"Stream source {stream_id} not found")

        tester = M3UStreamTester(self.db)

        try:
            result = await tester.test_stream(stream.url)

            # Update stream
            stream.last_tested = datetime.utcnow()
            stream.reliability_score = result.get("reliability_percentage")
            stream.total_channels = result.get("total_channels", 0)
            stream.working_channels = result.get("working_channels", 0)

            # Create test record
            test_record = M3UStreamTest(
                stream_source_id=stream_id,
                test_result="success" if result.get("success") else "failure",
                channels_tested=result.get("channels_tested", 0),
                channels_working=result.get("working_channels", 0),
                reliability_percentage=result.get("reliability_percentage"),
                test_duration=result.get("test_duration"),
                error_message=result.get("error_message"),
            )
            self.db.add(test_record)
            self.db.commit()

            return result

        finally:
            await tester.close()

    def close(self):
        """Close database session"""
        if self.db:
            self.db.close()
