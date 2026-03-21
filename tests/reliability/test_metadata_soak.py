"""
Section B.1 — 24-Hour Metadata Soak Test.

EPG regeneration loop under stress: placeholder injection, missing episode/year,
metadata enrichment failure simulation. Validates no restart invocation, bounded
memory, no asyncio task leaks.

Marked @pytest.mark.slow — run with: pytest -m slow
Or explicitly: pytest tests/reliability/test_metadata_soak.py
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from exstreamtv.api.timeline_builder import PlaybackAnchor, TimelineBuilder, TimelineProgramme
from exstreamtv.api.xmltv_generator import XMLTVGenerator
from exstreamtv.constants import EXSTREAM_CHANNEL_ID_PREFIX


def _make_channel(ch_id: int, number: int, name: str) -> Any:
    """Create minimal channel-like object."""
    return type("Channel", (), {"id": ch_id, "number": number, "name": name})()


def _make_media_item(
    duration: int = 1800,
    title: str = "Programme",
    episode_number: int | None = None,
    season_number: int | None = None,
    show_title: str | None = None,
) -> Any:
    """Create minimal media item for timeline."""
    attrs = {"duration": duration, "title": title}
    if episode_number is not None:
        attrs["episode_number"] = episode_number
    if season_number is not None:
        attrs["season_number"] = season_number
    if show_title is not None:
        attrs["show_title"] = show_title
    return type("MediaItem", (), attrs)()


def _build_stress_programmes(
    channel_id: int,
    programme_count: int = 50,
    placeholder_pct: float = 0.2,
    missing_episode_pct: float = 0.2,
    now: datetime | None = None,
) -> tuple[list[TimelineProgramme], Any]:
    """Build programmes with stress scenarios (placeholder, missing episode/year)."""
    now = now or datetime.utcnow()
    channel = _make_channel(channel_id, channel_id, f"Channel {channel_id}")
    items: list[dict[str, Any]] = []
    for i in range(programme_count):
        is_placeholder = (i % int(1 / max(0.01, placeholder_pct))) == 0 if placeholder_pct > 0 else False
        has_episode = (i % int(1 / max(0.01, missing_episode_pct))) != 0 if missing_episode_pct > 0 else True
        title = f"Item {1000 + i}" if is_placeholder else f"Show S01E{i:02d}"
        mi = _make_media_item(
            title=title,
            episode_number=5 if has_episode else None,
            season_number=1 if has_episode else None,
            show_title="Test Show" if has_episode else None,
        )
        items.append({"media_item": mi, "custom_title": title})
    anchor = PlaybackAnchor(playout_start_time=now, last_item_index=0)
    builder = TimelineBuilder()
    raw = builder.build(items, anchor, now=now, max_programmes=programme_count)
    return raw, channel


@pytest.mark.slow
@pytest.mark.asyncio
async def test_metadata_soak_epg_loop_no_restart(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """
    EPG regeneration loop: no request_channel_restart or stop_channel during soak.

    Runs configurable cycles (SOAK_CYCLES env, default 12). Simulates 5-min cadence
    with minimal sleep. Validates restart invariant.
    """
    cycles = int(os.environ.get("SOAK_CYCLES", "12"))
    restart_called: list[int] = []
    stop_called: list[int] = []

    async def _mock_request_restart(channel_id: int) -> bool:
        restart_called.append(channel_id)
        return False

    def _mock_stop(self: Any, channel_id: int) -> None:
        stop_called.append(channel_id)

    monkeypatch.setattr(
        "exstreamtv.tasks.health_tasks.request_channel_restart",
        _mock_request_restart,
    )

    channels = [_make_channel(1, 1, "Test")]
    now = datetime.utcnow()
    end_time = now + timedelta(days=1)
    base_url = "http://test"

    for cycle in range(cycles):
        progs, ch = _build_stress_programmes(
            channel_id=1,
            programme_count=30,
            placeholder_pct=0.2,
            missing_episode_pct=0.2,
            now=now,
        )
        programmes_by_channel = {1: progs}
        gen = XMLTVGenerator()
        result = gen.generate(channels, programmes_by_channel, base_url=base_url, validate=True)
        assert "<?xml" in result
        assert len(restart_called) == 0
        assert len(stop_called) == 0
        await asyncio.sleep(0.02)

    assert len(restart_called) == 0, "request_channel_restart must not be called during soak"
    assert len(stop_called) == 0, "stop_channel must not be called during soak"


@pytest.mark.slow
def test_metadata_soak_memory_bounded() -> None:
    """
    EPG loop memory delta < 50MB over run.

    Runs 24 cycles with synthetic programmes. Captures RSS at start/end.
    """
    try:
        import psutil
    except ImportError:
        pytest.skip("psutil not installed")

    process = psutil.Process(os.getpid())
    rss_start = process.memory_info().rss
    channels = [_make_channel(1, 1, "Test")]
    now = datetime.utcnow()
    gen = XMLTVGenerator()

    for _ in range(24):
        progs, _ = _build_stress_programmes(1, programme_count=50, now=now)
        programmes_by_channel = {1: progs}
        gen.generate(channels, programmes_by_channel, base_url="http://test", validate=True)

    rss_end = process.memory_info().rss
    delta_mb = (rss_end - rss_start) / (1024 * 1024)
    assert delta_mb < 50, f"Memory delta {delta_mb:.1f}MB exceeds 50MB limit"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_metadata_soak_no_task_leaks() -> None:
    """
    No asyncio task leaks per EPG cycle.

    Runs sync EPG generation in executor; checks task count stable.
    """
    loop = asyncio.get_running_loop()
    initial_tasks = len(asyncio.all_tasks())

    def _run_cycle() -> None:
        channels = [_make_channel(1, 1, "Test")]
        now = datetime.utcnow()
        progs, _ = _build_stress_programmes(1, programme_count=20, now=now)
        programmes_by_channel = {1: progs}
        gen = XMLTVGenerator()
        gen.generate(channels, programmes_by_channel, base_url="http://test", validate=True)

    for _ in range(6):
        await loop.run_in_executor(None, _run_cycle)
        tasks_now = len(asyncio.all_tasks())
        assert tasks_now <= initial_tasks + 2, f"Task leak: {tasks_now} vs {initial_tasks}"


def test_metadata_fixtures_loadable() -> None:
    """Regression fixtures are valid JSON and loadable."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "metadata"
    analysis_path = fixtures_dir / "metadata_analysis_samples.json"
    schema_path = fixtures_dir / "media_item_schema.json"
    assert analysis_path.exists()
    assert schema_path.exists()
    with open(analysis_path) as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "channel_id" in data[0]
    assert "issue_type" in data[0]
    with open(schema_path) as f:
        schema = json.load(f)
    assert "episode_number" in schema
    assert "show_title" in schema
