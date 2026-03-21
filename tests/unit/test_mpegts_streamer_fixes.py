"""Minimal tests for EXStreamTV streaming fixes (script field, seek guard, aresample)."""
import pytest
from exstreamtv.streaming.mpegts_streamer import _is_script_field, StreamSource, MPEGTSStreamer


def test_is_script_field_ytdlp_command() -> None:
    assert _is_script_field("/opt/homebrew/bin/yt-dlp --playlist-items 2 https://archive.org/... -o -") is True
    assert _is_script_field("ytdlp https://youtube.com/watch?v=1 -o -") is True


def test_is_script_field_url_not_script() -> None:
    assert _is_script_field("https://archive.org/details/foo") is False
    assert _is_script_field("https://youtube.com/watch?v=1") is False


def test_is_script_field_local_file_not_script() -> None:
    assert _is_script_field("/path/to/video.mp4") is False
    assert _is_script_field("/path/to/video.mkv") is False


def test_stream_source_archive_org() -> None:
    s = StreamSource("archive_org")
    assert s == StreamSource.ARCHIVE_ORG


def test_stream_source_unknown_fallback() -> None:
    with pytest.raises(ValueError):
        StreamSource("invalid_source_name")


def test_build_ffmpeg_command_accepts_is_piped_input() -> None:
    from exstreamtv.streaming.mpegts_streamer import CodecInfo
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
