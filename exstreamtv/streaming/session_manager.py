"""
Session Manager for stream connection tracking.

Ported from Tunarr's SessionManager with enhancements:
- Track active connections per channel
- Manage session lifecycle with automatic cleanup
- Health monitoring with error counting
- Restart tracking with limits
- Idle session cleanup

This provides centralized session management for all streaming
connections, enabling better resource management and diagnostics.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Stream session states."""
    
    CONNECTING = "connecting"
    ACTIVE = "active"
    BUFFERING = "buffering"
    PAUSED = "paused"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class SessionErrorType(str, Enum):
    """Types of session errors."""
    
    CONNECTION_TIMEOUT = "connection_timeout"
    STREAM_TIMEOUT = "stream_timeout"
    FFMPEG_ERROR = "ffmpeg_error"
    SOURCE_ERROR = "source_error"
    CLIENT_DISCONNECT = "client_disconnect"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    UNKNOWN = "unknown"


@dataclass
class SessionError:
    """Recorded session error."""
    
    error_type: SessionErrorType
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    recoverable: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamSession:
    """
    Represents a single stream session.
    
    Tracks connection state, health metrics, and error history
    for a client connection to a channel stream.
    """
    
    session_id: str
    channel_id: int
    channel_number: int
    client_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # State tracking
    state: SessionState = SessionState.CONNECTING
    last_activity_at: datetime = field(default_factory=datetime.utcnow)
    last_data_at: Optional[datetime] = None
    
    # Metrics
    bytes_sent: int = 0
    chunks_sent: int = 0
    errors: list[SessionError] = field(default_factory=list)
    restarts: int = 0
    
    # Configuration
    max_restarts: int = 10
    idle_timeout_seconds: int = 300  # 5 minutes
    
    # Callbacks
    on_error: Optional[Callable] = None
    on_disconnect: Optional[Callable] = None
    
    @property
    def is_active(self) -> bool:
        """Check if session is active."""
        return self.state in (SessionState.ACTIVE, SessionState.BUFFERING)
    
    @property
    def is_healthy(self) -> bool:
        """Check if session is healthy (active with recent data)."""
        if not self.is_active:
            return False
        
        if self.last_data_at is None:
            return False
        
        # Healthy if data received in last 30 seconds
        data_age = (datetime.utcnow() - self.last_data_at).total_seconds()
        return data_age < 30
    
    @property
    def is_idle(self) -> bool:
        """Check if session has been idle too long."""
        idle_duration = (datetime.utcnow() - self.last_activity_at).total_seconds()
        return idle_duration > self.idle_timeout_seconds
    
    @property
    def can_restart(self) -> bool:
        """Check if session can be restarted."""
        return self.restarts < self.max_restarts
    
    @property
    def error_count(self) -> int:
        """Get total error count."""
        return len(self.errors)
    
    @property
    def recent_error_count(self) -> int:
        """Get errors in last 5 minutes."""
        cutoff = datetime.utcnow() - timedelta(minutes=5)
        return sum(1 for e in self.errors if e.timestamp > cutoff)
    
    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def record_data(self, bytes_count: int) -> None:
        """Record data sent to client."""
        self.bytes_sent += bytes_count
        self.chunks_sent += 1
        self.last_data_at = datetime.utcnow()
        self.last_activity_at = datetime.utcnow()
        
        if self.state == SessionState.BUFFERING:
            self.state = SessionState.ACTIVE
    
    def record_error(self, error: SessionError) -> None:
        """Record an error."""
        self.errors.append(error)
        self.last_activity_at = datetime.utcnow()
        
        # Keep only last 50 errors
        if len(self.errors) > 50:
            self.errors = self.errors[-50:]
        
        if error.error_type == SessionErrorType.FFMPEG_ERROR:
            self.state = SessionState.ERROR
        
        if self.on_error:
            try:
                self.on_error(self, error)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")
    
    def record_restart(self) -> bool:
        """
        Record a restart attempt.
        
        Returns:
            True if restart is allowed, False if max restarts exceeded
        """
        self.restarts += 1
        self.last_activity_at = datetime.utcnow()
        
        if self.restarts > self.max_restarts:
            logger.warning(
                f"Session {self.session_id} exceeded max restarts "
                f"({self.restarts}/{self.max_restarts})"
            )
            return False
        
        return True
    
    def activate(self) -> None:
        """Mark session as active."""
        self.state = SessionState.ACTIVE
        self.last_activity_at = datetime.utcnow()
    
    def disconnect(self, reason: str = "unknown") -> None:
        """Mark session as disconnected."""
        self.state = SessionState.DISCONNECTED
        self.last_activity_at = datetime.utcnow()
        
        logger.info(
            f"Session {self.session_id} disconnected: {reason} "
            f"(duration: {self.duration_seconds:.1f}s, "
            f"bytes: {self.bytes_sent}, errors: {self.error_count})"
        )
        
        if self.on_disconnect:
            try:
                self.on_disconnect(self, reason)
            except Exception as e:
                logger.error(f"Disconnect callback failed: {e}")
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "session_id": self.session_id,
            "channel_id": self.channel_id,
            "channel_number": self.channel_number,
            "client_id": self.client_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "bytes_sent": self.bytes_sent,
            "chunks_sent": self.chunks_sent,
            "error_count": self.error_count,
            "recent_error_count": self.recent_error_count,
            "restarts": self.restarts,
            "is_healthy": self.is_healthy,
            "is_idle": self.is_idle,
        }


