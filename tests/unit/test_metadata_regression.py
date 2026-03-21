"""
Section B.3 — Regression Tests for Metadata Enrichment and Pattern Detection.

Uses deterministic fixtures from tests/fixtures/metadata/.
Validates: MetadataAnalysis, PatternDetector, XMLTV validation, restart guard.
"""

import json
from pathlib import Path

import pytest

from exstreamtv.ai_agent.pattern_detector import (
    MetadataAnalysis,
    MetadataIssueType,
    get_pattern_detector,
)


def _load_metadata_analysis_fixtures() -> list[dict]:
    """Load deterministic MetadataAnalysis samples from fixtures."""
    path = Path(__file__).parent.parent / "fixtures" / "metadata" / "metadata_analysis_samples.json"
    with open(path) as f:
        return json.load(f)


def test_pattern_detector_metadata_lookup_failure() -> None:
    """PatternDetector detects metadata_lookup_failure when lookup failures > 0."""
    detector = get_pattern_detector()
    metrics = {
        "metadata_lookup_success_total": 70,
        "metadata_lookup_failure_total": 30,
        "episode_metadata_missing_total": 0,
        "movie_metadata_missing_total": 0,
        "placeholder_title_generated_total": 0,
        "xmltv_validation_error_total": 0,
    }
    results = detector.analyze_metadata_issues(metrics, channel_id=1, programme_total=100)
    assert len(results) >= 1
    lookup_issues = [r for r in results if r.issue_type == MetadataIssueType.METADATA_LOOKUP_FAILURE.value]
    assert len(lookup_issues) == 1
    assert lookup_issues[0].affected_items_count == 30
    assert lookup_issues[0].metadata_failure_ratio == 0.3


def test_pattern_detector_episode_missing() -> None:
    """PatternDetector detects episode_num_missing when episode_metadata_missing_total > 0."""
    detector = get_pattern_detector()
    metrics = {
        "metadata_lookup_success_total": 100,
        "metadata_lookup_failure_total": 0,
        "episode_metadata_missing_total": 8,
        "movie_metadata_missing_total": 0,
        "placeholder_title_generated_total": 0,
        "xmltv_validation_error_total": 0,
    }
    results = detector.analyze_metadata_issues(metrics, channel_id=2, programme_total=80)
    episode_issues = [r for r in results if r.issue_type == MetadataIssueType.EPISODE_NUM_MISSING.value]
    assert len(episode_issues) == 1
    assert episode_issues[0].affected_items_count == 8


def test_pattern_detector_placeholder_excess() -> None:
    """PatternDetector detects placeholder_title_excess when total > 10."""
    detector = get_pattern_detector()
    metrics = {
        "metadata_lookup_success_total": 50,
        "metadata_lookup_failure_total": 0,
        "episode_metadata_missing_total": 0,
        "movie_metadata_missing_total": 0,
        "placeholder_title_generated_total": 25,
        "xmltv_validation_error_total": 0,
    }
    results = detector.analyze_metadata_issues(metrics, channel_id=None, programme_total=100)
    placeholder_issues = [r for r in results if r.issue_type == MetadataIssueType.PLACEHOLDER_TITLE_EXCESS.value]
    assert len(placeholder_issues) == 1
    assert placeholder_issues[0].affected_items_count == 25


def test_metadata_analysis_fixture_schema() -> None:
    """Fixture MetadataAnalysis samples match expected schema."""
    samples = _load_metadata_analysis_fixtures()
    for s in samples:
        assert "channel_id" in s
        assert "issue_type" in s
        assert "confidence" in s
        assert "affected_items_count" in s
        assert "metadata_failure_ratio" in s
        assert s["issue_type"] in [e.value for e in MetadataIssueType]


def test_media_item_schema_fixture() -> None:
    """Fixture media_item_schema has required fields for regression tests."""
    path = Path(__file__).parent.parent / "fixtures" / "metadata" / "media_item_schema.json"
    with open(path) as f:
        schema = json.load(f)
    assert "episode_number" in schema
    assert "season_number" in schema
    assert "show_title" in schema
    assert "title" in schema
