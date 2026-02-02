"""
EXStreamTV Streaming Module

Handles channel streaming, MPEG-TS generation, and continuous playback.
Ported from StreamTV with all bug fixes preserved.

Components:
- ChannelManager: ErsatzTV-style continuous background streaming
- ChannelStream: Individual channel stream management
- MPEGTSStreamer: FFmpeg-based MPEG-TS generation
- StreamManager: Unified stream source management
- ErrorHandler: Error classification and recovery
- RetryManager: Retry logic with backoff strategies
- SessionManager: Tunarr-style session tracking (NEW)
- StreamThrottler: dizqueTV-style rate limiting (NEW)
- ErrorScreenGenerator: dizqueTV-style error screens (NEW)
"""

from exstreamtv.streaming.channel_manager import ChannelManager, ChannelStream
from exstreamtv.streaming.error_handler import (
    ErrorClassifier,
    ErrorHandler,
    ErrorRecoveryStrategy,
    ErrorSeverity,
    ErrorType,
    StreamError,
)
from exstreamtv.streaming.mpegts_streamer import (
    CodecInfo,
    MPEGTSStreamer,
    StreamSource,
)
from exstreamtv.streaming.retry_manager import (
    HTTPRetryManager,
    RetryConfig,
    RetryManager,
)
from exstreamtv.streaming.url_resolver import MediaURLResolver, get_url_resolver
from exstreamtv.streaming.process_watchdog import FFmpegWatchdog, get_ffmpeg_watchdog

# New components from Tunarr/dizqueTV integration
from exstreamtv.streaming.session_manager import (
    SessionManager,
    StreamSession,
    SessionState,
    SessionErrorType,
    get_session_manager,
    init_session_manager,
)
from exstreamtv.streaming.throttler import (
    StreamThrottler,
    ThrottleConfig,
    ThrottleMode,
    ThrottledStreamWrapper,
    create_throttled_stream,
)
from exstreamtv.streaming.error_screens import (
    ErrorScreenGenerator,
    ErrorScreenConfig,
    ErrorScreenMessage,
    ErrorVisualMode,
    ErrorAudioMode,
    get_error_screen_generator,
    generate_quick_error_stream,
)


class StreamManager:
    """
    Unified stream source manager (stub for backwards compatibility).
    
    This is a placeholder class that will be fully implemented when
    stream management features are added. For now, it provides a
    minimal interface to avoid import errors.
    """
    
    def __init__(self):
        """Initialize the stream manager."""
        self._active_streams = {}
    
    async def start_stream(self, channel_id: int, source_url: str):
        """Start a stream for a channel (stub)."""
        pass
    
    async def stop_stream(self, channel_id: int):
        """Stop a stream for a channel (stub)."""
        pass
    
    def get_active_streams(self):
        """Get list of active streams."""
        return list(self._active_streams.keys())

__all__ = [
    # Channel management
    "ChannelManager",
    "ChannelStream",
    # MPEG-TS streaming
    "CodecInfo",
    "MPEGTSStreamer",
    "StreamSource",
    "StreamManager",
    # Error handling
    "ErrorClassifier",
    "ErrorHandler",
    "ErrorRecoveryStrategy",
    "ErrorSeverity",
    "ErrorType",
    "StreamError",
    # Retry management
    "HTTPRetryManager",
    "RetryConfig",
    "RetryManager",
    # URL resolution
    "MediaURLResolver",
    "get_url_resolver",
    # Process monitoring
    "FFmpegWatchdog",
    "get_ffmpeg_watchdog",
    # Session management (Tunarr)
    "SessionManager",
    "StreamSession",
    "SessionState",
    "SessionErrorType",
    "get_session_manager",
    "init_session_manager",
    # Stream throttling (dizqueTV)
    "StreamThrottler",
    "ThrottleConfig",
    "ThrottleMode",
    "ThrottledStreamWrapper",
    "create_throttled_stream",
    # Error screens (dizqueTV)
    "ErrorScreenGenerator",
    "ErrorScreenConfig",
    "ErrorScreenMessage",
    "ErrorVisualMode",
    "ErrorAudioMode",
    "get_error_screen_generator",
    "generate_quick_error_stream",
]
