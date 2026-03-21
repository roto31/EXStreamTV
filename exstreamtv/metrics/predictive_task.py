"""
Background predictive analysis. Runs every 60s. Cached metrics only.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

_predictive_result: dict[str, Any] = {}
_risk_score: int = 0


def get_predictive_result() -> dict[str, Any]:
    return dict(_predictive_result)


def get_risk_score() -> int:
    return _risk_score


def get_watchdog_interval() -> int:
    """Delegates to adaptive controller when available."""
    try:
        from exstreamtv.metrics.adaptive_controller import get_watchdog_interval as _adaptive
        return _adaptive()
    except ImportError:
        return 30 if _risk_score > 75 else 60


async def run_predictive_task() -> None:
    """Run every 60s. Never affects scheduling."""
    global _predictive_result, _risk_score
    while True:
        try:
            from exstreamtv.monitoring.metrics import get_metrics_collector
            from exstreamtv.metrics.history_store import get_history, record_sample
            from exstreamtv.metrics.predictive_analyzer import analyze_health_trend
            from exstreamtv.metrics.metrics_exporter import inc_predictive_warning

            mc = get_metrics_collector()
            record_sample(
                mc.drift_delta_seconds,
                mc.active_mismatch_total,
                mc.timeline_rebuild_total,
                mc.watchdog_interventions_total,
            )
            history = get_history()
            metrics_state = {
                "drift_delta": mc.drift_delta_seconds,
                "active_mismatch_total": mc.active_mismatch_total,
                "timeline_rebuild_total": mc.timeline_rebuild_total,
                "watchdog_interventions_total": mc.watchdog_interventions_total,
            }
            result = analyze_health_trend(history, metrics_state)
            _predictive_result = result
            _risk_score = result.get("risk_score", 0)

            mc.predictive_risk_score = _risk_score

            if _risk_score > 75:
                inc_predictive_warning()
                logger.warning(
                    f"Predictive early-warning: risk_score={_risk_score} - "
                    f"{result.get('prediction_text', '')}"
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Predictive task error: {e}")
        await asyncio.sleep(60)


def start_predictive_task() -> asyncio.Task:
    return asyncio.create_task(run_predictive_task())
