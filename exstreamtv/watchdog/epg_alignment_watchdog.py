"""
EPG alignment watchdog. Adaptive interval. Auto-heals mismatches.
Never crashes. Authoritative clock only. Cooldown safeguards.
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL_SECONDS = 60
MAX_RETRIES_PER_CYCLE = 2
_last_mismatches: list[int] = []


def _get_interval() -> int:
    try:
        from exstreamtv.metrics.adaptive_controller import get_watchdog_interval
        return get_watchdog_interval()
    except ImportError:
        try:
            from exstreamtv.metrics.predictive_task import get_watchdog_interval
            return get_watchdog_interval()
        except ImportError:
            return WATCHDOG_INTERVAL_SECONDS


def _channel_xmltv_id(channel: Any) -> str:
    num = str(getattr(channel, "number", "") or "").strip()
    if num:
        return num
    return f"exstream.{getattr(channel, 'id', channel)}"


def _parse_xmltv_epoch(s: str) -> Optional[float]:
    try:
        from exstreamtv.utils.xmltv_parse import parse_xmltv_datetime_to_epoch
        return parse_xmltv_datetime_to_epoch(s)
    except ImportError:
        return None


async def _run_watchdog_cycle(app: Any) -> None:
    """Single cycle: determine strategy, check channels, heal if mismatch."""
    global _last_mismatches
    try:
        from exstreamtv.scheduling.authoritative_time import now_epoch
        from exstreamtv.metrics.metrics_exporter import (
            inc_active_mismatch,
            inc_timeline_rebuild,
            inc_watchdog_interventions,
        )
    except ImportError:
        return

    channel_manager = getattr(app.state, "channel_manager", None)
    if not channel_manager:
        return

    try:
        from exstreamtv.database import get_sync_session, get_sync_session_factory
        from exstreamtv.database.models import Channel
        from exstreamtv.scheduling.authority import get_authority
        from exstreamtv.tasks.playout_tasks import rebuild_playouts_task
        from exstreamtv.streaming.resolution_service import get_resolution_service
        from exstreamtv.metrics.adaptive_controller import (
            determine_adaptive_strategy,
            can_full_rebuild,
            record_full_rebuild,
            record_channel_rebuild,
            record_preemptive_rebuild,
            can_channel_rebuild,
        )
        from exstreamtv.metrics.health_score import get_health_score
        from exstreamtv.metrics.predictive_task import get_risk_score
        from exstreamtv.monitoring.metrics import get_metrics_collector
        _has_adaptive = True
    except ImportError:
        _has_adaptive = False

    strategy = {"watchdog_interval_seconds": 60, "rebuild_scope": "channel-only", "preemptive_rebuild": False}
    if _has_adaptive:
        try:
            health = get_health_score()
            risk = get_risk_score()
            mc = get_metrics_collector()
            strategy = determine_adaptive_strategy(
                health, risk,
                {"active_mismatch_total": mc.active_mismatch_total, "timeline_rebuild_total": mc.timeline_rebuild_total},
            )
        except Exception:
            pass

    factory = get_sync_session_factory()
    auth = get_authority(factory)
    mismatches: list[int] = []

    with get_sync_session() as session:
        channels = session.query(Channel).filter(Channel.enabled == True).all()

    if strategy.get("preemptive_rebuild") and _last_mismatches and len(channels) > 0:
        unstable_ratio = len(_last_mismatches) / max(1, len(channels))
        if unstable_ratio <= 0.5 and risk > 75:
            for ch_id in _last_mismatches[:5]:
                try:
                    auth.invalidate_timeline(ch_id)
                    record_preemptive_rebuild()
                except Exception:
                    pass

    for channel in channels:
        try:
            clock = await auth.ensure_clock(channel.id)
            if not clock:
                continue
            timeline = auth.get_timeline(channel.id)
            if not timeline:
                continue
            resolved = clock.resolve_item_and_seek(timeline, now=None)
            if not resolved:
                continue
            timeline_title = resolved.item.title or resolved.item.custom_title or "Unknown"

            svc = get_resolution_service(factory)
            result = await svc.resolve_for_streaming(channel.id)
            playback_title = (result.title if result else None) or "(none)"

            if timeline_title != playback_title:
                inc_active_mismatch()
                mismatches.append(channel.id)
                scope = strategy.get("rebuild_scope", "channel-only")
                if scope in ("channel-only", "incremental", "full"):
                    if _has_adaptive and not can_channel_rebuild(channel.id):
                        pass
                    else:
                        auth.invalidate_timeline(channel.id)
                        if _has_adaptive:
                            record_channel_rebuild(channel.id)
                        inc_timeline_rebuild()
        except Exception as e:
            logger.debug(f"Watchdog channel {channel.id}: {e}")

    _last_mismatches = mismatches

    if mismatches:
        for _ in range(MAX_RETRIES_PER_CYCLE - 1):
            await asyncio.sleep(2)
            still_mismatch = []
            for ch_id in mismatches:
                try:
                    await auth.ensure_clock(ch_id)
                except Exception:
                    pass
            for channel in channels:
                if channel.id not in mismatches:
                    continue
                try:
                    result = await get_resolution_service(factory).resolve_for_streaming(channel.id)
                    clock = auth.get_clock(channel.id)
                    timeline = auth.get_timeline(channel.id)
                    if clock and timeline:
                        resolved = clock.resolve_item_and_seek(timeline, now=None)
                        if resolved:
                            t_title = resolved.item.title or resolved.item.custom_title or ""
                            p_title = (result.title if result else None) or ""
                            if t_title != p_title:
                                still_mismatch.append(channel.id)
                except Exception:
                    still_mismatch.append(channel.id)
            if not still_mismatch:
                break
            mismatches = still_mismatch

        if mismatches:
            scope = strategy.get("rebuild_scope", "channel-only")
            do_full = scope == "full" or (scope == "incremental" and len(mismatches) > max(1, len(channels)) // 2)
            if do_full:
                try:
                    if can_full_rebuild():
                        auth.invalidate_all_timelines()
                        await rebuild_playouts_task()
                        auth.invalidate_all_timelines()
                        record_full_rebuild()
                        inc_watchdog_interventions()
                except Exception as e:
                    logger.warning(f"Watchdog full rebuild failed: {e}")


async def run_epg_alignment_watchdog(app: Any) -> None:
    """Background daemon. Never crashes."""
    await asyncio.sleep(10)  # Let startup complete
    while True:
        try:
            await asyncio.sleep(_get_interval())
            await _run_watchdog_cycle(app)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Watchdog cycle error: {e}")


def start_watchdog(app: Any) -> None:
    """Launch watchdog at startup."""
    try:
        task = asyncio.create_task(run_epg_alignment_watchdog(app))
        setattr(app.state, "_epg_watchdog_task", task)
        logger.info("EPG alignment watchdog started")
    except Exception as e:
        logger.warning(f"Watchdog start failed: {e}")
