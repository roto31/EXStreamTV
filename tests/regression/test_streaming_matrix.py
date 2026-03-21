"""
Regression test matrix for streaming subsystem hardening.

Covers: Plex, File, URL, YouTube, IPTV, HDHomeRun, Clock integrity.

Run with: pytest tests/regression/test_streaming_matrix.py -v
"""

import pytest

from exstreamtv.streaming.contract import StreamSource, StreamingContractEnforcer
from exstreamtv.streaming.resolver_registry import ResolverRegistryError, get_resolver_registry
from exstreamtv.streaming.resolvers.base import SourceType
from exstreamtv.streaming.resolution_service import _source_str_to_type


# --- Part 5.1: Resolver registry / source type mapping ---


def test_registry_raises_for_missing_source_type():
    """Unknown source_type must raise; no default resolver."""
    registry = get_resolver_registry()
    # M3U is not registered in the default registry
    with pytest.raises(ResolverRegistryError):
        registry.get(SourceType.M3U)


def test_source_str_to_type_plex():
    """source='plex' maps to PLEX."""
    assert _source_str_to_type("plex") == SourceType.PLEX
    assert _source_str_to_type("PLEX") == SourceType.PLEX


def test_source_str_to_type_youtube():
    """source='youtube' maps to YOUTUBE."""
    assert _source_str_to_type("youtube") == SourceType.YOUTUBE
    assert _source_str_to_type("youtu.be") == SourceType.YOUTUBE


def test_source_str_to_type_archive():
    """source='archive' maps to ARCHIVE_ORG."""
    assert _source_str_to_type("archive") == SourceType.ARCHIVE_ORG


def test_source_str_to_type_local():
    """source='local' or 'file' maps to LOCAL."""
    assert _source_str_to_type("local") == SourceType.LOCAL
    assert _source_str_to_type("file") == SourceType.LOCAL


def test_source_str_to_type_unknown_for_generic():
    """Generic source maps to UNKNOWN."""
    assert _source_str_to_type("url") == SourceType.UNKNOWN
    assert _source_str_to_type("unknown") == SourceType.UNKNOWN


# --- Part 5.2–5.4: Contract validation (unit) ---


def test_contract_valid_http_url():
    """Valid HTTP stream passes contract."""
    enforcer = StreamingContractEnforcer()
    src = StreamSource(url="https://example.com/stream.m3u8")
    r = enforcer.validate(src)
    assert r.valid


def test_contract_rejects_empty_and_html():
    """Empty URL and HTML fail contract."""
    enforcer = StreamingContractEnforcer()
    assert not enforcer.validate(StreamSource(url="")).valid
    assert not enforcer.validate(StreamSource(url="<html>")).valid


# --- Matrix documentation (scenarios requiring live/mock services) ---
# See docs/STREAMING_ARCHITECTURE_ISOLATION.md Part 5 for full matrix.
# E2E / integration: tests/e2e/test_streaming_e2e.py, tests/integration/
