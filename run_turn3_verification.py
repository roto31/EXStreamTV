#!/usr/bin/env python3
"""Run Turn 3 verification (channel_manager + full stack). No pytest required."""
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    # 1) Syntax check on channel_manager.py
    cm_path = PROJECT_ROOT / "exstreamtv" / "streaming" / "channel_manager.py"
    try:
        src = cm_path.read_text()
        ast.parse(src)
        print("PASS: channel_manager.py syntax OK")
    except SyntaxError as e:
        print(f"FAIL: channel_manager.py syntax error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1

    # 2) No bare "for queue in self._client_queues" (must unpack tuple)
    if "for queue in self._client_queues" in src:
        print("FAIL: bare 'for queue in self._client_queues' found — tuple unpack required", file=sys.stderr)
        return 1
    print("PASS: _client_queues tuple structure consistent")

    # 3) Turn 1 checks (mpegts_streamer)
    try:
        from exstreamtv.streaming.mpegts_streamer import (
            _is_script_field,
            StreamSource,
            MPEGTSStreamer,
            CodecInfo,
        )
        assert _is_script_field("/opt/bin/yt-dlp https://x -o -") is True
        assert _is_script_field("https://archive.org/foo") is False
        assert StreamSource("archive_org") == StreamSource.ARCHIVE_ORG
        streamer = MPEGTSStreamer()
        cmd = streamer.build_ffmpeg_command(
            "pipe:0", CodecInfo(duration=0.0), StreamSource.UNKNOWN,
            seek_offset=0.0, is_piped_input=True,
        )
        assert cmd[cmd.index("-i") + 1] == "pipe:0"
        print("PASS: Turn 1 (mpegts_streamer) checks")
    except Exception as e:
        print(f"FAIL: Turn 1 checks: {e}", file=sys.stderr)
        return 1

    # 4) Turn 2 checks (error_handler)
    try:
        from exstreamtv.streaming.error_handler import (
            ErrorType,
            ErrorClassifier,
            ErrorHandler,
            _BACKOFF_MULTIPLIERS,
            StreamError,
            ErrorSeverity,
        )
        assert ErrorType.YTDLP_ERROR.value == "ytdlp_error"
        assert ErrorClassifier.classify_subprocess_result(None, 0, 10, "", {}) is None
        handler = ErrorHandler(max_retries=3, backoff_base=1.0)
        assert handler.get_backoff_delay(0, ErrorType.RATE_LIMIT_ERROR) > handler.get_backoff_delay(0, ErrorType.YTDLP_ERROR)
        err = StreamError(ErrorType.PERMISSION_ERROR, ErrorSeverity.HIGH, "private", context={})
        err.retry_count = 0
        err.max_retries = 3
        assert handler.should_retry(err) is False
        print("PASS: Turn 2 (error_handler) checks")
    except Exception as e:
        print(f"FAIL: Turn 2 checks: {e}", file=sys.stderr)
        return 1

    # 5) channel_manager has required helpers and usage
    if "_duration_to_seconds" not in src or "_safe_import" not in src:
        print("FAIL: channel_manager missing _duration_to_seconds or _safe_import", file=sys.stderr)
        return 1
    if "SLOW_CLIENT_THRESHOLD" not in src or "source_type" not in src:
        print("FAIL: channel_manager missing SLOW_CLIENT_THRESHOLD or source_type", file=sys.stderr)
        return 1
    print("PASS: channel_manager Turn 3 helpers and fields present")

    print("\nTurn 3 verification: all checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
