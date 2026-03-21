"""
Section D — XMLTV and Guide Hardening Tests.

Validates:
- Datetime validation (1970-2100) in XMLTVGenerator.
- Empty channel mapping returns 503.
- Lineup validation failure returns 503.
- XMLTVValidationError from EPG build returns 503 with Retry-After.
- Config: episode_num_required, plex_xmltv_mismatch_ratio_threshold.
- Production path uses validate=True.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from _pytest.fixtures import FixtureRequest


# ==================== Datetime Validation ====================


def test_xmltv_generator_rejects_datetime_before_1970() -> None:
    """XMLTVGenerator _validate rejects start_time before 1970."""
    from datetime import timezone

    from exstreamtv.api.timeline_builder import TimelineProgramme
    from exstreamtv.api.xmltv_generator import XMLTVGenerator, XMLTVValidationError

    # 1969-12-31 23:59:59 UTC (timezone-aware for consistent timestamp)
    invalid_start = datetime(1969, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
    stop_time = datetime(1970, 1, 1, 0, 5, 0, tzinfo=timezone.utc)
    prog = TimelineProgramme(
        start_time=invalid_start,
        stop_time=stop_time,
        media_item=None,
        playout_item=None,
        title="Test Show",
        index=0,
    )
    channels = [MagicMock(id=1, name="Channel 1")]
    programmes_by_channel = {1: [prog]}

    gen = XMLTVGenerator()
    with pytest.raises(XMLTVValidationError) as exc_info:
        gen.generate(channels, programmes_by_channel, validate=True)

    err = exc_info.value
    msg = str(err).lower()
    details = " ".join(getattr(err, "details", [])).lower()
    assert "1970" in msg or "1970" in details or "range" in details


def test_xmltv_generator_rejects_datetime_after_2100() -> None:
    """XMLTVGenerator _validate rejects stop_time after 2100."""
    from datetime import timezone

    from exstreamtv.api.timeline_builder import TimelineProgramme
    from exstreamtv.api.xmltv_generator import XMLTVGenerator, XMLTVValidationError

    start_time = datetime(2099, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
    invalid_stop = datetime(2101, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    prog = TimelineProgramme(
        start_time=start_time,
        stop_time=invalid_stop,
        media_item=None,
        playout_item=None,
        title="Test Show",
        index=0,
    )
    channels = [MagicMock(id=1, name="Channel 1")]
    programmes_by_channel = {1: [prog]}

    gen = XMLTVGenerator()
    with pytest.raises(XMLTVValidationError) as exc_info:
        gen.generate(channels, programmes_by_channel, validate=True)

    err = exc_info.value
    msg = str(err).lower()
    details = " ".join(getattr(err, "details", [])).lower()
    assert "2100" in msg or "2100" in details or "range" in details


def test_xmltv_generator_accepts_valid_datetime_range() -> None:
    """XMLTVGenerator accepts programmes within 1970-2100."""
    from exstreamtv.api.timeline_builder import TimelineProgramme
    from exstreamtv.api.xmltv_generator import XMLTVGenerator

    start_time = datetime(2025, 2, 21, 12, 0, 0)
    stop_time = datetime(2025, 2, 21, 12, 30, 0)
    prog = TimelineProgramme(
        start_time=start_time,
        stop_time=stop_time,
        media_item=None,
        playout_item=None,
        title="Valid Show",
        index=0,
    )
    channels = [MagicMock(id=1, name="Channel 1")]
    programmes_by_channel = {1: [prog]}

    gen = XMLTVGenerator()
    xml = gen.generate(channels, programmes_by_channel, validate=True)
    assert "<tv" in xml
    assert "Valid Show" in xml


# ==================== Config ====================


def test_epg_config_has_episode_num_required() -> None:
    """EPGConfig includes episode_num_required (default False)."""
    from exstreamtv.config import EPGConfig

    cfg = EPGConfig()
    assert hasattr(cfg, "episode_num_required")
    assert cfg.episode_num_required is False


def test_epg_config_has_plex_xmltv_mismatch_ratio_threshold() -> None:
    """EPGConfig includes plex_xmltv_mismatch_ratio_threshold (default 0.15)."""
    from exstreamtv.config import EPGConfig

    cfg = EPGConfig()
    assert hasattr(cfg, "plex_xmltv_mismatch_ratio_threshold")
    assert cfg.plex_xmltv_mismatch_ratio_threshold == 0.15


# ==================== Lineup Validation ====================


def test_validate_xmltv_lineup_rejects_duplicate_guide_number() -> None:
    """validate_xmltv_lineup returns False for duplicate GuideNumber."""
    from exstreamtv.monitoring.metadata_metrics import validate_xmltv_lineup

    ch1 = MagicMock(number="1", id=1, name="Channel A")
    ch2 = MagicMock(number="1", id=2, name="Channel B")  # same number
    result = validate_xmltv_lineup([ch1, ch2])
    assert result is False


def test_validate_xmltv_lineup_rejects_empty_display_name() -> None:
    """validate_xmltv_lineup returns False for empty display name."""
    from exstreamtv.monitoring.metadata_metrics import validate_xmltv_lineup

    ch = MagicMock()
    ch.number = "1"
    ch.id = 1
    ch.name = ""  # empty display name
    result = validate_xmltv_lineup([ch])
    assert result is False


def test_validate_xmltv_lineup_accepts_valid_lineup() -> None:
    """validate_xmltv_lineup returns True for valid lineup."""
    from exstreamtv.monitoring.metadata_metrics import validate_xmltv_lineup

    ch1 = MagicMock(number="1", id=1, name="Channel A")
    ch2 = MagicMock(number="2", id=2, name="Channel B")
    result = validate_xmltv_lineup([ch1, ch2])
    assert result is True


# ==================== get_epg 503 Behavior ====================


@pytest.mark.asyncio
async def test_get_epg_empty_channels_returns_503() -> None:
    """get_epg returns 503 when channel mapping is empty."""
    from fastapi import HTTPException

    with patch("exstreamtv.api.iptv.get_db", new_callable=AsyncMock) as mock_get_db:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_db.return_value = mock_session

        from exstreamtv.api.iptv import get_epg

        with pytest.raises(HTTPException) as exc_info:
            await get_epg(db=mock_session)

        assert exc_info.value.status_code == 503
        assert "Empty" in str(exc_info.value.detail)
        assert exc_info.value.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_get_epg_lineup_validation_failure_returns_503() -> None:
    """get_epg returns 503 when validate_xmltv_lineup returns False (duplicate GuideNumber)."""
    from fastapi import HTTPException

    ch1 = MagicMock()
    ch1.number = "1"
    ch1.id = 1
    ch1.name = "Channel A"
    ch2 = MagicMock()
    ch2.number = "1"  # duplicate
    ch2.id = 2
    ch2.name = "Channel B"
    with patch("exstreamtv.api.iptv.get_db", new_callable=AsyncMock) as mock_get_db:
        mock_session = AsyncMock()
        scalar_res = MagicMock()
        scalar_res.all.return_value = [ch1, ch2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = scalar_res
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_db.return_value = mock_session

        from exstreamtv.api.iptv import get_epg

        with pytest.raises(HTTPException) as exc_info:
            await get_epg(db=mock_session)

        assert exc_info.value.status_code == 503
        assert "lineup" in str(exc_info.value.detail).lower()
        assert exc_info.value.headers.get("Retry-After") == "60"


@pytest.mark.asyncio
async def test_get_epg_xmltv_validation_error_returns_503() -> None:
    """get_epg returns 503 with Retry-After when XMLTVValidationError raised."""
    from exstreamtv.api.xmltv_generator import XMLTVValidationError
    from fastapi import HTTPException

    ch = MagicMock(number="1", id=1, name="Channel A")
    with patch("exstreamtv.api.iptv.get_db", new_callable=AsyncMock) as mock_get_db:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars().all.return_value = [ch]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_get_db.return_value = mock_session

        async def _build_raises(*args: object, **kwargs: object) -> None:
            raise XMLTVValidationError("Invalid programme")

        with patch(
            "exstreamtv.api.iptv._build_epg_via_timeline_builder",
            new=_build_raises,
        ):
            from exstreamtv.api.iptv import get_epg

            with pytest.raises(HTTPException) as exc_info:
                await get_epg(db=mock_session)

            assert exc_info.value.status_code == 503
            assert exc_info.value.headers.get("Retry-After") == "60"


# ==================== Invariant: validate=True ====================


def test_build_epg_uses_validate_true() -> None:
    """_build_epg_via_timeline_builder passes validate=True (Section D.2)."""
    import inspect

    from exstreamtv.api import iptv

    source = inspect.getsource(iptv._build_epg_via_timeline_builder)
    assert "validate=True" in source
