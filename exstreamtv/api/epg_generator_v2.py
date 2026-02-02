"""XMLTV EPG generation v2 - Proper program mapping and metadata from schedule data"""

import logging
from datetime import datetime, timedelta
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from sqlalchemy.orm import Session

from ..database.models_v2 import Channel
from ..database.session import get_db
from ..scheduling.engine_v2 import ScheduleEngineV2
from ..scheduling.parser import ScheduleParser

logger = logging.getLogger(__name__)


class EPGGeneratorV2:
    """
    XMLTV EPG generator v2

    Generates proper XMLTV EPG data from schedule timeline with all metadata fields
    """

    def __init__(
        self,
        db_session_factory: Any | None = None,
        schedule_engine: Any | None = None,
        plex_client: Any | None = None,
    ) -> None:
        """
        Initialize EPG generator v2.

        Args:
            db_session_factory: Database session factory (callable returning Session)
            schedule_engine: Schedule engine instance
            plex_client: Optional Plex client for additional metadata
        """
        self.db_session_factory = db_session_factory or (lambda: get_db().__next__())
        self.schedule_engine = schedule_engine
        self.plex_client = plex_client

    def generate_xmltv(
        self,
        channels: list[Channel],
        start_time: datetime | None = None,
        duration_hours: int = 24,
        base_url: str | None = None,
    ) -> str:
        """
        Generate XMLTV EPG XML

        Args:
            channels: List of channels
            start_time: Start time for EPG
            duration_hours: Duration in hours
            base_url: Base URL for icons/streams

        Returns:
            XMLTV XML string
        """
        start_time = start_time or datetime.utcnow()
        end_time = start_time + timedelta(hours=duration_hours)

        # Initialize schedule engine if needed
        db = self.db_session_factory()
        if not self.schedule_engine:
            try:
                from ..scheduling.engine_v2 import ScheduleEngineV2

                self.schedule_engine = ScheduleEngineV2(db)
            except ImportError:
                logger.warning("ScheduleEngineV2 not available, EPG generation may be limited")
                self.schedule_engine = None

        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE tv SYSTEM "xmltv.dtd">',
            '<tv source-info-url="https://streamtv.example.com" source-info-name="StreamTV" generator-info-name="StreamTV EPG Generator v2" generator-info-url="https://streamtv.example.com">',
        ]

        # Generate channel entries
        for channel in channels:
            if not channel.enabled:
                continue

            channel_id = f"streamtv.{channel.number}"
            display_name = channel.name

            # Channel icon
            icon_tag = ""
            if channel.icon_path:
                icon_url = f"{base_url}{channel.icon_path}" if base_url else channel.icon_path
                icon_tag = f'<icon src="{xml_escape(icon_url)}" />'

            xml_parts.append(f'  <channel id="{xml_escape(channel_id)}">')
            xml_parts.append(f"    <display-name>{xml_escape(display_name)}</display-name>")
            if icon_tag:
                xml_parts.append(f"    {icon_tag}")
            xml_parts.append("  </channel>")

        # Generate programme entries
        for channel in channels:
            if not channel.enabled:
                continue

            channel_id = f"streamtv.{channel.number}"

            # Get timeline for channel
            timeline = self._get_channel_timeline(channel, start_time, end_time, db)

            for item in timeline:
                programme_xml = self._generate_programme_xml(
                    channel_id=channel_id, item=item, base_url=base_url
                )
                if programme_xml:
                    xml_parts.append(programme_xml)

        xml_parts.append("</tv>")

        db.close()

        return "\n".join(xml_parts)

    def _get_channel_timeline(
        self, channel: Channel, start_time: datetime, end_time: datetime, db: Session
    ) -> list[dict[str, Any]]:
        """Get timeline items for a channel"""
        try:
            # Load schedule
            schedule_file_path = channel.schedule_file_path
            if not schedule_file_path:
                return []

            from pathlib import Path

            schedule_path = Path(schedule_file_path)
            if not schedule_path.exists():
                return []

            schedule = ScheduleParser.parse_file(schedule_path)

            # Generate timeline
            if not self.schedule_engine:
                self.schedule_engine = ScheduleEngineV2(db)

            timeline = self.schedule_engine.generate_timeline(
                channel=channel,
                schedule=schedule,
                start_time=start_time,
                duration=end_time - start_time,
            )

            return timeline

        except Exception as e:
            logger.exception(f"Error getting timeline for channel {channel.number}: {e}")
            return []

    def _generate_programme_xml(
        self, channel_id: str, item: dict[str, Any], base_url: str | None = None
    ) -> str | None:
        """Generate XMLTV programme entry"""
        media_item = item.get("media_item")
        if not media_item:
            return None

        start_time = item.get("start_time", datetime.utcnow())
        end_time = item.get("end_time")
        if not end_time:
            duration = timedelta(seconds=media_item.duration or 3600)
            end_time = start_time + duration

        # Format times for XMLTV
        start_str = start_time.strftime("%Y%m%d%H%M%S %z")
        stop_str = end_time.strftime("%Y%m%d%H%M%S %z")

        # Get title (use AI-enhanced if available)
        title = media_item.ai_enhanced_title or media_item.title or "Untitled"

        # Get description (use AI-enhanced if available)
        description = media_item.ai_enhanced_description or media_item.description or ""

        # Build programme XML
        xml_parts = [
            f'  <programme start="{xml_escape(start_str)}" stop="{xml_escape(stop_str)}" channel="{xml_escape(channel_id)}">',
            f'    <title lang="en">{xml_escape(title)}</title>',
        ]

        if description:
            xml_parts.append(f'    <desc lang="en">{xml_escape(description[:500])}</desc>')

        # Add thumbnail
        if media_item.thumbnail:
            icon_url = media_item.thumbnail
            if base_url and not icon_url.startswith("http"):
                icon_url = f"{base_url}{icon_url}"
            xml_parts.append(f'    <icon src="{xml_escape(icon_url)}" />')

        # Add categories from metadata
        categories = []
        if media_item.archive_org_subject:
            import json

            try:
                subjects = json.loads(media_item.archive_org_subject)
                categories.extend(subjects[:3])  # Limit to 3 categories
            except Exception:
                pass

        if media_item.youtube_tags:
            import json

            try:
                tags = json.loads(media_item.youtube_tags)
                categories.extend(tags[:3])
            except Exception:
                pass

        for category in categories[:5]:  # Limit total categories
            xml_parts.append(f'    <category lang="en">{xml_escape(str(category))}</category>')

        # Add date if available
        if media_item.upload_date:
            date_str = media_item.upload_date.strftime("%Y%m%d")
            xml_parts.append(f"    <date>{xml_escape(date_str)}</date>")

        # Add episode number if extractable from title
        episode_num = self._extract_episode_number(title)
        if episode_num:
            xml_parts.append(
                f'    <episode-num system="onscreen">{xml_escape(episode_num)}</episode-num>'
            )

        xml_parts.append("  </programme>")

        return "\n".join(xml_parts)

    def _extract_episode_number(self, title: str) -> str | None:
        """Extract episode number from title (e.g., "S01E01", "Episode 1")"""
        import re

        # Try S##E## format
        match = re.search(r"S(\d+)E(\d+)", title, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return f"{season}.{episode}"

        # Try Episode ## format
        match = re.search(r"Episode\s+(\d+)", title, re.IGNORECASE)
        if match:
            return f"0.{match.group(1)}"

        return None
