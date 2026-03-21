"""
StreamPositionResolver — Resolve clock position to stream item + seek.

Queries ChannelClock. No schedule mutation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from exstreamtv.scheduling.authority import BroadcastScheduleAuthority, get_authority
from exstreamtv.scheduling.canonical_timeline import CanonicalTimelineItem
from exstreamtv.scheduling.clock import ResolvedPosition

logger = logging.getLogger(__name__)


@dataclass
class StreamPosition:
    """Resolved stream position for playback."""

    media_url: str
    seek_offset: float
    item: CanonicalTimelineItem
    title: str
    source: str
    media_id: Optional[int]
    canonical_duration: float


class StreamPositionResolver:
    """
    Resolve clock position to streamable item.
    Query ChannelClock only. No index, no advancement.
    """

    def __init__(self, authority: Optional[BroadcastScheduleAuthority] = None):
        self._authority = authority

    def _get_authority(self, db_session_factory: Callable[[], Session]) -> BroadcastScheduleAuthority:
        if self._authority:
            return self._authority
        return get_authority(db_session_factory)

    async def resolve(
        self,
        channel_id: int,
        db_session_factory: Callable[[], Session],
        now: Optional[datetime] = None,
        authority: Optional[BroadcastScheduleAuthority] = None,
    ) -> Optional[StreamPosition]:
        """
        Resolve current clock position to stream item.

        Returns media_url, seek_offset, and item metadata.
        """
        auth = authority or self._get_authority(db_session_factory)
        clock = await auth.ensure_clock(channel_id)
        if not clock:
            return None
        timeline = auth.get_timeline(channel_id)
        if not timeline:
            return None
        pos = clock.resolve_item_and_seek(timeline, now)
        if not pos:
            return None
        item = pos.item
        media_url = item.resolved_url
        if not media_url and item.media_item:
            try:
                from exstreamtv.streaming.url_resolver import get_url_resolver
                resolver = get_url_resolver()
                resolved = await resolver.resolve(item.media_item)
                media_url = resolved.url
            except Exception as e:
                logger.warning(f"URL resolve failed for item: {e}")
                return None
        if not media_url and item.playout_item and hasattr(item.playout_item, "source_url"):
            media_url = item.playout_item.source_url
        if not media_url:
            logger.warning("No media URL for resolved item")
            return None
        return StreamPosition(
            media_url=media_url,
            seek_offset=pos.seek_seconds,
            item=item,
            title=item.title or item.custom_title or "Unknown",
            source=item.source,
            media_id=item.media_id,
            canonical_duration=item.canonical_duration or 1800,
        )