@dataclass
class ChannelSessionStats:
    """Statistics for sessions on a channel."""
    
    channel_id: int
    channel_number: int
    active_sessions: int = 0
    total_sessions: int = 0
    total_bytes_sent: int = 0
    total_errors: int = 0
    total_restarts: int = 0
    avg_session_duration: float = 0.0


class SessionManager:
    """
    Manages all stream sessions across channels.
    
    Features:
    - Centralized session tracking
    - Per-channel connection limits
    - Idle session cleanup
    - Health monitoring and metrics
    - Restart coordination
    
    Usage:
        manager = SessionManager()
        await manager.start()
        
        session = await manager.create_session(channel_id=1, channel_number=101)
        
        # In streaming loop:
        session.record_data(len(chunk))
        
        # On disconnect:
        await manager.end_session(session.session_id)
    """
    
    DEFAULT_MAX_SESSIONS_PER_CHANNEL = 50
    DEFAULT_IDLE_CHECK_INTERVAL = 60  # seconds
    DEFAULT_IDLE_TIMEOUT = 300  # 5 minutes
    
    def __init__(
        self,
        max_sessions_per_channel: int = DEFAULT_MAX_SESSIONS_PER_CHANNEL,
        idle_check_interval: float = DEFAULT_IDLE_CHECK_INTERVAL,
        idle_timeout: int = DEFAULT_IDLE_TIMEOUT,
    ):
        """
        Initialize session manager.
        
        Args:
            max_sessions_per_channel: Maximum concurrent sessions per channel
            idle_check_interval: Seconds between idle checks
            idle_timeout: Seconds before session is considered idle
        """
        self._sessions: dict[str, StreamSession] = {}
        self._channel_sessions: dict[int, set[str]] = {}  # channel_id -> session_ids
        self._lock = asyncio.Lock()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Configuration
        self._max_sessions_per_channel = max_sessions_per_channel
        self._idle_check_interval = idle_check_interval
        self._idle_timeout = idle_timeout
        
        # Callbacks
        self._on_session_created: list[Callable] = []
        self._on_session_ended: list[Callable] = []
        self._on_channel_empty: list[Callable] = []
        
        # Metrics
        self._total_sessions_created = 0
        self._total_sessions_cleaned = 0
        self._total_errors_recorded = 0
        
        logger.info(
            f"SessionManager created: max_per_channel={max_sessions_per_channel}, "
            f"idle_timeout={idle_timeout}s"
        )
    
    async def start(self) -> None:
        """Start the session manager."""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("SessionManager started")
    
    async def stop(self) -> None:
        """Stop the session manager and cleanup all sessions."""
        if not self._running:
            return
        
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # End all sessions
        async with self._lock:
            for session in list(self._sessions.values()):
                session.disconnect("manager_shutdown")
            
            self._sessions.clear()
            self._channel_sessions.clear()
        
        logger.info("SessionManager stopped")
    
    async def create_session(
        self,
        channel_id: int,
        channel_number: int,
        client_id: Optional[str] = None,
        on_error: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
    ) -> StreamSession:
        """
        Create a new stream session.
        
        Args:
            channel_id: Channel database ID
            channel_number: Channel number for display
            client_id: Optional client identifier
            on_error: Callback for errors
            on_disconnect: Callback for disconnection
            
        Returns:
            New StreamSession
            
        Raises:
            ValueError: If channel is at capacity
        """
        async with self._lock:
            # Check channel capacity
            channel_session_ids = self._channel_sessions.get(channel_id, set())
            active_count = sum(
                1 for sid in channel_session_ids
                if sid in self._sessions and self._sessions[sid].is_active
            )
            
            if active_count >= self._max_sessions_per_channel:
                raise ValueError(
                    f"Channel {channel_number} at capacity "
                    f"({active_count}/{self._max_sessions_per_channel})"
                )
            
            # Create session
            session = StreamSession(
                session_id=str(uuid4()),
                channel_id=channel_id,
                channel_number=channel_number,
                client_id=client_id or str(uuid4()),
                idle_timeout_seconds=self._idle_timeout,
                on_error=on_error,
                on_disconnect=on_disconnect,
            )
            
            # Register session
            self._sessions[session.session_id] = session
            
            if channel_id not in self._channel_sessions:
                self._channel_sessions[channel_id] = set()
            self._channel_sessions[channel_id].add(session.session_id)
            
            self._total_sessions_created += 1
            
            logger.debug(
                f"Session created: {session.session_id[:8]}... "
                f"for channel {channel_number} (client: {session.client_id[:8]}...)"
            )
            
            # Notify callbacks
            for callback in self._on_session_created:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(session)
                    else:
                        callback(session)
                except Exception as e:
                    logger.error(f"Session created callback error: {e}")
            
            return session
    
    async def end_session(
        self,
        session_id: str,
        reason: str = "client_disconnect",
    ) -> Optional[StreamSession]:
        """
        End a session.
        
        Args:
            session_id: Session ID to end
            reason: Reason for ending
            
        Returns:
            The ended session, or None if not found
        """
        async with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            
            session.disconnect(reason)
            
            # Remove from tracking
            del self._sessions[session_id]
            
            if session.channel_id in self._channel_sessions:
                self._channel_sessions[session.channel_id].discard(session_id)
                
                # Check if channel is now empty
                if not self._channel_sessions[session.channel_id]:
                    del self._channel_sessions[session.channel_id]
                    
                    # Notify callbacks
                    for callback in self._on_channel_empty:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(session.channel_id)
                            else:
                                callback(session.channel_id)
                        except Exception as e:
                            logger.error(f"Channel empty callback error: {e}")
            
            # Notify callbacks
            for callback in self._on_session_ended:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(session)
                    else:
                        callback(session)
                except Exception as e:
                    logger.error(f"Session ended callback error: {e}")
            
            return session
    
    def get_session(self, session_id: str) -> Optional[StreamSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    def get_channel_sessions(self, channel_id: int) -> list[StreamSession]:
        """Get all sessions for a channel."""
        session_ids = self._channel_sessions.get(channel_id, set())
        return [
            self._sessions[sid]
            for sid in session_ids
            if sid in self._sessions
        ]
    
    def get_active_channel_sessions(self, channel_id: int) -> list[StreamSession]:
        """Get active sessions for a channel."""
        return [s for s in self.get_channel_sessions(channel_id) if s.is_active]
    
    def get_channel_stats(self, channel_id: int) -> ChannelSessionStats:
        """Get session statistics for a channel."""
        sessions = self.get_channel_sessions(channel_id)
        active = [s for s in sessions if s.is_active]
        
        # Find channel number from any session
        channel_number = sessions[0].channel_number if sessions else 0
        
        total_bytes = sum(s.bytes_sent for s in sessions)
        total_errors = sum(s.error_count for s in sessions)
        total_restarts = sum(s.restarts for s in sessions)
        
        durations = [s.duration_seconds for s in sessions if s.duration_seconds > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return ChannelSessionStats(
            channel_id=channel_id,
            channel_number=channel_number,
            active_sessions=len(active),
            total_sessions=len(sessions),
            total_bytes_sent=total_bytes,
            total_errors=total_errors,
            total_restarts=total_restarts,
            avg_session_duration=avg_duration,
        )
    
    def record_error(
        self,
        session_id: str,
        error_type: SessionErrorType,
        message: str,
        recoverable: bool = True,
        details: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Record an error for a session.
        
        Args:
            session_id: Session ID
            error_type: Type of error
            message: Error message
            recoverable: Whether error is recoverable
            details: Additional details
            
        Returns:
            True if error was recorded, False if session not found
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        error = SessionError(
            error_type=error_type,
            message=message,
            recoverable=recoverable,
            details=details or {},
        )
        
        session.record_error(error)
        self._total_errors_recorded += 1
        
        logger.debug(
            f"Session {session_id[:8]}... error: {error_type.value} - {message}"
        )
        
        return True
    
    def record_restart(self, session_id: str) -> bool:
        """
        Record a restart for a session.
        
        Returns:
            True if restart is allowed, False otherwise
        """
        session = self._sessions.get(session_id)
        if not session:
            return False
        
        return session.record_restart()
    
    async def _cleanup_loop(self) -> None:
        """Background loop to cleanup idle sessions."""
        while self._running:
            try:
                await asyncio.sleep(self._idle_check_interval)
                await self._cleanup_idle_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
    
    async def _cleanup_idle_sessions(self) -> int:
        """
        Cleanup idle sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        cleaned = 0
        
        async with self._lock:
            idle_sessions = [
                s for s in self._sessions.values()
                if s.is_idle or s.state == SessionState.DISCONNECTED
            ]
            
            for session in idle_sessions:
                logger.debug(f"Cleaning up idle session {session.session_id[:8]}...")
                
                # Remove from tracking
                del self._sessions[session.session_id]
                
                if session.channel_id in self._channel_sessions:
                    self._channel_sessions[session.channel_id].discard(session.session_id)
                
                cleaned += 1
                self._total_sessions_cleaned += 1
        
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} idle sessions")
        
        return cleaned
    
    def on_session_created(self, callback: Callable) -> None:
        """Register callback for session creation."""
        self._on_session_created.append(callback)
    
    def on_session_ended(self, callback: Callable) -> None:
        """Register callback for session ending."""
        self._on_session_ended.append(callback)
    
    def on_channel_empty(self, callback: Callable) -> None:
        """Register callback for when a channel has no sessions."""
        self._on_channel_empty.append(callback)
    
    def get_stats(self) -> dict[str, Any]:
        """Get session manager statistics."""
        active_sessions = sum(1 for s in self._sessions.values() if s.is_active)
        healthy_sessions = sum(1 for s in self._sessions.values() if s.is_healthy)
        
        return {
            "running": self._running,
            "total_sessions": len(self._sessions),
            "active_sessions": active_sessions,
            "healthy_sessions": healthy_sessions,
            "channels_with_sessions": len(self._channel_sessions),
            "total_sessions_created": self._total_sessions_created,
            "total_sessions_cleaned": self._total_sessions_cleaned,
            "total_errors_recorded": self._total_errors_recorded,
            "max_sessions_per_channel": self._max_sessions_per_channel,
            "idle_timeout": self._idle_timeout,
        }
    
    def get_all_sessions(self) -> list[StreamSession]:
        """Get all sessions."""
        return list(self._sessions.values())
    
    def get_active_sessions(self) -> list[StreamSession]:
        """Get all active sessions."""
        return [s for s in self._sessions.values() if s.is_active]


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global SessionManager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def init_session_manager(
    max_sessions_per_channel: int = SessionManager.DEFAULT_MAX_SESSIONS_PER_CHANNEL,
    idle_timeout: int = SessionManager.DEFAULT_IDLE_TIMEOUT,
) -> SessionManager:
    """Initialize and start the global session manager."""
    manager = get_session_manager()
    manager._max_sessions_per_channel = max_sessions_per_channel
    manager._idle_timeout = idle_timeout
    await manager.start()
    return manager
