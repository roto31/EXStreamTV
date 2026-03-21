#!/usr/bin/env python3
"""Run Turn 2 verification (error_handler fixes) without pytest.
Requires: source .venv/bin/activate  and  pip install -e .
"""
import sys


def main() -> int:
    try:
        from exstreamtv.streaming.error_handler import (
            ErrorType,
            ErrorClassifier,
            ErrorHandler,
            _BACKOFF_MULTIPLIERS,
            StreamError,
            ErrorSeverity,
        )
    except ModuleNotFoundError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("Activate venv and install:  source .venv/bin/activate && pip install -e .", file=sys.stderr)
        return 1

    ok = 0
    # test_ytdlp_and_pipe_eof_error_types_exist
    assert ErrorType.YTDLP_ERROR.value == "ytdlp_error"
    assert ErrorType.PIPE_EOF_ERROR.value == "pipe_eof_error"
    ok += 1
    print("PASS: test_ytdlp_and_pipe_eof_error_types_exist")

    # test_classify_subprocess_result_returns_none_when_clean
    out = ErrorClassifier.classify_subprocess_result(
        ytdlp_returncode=None,
        ffmpeg_returncode=0,
        chunks_yielded=10,
        stderr_text="",
        context={},
    )
    assert out is None
    ok += 1
    print("PASS: test_classify_subprocess_result_returns_none_when_clean")

    # test_classify_subprocess_result_ytdlp_nonzero
    out = ErrorClassifier.classify_subprocess_result(
        ytdlp_returncode=1,
        ffmpeg_returncode=None,
        chunks_yielded=0,
        stderr_text="ERROR: format is not available",
        context={"url": "https://youtube.com/foo"},
    )
    assert out is not None
    assert out.error_type == ErrorType.FORMAT_ERROR
    ok += 1
    print("PASS: test_classify_subprocess_result_ytdlp_nonzero")

    # test_classify_subprocess_result_pipe_eof
    out = ErrorClassifier.classify_subprocess_result(
        ytdlp_returncode=None,
        ffmpeg_returncode=1,
        chunks_yielded=0,
        stderr_text="end of file",
        context={},
    )
    assert out is not None
    assert out.error_type == ErrorType.PIPE_EOF_ERROR
    ok += 1
    print("PASS: test_classify_subprocess_result_pipe_eof")

    # test_handle_subprocess_result_returns_none_when_clean
    handler = ErrorHandler(max_retries=3, backoff_base=1.0)
    out = handler.handle_subprocess_result(
        ytdlp_returncode=None,
        ffmpeg_returncode=0,
        chunks_yielded=5,
        stderr_text="",
        context={},
    )
    assert out is None
    ok += 1
    print("PASS: test_handle_subprocess_result_returns_none_when_clean")

    # test_backoff_multipliers_include_new_types
    assert ErrorType.YTDLP_ERROR in _BACKOFF_MULTIPLIERS
    assert ErrorType.PIPE_EOF_ERROR in _BACKOFF_MULTIPLIERS
    assert _BACKOFF_MULTIPLIERS[ErrorType.YTDLP_ERROR] == 5.0
    ok += 1
    print("PASS: test_backoff_multipliers_include_new_types")

    # test_get_backoff_delay_uses_error_type
    delay_rate = handler.get_backoff_delay(0, ErrorType.RATE_LIMIT_ERROR)
    delay_ytdlp = handler.get_backoff_delay(0, ErrorType.YTDLP_ERROR)
    assert delay_rate > delay_ytdlp
    ok += 1
    print("PASS: test_get_backoff_delay_uses_error_type")

    # test_should_retry_permission_error_returns_false
    err = StreamError(
        ErrorType.PERMISSION_ERROR,
        ErrorSeverity.HIGH,
        "private video",
        context={},
    )
    err.retry_count = 0
    err.max_retries = 3
    assert handler.should_retry(err) is False
    ok += 1
    print("PASS: test_should_retry_permission_error_returns_false")

    print(f"\nTurn 2 verification: all {ok} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
