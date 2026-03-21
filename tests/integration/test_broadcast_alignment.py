"""
Broadcast Alignment Validation Tests.

Requires running EXStreamTV server. Run with:
  pytest tests/integration/test_broadcast_alignment.py -v -m "not slow"

Markers: integration, network, slow
"""

import pytest

from tests.integration.broadcast_alignment.clock_validator import validate_clock
from tests.integration.broadcast_alignment.dual_authority_detector import scan_for_dual_authority
from tests.integration.broadcast_alignment.hdhomerun_validator import validate_hdhomerun_protocol
from tests.integration.broadcast_alignment.xmltv_validator import (
    parse_xmltv,
    validate_channel_programmes,
)


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_clock_validator(base_url: str, sample_channel_ids: list[int]) -> None:
    """Validate /api/clock/{channel_id} returns valid data."""
    for ch_id in sample_channel_ids[:2]:
        res = await validate_clock(base_url, ch_id)
        assert res.channel_id == ch_id
        if res.message and "No clock" in str(res.message):
            pytest.skip("Channel has no clock (no timeline)")
        assert res.total_cycle_duration >= 0


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
async def test_hdhomerun_protocol(base_url: str) -> None:
    """Validate HDHomeRun discover, lineup, lineup_status, device.xml."""
    res = await validate_hdhomerun_protocol(base_url)
    assert res.discover.ok, res.discover.message
    assert res.device_id is not None
    assert len(res.device_id) == 8
    assert res.device_id.isalnum()
    assert len(res.duplicate_guide_numbers) == 0


@pytest.mark.integration
def test_dual_authority_detection() -> None:
    """Fail if _current_item_index or journal-based schedule restore detected."""
    ok, violations = scan_for_dual_authority()
    assert ok, f"Dual authority patterns detected: {violations}"


@pytest.mark.integration
def test_xmltv_validator_no_overlaps() -> None:
    """XMLTV validator correctly detects overlaps."""
    from tests.integration.broadcast_alignment.xmltv_validator import ProgrammeEntry
    from datetime import datetime
    progs = [
        ProgrammeEntry("100", datetime(2026, 2, 25, 4, 0), datetime(2026, 2, 25, 5, 0), "A", "", ""),
        ProgrammeEntry("100", datetime(2026, 2, 25, 4, 30), datetime(2026, 2, 25, 5, 30), "B", "", ""),
    ]
    res = validate_channel_programmes(progs, "100")
    assert not res.ok
    assert len(res.overlaps) > 0
