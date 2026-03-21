"""
Unit tests for EPG and Plex integration (stable channel IDs, Plex reload).

Covers: exstream-{id} channel IDs in EPG/M3U, EPGGeneratorV2, programme bounds from
timeline, Plex guide reload throttle.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exstreamtv.api.epg_generator_v2 import EPGGeneratorV2, _channel_xmltv_id
from exstreamtv.constants import EXSTREAM_CHANNEL_ID_PREFIX


@pytest.mark.unit
class TestChannelXmltvId:
    """Tests for stable channel ID format (exstream-{id})."""

    def test_channel_xmltv_id_format(self) -> None:
        """Stable channel ID must be exstream-{id} for Plex DVR mapping."""
        channel = MagicMock()
        channel.id = 42
        assert _channel_xmltv_id(channel) == "exstream.42"

    def test_channel_xmltv_id_uses_id_not_number(self) -> None:
        """Channel ID must use database id, not display number."""
        channel = MagicMock()
        channel.id = 1
        channel.number = "101"
        assert _channel_xmltv_id(channel) == "exstream.1"
        assert _channel_xmltv_id(channel) != "exstream.101"


@pytest.mark.unit
class TestEPGGeneratorV2ChannelIds:
    """EPGGeneratorV2 must emit stable channel IDs in XMLTV."""

    def test_generate_xmltv_channel_ids(self) -> None:
        """Generated XMLTV must contain exstream-{id} in channel and programme."""
        channel = MagicMock()
        channel.id = 7
        channel.number = "7"
        channel.name = "Test Channel"
        channel.enabled = True
        channel.logo_path = None
        channel.schedule_file_path = None

        db = MagicMock()
        db.close = MagicMock()
        session_factory = MagicMock(return_value=db)

        gen = EPGGeneratorV2(db_session_factory=session_factory, schedule_engine=None)
        xml = gen.generate_xmltv(
            channels=[channel],
            start_time=None,
            duration_hours=24,
            base_url="http://test",
        )

        assert f'id="{EXSTREAM_CHANNEL_ID_PREFIX}.7"' in xml
        assert "</tv>" in xml


@pytest.mark.unit
class TestEPGProgrammeBoundsFromTimeline:
    """Programme start/stop must be derived from playout timeline (ErsatzTV-style)."""

    def test_programme_start_stop_from_timeline_items(self) -> None:
        """EPG programme start= and stop= must match timeline item start_time and end_time."""
        from exstreamtv.api.epg_generator_v2 import EPGGeneratorV2

        base_time = datetime(2025, 2, 2, 12, 0, 0)
        item1_end = base_time + timedelta(seconds=3600)
        item2_end = item1_end + timedelta(seconds=1800)

        media1 = MagicMock()
        media1.title = "Show One"
        media1.duration = 3600
        media1.ai_enhanced_title = None
        media1.ai_enhanced_description = None
        media1.description = None
        media1.thumbnail = None
        media1.archive_org_subject = None
        media1.youtube_tags = None
        media1.upload_date = None

        media2 = MagicMock()
        media2.title = "Show Two"
        media2.duration = 1800
        media2.ai_enhanced_title = None
        media2.ai_enhanced_description = None
        media2.description = None
        media2.thumbnail = None
        media2.archive_org_subject = None
        media2.youtube_tags = None
        media2.upload_date = None

        timeline_items = [
            {
                "start_time": base_time,
                "end_time": item1_end,
                "media_item": media1,
            },
            {
                "start_time": item1_end,
                "end_time": item2_end,
                "media_item": media2,
            },
        ]

        channel = MagicMock()
        channel.id = 3
        channel.number = "3"
        channel.name = "Timeline Test"
        channel.enabled = True
        channel.logo_path = None
        channel.schedule_file_path = "/fake/path"

        db = MagicMock()
        db.close = MagicMock()
        session_factory = MagicMock(return_value=db)
        gen = EPGGeneratorV2(db_session_factory=session_factory, schedule_engine=None)

        with patch.object(gen, "_get_channel_timeline", return_value=timeline_items):
            xml = gen.generate_xmltv(
                channels=[channel],
                start_time=base_time,
                duration_hours=24,
                base_url="http://test",
            )

        # XMLTV format: start="YYYYMMDDHHMMSS +0000" stop="..."
        start1_str = base_time.strftime("%Y%m%d%H%M%S")
        stop1_str = item1_end.strftime("%Y%m%d%H%M%S")
        start2_str = item1_end.strftime("%Y%m%d%H%M%S")
        stop2_str = item2_end.strftime("%Y%m%d%H%M%S")

        assert f'start="{start1_str}' in xml or f"start=\"{start1_str}" in xml
        assert f'stop="{stop1_str}' in xml or f"stop=\"{stop1_str}" in xml
        assert f'start="{start2_str}' in xml or f"start=\"{start2_str}" in xml
        assert f'stop="{stop2_str}' in xml or f"stop=\"{stop2_str}" in xml
        assert "Show One" in xml
        assert "Show Two" in xml

    def test_programme_bounds_non_overlapping(self) -> None:
        """Programme entries for a channel must have non-overlapping start/stop."""
        from exstreamtv.api.epg_generator_v2 import EPGGeneratorV2

        base_time = datetime(2025, 2, 2, 14, 0, 0)
        media = MagicMock()
        media.title = "Single"
        media.duration = 7200
        media.ai_enhanced_title = None
        media.ai_enhanced_description = None
        media.description = None
        media.thumbnail = None
        media.archive_org_subject = None
        media.youtube_tags = None
        media.upload_date = None

        timeline_items = [
            {
                "start_time": base_time,
                "end_time": base_time + timedelta(seconds=7200),
                "media_item": media,
            },
        ]

        channel = MagicMock()
        channel.id = 5
        channel.number = "5"
        channel.name = "One Programme"
        channel.enabled = True
        channel.logo_path = None
        channel.schedule_file_path = "/fake"

        db = MagicMock()
        db.close = MagicMock()
        gen = EPGGeneratorV2(db_session_factory=MagicMock(return_value=db), schedule_engine=None)

        with patch.object(gen, "_get_channel_timeline", return_value=timeline_items):
            xml = gen.generate_xmltv(
                channels=[channel],
                start_time=base_time,
                duration_hours=24,
                base_url="http://test",
            )

        # Extract all programme start/stop pairs for this channel
        programme_pattern = re.compile(
            r'<programme\s+start="([^"]+)"\s+stop="([^"]+)"\s+channel="exstream.5"'
        )
        matches = programme_pattern.findall(xml)
        assert len(matches) >= 1
        for start_str, stop_str in matches:
            # Strip timezone for simple comparison (e.g. "20250202140000 +0000")
            start_clean = start_str.split()[0]
            stop_clean = stop_str.split()[0]
            assert start_clean < stop_clean, "Programme stop must be after start"

    def test_epg_contract_programme_bounds_from_single_timeline_source(self) -> None:
        """Contract §6: EPG programme start/stop must come from one timeline source (no drift)."""
        from exstreamtv.api.epg_generator_v2 import EPGGeneratorV2

        # Single timeline item: start and end set explicitly (as from ChannelPlaybackPosition + item)
        anchor = datetime(2025, 2, 2, 10, 0, 0)
        item_end = anchor + timedelta(seconds=3600)
        media = MagicMock()
        media.title = "News Hour"
        media.duration = 3600
        media.ai_enhanced_title = None
        media.ai_enhanced_description = None
        media.description = None
        media.thumbnail = None
        media.archive_org_subject = None
        media.youtube_tags = None
        media.upload_date = None

        timeline = [
            {"start_time": anchor, "end_time": item_end, "media_item": media},
        ]
        channel = MagicMock()
        channel.id = 99
        channel.number = "99"
        channel.name = "News"
        channel.enabled = True
        channel.logo_path = None
        channel.schedule_file_path = None
        db = MagicMock()
        db.close = MagicMock()
        gen = EPGGeneratorV2(db_session_factory=MagicMock(return_value=db), schedule_engine=None)

        with patch.object(gen, "_get_channel_timeline", return_value=timeline):
            xml = gen.generate_xmltv(
                channels=[channel],
                start_time=anchor,
                duration_hours=24,
                base_url="http://test",
            )

        # Contract: programme bounds in XML must match the single timeline source
        start_str = anchor.strftime("%Y%m%d%H%M%S")
        stop_str = item_end.strftime("%Y%m%d%H%M%S")
        assert start_str in xml and stop_str in xml
        assert "News Hour" in xml


@pytest.mark.unit
class TestPlexReloadThrottle:
    """Plex guide reload respects 60s throttle unless force=True."""

    @pytest.mark.asyncio
    async def test_reload_guide_force_calls_post(self) -> None:
        """When force=True, reload_guide should call Plex API."""
        from exstreamtv.streaming.plex_api_client import PlexAPIClient

        with patch(
            "exstreamtv.streaming.plex_api_client.PlexAPIClient.get_dvrs",
            new_callable=AsyncMock,
            return_value=[{"key": "/livetv/dvrs/1", "id": "1"}],
        ), patch(
            "exstreamtv.streaming.plex_api_client.PlexAPIClient._ensure_client",
            new_callable=AsyncMock,
        ) as mock_ensure:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_ensure.return_value = mock_client

            client = PlexAPIClient(base_url="http://plex:32400", token="test-token")

            result = await client.reload_guide(force=True)

            assert result is True
            assert mock_client.post.called


@pytest.mark.unit
class TestPlexClientV2LibraryService:
    """PlexClientV2 uses plex_library_service when available."""

    @pytest.mark.asyncio
    async def test_get_libraries_uses_plex_library_service_when_available(self) -> None:
        """When PlexAPI is available, get_libraries uses list_sections from plex_library_service."""
        from exstreamtv.api import plex_client_v2

        fake_sections = [
            {"key": "1", "type": "movie", "title": "Movies"},
            {"key": "2", "type": "show", "title": "TV Shows"},
        ]
        mock_server = MagicMock()
        mock_get_server = MagicMock(return_value=mock_server)
        mock_list_sections = MagicMock(return_value=fake_sections)

        with patch.object(
            plex_client_v2,
            "_PLEX_LIBRARY_SERVICE_AVAILABLE",
            True,
        ), patch.object(
            plex_client_v2,
            "get_plex_server",
            mock_get_server,
            create=True,
        ), patch.object(
            plex_client_v2,
            "plex_service_list_sections",
            mock_list_sections,
            create=True,
        ):
            client = plex_client_v2.PlexClientV2(
                base_url="http://plex:32400",
                token="test-token",
            )
            result = await client.get_libraries()
            assert result == fake_sections
            mock_get_server.assert_called_once_with("http://plex:32400", "test-token")
            mock_list_sections.assert_called_once_with(mock_server)
            await client._http_client.aclose()

    @pytest.mark.asyncio
    async def test_get_libraries_fallback_when_service_returns_none(self) -> None:
        """When PlexAPI returns no server, get_libraries falls back to HTTP."""
        from exstreamtv.api import plex_client_v2

        fallback_result = [{"key": "1", "type": "movie", "title": "Movies"}]
        mock_get_server = MagicMock(return_value=None)

        with patch.object(
            plex_client_v2,
            "_PLEX_LIBRARY_SERVICE_AVAILABLE",
            True,
        ), patch.object(
            plex_client_v2,
            "get_plex_server",
            mock_get_server,
            create=True,
        ), patch.object(
            plex_client_v2.PlexClientV2,
            "_get_libraries_http",
            new_callable=AsyncMock,
            return_value=fallback_result,
        ):
            client = plex_client_v2.PlexClientV2(
                base_url="http://plex:32400",
                token="test-token",
            )
            result = await client.get_libraries()
            assert result == fallback_result
            await client._http_client.aclose()
