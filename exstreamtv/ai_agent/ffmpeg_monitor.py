"""
FFmpeg AI Monitor for intelligent process monitoring and diagnostics.

Provides AI-powered FFmpeg monitoring:
- Stderr parsing in real-time
- Progress tracking: frame, fps, bitrate, speed, time
- Error classification by type and severity
- Performance anomaly detection
- AI diagnosis for root cause analysis
- Predictive warnings for impending failures
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FFmpegErrorType(str, Enum):
    """Types of FFmpeg errors."""
    
    CONNECTION_TIMEOUT = "connection_timeout"
    CONNECTION_REFUSED = "connection_refused"
    HTTP_ERROR = "http_error"
    CODEC_ERROR = "codec_error"
    DECODER_ERROR = "decoder_error"
    ENCODER_ERROR = "encoder_error"
    MUXER_ERROR = "muxer_error"
    IO_ERROR = "io_error"
    MEMORY_ERROR = "memory_error"
    PERMISSION_ERROR = "permission_error"
    FORMAT_ERROR = "format_error"
    STREAM_ERROR = "stream_error"
    HARDWARE_ERROR = "hardware_error"
    UNKNOWN = "unknown"


class FFmpegSeverity(str, Enum):
    """Severity of FFmpeg issues."""
    
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    """Health status of a channel."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"


@dataclass
class FFmpegProgress:
    """FFmpeg encoding progress metrics."""
    
    timestamp: datetime
    frame: int = 0
    fps: float = 0.0
    bitrate_kbps: float = 0.0
    speed: float = 0.0
    time_str: str = "00:00:00.00"
    size_bytes: int = 0
    dup_frames: int = 0
    drop_frames: int = 0
    
    @property
    def time_seconds(self) -> float:
        """Convert time string to seconds."""
        try:
            parts = self.time_str.split(":")
            if len(parts) == 3:
                h, m, s = parts
                return int(h) * 3600 + int(m) * 60 + float(s)
        except (ValueError, AttributeError):
            pass
        return 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "frame": self.frame,
            "fps": self.fps,
            "bitrate_kbps": self.bitrate_kbps,
            "speed": self.speed,
            "time": self.time_str,
            "time_seconds": self.time_seconds,
            "size_bytes": self.size_bytes,
            "dup_frames": self.dup_frames,
            "drop_frames": self.drop_frames,
        }


@dataclass
class FFmpegError:
    """A detected FFmpeg error."""
    
    error_id: str
    timestamp: datetime
    channel_id: int
    error_type: FFmpegErrorType
    severity: FFmpegSeverity
    message: str
    raw_line: str
    
    # Diagnosis
    suggested_fix: Optional[str] = None
    is_recoverable: bool = True
    requires_restart: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_id": self.error_id,
            "timestamp": self.timestamp.isoformat(),
            "channel_id": self.channel_id,
            "error_type": self.error_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
            "is_recoverable": self.is_recoverable,
            "requires_restart": self.requires_restart,
        }


@dataclass
class ChannelHealthMetrics:
    """Health metrics for a channel."""
    
    channel_id: int
    status: HealthStatus = HealthStatus.HEALTHY
    
    # Performance
    current_fps: float = 0.0
    expected_fps: float = 30.0
    current_speed: float = 1.0
    current_bitrate_kbps: float = 0.0
    target_bitrate_kbps: float = 4000.0
    
    # Health tracking
    last_output_at: Optional[datetime] = None
    uptime_seconds: float = 0.0
    dropped_frames: int = 0
    duplicate_frames: int = 0
    error_count: int = 0
    restart_count: int = 0
    
    # Recent history
    recent_errors: list[FFmpegError] = field(default_factory=list)
    progress_history: list[FFmpegProgress] = field(default_factory=list)
    
    @property
    def fps_ratio(self) -> float:
        """Get FPS as ratio of expected."""
        if self.expected_fps <= 0:
            return 1.0
        return self.current_fps / self.expected_fps
    
    @property
    def is_degraded(self) -> bool:
        """Check if performance is degraded."""
        return (
            self.current_speed < 0.9
            or self.fps_ratio < 0.8
            or self.dropped_frames > 100
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "channel_id": self.channel_id,
            "status": self.status.value,
            "current_fps": self.current_fps,
            "expected_fps": self.expected_fps,
            "fps_ratio": self.fps_ratio,
            "current_speed": self.current_speed,
            "current_bitrate_kbps": self.current_bitrate_kbps,
            "last_output_at": self.last_output_at.isoformat() if self.last_output_at else None,
            "uptime_seconds": self.uptime_seconds,
            "dropped_frames": self.dropped_frames,
            "duplicate_frames": self.duplicate_frames,
            "error_count": self.error_count,
            "restart_count": self.restart_count,
            "is_degraded": self.is_degraded,
        }


