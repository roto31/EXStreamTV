"""
Central error handling and recovery for streaming infrastructure.

Ported from StreamTV with all error types and recovery strategies preserved.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorType(str, Enum):
    """Classification of error types."""

    NETWORK_ERROR = "network_error"  # Connection failures, timeouts
    HTTP_401 = "http_401"  # Unauthorized
    HTTP_403 = "http_403"  # Forbidden
    HTTP_464 = "http_464"  # Archive.org quota/rate limit exceeded
    HTTP_500 = "http_500"  # Internal Server Error
    HTTP_OTHER = "http_other"  # Other HTTP errors (4xx, 5xx)
    AUTHENTICATION_ERROR = "authentication_error"  # Cookie/token failures
    CODEC_ERROR = "codec_error"  # FFmpeg codec issues
    STREAM_ERROR = "stream_error"  # Stream parsing/format errors
    CDN_ERROR = "cdn_error"  # CDN-specific issues
    QUOTA_ERROR = "quota_error"  # Quota/rate limit errors
    FORMAT_ERROR = "format_error"  # Unsupported format or format selection failure
    PERMISSION_ERROR = "permission_error"  # Privacy/geoblocking/access denied
    EXPIRATION_ERROR = "expiration_error"  # URL expired (enhanced HTTP_403)
    RATE_LIMIT_ERROR = "rate_limit_error"  # Rate limiting (enhanced QUOTA_ERROR)
    UNKNOWN = "unknown"  # Unclassified errors


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    LOW = "low"  # Recoverable, can retry
    MEDIUM = "medium"  # May require configuration change
    HIGH = "high"  # Requires manual intervention
    CRITICAL = "critical"  # System failure


@dataclass
class StreamError:
    """Represents a streaming error with context."""

    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    original_exception: Exception | None = None
    context: dict[str, Any] | None = None
    timestamp: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.context is None:
            self.context = {}


class ErrorClassifier:
    """Classifies errors into error types and severity."""

    @staticmethod
    def classify(error: Exception, context: dict[str, Any] | None = None) -> StreamError:
        """
        Classify an exception into a StreamError.

        Args:
            error: The exception to classify.
            context: Additional context about the error.

        Returns:
            StreamError with classified type and severity.
        """
        if context is None:
            context = {}

        error_str = str(error).lower()
        error_type = ErrorType.UNKNOWN
        severity = ErrorSeverity.MEDIUM

        # Format errors (check before HTTP errors as they may contain HTTP codes)
        if any(
            term in error_str
            for term in [
                "requested format is not available",
                "format is not available",
                "no suitable format",
                "format selection failed",
                "unable to download video",
                "format not found",
            ]
        ):
            error_type = ErrorType.FORMAT_ERROR
            severity = ErrorSeverity.MEDIUM

        # Permission/geoblocking errors
        elif any(
            term in error_str
            for term in [
                "private video",
                "video is private",
                "geoblocked",
                "not available in your country",
                "region restricted",
                "access denied",
                "permission denied",
                "this video is not available",
            ]
        ):
            error_type = ErrorType.PERMISSION_ERROR
            severity = ErrorSeverity.HIGH

        # URL expiration errors (enhanced 403 detection)
        elif any(
            term in error_str
            for term in [
                "url expired",
                "url may have expired",
                "expired",
                "signature.*expired",
            ]
        ) or (
            "403" in error_str
            and any(term in error_str for term in ["expire", "expired", "expiration"])
        ):
            error_type = ErrorType.EXPIRATION_ERROR
            severity = ErrorSeverity.MEDIUM

        # Rate limit errors (enhanced quota detection)
        elif any(
            term in error_str
            for term in [
                "rate limit",
                "rate limit exceeded",
                "too many requests",
                "429",
                "quota exceeded",
                "quota limit",
            ]
        ):
            error_type = ErrorType.RATE_LIMIT_ERROR
            severity = ErrorSeverity.HIGH

        # HTTP errors
        elif "401" in error_str or "unauthorized" in error_str:
            error_type = ErrorType.HTTP_401
            severity = ErrorSeverity.MEDIUM
        elif "403" in error_str or "forbidden" in error_str:
            if error_type != ErrorType.EXPIRATION_ERROR:
                error_type = ErrorType.HTTP_403
                severity = ErrorSeverity.MEDIUM
        elif (
            "464" in error_str
            or ("http 464" in error_str)
            or ("quota" in error_str and "archive" in error_str)
        ):
            error_type = ErrorType.HTTP_464
            severity = ErrorSeverity.HIGH
        elif "429" in error_str:
            error_type = ErrorType.RATE_LIMIT_ERROR
            severity = ErrorSeverity.HIGH
        elif "500" in error_str or "internal server error" in error_str:
            error_type = ErrorType.HTTP_500
            severity = ErrorSeverity.LOW
        elif any(code in error_str for code in ["400", "404", "502", "503", "504"]):
            error_type = ErrorType.HTTP_OTHER
            severity = ErrorSeverity.MEDIUM

        # Network errors (including DNS)
        elif any(
            term in error_str
            for term in [
                "timeout",
                "connection",
                "network",
                "dns",
                "nodename nor servname",
                "failed to resolve hostname",
                "cannot resolve hostname",
            ]
        ):
            error_type = ErrorType.NETWORK_ERROR
            severity = ErrorSeverity.LOW

        # Authentication errors
        elif any(term in error_str for term in ["cookie", "token", "auth", "login", "credential"]):
            error_type = ErrorType.AUTHENTICATION_ERROR
            severity = ErrorSeverity.MEDIUM

        # Codec errors
        elif any(term in error_str for term in ["codec", "encoder", "decoder"]):
            error_type = ErrorType.CODEC_ERROR
            severity = ErrorSeverity.HIGH

        # Stream errors
        elif any(term in error_str for term in ["stream", "m3u8", "playlist", "segment"]):
            error_type = ErrorType.STREAM_ERROR
            severity = ErrorSeverity.MEDIUM

        # CDN errors
        elif any(term in error_str for term in ["cdn", "edge", "mirror"]):
            error_type = ErrorType.CDN_ERROR
            severity = ErrorSeverity.LOW

        # Check context for additional hints
        if context:
            provider = context.get("provider", "").lower()

            # YouTube-specific errors
            if provider == "youtube":
                if "format" in error_str and (
                    "not available" in error_str or "unable" in error_str
                ):
                    error_type = ErrorType.FORMAT_ERROR
                    severity = ErrorSeverity.MEDIUM
                elif "private" in error_str or "unavailable" in error_str:
                    error_type = ErrorType.PERMISSION_ERROR
                    severity = ErrorSeverity.HIGH
                elif context.get("is_expired_url", False):
                    error_type = ErrorType.EXPIRATION_ERROR
                    severity = ErrorSeverity.MEDIUM

            # Archive.org-specific errors
            elif provider == "archive.org":
                if "quota" in error_str or "rate limit" in error_str:
                    error_type = ErrorType.RATE_LIMIT_ERROR
                    severity = ErrorSeverity.HIGH

            # Plex-specific errors
            elif provider == "plex":
                if "unauthorized" in error_str or "token" in error_str:
                    error_type = ErrorType.AUTHENTICATION_ERROR
                    severity = ErrorSeverity.MEDIUM

            # HTTP status code detection
            if context.get("http_status_code"):
                status = context["http_status_code"]
                if status == 401:
                    error_type = ErrorType.HTTP_401
                elif status == 403:
                    if context.get("is_expired_url", False) or "expired" in error_str:
                        error_type = ErrorType.EXPIRATION_ERROR
                    else:
                        error_type = ErrorType.HTTP_403
                elif status == 429:
                    error_type = ErrorType.RATE_LIMIT_ERROR
                    severity = ErrorSeverity.HIGH
                elif status == 464:
                    error_type = ErrorType.RATE_LIMIT_ERROR
                    severity = ErrorSeverity.HIGH
                elif status == 500:
                    error_type = ErrorType.HTTP_500
                elif 400 <= status < 500:
                    error_type = ErrorType.HTTP_OTHER
                    severity = ErrorSeverity.MEDIUM
                elif 500 <= status < 600:
                    error_type = ErrorType.HTTP_OTHER
                    severity = ErrorSeverity.LOW

        return StreamError(
            error_type=error_type,
            severity=severity,
            message=str(error),
            original_exception=error if isinstance(error, Exception) else None,
            context=context,
        )


class ErrorRecoveryStrategy:
    """Defines recovery strategies for different error types."""

    RECOVERY_STRATEGIES: dict[ErrorType, list[str]] = {
        ErrorType.FORMAT_ERROR: [
            "try_alternative_format",
            "retry_with_different_format_selector",
            "fallback_to_worst_format",
            "fallback_to_alternative_source",
        ],
        ErrorType.PERMISSION_ERROR: [
            "retry_with_different_cookies",
            "try_alternative_account",
            "fallback_to_alternative_source",
        ],
        ErrorType.EXPIRATION_ERROR: [
            "refresh_url",
            "retry_with_fresh_url",
            "retry_with_refreshed_cookies",
            "fallback_to_alternative_source",
        ],
        ErrorType.RATE_LIMIT_ERROR: [
            "retry_with_long_backoff",
            "switch_to_alternative_account",
            "retry_with_throttling",
            "fallback_to_alternative_source",
        ],
        ErrorType.HTTP_500: [
            "retry_without_cookies",
            "retry_with_different_user_agent",
            "try_alternative_cdn",
            "retry_with_minimal_headers",
            "fallback_to_alternative_source",
        ],
        ErrorType.HTTP_403: [
            "retry_with_refreshed_cookies",
            "retry_with_different_auth_method",
            "try_alternative_cdn",
            "fallback_to_alternative_source",
        ],
        ErrorType.HTTP_401: [
            "refresh_authentication",
            "retry_with_updated_credentials",
            "try_alternative_auth_method",
            "fallback_to_alternative_source",
        ],
        ErrorType.HTTP_464: [
            "retry_with_long_backoff",
            "try_alternative_cdn",
            "retry_without_cookies",
            "try_alternative_url_format",
            "retry_with_minimal_headers",
            "fallback_to_alternative_source",
        ],
        ErrorType.NETWORK_ERROR: [
            "retry_with_backoff",
            "retry_with_longer_timeout",
            "try_alternative_cdn",
            "fallback_to_alternative_source",
        ],
        ErrorType.CDN_ERROR: [
            "try_alternative_cdn",
            "retry_with_backoff",
            "fallback_to_alternative_source",
        ],
        ErrorType.AUTHENTICATION_ERROR: [
            "refresh_authentication",
            "reload_cookies",
            "retry_with_updated_credentials",
        ],
        ErrorType.CODEC_ERROR: [
            "try_different_codec",
            "fallback_to_alternative_source",
        ],
        ErrorType.STREAM_ERROR: [
            "retry_with_backoff",
            "try_alternative_format",
            "fallback_to_alternative_source",
        ],
    }

    @classmethod
    def get_strategies(cls, error_type: ErrorType) -> list[str]:
        """Get recovery strategies for an error type."""
        return cls.RECOVERY_STRATEGIES.get(
            error_type, ["retry_with_backoff", "fallback_to_alternative_source"]
        )


class ErrorHandler:
    """Central error handler for streaming operations."""

    def __init__(self, max_retries: int = 3, backoff_base: float = 1.0):
        """
        Initialize error handler.

        Args:
            max_retries: Maximum number of retry attempts.
            backoff_base: Base delay for exponential backoff (seconds).
        """
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.classifier = ErrorClassifier()
        self.error_history: list[StreamError] = []

    def handle_error(
        self,
        error: Exception,
        context: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> StreamError:
        """
        Handle an error by classifying it and determining recovery strategy.

        Args:
            error: The exception to handle.
            context: Additional context about the error.
            retry_count: Current retry attempt number.

        Returns:
            StreamError with classification and recovery strategies.
        """
        stream_error = self.classifier.classify(error, context)
        stream_error.retry_count = retry_count
        stream_error.max_retries = self.max_retries

        # Store in history
        self.error_history.append(stream_error)

        # Keep only last 100 errors
        if len(self.error_history) > 100:
            self.error_history = self.error_history[-100:]

        logger.warning(
            f"Error classified: {stream_error.error_type.value} "
            f"(severity: {stream_error.severity.value}, "
            f"retry: {retry_count}/{self.max_retries})"
        )

        return stream_error

    def should_retry(self, stream_error: StreamError) -> bool:
        """Determine if an error should be retried."""
        if stream_error.retry_count >= stream_error.max_retries:
            return False

        # Don't retry critical errors
        if stream_error.severity == ErrorSeverity.CRITICAL:
            return False

        # Always retry low severity errors
        if stream_error.severity == ErrorSeverity.LOW:
            return True

        # Retry medium/high severity errors if we haven't exceeded max retries
        return True

    def get_recovery_strategies(self, stream_error: StreamError) -> list[str]:
        """Get recovery strategies for an error."""
        return ErrorRecoveryStrategy.get_strategies(stream_error.error_type)

    def get_backoff_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay."""
        return self.backoff_base * (2**retry_count)

    def get_recent_errors(
        self,
        error_type: ErrorType | None = None,
        limit: int = 10,
    ) -> list[StreamError]:
        """Get recent errors, optionally filtered by type."""
        errors = self.error_history[-limit:]
        if error_type:
            errors = [e for e in errors if e.error_type == error_type]
        return errors
