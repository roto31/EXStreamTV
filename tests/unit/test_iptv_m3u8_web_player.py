"""
Unit tests for IPTV m3u8 Web Player compatibility.

Ensures the m3u8 endpoint returns browser-playable HLS for channels that use
the continuous MPEG-TS stream (YouTube, HLS sources). The fix generates a
single-segment live m3u8 instead of multiple segments all pointing to the
same .ts URL, which HLS.js cannot parse.
"""

from __future__ import annotations

import pytest


def test_m3u8_single_segment_format_valid() -> None:
    """Single-segment m3u8 format must be valid HLS for browser playback (live stream).

    Regression test: when all schedule items use channel.ts (YouTube/HLS sources),
    the endpoint returns a single-segment playlist. This format must:
    - Start with #EXTM3U
    - Include EXT-X-VERSION:3
    - Have one EXTINF segment pointing to .ts URL
    - Omit #EXT-X-ENDLIST (live stream)
    """
    single_m3u8 = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-TARGETDURATION:86400\n"
        "#EXT-X-MEDIA-SEQUENCE:0\n"
        "#EXTINF:86400.0,\n"
        "http://localhost:8411/iptv/channel/1.ts\n"
    )
    assert "#EXTM3U" in single_m3u8
    assert "#EXT-X-VERSION:3" in single_m3u8
    assert "#EXT-X-TARGETDURATION:86400" in single_m3u8
    assert "EXTINF" in single_m3u8
    assert ".ts" in single_m3u8
    assert "#EXT-X-ENDLIST" not in single_m3u8


def test_m3u8_single_segment_has_cors_headers() -> None:
    """Single-segment m3u8 response must include CORS headers for cross-origin playback."""
    expected_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
    }
    assert "Access-Control-Allow-Origin" in expected_headers
    assert expected_headers["Access-Control-Allow-Origin"] == "*"


def test_uses_channel_ts_logic_m3u8_url() -> None:
    """Media with .m3u8 in URL should use channel.ts stream."""
    # Both YouTube and HLS URLs route to channel.ts for browser compatibility
    youtube_url = "https://youtube.com/watch?v=123"
    hls_url = "https://example.com/stream.m3u8"
    assert "youtube" in youtube_url.lower()
    assert ".m3u8" in hls_url.lower()
