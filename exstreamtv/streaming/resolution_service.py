"""
Stream Resolution Service — Unified resolution boundary.

ChannelManager calls only this service. Isolates:
- Authority (clock, timeline)
- Resolver registry
- Contract enforcement

ORM boundary: service uses DB for authority; resolvers receive DTO only.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from exstreamtv.scheduling.canonical_timeline import CanonicalTimelineItem
from exstreamtv.scheduling.clock import ResolvedPosition
from exstreamtv.streaming.contract import (
    SourceClassification,
    StreamingContractEnforcer,
    StreamSource,
    ValidationResult,
)
from exstreamtv.streaming.resolver_registry import ResolverRegistryError, get_resolver_registry, _resolved_to_stream_source
from exstreamtv.streaming.resolvers.base import ResolverError, SourceType

logger = logging.getLogger(__name__)


@dataclass
class ResolvedStreamPosition:
    """Resolved position with validated StreamSource or contract violation."""

    item: CanonicalTimelineItem
    seek_offset: float
    title: str
    source: str
    media_id: Optional[int]
    canonical_duration: float
    stream_source: Optional[StreamSource] = None
    validation: Optional[ValidationResult] = None
    anchor_time: Optional[datetime] = None


def _source_str_to_type(source: str) -> SourceType:
    """Map source string to SourceType."""
    s = (source or "unknown").lower()
    if "plex" in s:
        return SourceType.PLEX
    if "youtube" in s or "youtu" in s:
        return SourceType.YOUTUBE
    if "archive" in s:
        return SourceType.ARCHIVE_ORG
    if "jellyfin" in s or "emby" in s:
        return SourceType.JELLYFIN
    if "local" in s or "file" in s:
        return SourceType.LOCAL
    if "m3u" in s:
        return SourceType.M3U
    return SourceType.UNKNOWN


class StreamResolutionService:
    """
    Unified resolution: position + source + contract.

    Usage:
        service = StreamResolutionService(db_session_factory)
        result = await service.resolve_for_streaming(channel_id)
        if result and result.stream_source:
            # validated, launch FFmpeg
        elif result and not result.stream_source:
            # contract violation, emit slate
    """

    def __init__(
        self,
        db_session_factory: Callable[[], Session],
        authority: Optional[Any] = None,
        registry: Optional[Any] = None,
    ):
        self._db_session_factory = db_session_factory
        self._authority = authority
        self._registry = registry or get_resolver_registry()
        self._contract = StreamingContractEnforcer()

    def _get_authority(self) -> Any:
        if self._authority:
            return self._authority
        from exstreamtv.scheduling.authority import get_authority
        return get_authority(self._db_session_factory)

    async def resolve_position(
        self,
        channel_id: int,
        now: Optional[datetime] = None,
    ) -> Optional[ResolvedPosition]:
        """Resolve clock position to timeline item. No DB beyond authority."""
        auth = self._get_authority()
        clock = await auth.ensure_clock(channel_id)
        if not clock:
            return None
        timeline = auth.get_timeline(channel_id)
        if not timeline:
            return None
        return clock.resolve_item_and_seek(timeline, now)

    async def resolve_source(
        self,
        item: CanonicalTimelineItem,
        seek_offset: float,
    ) -> Optional[StreamSource]:
        """
        Resolve timeline item to StreamSource via registry.

        Returns None on resolver failure. Never raises for recoverable errors.
        """
        if item.resolved_url:
            source_type = _source_str_to_type(item.source)
            class_map = {
                SourceType.PLEX: SourceClassification.PLEX,
                SourceType.YOUTUBE: SourceClassification.YOUTUBE,
                SourceType.ARCHIVE_ORG: SourceClassification.ARCHIVE,
                SourceType.LOCAL: SourceClassification.FILE,
            }
            return StreamSource(
                url=item.resolved_url,
                headers={},
                seek_offset=seek_offset,
                probe_required="archive" in (item.source or "") or "youtube" in (item.source or "").lower(),
                allow_retry=True,
                classification=class_map.get(source_type, SourceClassification.URL),
                source_type=source_type,
                title=item.title or item.custom_title or "Unknown",
                canonical_duration=item.canonical_duration or 1800.0,
            )

        source_type = _source_str_to_type(item.source)
        try:
            resolver = self._registry.get(source_type)
        except ResolverRegistryError as e:
            logger.warning(f"No resolver for {source_type.value}: {e}")
            return None

        media_item = item.media_item or {}
        if isinstance(media_item, dict) and not media_item and item.playout_item:
            url = (item.playout_item or {}).get("source_url") if isinstance(item.playout_item, dict) else getattr(item.playout_item, "source_url", None)
            if url:
                return StreamSource(
                    url=url,
                    headers={},
                    seek_offset=seek_offset,
                    probe_required=True,
                    allow_retry=True,
                    classification=SourceClassification.URL,
                    source_type=SourceType.UNKNOWN,
                    title=item.title or "Unknown",
                    canonical_duration=item.canonical_duration or 1800.0,
                )
            return None

        try:
            resolved = await resolver.resolve(media_item, force_refresh=False)
            return _resolved_to_stream_source(
                resolved,
                seek_offset=seek_offset,
                title=item.title or item.custom_title or "Unknown",
                duration=item.canonical_duration or 1800.0,
            )
        except ResolverError as e:
            logger.warning(f"Resolver failed for {item.title}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Resolution failed for {item.title}: {e}")
            return None

    async def resolve_for_streaming(
        self,
        channel_id: int,
        now: Optional[datetime] = None,
    ) -> Optional[ResolvedStreamPosition]:
        """
        Full resolution: position + source + contract validation.

        Returns ResolvedStreamPosition with stream_source and validation.
        If validation.valid is False, emit slate and advance.
        """
        auth = self._get_authority()
        clock = await auth.ensure_clock(channel_id)
        if not clock:
            logger.debug(
                f"resolve_for_streaming ch={channel_id}: no clock (timeline load failed)"
            )
            return None
        timeline = auth.get_timeline(channel_id)
        if not timeline:
            logger.debug(
                f"resolve_for_streaming ch={channel_id}: empty timeline (no playout/schedule)"
            )
            return None
        pos = clock.resolve_item_and_seek(timeline, now)
        if not pos:
            logger.debug(
                f"resolve_for_streaming ch={channel_id}: no position from clock"
            )
            return None

        item = pos.item
        anchor_time = clock.anchor_time
        stream_source = await self.resolve_source(item, pos.seek_seconds)
        if not stream_source:
            logger.info(
                f"resolve_for_streaming ch={channel_id}: resolver returned None "
                f"for item '{item.title or item.custom_title}' source={item.source}"
            )
            return ResolvedStreamPosition(
                item=item,
                seek_offset=pos.seek_seconds,
                title=item.title or item.custom_title or "Unknown",
                source=item.source,
                media_id=item.media_id,
                canonical_duration=item.canonical_duration or 1800,
                stream_source=None,
                validation=None,
                anchor_time=anchor_time,
            )

        validation = self._contract.validate(stream_source)
        if not validation.valid:
            logger.info(
                f"resolve_for_streaming ch={channel_id}: contract violation "
                f"'{validation.violation_reason}' for '{item.title or item.custom_title}'"
            )
        return ResolvedStreamPosition(
            item=item,
            seek_offset=pos.seek_seconds,
            title=item.title or item.custom_title or "Unknown",
            source=item.source,
            media_id=item.media_id,
            canonical_duration=item.canonical_duration or 1800,
            stream_source=stream_source if validation.valid else None,
            validation=validation,
            anchor_time=anchor_time,
        )


_resolution_service: Optional[StreamResolutionService] = None


def get_resolution_service(db_session_factory: Callable[[], Session]) -> StreamResolutionService:
    """Get or create the global StreamResolutionService."""
    global _resolution_service
    if _resolution_service is None:
        _resolution_service = StreamResolutionService(db_session_factory)
    return _resolution_service
