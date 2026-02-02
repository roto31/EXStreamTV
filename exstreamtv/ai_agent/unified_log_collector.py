"""
Unified Log Collector for real-time log aggregation and AI analysis.

Provides centralized log collection with real-time streaming to AI:
- Multi-source aggregation: App logs, FFmpeg stderr, Plex, Jellyfin
- Real-time log streaming: Push logs to AI as they arrive
- Structured log parsing: Extract timestamps, levels, components
- Log correlation: Correlate events across sources by timestamp/session
- Ring buffer: Keep last N minutes in memory for instant AI access
- Log tagging: Auto-tag logs with channel_id, session_id, ffmpeg_pid
"""

import asyncio
import logging
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class LogSource(str, Enum):
    """Log source types."""
    
    APPLICATION = "application"
    FFMPEG = "ffmpeg"
    PLEX = "plex"
    JELLYFIN = "jellyfin"
    EMBY = "emby"
    ARCHIVE_ORG = "archive_org"
    YOUTUBE = "youtube"
    BROWSER = "browser"
    SYSTEM = "system"


class LogLevel(str, Enum):
    """Log severity levels."""
    
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogEvent:
    """A structured log event."""
    
    event_id: str
    timestamp: datetime
    source: LogSource
    level: LogLevel
    message: str
    
    # Context
    component: Optional[str] = None
    channel_id: Optional[int] = None
    session_id: Optional[str] = None
    ffmpeg_pid: Optional[int] = None
    
    # Raw data
    raw_line: Optional[str] = None
    
    # Parsed data
    parsed_data: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    
    @property
    def age_seconds(self) -> float:
        """Get age in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()
    
    @property
    def is_error(self) -> bool:
        """Check if this is an error or critical event."""
        return self.level in (LogLevel.ERROR, LogLevel.CRITICAL)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
            "level": self.level.value,
            "message": self.message,
            "component": self.component,
            "channel_id": self.channel_id,
            "session_id": self.session_id,
            "ffmpeg_pid": self.ffmpeg_pid,
            "parsed_data": self.parsed_data,
            "tags": self.tags,
        }
    
    def matches_context(
        self,
        channel_id: Optional[int] = None,
        session_id: Optional[str] = None,
        source: Optional[LogSource] = None,
    ) -> bool:
        """Check if event matches context filters."""
        if channel_id is not None and self.channel_id != channel_id:
            return False
        if session_id is not None and self.session_id != session_id:
            return False
        if source is not None and self.source != source:
            return False
        return True


@dataclass
class FFmpegLogLine:
    """Parsed FFmpeg log line."""
    
    timestamp: datetime
    channel_id: int
    line_type: str  # "progress", "error", "warning", "info"
    message: str
    
    # Progress metrics
    frame: Optional[int] = None
    fps: Optional[float] = None
    bitrate: Optional[str] = None
    speed: Optional[float] = None
    time: Optional[str] = None
    size: Optional[str] = None
    
    # Error info
    error_code: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "channel_id": self.channel_id,
            "line_type": self.line_type,
            "message": self.message,
            "frame": self.frame,
            "fps": self.fps,
            "bitrate": self.bitrate,
            "speed": self.speed,
            "time": self.time,
        }


class LogParser:
    """Parses raw log lines into structured events."""
    
    # Patterns for different log formats
    PATTERNS = {
        "standard": re.compile(
            r"(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\.]\d+)\s*"
            r"[-\s]*(?P<level>\w+)[-\s]*"
            r"(?P<component>[\w\.]+)?[-:\s]*"
            r"(?P<message>.*)"
        ),
        "ffmpeg_progress": re.compile(
            r"frame=\s*(?P<frame>\d+)\s+"
            r"fps=\s*(?P<fps>[\d.]+)\s+"
            r".*?bitrate=\s*(?P<bitrate>[\d.]+\w+/s)\s+"
            r".*?speed=\s*(?P<speed>[\d.]+)x"
        ),
        "ffmpeg_time": re.compile(
            r"time=(?P<time>\d{2}:\d{2}:\d{2}\.\d{2})"
        ),
        "ffmpeg_error": re.compile(
            r"(?P<error_type>Error|error|ERROR|FATAL|Fatal)[\s:]+(?P<message>.*)"
        ),
        "channel_id": re.compile(r"channel[_\s]?(?:id)?[=:\s]?(\d+)", re.I),
        "session_id": re.compile(r"session[_\s]?(?:id)?[=:\s]?([a-f0-9-]{8,})", re.I),
    }
    
    def parse_application_log(
        self,
        line: str,
        source: LogSource = LogSource.APPLICATION,
    ) -> Optional[LogEvent]:
        """Parse a standard application log line."""
        match = self.PATTERNS["standard"].match(line.strip())
        
        if not match:
            # Simple fallback
            return LogEvent(
                event_id=str(uuid4()),
                timestamp=datetime.utcnow(),
                source=source,
                level=self._detect_level(line),
                message=line.strip(),
                raw_line=line,
            )
        
        groups = match.groupdict()
        
        # Parse timestamp
        try:
            ts_str = groups["timestamp"].replace(",", ".")
            timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            timestamp = datetime.utcnow()
        
        # Parse level
        level_str = groups.get("level", "INFO").upper()
        level = LogLevel.INFO
        for l in LogLevel:
            if l.value.upper() == level_str:
                level = l
                break
        
        event = LogEvent(
            event_id=str(uuid4()),
            timestamp=timestamp,
            source=source,
            level=level,
            message=groups.get("message", "").strip(),
            component=groups.get("component"),
            raw_line=line,
        )
        
        # Extract context from message
        self._extract_context(event)
        
        return event
    
    def parse_ffmpeg_line(
        self,
        line: str,
        channel_id: int,
    ) -> Optional[FFmpegLogLine]:
        """Parse FFmpeg stderr line."""
        line = line.strip()
        if not line:
            return None
        
        result = FFmpegLogLine(
            timestamp=datetime.utcnow(),
            channel_id=channel_id,
            line_type="info",
            message=line,
        )
        
        # Check for progress line
        progress_match = self.PATTERNS["ffmpeg_progress"].search(line)
        if progress_match:
            result.line_type = "progress"
            result.frame = int(progress_match.group("frame"))
            result.fps = float(progress_match.group("fps"))
            result.bitrate = progress_match.group("bitrate")
            result.speed = float(progress_match.group("speed"))
            
            time_match = self.PATTERNS["ffmpeg_time"].search(line)
            if time_match:
                result.time = time_match.group("time")
            
            return result
        
        # Check for error
        error_match = self.PATTERNS["ffmpeg_error"].search(line)
        if error_match:
            result.line_type = "error"
            result.message = error_match.group("message")
            return result
        
        # Check for warning
        if "warning" in line.lower():
            result.line_type = "warning"
        
        return result
    
    def _detect_level(self, line: str) -> LogLevel:
        """Detect log level from line content."""
        line_lower = line.lower()
        
        if "critical" in line_lower or "fatal" in line_lower:
            return LogLevel.CRITICAL
        if "error" in line_lower:
            return LogLevel.ERROR
        if "warning" in line_lower or "warn" in line_lower:
            return LogLevel.WARNING
        if "debug" in line_lower:
            return LogLevel.DEBUG
        
        return LogLevel.INFO
    
    def _extract_context(self, event: LogEvent) -> None:
        """Extract context (channel_id, session_id) from event."""
        message = event.message + (event.raw_line or "")
        
        # Extract channel_id
        channel_match = self.PATTERNS["channel_id"].search(message)
        if channel_match:
            try:
                event.channel_id = int(channel_match.group(1))
            except ValueError:
                pass
        
        # Extract session_id
        session_match = self.PATTERNS["session_id"].search(message)
        if session_match:
            event.session_id = session_match.group(1)


class UnifiedLogCollector:
    """
    Collects and correlates logs from all sources for AI analysis.
    
    Features:
    - Multi-source aggregation
    - Real-time streaming to subscribers
    - Ring buffer for context windows
    - Log correlation by channel/session
    - FFmpeg stderr parsing
    
    Usage:
        collector = UnifiedLogCollector()
        await collector.start()
        
        # Subscribe to real-time events
        async def on_event(event: LogEvent):
            print(f"{event.source}: {event.message}")
        
        collector.subscribe(on_event)
        
        # Emit events
        await collector.emit(LogEvent(...))
        
        # Get context window
        events = collector.get_context_window(channel_id=1, minutes=5)
    """
    
    DEFAULT_BUFFER_SIZE = 10000  # Max events in buffer
    DEFAULT_BUFFER_MINUTES = 30  # Max age of events
    
    def __init__(
        self,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        buffer_minutes: int = DEFAULT_BUFFER_MINUTES,
    ):
        """
        Initialize log collector.
        
        Args:
            buffer_size: Maximum events to keep in buffer
            buffer_minutes: Maximum age of events in buffer
        """
        self._buffer_size = buffer_size
        self._buffer_minutes = buffer_minutes
        self._buffer: deque[LogEvent] = deque(maxlen=buffer_size)
        self._ffmpeg_buffer: dict[int, deque[FFmpegLogLine]] = {}  # channel_id -> lines
        
        self._subscribers: list[Callable[[LogEvent], Any]] = []
        self._parser = LogParser()
        self._lock = asyncio.Lock()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Metrics
        self._total_events = 0
        self._events_by_source: dict[str, int] = {}
        self._errors_count = 0
        
        logger.info(
            f"UnifiedLogCollector initialized: "
            f"buffer_size={buffer_size}, buffer_minutes={buffer_minutes}"
        )
    
    async def start(self) -> None:
        """Start the log collector."""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("UnifiedLogCollector started")
    
    async def stop(self) -> None:
        """Stop the log collector."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("UnifiedLogCollector stopped")
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup of old events."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_old_events()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_old_events(self) -> int:
        """Remove events older than buffer_minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=self._buffer_minutes)
        removed = 0
        
        async with self._lock:
            while self._buffer and self._buffer[0].timestamp < cutoff:
                self._buffer.popleft()
                removed += 1
        
        return removed
    
    def subscribe(self, callback: Callable[[LogEvent], Any]) -> None:
        """
        Subscribe to real-time log events.
        
        Args:
            callback: Function called for each event (can be async)
        """
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[LogEvent], Any]) -> None:
        """Unsubscribe from log events."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def emit(self, event: LogEvent) -> None:
        """
        Emit a log event.
        
        Args:
            event: LogEvent to emit
        """
        async with self._lock:
            self._buffer.append(event)
            self._total_events += 1
            self._events_by_source[event.source.value] = (
                self._events_by_source.get(event.source.value, 0) + 1
            )
            
            if event.is_error:
                self._errors_count += 1
        
        # Notify subscribers
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")
    
    async def emit_log_line(
        self,
        line: str,
        source: LogSource = LogSource.APPLICATION,
    ) -> Optional[LogEvent]:
        """
        Parse and emit a log line.
        
        Args:
            line: Raw log line
            source: Log source
            
        Returns:
            Parsed LogEvent or None
        """
        event = self._parser.parse_application_log(line, source)
        if event:
            await self.emit(event)
        return event
    
    async def emit_ffmpeg_line(
        self,
        line: str,
        channel_id: int,
    ) -> Optional[FFmpegLogLine]:
        """
        Parse and store FFmpeg stderr line.
        
        Args:
            line: FFmpeg stderr line
            channel_id: Channel ID
            
        Returns:
            Parsed FFmpegLogLine or None
        """
        parsed = self._parser.parse_ffmpeg_line(line, channel_id)
        if not parsed:
            return None
        
        async with self._lock:
            if channel_id not in self._ffmpeg_buffer:
                self._ffmpeg_buffer[channel_id] = deque(maxlen=1000)
            
            self._ffmpeg_buffer[channel_id].append(parsed)
        
        # Emit as LogEvent for errors
        if parsed.line_type == "error":
            event = LogEvent(
                event_id=str(uuid4()),
                timestamp=parsed.timestamp,
                source=LogSource.FFMPEG,
                level=LogLevel.ERROR,
                message=parsed.message,
                channel_id=channel_id,
                tags=["ffmpeg_error"],
            )
            await self.emit(event)
        
        return parsed
    
    def get_context_window(
        self,
        channel_id: Optional[int] = None,
        session_id: Optional[str] = None,
        source: Optional[LogSource] = None,
        minutes: int = 5,
        max_events: int = 100,
    ) -> list[LogEvent]:
        """
        Get correlated logs for a specific context.
        
        Args:
            channel_id: Filter by channel
            session_id: Filter by session
            source: Filter by source
            minutes: Time window in minutes
            max_events: Maximum events to return
            
        Returns:
            List of matching LogEvents
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        events = [
            e for e in self._buffer
            if e.timestamp >= cutoff
            and e.matches_context(channel_id, session_id, source)
        ]
        
        # Return most recent
        return events[-max_events:]
    
    def get_ffmpeg_output(
        self,
        channel_id: int,
        max_lines: int = 100,
    ) -> list[FFmpegLogLine]:
        """
        Get recent FFmpeg output for a channel.
        
        Args:
            channel_id: Channel ID
            max_lines: Maximum lines to return
            
        Returns:
            List of FFmpegLogLines
        """
        if channel_id not in self._ffmpeg_buffer:
            return []
        
        lines = list(self._ffmpeg_buffer[channel_id])
        return lines[-max_lines:]
    
    def get_recent_errors(
        self,
        minutes: int = 60,
        max_errors: int = 50,
    ) -> list[LogEvent]:
        """
        Get recent error events.
        
        Args:
            minutes: Time window
            max_errors: Maximum errors to return
            
        Returns:
            List of error LogEvents
        """
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        
        errors = [
            e for e in self._buffer
            if e.timestamp >= cutoff and e.is_error
        ]
        
        return errors[-max_errors:]
    
    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics."""
        return {
            "running": self._running,
            "buffer_size": len(self._buffer),
            "buffer_capacity": self._buffer_size,
            "buffer_minutes": self._buffer_minutes,
            "total_events": self._total_events,
            "events_by_source": dict(self._events_by_source),
            "errors_count": self._errors_count,
            "subscribers_count": len(self._subscribers),
            "ffmpeg_channels": list(self._ffmpeg_buffer.keys()),
        }


# Global log collector instance
_log_collector: Optional[UnifiedLogCollector] = None


def get_log_collector() -> UnifiedLogCollector:
    """Get the global UnifiedLogCollector instance."""
    global _log_collector
    if _log_collector is None:
        _log_collector = UnifiedLogCollector()
    return _log_collector


async def init_log_collector(
    buffer_size: int = UnifiedLogCollector.DEFAULT_BUFFER_SIZE,
    buffer_minutes: int = UnifiedLogCollector.DEFAULT_BUFFER_MINUTES,
) -> UnifiedLogCollector:
    """Initialize and start the log collector."""
    global _log_collector
    _log_collector = UnifiedLogCollector(
        buffer_size=buffer_size,
        buffer_minutes=buffer_minutes,
    )
    await _log_collector.start()
    return _log_collector
