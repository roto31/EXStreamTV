"""
CanonicalTimelineBuilder — Build timeline with ffprobe-validated durations.

YAML duration and metadata duration are not authoritative.
Canonical duration is derived from ffprobe only.

CRITICAL: All ORM objects must be converted to plain DTOs before session closes.
Never store MediaItem/PlayoutItem in timeline items — lazy .files causes DetachedInstanceError.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from exstreamtv.database import Channel, Playout, PlayoutItem, MediaItem
from exstreamtv.scheduling.duration_validator import (
    DEFAULT_DURATION_IF_PROBE_FAILS,
    validate_duration,
)

# Import for metadata-only duration (no ffprobe)
from exstreamtv.scheduling.duration_validator import _get_metadata_duration as _duration_from_metadata  # noqa: SLF001
from exstreamtv.scheduling.parser import ParsedSchedule, ScheduleParser
from exstreamtv.scheduling.engine import ScheduleEngine

logger = logging.getLogger(__name__)


def _media_item_to_dto(mi: Any) -> Optional[dict]:
    """
    Convert MediaItem ORM to plain dict. Must be called while session is open.
    Extracts files to avoid lazy-load DetachedInstanceError.
    Includes source-specific fields needed by URL resolvers.
    """
    if not mi:
        return None
    files_list: list[dict] = []
    try:
        for f in (mi.files or []):
            files_list.append({"path": getattr(f, "path", None) or "", "url": getattr(f, "url", None)})
    except Exception:
        pass
    path = None
    if files_list and files_list[0].get("path"):
        path = files_list[0]["path"]
    url = getattr(mi, "url", None)
    if not url and path:
        url = path if (str(path).startswith("http") or "archive.org" in str(path)) else None
    if not url:
        yid = getattr(mi, "youtube_video_id", None)
        if yid:
            url = f"https://www.youtube.com/watch?v={yid}"
    return {
        "id": getattr(mi, "id", None),
        "duration": getattr(mi, "duration", None),
        "title": getattr(mi, "title", None),
        "source": getattr(mi, "source", None) or "url",
        "url": url,
        "path": path or getattr(mi, "path", None),
        "files": files_list,
        # Source-specific fields for resolver detection/URL building
        "archive_org_identifier": getattr(mi, "archive_org_identifier", None),
        "archive_org_filename": getattr(mi, "archive_org_filename", None),
        "youtube_video_id": getattr(mi, "youtube_video_id", None),
        "plex_rating_key": getattr(mi, "plex_rating_key", None),
        "source_id": getattr(mi, "source_id", None),
        "external_id": getattr(mi, "external_id", None),
        "jellyfin_item_id": getattr(mi, "jellyfin_item_id", None),
        "emby_item_id": getattr(mi, "emby_item_id", None),
        "meta_data": getattr(mi, "meta_data", None),
        # Title fallbacks for EPG
        "original_title": getattr(mi, "original_title", None),
        "sort_title": getattr(mi, "sort_title", None),
        "episode_title": getattr(mi, "episode_title", None),
        "series_title": getattr(mi, "series_title", None),
        "show_title": getattr(mi, "show_title", None),
    }


def _playout_item_to_dto(pi: Any) -> Optional[dict]:
    """Convert PlayoutItem ORM to plain dict. Must be called while session is open."""
    if not pi:
        return None
    duration_secs = None
    st = getattr(pi, "start_time", None)
    ft = getattr(pi, "finish_time", None)
    if st and ft:
        delta = ft - st
        duration_secs = delta.total_seconds() if hasattr(delta, "total_seconds") else None
    return {
        "id": getattr(pi, "id", None),
        "title": getattr(pi, "title", None),
        "custom_title": getattr(pi, "custom_title", None),
        "source_url": getattr(pi, "source_url", None),
        "duration": duration_secs,
    }


@dataclass
class CanonicalTimelineItem:
    """Single item in canonical timeline with ffprobe-validated duration."""

    media_item: Optional[Any] = None
    playout_item: Optional[Any] = None
    canonical_duration: float = 0.0
    title: str = ""
    source: str = "unknown"
    media_id: Optional[int] = None
    custom_title: Optional[str] = None
    # Resolved URL for streaming (set when building)
    resolved_url: Optional[str] = None


async def _resolve_url(media_item: Any, resolver: Any) -> Optional[str]:
    """Resolve media item to stream URL."""
    try:
        resolved = await resolver.resolve(media_item)
        return resolved.url
    except Exception:
        return None


def _get_item_url_or_path(item: dict, media_item: Any) -> Optional[str]:
    """Extract URL or path from schedule item."""
    if media_item:
        if hasattr(media_item, "url") and media_item.url:
            return media_item.url
        if hasattr(media_item, "path") and media_item.path:
            return str(media_item.path)
    pi = item.get("playout_item")
    if pi and hasattr(pi, "source_url") and pi.source_url:
        return pi.source_url
    return None


async def build_from_yaml(
    channel_id: int,
    schedule_file_path: Path,
    db_session_factory: Callable[[], Session],
    max_items: int = 1000,
    probe_timeout: float = 15.0,
) -> list[CanonicalTimelineItem]:
    """
    Build canonical timeline from YAML schedule.

    Parses YAML, runs ScheduleEngine, ffprobes each item for canonical_duration.
    """
    from exstreamtv.streaming.url_resolver import get_url_resolver

    def _sync_build() -> list[dict]:
        session = db_session_factory()
        try:
            channel = session.get(Channel, channel_id)
            if not channel:
                return []
            parsed = ScheduleParser.parse_file(schedule_file_path, schedule_file_path.parent)
            engine = ScheduleEngine(session)
            raw = engine.generate_playlist_from_schedule(channel, parsed, max_items=max_items)
            for item in raw:
                mi = item.get("media_item")
                item["media_item"] = _media_item_to_dto(mi) if mi else None
            return raw
        finally:
            session.close()

    raw_items = await asyncio.to_thread(_sync_build)
    if not raw_items:
        return []

    resolver = get_url_resolver()
    result: list[CanonicalTimelineItem] = []

    for raw in raw_items[:max_items]:
        media_item = raw.get("media_item")  # Plain dict DTO (converted in _sync_build)
        title = raw.get("custom_title") or (media_item.get("title") if media_item else "") or "Unknown"
        source = media_item.get("source") if media_item else "unknown"
        media_id = media_item.get("id") if media_item else None
        resolved_url = None
        if media_item:
            resolved_url = await _resolve_url(media_item, resolver)
        if not resolved_url:
            logger.warning(f"Skipping timeline item '{title}' (media_id={media_id}): resolution failed")
            continue
        canonical_duration = await validate_duration(
            raw,
            resolved_url=resolved_url,
            timeout=probe_timeout,
        )
        result.append(
            CanonicalTimelineItem(
                media_item=media_item,
                playout_item=None,
                canonical_duration=canonical_duration,
                title=title,
                source=source,
                media_id=media_id,
                custom_title=raw.get("custom_title"),
                resolved_url=resolved_url,
            )
        )
    return result


async def build_from_playout(
    channel_id: int,
    db_session_factory: Callable[[], Session],
    max_items: int = 2000,
    probe_timeout: float = 15.0,
    skip_resolution: bool = False,
) -> list[CanonicalTimelineItem]:
    """
    Build canonical timeline from Playout/PlayoutItem (DB).

    When skip_resolution=True (EPG/XML context): use metadata only, no URL resolution
    or ffprobe. All items included. resolved_url=None; resolution happens at stream time.

    When skip_resolution=False: resolve URLs and validate duration via ffprobe.
    Items that fail resolution are skipped (legacy streaming-ready build).
    """

    def _sync_load() -> list[tuple[dict | None, dict | None]]:
        session = db_session_factory()
        try:
            playout_stmt = select(Playout).where(
                Playout.channel_id == channel_id,
                Playout.is_active == True,
            )
            playout = session.execute(playout_stmt).scalar_one_or_none()
            if not playout:
                return []
            stmt = (
                select(PlayoutItem, MediaItem)
                .options(selectinload(MediaItem.files))
                .outerjoin(MediaItem, PlayoutItem.media_item_id == MediaItem.id)
                .where(PlayoutItem.playout_id == playout.id)
                .order_by(PlayoutItem.start_time)
            )
            rows = list(session.execute(stmt).all())
            return [
                (_playout_item_to_dto(pi), _media_item_to_dto(mi))
                for pi, mi in rows
            ]
        finally:
            session.close()

    rows = await asyncio.to_thread(_sync_load)
    if not rows:
        return []

    result: list[CanonicalTimelineItem] = []
    skipped_resolution = 0


    for playout_item_dto, media_item_dto in rows[:max_items]:
        title = (
            (playout_item_dto.get("title") or playout_item_dto.get("custom_title") if playout_item_dto else None)
            or (media_item_dto.get("title") if media_item_dto else "")
            or "Unknown"
        )
        source = (media_item_dto.get("source") if media_item_dto else None) or "url"
        media_id = media_item_dto.get("id") if media_item_dto else None
        resolved_url = None
        canonical_duration = None

        if skip_resolution:
            # Metadata-only: use duration from playout or metadata; resolution at stream time
            raw = {"media_item": media_item_dto, "playout_item": playout_item_dto}
            meta_d = _duration_from_metadata(raw)
            canonical_duration = float(meta_d) if meta_d and meta_d > 0 else DEFAULT_DURATION_IF_PROBE_FAILS
            if os.environ.get("EXSTREAMTV_VALIDATE_DURATIONS") == "1":
                assert canonical_duration > 0, f"canonical_duration must be > 0 for {title}"
        else:
            from exstreamtv.streaming.url_resolver import get_url_resolver
            resolver = get_url_resolver()
            if media_item_dto:
                resolved_url = await _resolve_url(media_item_dto, resolver)
            elif playout_item_dto and playout_item_dto.get("source_url"):
                resolved_url = playout_item_dto["source_url"]
            if not resolved_url:
                skipped_resolution += 1
                logger.warning(f"Skipping playout item '{title}' (media_id={media_id}): resolution failed")
                continue
            raw = {"media_item": media_item_dto, "playout_item": playout_item_dto}
            canonical_duration = await validate_duration(
                raw,
                resolved_url=resolved_url,
                timeout=probe_timeout,
            )
            if os.environ.get("EXSTREAMTV_VALIDATE_DURATIONS") == "1":
                assert canonical_duration > 0, f"canonical_duration must be > 0 for {title}"

        result.append(
            CanonicalTimelineItem(
                media_item=media_item_dto,
                playout_item=playout_item_dto,
                canonical_duration=canonical_duration,
                title=title,
                source=source,
                media_id=media_id,
                custom_title=playout_item_dto.get("custom_title") if playout_item_dto else None,
                resolved_url=resolved_url,
            )
        )
    return result
