"""
Section C — AI Containment and Gating Model Tests.

Validates:
- C.6: Minimum confidence for metadata tools, decay, multi-failure shutdown,
       disable_hours config, force_metadata_resolution override
- C.7: Regression detection and automatic shutdown override
"""

from unittest.mock import AsyncMock, patch

import pytest

from exstreamtv.ai_agent.bounded_agent_loop import (
    CONFIDENCE_DECAY,
    CONSECUTIVE_FAILURE_SHUTDOWN,
    METADATA_CONFIDENCE_MIN,
    PlanAction,
    PlanStep,
    PersonaConfig,
    run_bounded_loop,
)
from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope
from exstreamtv.ai_agent.metadata_self_resolution import (
    _detect_regression,
    _is_regression_override_active,
    _set_regression_override,
    _snapshot_metrics,
)


# ==================== C.6 Confidence Gating ====================


@pytest.mark.asyncio
async def test_metadata_tool_skipped_when_confidence_below_threshold() -> None:
    """Metadata tools skipped when confidence < 0.3 (and > 0)."""
    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
        confidence=0.25,
    )
    planned_steps = [
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.STOP, None, {}),
    ]

    with patch(
        "exstreamtv.ai_agent.bounded_agent_loop.execute_tool",
        new_callable=AsyncMock,
    ) as mock_exec:
        result = await run_bounded_loop(
            envelope,
            planned_steps,
            enabled_override=True,
            mode_override="metadata",
            force_confidence_gate=False,
        )

    mock_exec.assert_not_called()
    assert result.steps_executed == 0


@pytest.mark.asyncio
async def test_metadata_tool_executed_when_confidence_above_threshold() -> None:
    """Metadata tools executed when confidence >= 0.3."""
    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
        confidence=0.5,
    )
    planned_steps = [
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.STOP, None, {}),
    ]

    with patch(
        "exstreamtv.ai_agent.bounded_agent_loop.asyncio.sleep",
        new_callable=AsyncMock,
    ), patch(
        "exstreamtv.ai_agent.metadata_tools_impl.execute_re_enrich_metadata",
        new_callable=AsyncMock,
        return_value={"success": True, "message": "ok"},
    ):
        result = await run_bounded_loop(
            envelope,
            planned_steps,
            enabled_override=True,
            mode_override="metadata",
            force_confidence_gate=False,
        )

    assert result.steps_executed == 1
    assert result.success is True


@pytest.mark.asyncio
async def test_force_confidence_gate_bypasses_check() -> None:
    """force_confidence_gate=True bypasses confidence threshold."""
    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
        confidence=0.1,
    )
    planned_steps = [
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.STOP, None, {}),
    ]

    with patch(
        "exstreamtv.ai_agent.bounded_agent_loop.asyncio.sleep",
        new_callable=AsyncMock,
    ), patch(
        "exstreamtv.ai_agent.metadata_tools_impl.execute_re_enrich_metadata",
        new_callable=AsyncMock,
        return_value={"success": True, "message": "ok"},
    ):
        result = await run_bounded_loop(
            envelope,
            planned_steps,
            enabled_override=True,
            mode_override="metadata",
            force_confidence_gate=True,
        )

    assert result.steps_executed == 1


@pytest.mark.asyncio
async def test_confidence_decay_on_metadata_tool_failure() -> None:
    """Envelope confidence decays by 0.8 on metadata tool failure."""
    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
        confidence=0.5,
    )
    planned_steps = [
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.STOP, None, {}),
    ]

    with patch(
        "exstreamtv.ai_agent.bounded_agent_loop.asyncio.sleep",
        new_callable=AsyncMock,
    ), patch(
        "exstreamtv.ai_agent.metadata_tools_impl.execute_re_enrich_metadata",
        new_callable=AsyncMock,
        side_effect=[
            {"success": False, "message": "fail"},
            {"success": True, "message": "ok"},
        ],
    ):
        result = await run_bounded_loop(
            envelope,
            planned_steps,
            enabled_override=True,
            mode_override="metadata",
            force_confidence_gate=True,
        )

    assert result.steps_executed == 2
    expected_decayed = 0.5 * CONFIDENCE_DECAY
    assert result.final_envelope.confidence == pytest.approx(expected_decayed)


