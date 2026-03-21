"""
Per-source adaptive retry policies.

Retry must NEVER implicitly advance index.
Advance only after threshold exceeded.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Archive.org: MAX_RETRIES=2, BACKOFF=[2, 5]
ARCHIVE_ORG_MAX_RETRIES = 2
ARCHIVE_ORG_BACKOFF_SECONDS = [2, 5]

# YouTube: MAX_RETRIES=5, BACKOFF=[5, 15, 30, 60, 120]
YOUTUBE_MAX_RETRIES = 5
YOUTUBE_BACKOFF_SECONDS = [5, 15, 30, 60, 120]

# Default for unknown sources
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = [2, 5, 10]


def get_backoff_seconds(source: str, retry_count: int) -> Optional[int]:
    """
    Get backoff delay for the given retry attempt. Returns None if retries exhausted.
    """
    source_lower = (source or "").lower()
    if "archive" in source_lower:
        max_retries = ARCHIVE_ORG_MAX_RETRIES
        backoff = ARCHIVE_ORG_BACKOFF_SECONDS
    elif "youtube" in source_lower or "youtu" in source_lower:
        max_retries = YOUTUBE_MAX_RETRIES
        backoff = YOUTUBE_BACKOFF_SECONDS
    else:
        max_retries = DEFAULT_MAX_RETRIES
        backoff = DEFAULT_BACKOFF_SECONDS

    if retry_count >= max_retries:
        return None  # Exhausted
    if retry_count >= len(backoff):
        return backoff[-1]
    return backoff[retry_count]


def should_advance_after_retry_exhausted(source: str, retry_count: int) -> bool:
    """True when retries exhausted - advance to next item."""
    backoff = get_backoff_seconds(source, retry_count)
    return backoff is None


async def retry_backoff(source: str, retry_count: int) -> bool:
    """
    Sleep for backoff duration. Returns True if we should retry same item,
    False if retries exhausted (caller should advance).
    """
    delay = get_backoff_seconds(source, retry_count)
    if delay is None:
        logger.info(f"Retries exhausted for source={source} after {retry_count} attempts")
        return False
    logger.info(f"Retry {retry_count} for {source}: backing off {delay}s")
    await asyncio.sleep(delay)
    return True


class RetryPolicy:
    """Per-source retry policy helper."""

    def __init__(self, source: str = "unknown"):
        self.source = source
        self.retry_count = 0

    def get_backoff(self) -> Optional[int]:
        return get_backoff_seconds(self.source, self.retry_count)

    def is_exhausted(self) -> bool:
        return self.get_backoff() is None

    async def wait_and_retry(self) -> bool:
        """Wait for backoff, return True if should retry, False if exhausted."""
        return await retry_backoff(self.source, self.retry_count)

    def increment(self) -> None:
        self.retry_count += 1

    def reset(self) -> None:
        self.retry_count = 0


def get_retry_policy(source: str) -> RetryPolicy:
    return RetryPolicy(source=source)
