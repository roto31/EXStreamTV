"""Metadata self-healing loop orchestration and regression guardrails."""

from __future__ import annotations

from typing import Any, Optional

from exstreamtv.ai_agent.bounded_agent_loop import (
    PlanAction,
    PlanStep,
    run_bounded_loop,
)
from exstreamtv.ai_agent.grounded_envelope import GroundedEnvelope

_regression_override_active: bool = False


def _snapshot_metrics() -> dict[str, Any]:
    return {
        "metadata_failure_ratio": 0.0,
        "xmltv_validation_error_total": 0,
        "stream_failure_total": {},
    }


def _detect_regression(
    before: dict[str, Any],
    after: dict[str, Any],
    channel_ids: list[int],
) -> bool:
    br = float(before.get("metadata_failure_ratio", 0.0))
    ar = float(after.get("metadata_failure_ratio", 0.0))
    if ar - br > 0.1:
        return True
    if int(after.get("xmltv_validation_error_total", 0)) > int(
        before.get("xmltv_validation_error_total", 0)
    ):
        return True
    b_streams: dict[str, Any] = before.get("stream_failure_total") or {}
    a_streams: dict[str, Any] = after.get("stream_failure_total") or {}
    for cid in channel_ids:
        key = str(cid)
        if int(a_streams.get(key, 0)) > int(b_streams.get(key, 0)):
            return True
    return False


def _set_regression_override(active: bool) -> None:
    global _regression_override_active
    _regression_override_active = active


def _is_regression_override_active() -> bool:
    return _regression_override_active


def _check_guardrails(envelope: GroundedEnvelope) -> tuple[bool, str]:
    if envelope.containment_mode:
        return False, "aborted: containment mode blocks metadata self-resolution"
    return True, ""


async def _run_single(
    envelope: GroundedEnvelope,
    planned_steps: list[PlanStep],
    *,
    enabled_override: bool = True,
    force_confidence_gate: bool = False,
) -> Any:
    return await run_bounded_loop(
        envelope,
        planned_steps,
        enabled_override=enabled_override,
        mode_override="metadata",
        force_confidence_gate=force_confidence_gate,
    )