@dataclass
class FailurePrediction:
    """Prediction of impending failure."""
    
    prediction_id: str
    channel_id: int
    timestamp: datetime
    confidence: float  # 0.0 - 1.0
    predicted_failure_type: FFmpegErrorType
    predicted_time_to_failure_seconds: float
    reason: str
    recommended_action: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_id": self.prediction_id,
            "channel_id": self.channel_id,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "predicted_failure_type": self.predicted_failure_type.value,
            "predicted_time_to_failure_seconds": self.predicted_time_to_failure_seconds,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
        }


@dataclass
class AIAnalysis:
    """AI analysis result for an error."""
    
    error_id: str
    analysis_timestamp: datetime
    root_cause: str
    suggested_fixes: list[str]
    confidence: float
    requires_human_intervention: bool = False
    additional_context: dict[str, Any] = field(default_factory=dict)


class FFmpegAIMonitor:
    """
    AI-powered FFmpeg monitoring and diagnostics.
    
    Features:
    - Real-time stderr parsing
    - Progress metric extraction
    - Error classification
    - Performance anomaly detection
    - AI-assisted diagnosis
    - Failure prediction
    
    Usage:
        monitor = FFmpegAIMonitor()
        
        # Process FFmpeg stderr
        async for line in ffmpeg_stderr:
            event = await monitor.parse_stderr_line(line, channel_id)
            if event and event.is_error:
                analysis = await monitor.diagnose_error(event)
        
        # Get channel health
        health = monitor.get_channel_health(channel_id)
        
        # Check for predictions
        prediction = await monitor.predict_failure(channel_id)
    """
    
    # Patterns for parsing FFmpeg output
    PATTERNS = {
        "progress": re.compile(
            r"frame=\s*(\d+)\s+fps=\s*([\d.]+)\s+.*?"
            r"bitrate=\s*([\d.]+)(\w+)/s\s+.*?"
            r"speed=\s*([\d.]+)x"
        ),
        "time": re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})"),
        "size": re.compile(r"size=\s*(\d+)(\w+)"),
        "dup": re.compile(r"dup=(\d+)"),
        "drop": re.compile(r"drop=(\d+)"),
        "error_http": re.compile(r"HTTP error (\d+)"),
        "error_connection": re.compile(r"Connection (refused|timed out|reset)"),
        "error_codec": re.compile(r"(Decoder|Encoder|Codec) .* not found"),
        "error_io": re.compile(r"(Input/output error|No such file|Permission denied)"),
        "error_hardware": re.compile(r"(videotoolbox|nvenc|qsv|vaapi).*error", re.I),
    }
    
    # Error patterns with classification
    ERROR_PATTERNS = [
        (re.compile(r"Connection timed out", re.I), FFmpegErrorType.CONNECTION_TIMEOUT, FFmpegSeverity.ERROR),
        (re.compile(r"Connection refused", re.I), FFmpegErrorType.CONNECTION_REFUSED, FFmpegSeverity.ERROR),
        (re.compile(r"HTTP error (\d{3})", re.I), FFmpegErrorType.HTTP_ERROR, FFmpegSeverity.ERROR),
        (re.compile(r"Decoder .* not found", re.I), FFmpegErrorType.DECODER_ERROR, FFmpegSeverity.CRITICAL),
        (re.compile(r"Encoder .* not found", re.I), FFmpegErrorType.ENCODER_ERROR, FFmpegSeverity.CRITICAL),
        (re.compile(r"Invalid data found", re.I), FFmpegErrorType.FORMAT_ERROR, FFmpegSeverity.WARNING),
        (re.compile(r"Permission denied", re.I), FFmpegErrorType.PERMISSION_ERROR, FFmpegSeverity.CRITICAL),
        (re.compile(r"No such file", re.I), FFmpegErrorType.IO_ERROR, FFmpegSeverity.CRITICAL),
        (re.compile(r"Out of memory", re.I), FFmpegErrorType.MEMORY_ERROR, FFmpegSeverity.CRITICAL),
        (re.compile(r"videotoolbox.*error", re.I), FFmpegErrorType.HARDWARE_ERROR, FFmpegSeverity.ERROR),
        (re.compile(r"nvenc.*error", re.I), FFmpegErrorType.HARDWARE_ERROR, FFmpegSeverity.ERROR),
        (re.compile(r"Stream.*error", re.I), FFmpegErrorType.STREAM_ERROR, FFmpegSeverity.WARNING),
    ]
    
    def __init__(self):
        """Initialize the monitor."""
        self._channel_metrics: dict[int, ChannelHealthMetrics] = {}
        self._error_history: list[FFmpegError] = []
        self._predictions: dict[int, FailurePrediction] = {}
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._on_error_callbacks: list[Callable] = []
        self._on_degraded_callbacks: list[Callable] = []
        self._on_prediction_callbacks: list[Callable] = []
        
        # Error counter for IDs
        self._error_counter = 0
        self._prediction_counter = 0
        
        logger.info("FFmpegAIMonitor initialized")
    
    async def parse_stderr_line(
        self,
        line: str,
        channel_id: int,
    ) -> Optional[FFmpegError]:
        """
        Parse FFmpeg stderr line and detect issues.
        
        Args:
            line: FFmpeg stderr line
            channel_id: Channel ID
            
        Returns:
            FFmpegError if error detected, None otherwise
        """
        line = line.strip()
        if not line:
            return None
        
        async with self._lock:
            # Ensure metrics exist for channel
            if channel_id not in self._channel_metrics:
                self._channel_metrics[channel_id] = ChannelHealthMetrics(channel_id=channel_id)
            
            metrics = self._channel_metrics[channel_id]
        
        # Check for progress line
        progress = self._parse_progress(line)
        if progress:
            await self._update_progress(channel_id, progress)
            return None
        
        # Check for errors
        error = self._detect_error(line, channel_id)
        if error:
            await self._record_error(error)
            return error
        
        return None
    
    def _parse_progress(self, line: str) -> Optional[FFmpegProgress]:
        """Parse progress metrics from line."""
        match = self.PATTERNS["progress"].search(line)
        if not match:
            return None
        
        progress = FFmpegProgress(
            timestamp=datetime.utcnow(),
            frame=int(match.group(1)),
            fps=float(match.group(2)),
            bitrate_kbps=float(match.group(3)),
            speed=float(match.group(5)),
        )
        
        # Parse time
        time_match = self.PATTERNS["time"].search(line)
        if time_match:
            progress.time_str = time_match.group(1)
        
        # Parse dup/drop
        dup_match = self.PATTERNS["dup"].search(line)
        if dup_match:
            progress.dup_frames = int(dup_match.group(1))
        
        drop_match = self.PATTERNS["drop"].search(line)
        if drop_match:
            progress.drop_frames = int(drop_match.group(1))
        
        return progress
    
    def _detect_error(self, line: str, channel_id: int) -> Optional[FFmpegError]:
        """Detect and classify errors from line."""
        for pattern, error_type, severity in self.ERROR_PATTERNS:
            if pattern.search(line):
                self._error_counter += 1
                
                return FFmpegError(
                    error_id=f"ffmpeg_err_{self._error_counter}",
                    timestamp=datetime.utcnow(),
                    channel_id=channel_id,
                    error_type=error_type,
                    severity=severity,
                    message=line[:200],
                    raw_line=line,
                    is_recoverable=severity != FFmpegSeverity.CRITICAL,
                    requires_restart=severity in (FFmpegSeverity.ERROR, FFmpegSeverity.CRITICAL),
                )
        
        # Generic error detection
        if "error" in line.lower():
            self._error_counter += 1
            return FFmpegError(
                error_id=f"ffmpeg_err_{self._error_counter}",
                timestamp=datetime.utcnow(),
                channel_id=channel_id,
                error_type=FFmpegErrorType.UNKNOWN,
                severity=FFmpegSeverity.WARNING,
                message=line[:200],
                raw_line=line,
            )
        
        return None
    
    async def _update_progress(self, channel_id: int, progress: FFmpegProgress) -> None:
        """Update channel metrics with progress."""
        async with self._lock:
            metrics = self._channel_metrics[channel_id]
            
            # Update current values
            metrics.current_fps = progress.fps
            metrics.current_speed = progress.speed
            metrics.current_bitrate_kbps = progress.bitrate_kbps
            metrics.last_output_at = progress.timestamp
            metrics.dropped_frames = progress.drop_frames
            metrics.duplicate_frames = progress.dup_frames
            
            # Add to history (keep last 60 samples)
            metrics.progress_history.append(progress)
            if len(metrics.progress_history) > 60:
                metrics.progress_history = metrics.progress_history[-60:]
            
            # Update status
            if metrics.is_degraded:
                if metrics.status == HealthStatus.HEALTHY:
                    metrics.status = HealthStatus.DEGRADED
                    await self._notify_degraded(channel_id, metrics)
            else:
                metrics.status = HealthStatus.HEALTHY
    
    async def _record_error(self, error: FFmpegError) -> None:
        """Record an error and notify callbacks."""
        async with self._lock:
            self._error_history.append(error)
            
            # Keep last 1000 errors
            if len(self._error_history) > 1000:
                self._error_history = self._error_history[-1000:]
            
            # Update channel metrics
            if error.channel_id in self._channel_metrics:
                metrics = self._channel_metrics[error.channel_id]
                metrics.error_count += 1
                metrics.recent_errors.append(error)
                
                if len(metrics.recent_errors) > 20:
                    metrics.recent_errors = metrics.recent_errors[-20:]
                
                # Update status based on severity
                if error.severity == FFmpegSeverity.CRITICAL:
                    metrics.status = HealthStatus.FAILED
                elif error.severity == FFmpegSeverity.ERROR:
                    metrics.status = HealthStatus.UNHEALTHY
        
        # Notify callbacks
        for callback in self._on_error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error)
                else:
                    callback(error)
            except Exception as e:
                logger.error(f"Error callback failed: {e}")
    
    async def _notify_degraded(self, channel_id: int, metrics: ChannelHealthMetrics) -> None:
        """Notify callbacks about degraded performance."""
        for callback in self._on_degraded_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(channel_id, metrics)
                else:
                    callback(channel_id, metrics)
            except Exception as e:
                logger.error(f"Degraded callback failed: {e}")
    
    async def diagnose_error(self, error: FFmpegError) -> AIAnalysis:
        """
        Use AI to diagnose FFmpeg error and suggest fixes.
        
        Args:
            error: The error to diagnose
            
        Returns:
            AIAnalysis with root cause and fixes
        """
        # Rule-based diagnosis (can be extended with actual AI)
        fixes = []
        root_cause = "Unknown error"
        requires_human = False
        
        if error.error_type == FFmpegErrorType.CONNECTION_TIMEOUT:
            root_cause = "Network connection timed out to media source"
            fixes = [
                "Check network connectivity",
                "Verify media URL is accessible",
                "Increase connection timeout in FFmpeg settings",
                "Check if source server is responding",
            ]
        
        elif error.error_type == FFmpegErrorType.HTTP_ERROR:
            root_cause = "HTTP error from media server"
            fixes = [
                "Check if media URL has expired",
                "Refresh media source credentials",
                "Verify media file still exists",
            ]
        
        elif error.error_type == FFmpegErrorType.HARDWARE_ERROR:
            root_cause = "Hardware encoder/decoder error"
            fixes = [
                "Fall back to software encoding",
                "Check GPU driver status",
                "Reduce concurrent hardware encoding channels",
            ]
            requires_human = True
        
        elif error.error_type == FFmpegErrorType.CODEC_ERROR:
            root_cause = "Unsupported or missing codec"
            fixes = [
                "Install required codec",
                "Use software fallback encoding",
                "Transcode to supported format",
            ]
            requires_human = True
        
        elif error.error_type == FFmpegErrorType.MEMORY_ERROR:
            root_cause = "System out of memory"
            fixes = [
                "Reduce number of concurrent channels",
                "Lower encoding quality/bitrate",
                "Restart application to free memory",
                "Add more system RAM",
            ]
            requires_human = True
        
        else:
            root_cause = f"FFmpeg error: {error.message}"
            fixes = [
                "Check FFmpeg logs for details",
                "Restart the affected channel",
                "Verify media source accessibility",
            ]
        
        return AIAnalysis(
            error_id=error.error_id,
            analysis_timestamp=datetime.utcnow(),
            root_cause=root_cause,
            suggested_fixes=fixes,
            confidence=0.75,
            requires_human_intervention=requires_human,
        )
    
    async def predict_failure(self, channel_id: int) -> Optional[FailurePrediction]:
        """
        Predict impending failures based on trends.
        
        Args:
            channel_id: Channel to analyze
            
        Returns:
            FailurePrediction if failure predicted, None otherwise
        """
        async with self._lock:
            if channel_id not in self._channel_metrics:
                return None
            
            metrics = self._channel_metrics[channel_id]
        
        # Analyze recent performance trends
        if len(metrics.progress_history) < 10:
            return None
        
        recent = metrics.progress_history[-10:]
        
        # Check for declining speed
        speeds = [p.speed for p in recent]
        speed_trend = speeds[-1] - speeds[0]
        
        if speed_trend < -0.3 and speeds[-1] < 0.5:
            self._prediction_counter += 1
            prediction = FailurePrediction(
                prediction_id=f"pred_{self._prediction_counter}",
                channel_id=channel_id,
                timestamp=datetime.utcnow(),
                confidence=0.7,
                predicted_failure_type=FFmpegErrorType.STREAM_ERROR,
                predicted_time_to_failure_seconds=30,
                reason=f"Encoding speed declining rapidly: {speeds[-1]:.2f}x",
                recommended_action="Restart channel or reduce encoding quality",
            )
            
            self._predictions[channel_id] = prediction
            
            # Notify callbacks
            for callback in self._on_prediction_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(prediction)
                    else:
                        callback(prediction)
                except Exception as e:
                    logger.error(f"Prediction callback failed: {e}")
            
            return prediction
        
        # Check for high drop rate
        drop_rate = recent[-1].drop_frames - recent[0].drop_frames
        if drop_rate > 50:
            self._prediction_counter += 1
            return FailurePrediction(
                prediction_id=f"pred_{self._prediction_counter}",
                channel_id=channel_id,
                timestamp=datetime.utcnow(),
                confidence=0.6,
                predicted_failure_type=FFmpegErrorType.STREAM_ERROR,
                predicted_time_to_failure_seconds=60,
                reason=f"High frame drop rate: {drop_rate} frames in 10 samples",
                recommended_action="Check source stream stability",
            )
        
        return None
    
    def get_channel_health(self, channel_id: int) -> ChannelHealthMetrics:
        """Get current health metrics for a channel."""
        if channel_id not in self._channel_metrics:
            return ChannelHealthMetrics(channel_id=channel_id)
        return self._channel_metrics[channel_id]
    
    def get_all_health(self) -> dict[int, ChannelHealthMetrics]:
        """Get health metrics for all channels."""
        return dict(self._channel_metrics)
    
    def on_error(self, callback: Callable) -> None:
        """Register callback for errors."""
        self._on_error_callbacks.append(callback)
    
    def on_degraded(self, callback: Callable) -> None:
        """Register callback for degraded performance."""
        self._on_degraded_callbacks.append(callback)
    
    def on_prediction(self, callback: Callable) -> None:
        """Register callback for failure predictions."""
        self._on_prediction_callbacks.append(callback)
    
    def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        return {
            "channels_monitored": len(self._channel_metrics),
            "total_errors": len(self._error_history),
            "active_predictions": len(self._predictions),
            "channels": {
                ch_id: metrics.to_dict()
                for ch_id, metrics in self._channel_metrics.items()
            },
        }


# Global monitor instance
_ffmpeg_monitor: Optional[FFmpegAIMonitor] = None


def get_ffmpeg_monitor() -> FFmpegAIMonitor:
    """Get the global FFmpegAIMonitor instance."""
    global _ffmpeg_monitor
    if _ffmpeg_monitor is None:
        _ffmpeg_monitor = FFmpegAIMonitor()
    return _ffmpeg_monitor
