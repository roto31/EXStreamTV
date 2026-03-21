"""
Regression tests for XMLTV and HDHomeRun EPG.

Ensures:
- XMLTV includes GuideNumber as display-name (Plex DVR channel matching)
- Duplicate (channel, start) programmes are skipped
- Generated XMLTV has no duplicate programme elements for same start
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from exstreamtv.api.timeline_builder import TimelineProgramme
from exstreamtv.api.xmltv_generator import XMLTVGenerator


@pytest.mark.unit
class TestXMLTVGuideNumberDisplayName:
    """GuideNumber must be emitted as display-name for Plex DVR channel matching."""

    def test_channel_includes_guide_number_display_name(self) -> None:
        """XMLTV channel must have display-name with GuideNumber for lineup matching."""
        channel = MagicMock()
        channel.id = 5
        channel.number = "105"
        channel.name = "Test Channel"
        channel.logo_path = None

        base = datetime(2025, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
        prog = TimelineProgramme(
            start_time=base,
            stop_time=base.replace(hour=13),
            media_item=None,
            playout_item=None,
            title="Show",
            index=0,
        )

        gen = XMLTVGenerator()
        xml = gen.generate([channel], {5: [prog]}, validate=False)

        # GuideNumber first (Plex matches by first display-name)
        assert "<display-name>105</display-name>" in xml
        assert "<display-name>Test Channel</display-name>" in xml
        assert 'id="exstream.5"' in xml
        # First display-name must be GuideNumber for Plex lineup mapping
        assert xml.find("<display-name>105</display-name>") < xml.find("<display-name>Test Channel</display-name>")


@pytest.mark.unit
class TestXMLTVDuplicateProgrammeDedup:
    """Duplicate (channel, start) programmes must be skipped."""

    def test_duplicate_start_times_deduped(self) -> None:
        """When programmes share same start_time, only first is emitted."""
        channel = MagicMock()
        channel.id = 1
        channel.number = "100"
        channel.name = "Ch"
        channel.logo_path = None

        base = datetime(2025, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
        dup = TimelineProgramme(
            start_time=base,
            stop_time=base.replace(hour=12, minute=30),
            media_item=None,
            playout_item=None,
            title="Duplicate",
            index=1,
        )
        # Same start as dup - should be skipped
        dup2 = TimelineProgramme(
            start_time=base,
            stop_time=base.replace(hour=12, minute=30),
            media_item=None,
            playout_item=None,
            title="Duplicate",
            index=2,
        )

        gen = XMLTVGenerator()
        xml = gen.generate([channel], {1: [dup, dup2]}, validate=False)

        # Only one programme with start="20250222120000"
        count = xml.count('start="20250222120000')
        assert count == 1
