"""
HDHomeRun Stress Load Tests.

Requires running EXStreamTV server. Run with:
  pytest tests/load/test_hdhomerun_stress.py -v -m "not slow"

Markers: integration, network, slow
"""

import pytest

from tests.load.hdhomerun_stress.load_runner import run_load
from tests.load.hdhomerun_stress.reconnect_storm import run_reconnect_storm
from tests.load.hdhomerun_stress.channel_switcher import run_channel_switch_test


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
@pytest.mark.slow
async def test_reconnect_storm(base_url: str, sample_guide_numbers: list[str]) -> None:
    """Run reconnect storm (connect 3-10s, disconnect, repeat)."""
    if not sample_guide_numbers:
        pytest.skip("No guide numbers")
    res = await run_reconnect_storm(
        base_url, sample_guide_numbers[0], duration_seconds=30,
        min_connect_sec=2.0, max_connect_sec=5.0,
    )
    # With 2-5s per cycle, 30s yields ~6-15 cycles
    assert res.cycles_completed >= 3, f"Expected >=3 cycles, got {res.cycles_completed}"
    assert len(res.errors) == 0, res.errors


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.asyncio
@pytest.mark.slow
async def test_channel_switch(base_url: str, sample_guide_numbers: list[str]) -> None:
    """Switch channels every 5s for 30s."""
    if not sample_guide_numbers:
        pytest.skip("No guide numbers")
    res = await run_channel_switch_test(
        base_url,
        sample_guide_numbers,
        switch_interval_seconds=5.0,
        duration_seconds=30.0,
    )
    assert res.switches_completed >= 3
    assert len(res.errors) == 0, res.errors
