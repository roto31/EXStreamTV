"""
Stream Throttler for rate-limited MPEG-TS delivery.

Ported from dizqueTV's throttler.js with enhancements:
- Rate-limit MPEG-TS delivery to target bitrate
- Prevent buffer overruns in clients
- Keepalive packet support during stalls
- Adaptive throttling based on client feedback

This ensures smooth playback by controlling the rate at which
data is sent to clients, preventing buffer overflows.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Optional

logger = logging.getLogger(__name__)


# MPEG-TS packet size is always 188 bytes
MPEG_TS_PACKET_SIZE = 188

# Null TS packet for keepalive (sync byte 0x47, null PID 0x1FFF)
NULL_TS_PACKET = bytes([0x47, 0x1F, 0xFF, 0x10] + [0xFF] * 184)


class ThrottleMode(str, Enum):
    """Throttling modes."""
    
    REALTIME = "realtime"  # Match real-time playback rate
    BURST = "burst"  # Allow bursts up to buffer size
    ADAPTIVE = "adaptive"  # Adjust based on client feedback
    DISABLED = "disabled"  # No throttling


@dataclass
class ThrottleConfig:
    """Configuration for stream throttling."""
    
    # Target bitrate in bits per second (default 4 Mbps)
    target_bitrate_bps: int = 4_000_000
    
    # Mode
    mode: ThrottleMode = ThrottleMode.REALTIME
    
    # Buffer settings
    max_buffer_bytes: int = 2 * 1024 * 1024  # 2MB max buffer
    min_buffer_bytes: int = 64 * 1024  # 64KB min buffer
    
    # Timing
    burst_duration_ms: int = 100  # Allow bursts of this duration
    keepalive_interval_ms: int = 5000  # Send keepalive every 5 seconds
    
    # Adaptive settings
    adaptive_window_ms: int = 1000  # Window for adaptive calculations
    adaptive_factor: float = 1.2  # Allow 20% over target in adaptive mode


@dataclass
class ThrottleMetrics:
    """Metrics for throttle monitoring."""
    
    bytes_sent: int = 0
    bytes_throttled: int = 0
    packets_sent: int = 0
    keepalives_sent: int = 0
    throttle_delays: int = 0
    total_delay_ms: float = 0.0
    current_bitrate_bps: float = 0.0
    buffer_level_bytes: int = 0
    
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_send_time: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        return (datetime.utcnow() - self.start_time).total_seconds()
    
    @property
    def average_bitrate_bps(self) -> float:
        """Calculate average bitrate."""
        duration = self.duration_seconds
        if duration > 0:
            return (self.bytes_sent * 8) / duration
        return 0.0


class StreamThrottler:
    """
    Rate-limits stream delivery to match target bitrate.
    
    Prevents buffer overflows by controlling the pace of data
    sent to clients. Uses timing-based throttling to match
    the real-time playback rate.
    
    Usage:
        throttler = StreamThrottler(target_bitrate_bps=4_000_000)
        
        async for chunk in stream:
            async for throttled_chunk in throttler.throttle(chunk):
                yield throttled_chunk
    """
    
    def __init__(
        self,
        config: Optional[ThrottleConfig] = None,
        channel_id: Optional[int] = None,
    ):
        """
        Initialize the throttler.
        
        Args:
            config: Throttle configuration
            channel_id: Channel ID for logging
        """
        self._config = config or ThrottleConfig()
        self._channel_id = channel_id
        self._metrics = ThrottleMetrics()
        
        # Timing state
        self._start_time: Optional[float] = None
        self._bytes_sent_window: int = 0
        self._window_start: float = 0.0
        self._last_send: float = 0.0
        self._buffer: bytes = b""
        
        # Adaptive state
        self._adaptive_multiplier: float = 1.0
        self._feedback_queue: list[tuple[float, float]] = []  # (timestamp, delay)
        
        # Keepalive state
        self._last_keepalive: float = 0.0
        
        logger.debug(
            f"StreamThrottler initialized: "
            f"bitrate={self._config.target_bitrate_bps / 1_000_000:.1f} Mbps, "
            f"mode={self._config.mode.value}"
        )
    
    @property
    def target_bytes_per_second(self) -> float:
        """Get target bytes per second."""
        return self._config.target_bitrate_bps / 8
    
    @property
    def metrics(self) -> ThrottleMetrics:
        """Get current metrics."""
        return self._metrics
    
    def reset(self) -> None:
        """Reset throttler state."""
        self._start_time = None
        self._bytes_sent_window = 0
        self._window_start = 0.0
        self._last_send = 0.0
        self._buffer = b""
        self._metrics = ThrottleMetrics()
        
        logger.debug(f"StreamThrottler reset for channel {self._channel_id}")
    
    async def throttle(
        self,
        data: bytes,
        force: bool = False,
    ) -> AsyncIterator[bytes]:
        """
        Throttle data to target bitrate.
        
        Args:
            data: Data chunk to throttle
            force: If True, skip throttling (for urgent data)
            
        Yields:
            Throttled data chunks
        """
        if self._config.mode == ThrottleMode.DISABLED or force:
            self._record_send(len(data))
            yield data
            return
        
        now = time.monotonic()
        
        # Initialize timing on first call
        if self._start_time is None:
            self._start_time = now
            self._window_start = now
            self._last_send = now
        
        # Add data to buffer
        self._buffer += data
        self._metrics.buffer_level_bytes = len(self._buffer)
        
        # Check if buffer exceeds max
        if len(self._buffer) > self._config.max_buffer_bytes:
            logger.warning(
                f"Channel {self._channel_id}: Buffer overflow, "
                f"dropping {len(self._buffer) - self._config.max_buffer_bytes} bytes"
            )
            self._buffer = self._buffer[-self._config.max_buffer_bytes:]
        
        # Calculate how much we can send
        while len(self._buffer) >= self._config.min_buffer_bytes:
            chunk_size = self._calculate_chunk_size(now)
            
            if chunk_size <= 0:
                # Need to wait before sending more
                delay = self._calculate_delay(now)
                if delay > 0:
                    self._metrics.throttle_delays += 1
                    self._metrics.total_delay_ms += delay * 1000
                    await asyncio.sleep(delay)
                    now = time.monotonic()
                    continue
            
            # Send chunk
            chunk = self._buffer[:chunk_size]
            self._buffer = self._buffer[chunk_size:]
            
            self._record_send(len(chunk))
            self._last_send = time.monotonic()
            
            yield chunk
        
        # Send remaining buffer if any
        if self._buffer:
            self._record_send(len(self._buffer))
            yield self._buffer
            self._buffer = b""
    
    def _calculate_chunk_size(self, now: float) -> int:
        """Calculate how many bytes we can send now."""
        if self._config.mode == ThrottleMode.BURST:
            # In burst mode, allow sending up to burst duration worth
            burst_bytes = int(
                self.target_bytes_per_second 
                * (self._config.burst_duration_ms / 1000)
            )
            return min(len(self._buffer), burst_bytes)
        
        # Calculate time elapsed since window start
        elapsed = now - self._window_start
        
        # Calculate target bytes for elapsed time
        target_multiplier = self._adaptive_multiplier if self._config.mode == ThrottleMode.ADAPTIVE else 1.0
        target_bytes = int(elapsed * self.target_bytes_per_second * target_multiplier)
        
        # Calculate how many bytes we can send
        available = target_bytes - self._bytes_sent_window
        
        # Reset window if it's been too long
        if elapsed > self._config.adaptive_window_ms / 1000:
            self._window_start = now
            self._bytes_sent_window = 0
            available = int(
                (self._config.adaptive_window_ms / 1000) 
                * self.target_bytes_per_second 
                * target_multiplier
            )
        
        return min(max(0, available), len(self._buffer))
    
    def _calculate_delay(self, now: float) -> float:
        """Calculate how long to wait before sending more."""
        # Calculate bytes per millisecond
        bytes_per_ms = self.target_bytes_per_second / 1000
        
        # Calculate time to clear buffer at target rate
        time_to_clear_ms = len(self._buffer) / bytes_per_ms
        
        # Calculate how far ahead we are
        elapsed = now - self._window_start
        elapsed_ms = elapsed * 1000
        
        expected_bytes = elapsed_ms * bytes_per_ms
        ahead_bytes = self._bytes_sent_window - expected_bytes
        
        if ahead_bytes > 0:
            # We're ahead, need to wait
            delay_ms = ahead_bytes / bytes_per_ms
            return min(delay_ms / 1000, 0.1)  # Max 100ms delay
        
        return 0.0
    
    def _record_send(self, byte_count: int) -> None:
        """Record bytes sent."""
        now = time.monotonic()
        
        self._bytes_sent_window += byte_count
        self._metrics.bytes_sent += byte_count
        self._metrics.packets_sent += byte_count // MPEG_TS_PACKET_SIZE
        self._metrics.last_send_time = datetime.utcnow()
        
        # Calculate current bitrate
        elapsed = now - self._window_start if self._window_start else 1.0
        if elapsed > 0:
            self._metrics.current_bitrate_bps = (self._bytes_sent_window * 8) / elapsed
    
    async def send_keepalive(self) -> bytes:
        """
        Generate keepalive packets.
        
        Returns:
            Null TS packets for keepalive
        """
        now = time.monotonic()
        
        # Check if enough time has passed
        if now - self._last_keepalive < self._config.keepalive_interval_ms / 1000:
            return b""
        
        self._last_keepalive = now
        self._metrics.keepalives_sent += 1
        
        # Send 7 null packets (about 1.3KB)
        keepalive_data = NULL_TS_PACKET * 7
        
        logger.debug(f"Channel {self._channel_id}: Sending keepalive packets")
        
        return keepalive_data
    
    def provide_feedback(self, delay_ms: float) -> None:
        """
        Provide client feedback for adaptive throttling.
        
        Args:
            delay_ms: Measured delay/latency in milliseconds
        """
        if self._config.mode != ThrottleMode.ADAPTIVE:
            return
        
        now = time.monotonic()
        self._feedback_queue.append((now, delay_ms))
        
        # Keep only recent feedback
        cutoff = now - (self._config.adaptive_window_ms / 1000)
        self._feedback_queue = [
            (t, d) for t, d in self._feedback_queue if t > cutoff
        ]
        
        # Adjust multiplier based on feedback
        if self._feedback_queue:
            avg_delay = sum(d for _, d in self._feedback_queue) / len(self._feedback_queue)
            
            if avg_delay > 100:  # Client is lagging
                self._adaptive_multiplier = max(0.5, self._adaptive_multiplier * 0.95)
            elif avg_delay < 20:  # Client keeping up well
                self._adaptive_multiplier = min(
                    self._config.adaptive_factor,
                    self._adaptive_multiplier * 1.02
                )
    
    def get_stats(self) -> dict[str, Any]:
        """Get throttler statistics."""
        return {
            "channel_id": self._channel_id,
            "mode": self._config.mode.value,
            "target_bitrate_mbps": self._config.target_bitrate_bps / 1_000_000,
            "bytes_sent": self._metrics.bytes_sent,
            "packets_sent": self._metrics.packets_sent,
            "keepalives_sent": self._metrics.keepalives_sent,
            "throttle_delays": self._metrics.throttle_delays,
            "total_delay_ms": self._metrics.total_delay_ms,
            "current_bitrate_mbps": self._metrics.current_bitrate_bps / 1_000_000,
            "average_bitrate_mbps": self._metrics.average_bitrate_bps / 1_000_000,
            "buffer_level_bytes": self._metrics.buffer_level_bytes,
            "adaptive_multiplier": self._adaptive_multiplier,
            "duration_seconds": self._metrics.duration_seconds,
        }


class ThrottledStreamWrapper:
    """
    Wrapper that applies throttling to an async stream.
    
    Usage:
        wrapper = ThrottledStreamWrapper(stream, target_bitrate_bps=4_000_000)
        
        async for chunk in wrapper:
            yield chunk
    """
    
    def __init__(
        self,
        source_stream: AsyncIterator[bytes],
        target_bitrate_bps: int = 4_000_000,
        mode: ThrottleMode = ThrottleMode.REALTIME,
        channel_id: Optional[int] = None,
    ):
        """
        Initialize the wrapper.
        
        Args:
            source_stream: Source async iterator
            target_bitrate_bps: Target bitrate
            mode: Throttle mode
            channel_id: Channel ID for logging
        """
        self._source = source_stream
        self._throttler = StreamThrottler(
            config=ThrottleConfig(
                target_bitrate_bps=target_bitrate_bps,
                mode=mode,
            ),
            channel_id=channel_id,
        )
        self._channel_id = channel_id
    
    @property
    def throttler(self) -> StreamThrottler:
        """Get the throttler instance."""
        return self._throttler
    
    async def __aiter__(self) -> AsyncIterator[bytes]:
        """Iterate over throttled stream."""
        async for chunk in self._source:
            async for throttled in self._throttler.throttle(chunk):
                yield throttled
    
    def get_stats(self) -> dict[str, Any]:
        """Get wrapper statistics."""
        return self._throttler.get_stats()


def create_throttled_stream(
    source: AsyncIterator[bytes],
    target_bitrate_bps: int = 4_000_000,
    mode: ThrottleMode = ThrottleMode.REALTIME,
    channel_id: Optional[int] = None,
) -> ThrottledStreamWrapper:
    """
    Create a throttled stream wrapper.
    
    Args:
        source: Source async iterator
        target_bitrate_bps: Target bitrate in bits per second
        mode: Throttle mode
        channel_id: Channel ID for logging
        
    Returns:
        ThrottledStreamWrapper
    """
    return ThrottledStreamWrapper(
        source_stream=source,
        target_bitrate_bps=target_bitrate_bps,
        mode=mode,
        channel_id=channel_id,
    )