@pytest.mark.asyncio
async def test_multi_failure_shutdown_escalates() -> None:
    """Consecutive metadata tool failures >= 3 causes escalation."""
    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
        confidence=0.8,
    )
    planned_steps = [
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.STOP, None, {}),
    ]

    persona = PersonaConfig(planning_depth_max=5)

    with patch(
        "exstreamtv.ai_agent.bounded_agent_loop.asyncio.sleep",
        new_callable=AsyncMock,
    ), patch(
        "exstreamtv.ai_agent.metadata_tools_impl.execute_re_enrich_metadata",
        new_callable=AsyncMock,
        return_value={"success": False, "message": "fail"},
    ):
        result = await run_bounded_loop(
            envelope,
            planned_steps,
            persona=persona,
            enabled_override=True,
            mode_override="metadata",
            force_confidence_gate=True,
        )

    assert result.escalated is True
    assert "Consecutive" in result.message or str(CONSECUTIVE_FAILURE_SHUTDOWN) in result.message
    assert result.steps_executed < 4


# ==================== C.7 Regression Shutdown ====================


def test_snapshot_metrics_returns_dict() -> None:
    """_snapshot_metrics returns dict with expected keys."""
    snap = _snapshot_metrics()
    assert "metadata_failure_ratio" in snap
    assert "xmltv_validation_error_total" in snap
    assert "stream_failure_total" in snap
    assert isinstance(snap["stream_failure_total"], dict)


def test_detect_regression_failure_ratio_increase() -> None:
    """_detect_regression returns True when metadata_failure_ratio increases > 0.1."""
    before = {"metadata_failure_ratio": 0.2, "xmltv_validation_error_total": 0, "stream_failure_total": {}}
    after = {"metadata_failure_ratio": 0.35, "xmltv_validation_error_total": 0, "stream_failure_total": {}}
    assert _detect_regression(before, after, [1]) is True


def test_detect_regression_xmltv_errors_increase() -> None:
    """_detect_regression returns True when xmltv_validation_error_total increases."""
    before = {"metadata_failure_ratio": 0.2, "xmltv_validation_error_total": 0, "stream_failure_total": {}}
    after = {"metadata_failure_ratio": 0.2, "xmltv_validation_error_total": 1, "stream_failure_total": {}}
    assert _detect_regression(before, after, [1]) is True


def test_detect_regression_stream_failure_increase() -> None:
    """_detect_regression returns True when stream_failure_total increases for channel."""
    before = {"metadata_failure_ratio": 0.0, "xmltv_validation_error_total": 0, "stream_failure_total": {"1": 2}}
    after = {"metadata_failure_ratio": 0.0, "xmltv_validation_error_total": 0, "stream_failure_total": {"1": 3}}
    assert _detect_regression(before, after, [1]) is True


def test_detect_regression_no_regression() -> None:
    """_detect_regression returns False when metrics unchanged or improved."""
    before = {"metadata_failure_ratio": 0.3, "xmltv_validation_error_total": 1, "stream_failure_total": {"1": 2}}
    after = {"metadata_failure_ratio": 0.25, "xmltv_validation_error_total": 1, "stream_failure_total": {"1": 2}}
    assert _detect_regression(before, after, [1]) is False


def test_regression_override_set_and_read() -> None:
    """_set_regression_override and _is_regression_override_active work."""
    try:
        _set_regression_override(True)
        assert _is_regression_override_active() is True
        _set_regression_override(False)
        assert _is_regression_override_active() is False
    finally:
        _set_regression_override(False)
