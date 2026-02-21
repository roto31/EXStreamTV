"""
Prometheus metrics exporter for EXStreamTV.

Exposes GET /metrics endpoint in Prometheus text exposition format.
Integrates ProcessPoolManager, MetricsCollector, and DB connection pool.
"""

import asyncio
import logging
import time
from typing import Callable, Optional

from fastapi import APIRouter, Response

logger = logging.getLogger(__name__)


def create_prometheus_router(
    get_process_pool_metrics: Optional[Callable] = None,
    get_metrics_collector: Optional[Callable] = None,
    get_db_metrics: Optional[Callable] = None,
) -> APIRouter:
    """
    Create FastAPI router for /metrics endpoint.

    Args:
        get_process_pool_metrics: Optional callable returning dict of process pool metrics.
        get_metrics_collector: Optional callable returning MetricsCollector.
        get_db_metrics: Optional callable returning {checked_out, size}.
    """
    router = APIRouter(tags=["monitoring"])

    @router.get("/metrics")
    async def prometheus_metrics() -> Response:
        """
        Prometheus text exposition format.

        Combines ProcessPoolManager, MetricsCollector, and DB pool metrics.
        """
        try:
            from exstreamtv.monitoring.metrics import get_metrics_collector as _get_mc
            mc = (get_metrics_collector or _get_mc)()
        except ImportError:
            mc = None

        # Update from ProcessPoolManager
        if get_process_pool_metrics:
            try:
                ppm = get_process_pool_metrics()
                if hasattr(ppm, "get_metrics"):
                    metrics = ppm.get_metrics()
                    if mc:
                        mc.ffmpeg_processes_active = metrics.get(
                            "exstreamtv_ffmpeg_processes_active", 0
                        )
                        mc.ffmpeg_spawn_rejected_memory_total = metrics.get(
                            "exstreamtv_ffmpeg_spawn_rejected_memory_total", 0
                        )
                        mc.ffmpeg_spawn_rejected_fd_total = metrics.get(
                            "exstreamtv_ffmpeg_spawn_rejected_fd_total", 0
                        )
                        mc.ffmpeg_spawn_rejected_capacity_total = metrics.get(
                            "exstreamtv_ffmpeg_spawn_rejected_capacity_total", 0
                        )
            except Exception as e:
                logger.debug(f"Process pool metrics error: {e}")

        # Update from DB
        if get_db_metrics and mc:
            try:
                dbm = get_db_metrics()
                if dbm:
                    mc.set_db_pool(
                        dbm.get("checked_out", 0),
                        dbm.get("size", 0),
                    )
            except Exception as e:
                logger.debug(f"DB metrics error: {e}")

        # Event loop lag (simple measurement)
        if mc:
            t0 = time.monotonic()
            await asyncio.sleep(0)
            lag = time.monotonic() - t0
            mc.update_event_loop_lag(lag)

        if mc is None:
            return Response(content="# No metrics collector\n", media_type="text/plain")
        return Response(
            content=mc.to_prometheus_text(),
            media_type="text/plain; charset=utf-8",
        )

    return router
