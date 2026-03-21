"""
Unit tests for MediaURLResolver source type detection.

Verifies strict routing: no Plex misrouting from loose URL patterns.
"""

import pytest

from exstreamtv.streaming.url_resolver import MediaURLResolver
from exstreamtv.streaming.resolvers.base import SourceType


def test_detect_source_type_plex_requires_explicit_or_library_path():
    """Plex is NOT matched by ':32400' or 'plex' substring alone."""
    resolver = MediaURLResolver()
    # URL with plex in path but not /library/metadata/ - should NOT be Plex
    assert resolver._detect_source_type({"url": "https://cdn.example.com/plexproxy/video.mp4"}) != SourceType.PLEX
    assert resolver._detect_source_type({"url": "https://example.com:32400/other"}) != SourceType.PLEX
    # Explicit source wins
    assert resolver._detect_source_type({"source": "plex", "url": "https://other.com"}) == SourceType.PLEX
    # plex_rating_key implies Plex
    assert resolver._detect_source_type({"plex_rating_key": "12345"}) == SourceType.PLEX
    # /library/metadata/ path is Plex
    assert resolver._detect_source_type({"url": "http://server:32400/library/metadata/123"}) == SourceType.PLEX


def test_detect_source_type_youtube():
    """YouTube matched by URL patterns."""
    resolver = MediaURLResolver()
    assert resolver._detect_source_type({"url": "https://youtube.com/watch?v=abc"}) == SourceType.YOUTUBE
    assert resolver._detect_source_type({"url": "https://googlevideo.com/..."}) == SourceType.YOUTUBE


def test_detect_source_type_archive_org():
    """Archive.org matched by URL or fields."""
    resolver = MediaURLResolver()
    assert resolver._detect_source_type({"url": "https://archive.org/download/xyz"}) == SourceType.ARCHIVE_ORG
    assert resolver._detect_source_type({"archive_org_identifier": "xyz"}) == SourceType.ARCHIVE_ORG


def test_detect_source_type_local():
    """Local matched by path prefix."""
    resolver = MediaURLResolver()
    assert resolver._detect_source_type({"path": "/local/video.mp4"}) == SourceType.LOCAL
    assert resolver._detect_source_type({"url": "file:///video.mp4"}) == SourceType.LOCAL


def test_detect_source_type_unknown_for_generic_http():
    """Generic http URL with no source hints returns UNKNOWN."""
    resolver = MediaURLResolver()
    result = resolver._detect_source_type({"url": "https://cdn.example.com/video.m3u8"})
    assert result == SourceType.UNKNOWN
