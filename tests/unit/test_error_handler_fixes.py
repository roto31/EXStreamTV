"""Minimal tests for EXStreamTV error handler fixes (subprocess classification, backoff)."""
import pytest
from exstreamtv.streaming.error_handler import (
    ErrorType,
    ErrorClassifier,
    ErrorHandler,
    _BACKOFF_MULTIPLIERS,
    StreamError,
    ErrorSeverity,
)


def test_ytdlp_and_pipe_eof_error_types_exist() -> None:
    assert ErrorType.YTDLP_ERROR.value == "ytdlp_error"
    assert ErrorType.PIPE_EOF_ERROR.value == "pipe_eof_error"


def test_classify_subprocess_result_returns_none_when_clean() -> None:
    out = ErrorClassifier.classify_subprocess_result(
        ytdlp_returncode=None,
        ffmpeg_returncode=0,
        chunks_yielded=10,
        stderr_text="",
        context={},
    )
    assert out is None


def test_classify_subprocess_result_ytdlp_nonzero() -> None:
    out = ErrorClassifier.classify_subprocess_result(
        ytdlp_returncode=1,
        ffmpeg_returncode=None,
        chunks_yielded=0,
        stderr_text="ERROR: format is not available",
        context={"url": "https://youtube.com/foo"},
    )
    assert out is not None
    assert out.error_type == ErrorType.FORMAT_ERROR


def test_classify_subprocess_result_pipe_eof() -> None:
    out = ErrorClassifier.classify_subprocess_result(
        ytdlp_returncode=None,
        ffmpeg_returncode=1,
        chunks_yielded=0,
        stderr_text="end of file",
        context={},
    )
    assert out is not None
    assert out.error_type == ErrorType.PIPE_EOF_ERROR


def test_handle_subprocess_result_returns_none_when_clean() -> None:
    handler = ErrorHandler(max_retries=3, backoff_base=1.0)
    out = handler.handle_subprocess_result(
        ytdlp_returncode=None,
        ffmpeg_returncode=0,
        chunks_yielded=5,
        stderr_text="",
        context={},
    )
    assert out is None


def test_backoff_multipliers_include_new_types() -> None:
    assert ErrorType.YTDLP_ERROR in _BACKOFF_MULTIPLIERS
    assert ErrorType.PIPE_EOF_ERROR in _BACKOFF_MULTIPLIERS
    assert _BACKOFF_MULTIPLIERS[ErrorType.YTDLP_ERROR] == 5.0


def test_get_backoff_delay_uses_error_type() -> None:
    handler = ErrorHandler(max_retries=3, backoff_base=1.0)
    delay_rate = handler.get_backoff_delay(0, ErrorType.RATE_LIMIT_ERROR)
    delay_ytdlp = handler.get_backoff_delay(0, ErrorType.YTDLP_ERROR)
    assert delay_rate > delay_ytdlp


def test_should_retry_permission_error_returns_false() -> None:
    handler = ErrorHandler(max_retries=3, backoff_base=1.0)
    err = StreamError(
        ErrorType.PERMISSION_ERROR,
        ErrorSeverity.HIGH,
        "private video",
        context={},
    )
    err.retry_count = 0
    err.max_retries = 3
    assert handler.should_retry(err) is False
