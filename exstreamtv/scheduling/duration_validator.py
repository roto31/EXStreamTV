"""
DurationValidator — ffprobe-based canonical duration validation.

YAML duration and metadata duration are not authoritative.
Canonical duration is derived from ffprobe only.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional

from exstreamtv.config import get_config

logger = logging.getLogger(__name__)

DEFAULT_DURATION_IF_PROBE_FAILS = 1800  # 30 min fallback


async def get_duration_from_path(path: Path, timeout: float = 30.0) -> Optional[float]:
    """
    Get duration in seconds from a local file path using ffprobe.

    Args:
        path: Path to media file.
        timeout: Probe timeout in seconds.

    Returns:
        Duration in seconds, or None if probe fails.
    """
    try:
        from exstreamtv.media.scanner.ffprobe import FFprobeAnalyzer

        config = get_config()
        ffprobe_path = getattr(config.ffmpeg, "ffprobe_path", None) or "ffprobe"
        analyzer = FFprobeAnalyzer(ffprobe_path=ffprobe_path)
        info = await analyzer.analyze(path, timeout=timeout)
        if info.duration:
            return info.duration.total_seconds()
        return None
    except Exception as e:
        logger.debug(f"FFprobe path failed for {path}: {e}")
        return None


async def get_duration_from_url(url: str, timeout: float = 30.0) -> Optional[float]:
    """
    Get duration in seconds from a stream URL using ffprobe.

    Probe safety: never probe empty or null URL.

    Args:
        url: Stream URL (archive.org, YouTube, Plex, etc.).
        timeout: Probe timeout in seconds.

    Returns:
        Duration in seconds, or None if probe fails.
    """
    if not url or not str(url).strip():
        return None
    try:
        from exstreamtv.streaming.mpegts_streamer import MPEGTSStreamer

        streamer = MPEGTSStreamer()
        codec_info = await streamer.probe_stream(url)
        if codec_info and codec_info.duration and codec_info.duration > 0:
            return float(codec_info.duration)
        return None
    except Exception as e:
        logger.debug(f"FFprobe URL failed for {url[:80]}...: {e}")
        return None


async def validate_duration(
    media_item: Any,
    resolved_url: Optional[str] = None,
    timeout: float = 30.0,
) -> float:
    """
    Validate and return canonical duration for a media item.

    Prefers ffprobe over metadata duration. Falls back to metadata, then default.

    Args:
        media_item: MediaItem or dict with duration, url, path.
        resolved_url: Pre-resolved stream URL (for YouTube/archive/Plex).
        timeout: Probe timeout.

    Returns:
        Canonical duration in seconds.
    """
    if resolved_url:
        probed = await get_duration_from_url(resolved_url, timeout)
        if probed and probed > 0:
            return probed
    path = _get_path(media_item)
    if path:
        probed = await get_duration_from_path(Path(path), timeout)
        if probed and probed > 0:
            return probed
    meta_duration = _get_metadata_duration(media_item)
    if meta_duration and meta_duration > 0:
        return float(meta_duration)
    return float(DEFAULT_DURATION_IF_PROBE_FAILS)


def _get_path(media_item: Any) -> Optional[str]:
    """
    Extract file path from media item.
    Only reads plain dicts. Never accesses ORM relations (e.g. .files) outside session.
    """
    if isinstance(media_item, dict):
        m = media_item.get("media_item") or media_item
        if isinstance(m, dict):
            path = m.get("path") or m.get("url")
            if path:
                return path
            files = m.get("files") or media_item.get("files")
            if files and isinstance(files, list) and len(files) > 0:
                f0 = files[0]
                if isinstance(f0, dict):
                    return f0.get("path") or f0.get("url")
        return media_item.get("path") or media_item.get("url")
    if hasattr(media_item, "path") and media_item.path:
        return media_item.path
    return None


def _get_metadata_duration(media_item: Any) -> Optional[int | float]:
    """
    Extract duration from metadata (non-authoritative).

    Order: media_item.duration > playout_item.duration > top-level duration.
    Never return 0; use None to trigger fallback.
    """
    if isinstance(media_item, dict):
        m = media_item.get("media_item") or media_item
        if isinstance(m, dict):
            d = m.get("duration")
            if d is not None and float(d) > 0:
                return float(d)
        pi = media_item.get("playout_item")
        if isinstance(pi, dict) and pi.get("duration") is not None:
            pd = float(pi["duration"])
            if pd > 0:
                return pd
        d = media_item.get("duration")
        if d is not None and float(d) > 0:
            return float(d)
        return None
    if hasattr(media_item, "duration") and media_item.duration:
        return float(media_item.duration)
    return None
