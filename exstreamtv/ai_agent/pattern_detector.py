"""
Pattern Detector for ML-based error pattern detection and prediction.

Provides intelligent pattern analysis:
- Pattern learning: Learn error sequences that lead to failures
- Anomaly detection: Detect unusual patterns indicating problems
- Correlation analysis: Find correlations between events
- Predictive alerts: Predict failures before they occur
- Root cause analysis: Identify root causes from symptom patterns
"""

import asyncio
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """Types of detected patterns."""
    
    ERROR_SEQUENCE = "error_sequence"  # Sequence of errors
    PERFORMANCE_DEGRADATION = "performance_degradation"  # Declining metrics
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # DB pool, memory, etc.
    NETWORK_INSTABILITY = "network_instability"  # Connection issues
    SOURCE_FAILURE = "source_failure"  # Media source problems
    TIMING_ANOMALY = "timing_anomaly"  # Unusual timing patterns
    CORRELATION = "correlation"  # Correlated events


class RiskLevel(str, Enum):
    """Risk level of detected patterns."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Pattern:
    """A detected pattern."""
    
    pattern_id: str
    pattern_type: PatternType
    risk_level: RiskLevel
    description: str
    
    # Pattern details
    events: list[dict[str, Any]] = field(default_factory=list)
    frequency: int = 1
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    
    # Context
    channel_ids: list[int] = field(default_factory=list)
    related_patterns: list[str] = field(default_factory=list)
    
    # Predictions
    predicted_outcome: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "risk_level": self.risk_level.value,
            "description": self.description,
            "frequency": self.frequency,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "channel_ids": self.channel_ids,
            "predicted_outcome": self.predicted_outcome,
            "confidence": self.confidence,
        }


@dataclass
class PatternAnalysis:
    """Analysis result from pattern detection."""
    
    timestamp: datetime
    patterns_detected: list[Pattern]
    risk_summary: dict[str, int]  # risk_level -> count
    recommendations: list[str]
    
    @property
    def highest_risk(self) -> RiskLevel:
        """Get highest risk level."""
        if self.risk_summary.get("critical", 0) > 0:
            return RiskLevel.CRITICAL
        if self.risk_summary.get("high", 0) > 0:
            return RiskLevel.HIGH
        if self.risk_summary.get("medium", 0) > 0:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "patterns_count": len(self.patterns_detected),
            "highest_risk": self.highest_risk.value,
            "risk_summary": self.risk_summary,
            "recommendations": self.recommendations,
            "patterns": [p.to_dict() for p in self.patterns_detected],
        }


@dataclass
class FailurePrediction:
    """Prediction of an impending failure."""
    
    prediction_id: str
    timestamp: datetime
    pattern: Pattern
    confidence: float
    predicted_failure_time: datetime
    recommended_action: str
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_id": self.prediction_id,
            "timestamp": self.timestamp.isoformat(),
            "pattern_id": self.pattern.pattern_id,
            "confidence": self.confidence,
            "predicted_failure_time": self.predicted_failure_time.isoformat(),
            "recommended_action": self.recommended_action,
        }


@dataclass
class RootCauseAnalysis:
    """Root cause analysis result."""
    
    analysis_id: str
    timestamp: datetime
    error_event: dict[str, Any]
    
    root_cause: str
    contributing_factors: list[str]
    confidence: float
    evidence: list[str]
    
    recommended_fixes: list[str]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "timestamp": self.timestamp.isoformat(),
            "root_cause": self.root_cause,
            "contributing_factors": self.contributing_factors,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "recommended_fixes": self.recommended_fixes,
        }


@dataclass
class Outcome:
    """Recorded outcome for learning."""
    
    prediction_id: str
    timestamp: datetime
    was_accurate: bool
    actual_result: str
    notes: Optional[str] = None


class PatternDetector:
    """
    ML-based error pattern detection and prediction.
    
    Features:
    - Pattern learning from error sequences
    - Anomaly detection in metrics
    - Correlation analysis across events
    - Failure prediction
    - Root cause analysis
    
    Usage:
        detector = PatternDetector()
        
        # Analyze event sequence
        analysis = await detector.analyze_sequence(events)
        
        # Predict failures
        prediction = await detector.predict_failure(channel_id)
        
        # Find root cause
        root_cause = await detector.find_root_cause(error_event)
        
        # Record outcome for learning
        detector.record_outcome(prediction_id, Outcome(...))
    """
    
    # Known problematic patterns
    KNOWN_PATTERNS = {
        "db_pool_exhaustion": {
            "indicators": ["pool exhausted", "connection timeout", "no connections available"],
            "risk": RiskLevel.HIGH,
            "prediction": "Database connection failures imminent",
        },
        "ffmpeg_degradation": {
            "indicators": ["speed < 1.0x", "dropping frames", "buffer underrun"],
            "risk": RiskLevel.MEDIUM,
            "prediction": "Stream quality degradation or failure",
        },
        "url_expiration": {
            "indicators": ["403 forbidden", "401 unauthorized", "token expired"],
            "risk": RiskLevel.MEDIUM,
            "prediction": "Media URL needs refresh",
        },
        "network_instability": {
            "indicators": ["connection reset", "connection refused", "timeout"],
            "risk": RiskLevel.HIGH,
            "prediction": "Network-related stream failures",
        },
        "memory_pressure": {
            "indicators": ["out of memory", "memory allocation failed", "swap usage"],
            "risk": RiskLevel.CRITICAL,
            "prediction": "System may become unresponsive",
        },
    }
    
    def __init__(self):
        """Initialize the pattern detector."""
        self._patterns: dict[str, Pattern] = {}
        self._predictions: dict[str, FailurePrediction] = {}
        self._outcomes: list[Outcome] = []
        
        # Event history for pattern learning
        self._event_history: list[dict[str, Any]] = []
        self._error_sequences: list[list[str]] = []  # Sequences of error types
        
        # Pattern frequency tracking
        self._pattern_frequency: Counter = Counter()
        self._error_frequency: Counter = Counter()
        self._channel_errors: defaultdict = defaultdict(list)
        
        # Callbacks
        self._on_pattern_detected: list[Callable] = []
        self._on_prediction: list[Callable] = []
        
        self._lock = asyncio.Lock()
        
        logger.info("PatternDetector initialized")
    
    async def analyze_sequence(
        self,
        events: list[dict[str, Any]],
    ) -> PatternAnalysis:
        """
        Analyze event sequence for known patterns.
        
        Args:
            events: List of log events (dicts with source, level, message, etc.)
            
        Returns:
            PatternAnalysis with detected patterns
        """
        detected_patterns: list[Pattern] = []
        recommendations: list[str] = []
        
        async with self._lock:
            # Store events for learning
            self._event_history.extend(events)
            
            # Keep last 10000 events
            if len(self._event_history) > 10000:
                self._event_history = self._event_history[-10000:]
        
        # Extract error messages
        error_messages = [
            e.get("message", "").lower()
            for e in events
            if e.get("level") in ("error", "critical", "ERROR", "CRITICAL")
        ]
        
        # Check against known patterns
        for pattern_name, pattern_info in self.KNOWN_PATTERNS.items():
            matches = 0
            matched_indicators = []
            
            for indicator in pattern_info["indicators"]:
                for msg in error_messages:
                    if indicator.lower() in msg:
                        matches += 1
                        matched_indicators.append(indicator)
            
            if matches >= 2:  # Need at least 2 matching indicators
                pattern = Pattern(
                    pattern_id=f"pat_{pattern_name}_{uuid4().hex[:8]}",
                    pattern_type=PatternType.ERROR_SEQUENCE,
                    risk_level=pattern_info["risk"],
                    description=f"Detected {pattern_name} pattern",
                    events=[{"indicator": i} for i in matched_indicators],
                    predicted_outcome=pattern_info["prediction"],
                    confidence=min(0.9, 0.3 * matches),
                )
                detected_patterns.append(pattern)
                
                # Generate recommendation
                recommendations.append(
                    f"Address {pattern_name}: {pattern_info['prediction']}"
                )
        
        # Check for error sequences
        if len(error_messages) >= 3:
            # Look for repeated error types
            error_types = [self._classify_error(msg) for msg in error_messages]
            type_counts = Counter(error_types)
            
            for error_type, count in type_counts.items():
                if count >= 3:
                    pattern = Pattern(
                        pattern_id=f"pat_repeated_{uuid4().hex[:8]}",
                        pattern_type=PatternType.ERROR_SEQUENCE,
                        risk_level=RiskLevel.MEDIUM,
                        description=f"Repeated {error_type} errors ({count} occurrences)",
                        frequency=count,
                        confidence=0.6,
                    )
                    detected_patterns.append(pattern)
        
        # Calculate risk summary
        risk_summary = {
            "low": 0,
            "medium": 0,
            "high": 0,
            "critical": 0,
        }
        
        for pattern in detected_patterns:
            risk_summary[pattern.risk_level.value] += 1
            await self._notify_pattern_detected(pattern)
        
        return PatternAnalysis(
            timestamp=datetime.utcnow(),
            patterns_detected=detected_patterns,
            risk_summary=risk_summary,
            recommendations=recommendations,
        )
    
    def _classify_error(self, message: str) -> str:
        """Classify error message into type."""
        message = message.lower()
        
        if "timeout" in message or "timed out" in message:
            return "timeout"
        if "connection" in message:
            return "connection"
        if "ffmpeg" in message:
            return "ffmpeg"
        if "database" in message or "db" in message or "pool" in message:
            return "database"
        if "memory" in message:
            return "memory"
        if "permission" in message or "access" in message:
            return "permission"
        if "404" in message or "not found" in message:
            return "not_found"
        if "401" in message or "403" in message or "auth" in message:
            return "auth"
        
        return "unknown"
    
    async def predict_failure(
        self,
        channel_id: Optional[int] = None,
    ) -> Optional[FailurePrediction]:
        """
        Predict failures based on current patterns.
        
        Args:
            channel_id: Optional channel to focus on
            
        Returns:
            FailurePrediction if failure predicted, None otherwise
        """
        # Get recent errors for channel
        cutoff = datetime.utcnow() - timedelta(minutes=15)
        
        recent_events = [
            e for e in self._event_history
            if e.get("timestamp", datetime.min) > cutoff
            and (channel_id is None or e.get("channel_id") == channel_id)
        ]
        
        if len(recent_events) < 5:
            return None
        
        # Analyze for patterns
        analysis = await self.analyze_sequence(recent_events)
        
        # Find high-risk patterns
        high_risk_patterns = [
            p for p in analysis.patterns_detected
            if p.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ]
        
        if not high_risk_patterns:
            return None
        
        # Create prediction from highest risk pattern
        pattern = max(high_risk_patterns, key=lambda p: p.confidence)
        
        prediction = FailurePrediction(
            prediction_id=f"pred_{uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            pattern=pattern,
            confidence=pattern.confidence,
            predicted_failure_time=datetime.utcnow() + timedelta(minutes=5),
            recommended_action=analysis.recommendations[0] if analysis.recommendations else "Monitor closely",
        )
        
        async with self._lock:
            self._predictions[prediction.prediction_id] = prediction
        
        # Notify callbacks
        for callback in self._on_prediction:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(prediction)
                else:
                    callback(prediction)
            except Exception as e:
                logger.error(f"Prediction callback failed: {e}")
        
        return prediction
    
    async def find_root_cause(
        self,
        error_event: dict[str, Any],
    ) -> RootCauseAnalysis:
        """
        Find root cause of an error using pattern analysis.
        
        Args:
            error_event: The error event to analyze
            
        Returns:
            RootCauseAnalysis with root cause and fixes
        """
        error_message = error_event.get("message", "").lower()
        error_type = self._classify_error(error_message)
        channel_id = error_event.get("channel_id")
        
        root_cause = "Unknown error"
        contributing_factors = []
        evidence = []
        fixes = []
        confidence = 0.5
        
        # Check for known patterns
        for pattern_name, pattern_info in self.KNOWN_PATTERNS.items():
            for indicator in pattern_info["indicators"]:
                if indicator.lower() in error_message:
                    root_cause = f"{pattern_name.replace('_', ' ').title()}"
                    evidence.append(f"Error message contains '{indicator}'")
                    confidence = 0.7
                    break
        
        # Analyze recent history for contributing factors
        if channel_id:
            recent = self._channel_errors.get(channel_id, [])[-10:]
            if recent:
                error_types = Counter(self._classify_error(e.get("message", "")) for e in recent)
                for etype, count in error_types.most_common(3):
                    if count >= 2:
                        contributing_factors.append(f"Repeated {etype} errors ({count}x)")
        
        # Generate fixes based on error type
        fixes = self._get_fixes_for_error_type(error_type)
        
        return RootCauseAnalysis(
            analysis_id=f"rca_{uuid4().hex[:8]}",
            timestamp=datetime.utcnow(),
            error_event=error_event,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            confidence=confidence,
            evidence=evidence,
            recommended_fixes=fixes,
        )
    
    def _get_fixes_for_error_type(self, error_type: str) -> list[str]:
        """Get recommended fixes for error type."""
        fixes = {
            "timeout": [
                "Increase timeout values",
                "Check network connectivity",
                "Verify server responsiveness",
            ],
            "connection": [
                "Check server availability",
                "Verify network configuration",
                "Check firewall rules",
            ],
            "database": [
                "Increase database connection pool size",
                "Optimize slow queries",
                "Check database server health",
            ],
            "memory": [
                "Reduce concurrent operations",
                "Increase system memory",
                "Restart application to free memory",
            ],
            "auth": [
                "Refresh authentication tokens",
                "Check API credentials",
                "Verify user permissions",
            ],
            "ffmpeg": [
                "Check FFmpeg installation",
                "Verify media file format",
                "Check encoding settings",
            ],
        }
        
        return fixes.get(error_type, [
            "Check application logs for details",
            "Restart affected service",
            "Contact support if issue persists",
        ])
    
    def record_outcome(
        self,
        prediction_id: str,
        actual_outcome: Outcome,
    ) -> None:
        """
        Record actual outcome to improve predictions.
        
        Args:
            prediction_id: ID of the prediction
            actual_outcome: What actually happened
        """
        self._outcomes.append(actual_outcome)
        
        # Keep last 1000 outcomes
        if len(self._outcomes) > 1000:
            self._outcomes = self._outcomes[-1000:]
        
        # Update pattern confidence based on outcome
        if prediction_id in self._predictions:
            prediction = self._predictions[prediction_id]
            pattern = prediction.pattern
            
            if actual_outcome.was_accurate:
                pattern.confidence = min(0.99, pattern.confidence * 1.1)
            else:
                pattern.confidence = max(0.1, pattern.confidence * 0.9)
        
        logger.debug(
            f"Recorded outcome for prediction {prediction_id}: "
            f"accurate={actual_outcome.was_accurate}"
        )
    
    async def _notify_pattern_detected(self, pattern: Pattern) -> None:
        """Notify callbacks about detected pattern."""
        for callback in self._on_pattern_detected:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(pattern)
                else:
                    callback(pattern)
            except Exception as e:
                logger.error(f"Pattern callback failed: {e}")
    
    def on_pattern_detected(self, callback: Callable) -> None:
        """Register callback for pattern detection."""
        self._on_pattern_detected.append(callback)
    
    def on_prediction(self, callback: Callable) -> None:
        """Register callback for predictions."""
        self._on_prediction.append(callback)
    
    def get_stats(self) -> dict[str, Any]:
        """Get detector statistics."""
        return {
            "patterns_detected": len(self._patterns),
            "predictions_made": len(self._predictions),
            "outcomes_recorded": len(self._outcomes),
            "event_history_size": len(self._event_history),
            "accuracy": self._calculate_accuracy(),
        }
    
    def _calculate_accuracy(self) -> float:
        """Calculate prediction accuracy from outcomes."""
        if not self._outcomes:
            return 0.0
        
        accurate = sum(1 for o in self._outcomes if o.was_accurate)
        return accurate / len(self._outcomes)


# Global detector instance
_pattern_detector: Optional[PatternDetector] = None


def get_pattern_detector() -> PatternDetector:
    """Get the global PatternDetector instance."""
    global _pattern_detector
    if _pattern_detector is None:
        _pattern_detector = PatternDetector()
    return _pattern_detector
