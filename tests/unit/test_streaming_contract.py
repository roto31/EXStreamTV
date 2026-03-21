"""
Unit tests for StreamingContractEnforcer and StreamSource validation.

Verifies contract rules: non-empty URL, valid scheme, no HTML, no error pages.
"""

import pytest

from exstreamtv.streaming.contract import (
    StreamingContractEnforcer,
    StreamSource,
    SourceClassification,
)
from exstreamtv.streaming.resolvers.base import SourceType


def test_contract_rejects_none():
    """None source returns invalid."""
    enforcer = StreamingContractEnforcer()
    result = enforcer.validate(None)
    assert result.valid is False
    assert "None" in (result.violation_reason or "")


def test_contract_rejects_empty_url():
    """Empty URL returns invalid."""
    enforcer = StreamingContractEnforcer()
    source = StreamSource(url="", headers={})
    result = enforcer.validate(source)
    assert result.valid is False
    assert "empty" in (result.violation_reason or "").lower()


def test_contract_rejects_html_url():
    """URL containing HTML indicators returns invalid."""
    enforcer = StreamingContractEnforcer()
    source = StreamSource(url="<!DOCTYPE html><html>", headers={})
    result = enforcer.validate(source)
    assert result.valid is False
    assert "HTML" in (result.violation_reason or "")


def test_contract_rejects_invalid_scheme():
    """Invalid URL scheme returns invalid."""
    enforcer = StreamingContractEnforcer()
    source = StreamSource(url="invalid://example.com/video", headers={})
    result = enforcer.validate(source)
    assert result.valid is False
    assert "scheme" in (result.violation_reason or "").lower()


def test_contract_accepts_valid_http():
    """Valid HTTP URL passes."""
    enforcer = StreamingContractEnforcer()
    source = StreamSource(
        url="https://example.com/stream.m3u8",
        headers={},
    )
    result = enforcer.validate(source)
    assert result.valid is True
    assert result.source is source


def test_contract_accepts_file_scheme():
    """Valid file:// URL passes."""
    enforcer = StreamingContractEnforcer()
    source = StreamSource(url="file:///local/video.mp4", headers={})
    result = enforcer.validate(source)
    assert result.valid is True
