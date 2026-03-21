#!/usr/bin/env python3
"""Run Turn 1 verification (mpegts_streamer fixes) without pytest.
Requires project deps installed: pip install -e .   (or at least: pip install pyyaml)
"""
import sys


def main() -> int:
    try:
        from exstreamtv.streaming.mpegts_streamer import (
            _is_script_field,
            StreamSource,
            MPEGTSStreamer,
            CodecInfo,
        )
    except ModuleNotFoundError as e:
        print(f"Missing dependency: {e}", file=sys.stderr)
        print("Install project deps:  pip install -e .", file=sys.stderr)
        print("Or minimal:            pip install pyyaml", file=sys.stderr)
        return 1
    ok = 0
    # test_is_script_field_ytdlp_command
    assert _is_script_field("/opt/homebrew/bin/yt-dlp --playlist-items 2 https://archive.org/... -o -") is True
    assert _is_script_field("ytdlp https://youtube.com/watch?v=1 -o -") is True
    ok += 1
    print("PASS: test_is_script_field_ytdlp_command")
    # test_is_script_field_url_not_script
    assert _is_script_field("https://archive.org/details/foo") is False
    assert _is_script_field("https://youtube.com/watch?v=1") is False
    ok += 1
    print("PASS: test_is_script_field_url_not_script")
    # test_is_script_field_local_file_not_script
    assert _is_script_field("/path/to/video.mp4") is False
    assert _is_script_field("/path/to/video.mkv") is False
    ok += 1
    print("PASS: test_is_script_field_local_file_not_script")
    # test_stream_source_archive_org
    assert StreamSource("archive_org") == StreamSource.ARCHIVE_ORG
    ok += 1
    print("PASS: test_stream_source_archive_org")
    # test_stream_source_unknown_fallback
    try:
        StreamSource("invalid_source_name")
        assert False, "expected ValueError"
    except ValueError:
        pass
    ok += 1
    print("PASS: test_stream_source_unknown_fallback")
    # test_build_ffmpeg_command_accepts_is_piped_input
    streamer = MPEGTSStreamer()
    info = CodecInfo(duration=0.0)
    cmd = streamer.build_ffmpeg_command(
        "pipe:0",
        codec_info=info,
        source=StreamSource.UNKNOWN,
        seek_offset=0.0,
        is_piped_input=True,
    )
    assert "-i" in " ".join(cmd)
    i_idx = cmd.index("-i")
    assert cmd[i_idx + 1] == "pipe:0"
    ok += 1
    print("PASS: test_build_ffmpeg_command_accepts_is_piped_input")
    print(f"\nTurn 1 verification: all {ok} checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
