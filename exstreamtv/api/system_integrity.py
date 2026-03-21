"""System integrity and predictive stability API."""

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system-integrity", tags=["System Integrity"])


@router.get("/summary")
async def get_system_integrity_summary(request: Request) -> dict[str, Any]:
    """System integrity with predictive stability forecast."""
    result: dict[str, Any] = {
        "channel_manager": "initialized" if getattr(request.app.state, "channel_manager", None) else "not-initialized",
        "predictive_analysis": {
            "risk_score": 0,
            "forecast": "Stable",
            "prediction_text": "System stability trend is normal. No degradation predicted.",
        },
        "adaptive_mode": {
            "mode": 0,
            "label": "Normal",
            "watchdog_interval_seconds": 60,
            "rebuild_scope": "channel-only",
            "preemptive_rebuild": False,
        },
    }
    try:
        from exstreamtv.metrics.predictive_task import get_predictive_result
        from exstreamtv.metrics.history_store import get_history
        from exstreamtv.metrics.adaptive_controller import get_adaptive_strategy, get_adaptive_mode_label
        pred = get_predictive_result()
        if pred:
            result["predictive_analysis"] = {
                "risk_score": pred.get("risk_score", 0),
                "forecast": pred.get("forecast", "Stable"),
                "prediction_text": pred.get("prediction_text", ""),
                "components": pred.get("components", {}),
            }
        hist = get_history()
        result["trend_data"] = {
            "drift_60m": hist.get("drift_deltas_60m", []),
            "mismatch_24h": hist.get("mismatch_by_hour", []),
            "rebuild_24h": hist.get("rebuild_by_hour", []),
        }
        strat = get_adaptive_strategy()
        if strat:
            result["adaptive_mode"] = {
                "mode": strat.get("adaptive_mode", 0),
                "label": get_adaptive_mode_label(),
                "watchdog_interval_seconds": strat.get("watchdog_interval_seconds", 60),
                "rebuild_scope": strat.get("rebuild_scope", "channel-only"),
                "preemptive_rebuild": strat.get("preemptive_rebuild", False),
            }
    except ImportError:
        pass
    return result
