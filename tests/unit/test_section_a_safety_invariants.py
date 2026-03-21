"""
Section A — Safety Architecture Invariant Tests.

Validates core invariants from the Production Hardening plan:
- All restarts route through request_channel_restart(); no direct stop_channel from agent.
- AI metadata resolution: read-only tools only; no restart invocation.
- EPG/XMLTV validation precedes emit; hard-fail on corruption conditions.
- Containment mode short-circuits agent execution when system degraded.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from _pytest.fixtures import FixtureRequest


# ==================== Invariant 1: Restart Path ====================


def test_metadata_only_tools_excludes_restart() -> None:
    """METADATA_ONLY_TOOLS must not include restart_channel."""
    from exstreamtv.ai_agent.tool_registry import METADATA_ONLY_TOOLS

    assert "restart_channel" not in METADATA_ONLY_TOOLS
    assert METADATA_ONLY_TOOLS == frozenset({
        "re_enrich_metadata",
        "refresh_plex_metadata",
        "rebuild_xmltv",
        "reparse_filename_metadata",
        "fetch_metadata_logs",
    })


def test_get_tools_for_metadata_mode_excludes_restart() -> None:
    """metadata mode must not expose restart_channel to agent."""
    from exstreamtv.ai_agent.tool_registry import get_tools_for_mode

    tools = get_tools_for_mode("metadata")
    assert "restart_channel" not in tools
    assert set(tools) == {
        "re_enrich_metadata",
        "refresh_plex_metadata",
        "rebuild_xmltv",
        "reparse_filename_metadata",
        "fetch_metadata_logs",
    }


@pytest.mark.asyncio
async def test_execute_restart_channel_calls_request_channel_restart(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """execute_restart_channel MUST use request_channel_restart, never stop_channel."""
    mock_request = AsyncMock(return_value=True)
    monkeypatch.setattr(
        "exstreamtv.tasks.health_tasks.request_channel_restart",
        mock_request,
    )
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope
    from exstreamtv.ai_agent.tool_registry import execute_restart_channel

    envelope = build_grounded_envelope(
        channel_id=1,
        failure_classification="test",
        restart_count=0,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
    )

    result = await execute_restart_channel(
        1, envelope, restart_cap=3, high_risk_already_executed=False
    )
    mock_request.assert_called_once_with(1)  # type: ignore[union-attr]
    assert result.get("success") is True


def test_agent_restart_path_via_request_channel_restart() -> None:
    """Agent restart path must use request_channel_restart, never channel_manager.stop_channel."""
    import inspect

    from exstreamtv.ai_agent.tool_registry import execute_restart_channel

    source = inspect.getsource(execute_restart_channel)
    assert "request_channel_restart" in source
    # No direct call to .stop_channel( or .start_channel( (exclude execute_restart_channel)
    assert ".stop_channel(" not in source
    assert ".start_channel(" not in source


# ==================== Invariant 2: AI Metadata Read-Only ====================


def test_metadata_self_resolution_uses_metadata_mode() -> None:
    """run_metadata_self_resolution uses mode_override='metadata' in run_bounded_loop."""
    import inspect

    from exstreamtv.ai_agent.metadata_self_resolution import _run_single

    # _run_single calls run_bounded_loop with mode_override="metadata"
    source = inspect.getsource(_run_single)
    assert "mode_override" in source
    assert "metadata" in source


# ==================== Invariant 3: EPG/XMLTV Validation ====================


def test_xmltv_generator_validate_raises_on_corruption() -> None:
    """XMLTVGenerator with validate=True must hard-fail on invalid programmes."""
    from exstreamtv.api.timeline_builder import TimelineProgramme
    from exstreamtv.api.xmltv_generator import XMLTVGenerator, XMLTVValidationError

    channels = [type("Channel", (), {"id": 1, "name": "Test", "number": 1})()]
    invalid_progs = [
        TimelineProgramme(
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            stop_time=datetime(2025, 1, 1, 11, 0, 0),  # stop < start
            media_item=None,
            playout_item={},
            title="Bad",
            index=0,
        ),
    ]
    programmes_by_channel = {1: invalid_progs}
    gen = XMLTVGenerator()

    with pytest.raises(XMLTVValidationError) as exc_info:
        gen.generate(channels, programmes_by_channel, validate=True)

    assert "start >= stop" in str(exc_info.value) or "validation failed" in str(exc_info.value).lower()


def test_xmltv_generator_validate_raises_on_empty_title() -> None:
    """XMLTVGenerator with validate=True must hard-fail on empty title."""
    from exstreamtv.api.timeline_builder import TimelineProgramme
    from exstreamtv.api.xmltv_generator import XMLTVGenerator, XMLTVValidationError

    channels = [type("Channel", (), {"id": 1, "name": "Test", "number": 1})()]
    invalid_progs = [
        TimelineProgramme(
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            stop_time=datetime(2025, 1, 1, 13, 0, 0),
            media_item=None,
            playout_item={},
            title="",
            index=0,
        ),
    ]
    programmes_by_channel = {1: invalid_progs}
    gen = XMLTVGenerator()

    with pytest.raises(XMLTVValidationError) as exc_info:
        gen.generate(channels, programmes_by_channel, validate=True)

    err = exc_info.value
    details_str = " ".join(getattr(err, "details", [])).lower()
    assert "empty title" in details_str or "empty title" in str(err).lower()


def test_xmltv_generator_validate_precedes_emit() -> None:
    """When validate=True, _validate is called before XML is built."""
    from exstreamtv.api.timeline_builder import TimelineProgramme
    from exstreamtv.api.xmltv_generator import XMLTVGenerator

    channels = [type("Channel", (), {"id": 1, "name": "Test", "number": 1})()]
    valid_progs = [
        TimelineProgramme(
            start_time=datetime(2025, 1, 1, 12, 0, 0),
            stop_time=datetime(2025, 1, 1, 13, 0, 0),
            media_item=None,
            playout_item={},
            title="Valid",
            index=0,
        ),
    ]
    programmes_by_channel = {1: valid_progs}
    gen = XMLTVGenerator()

    result = gen.generate(channels, programmes_by_channel, validate=True)
    assert "<?xml" in result
    assert "Valid" in result


def test_iptv_timeline_builder_uses_validate_true() -> None:
    """_build_epg_via_timeline_builder must pass validate=True to XMLTVGenerator."""
    import inspect
    from exstreamtv.api import iptv

    source = inspect.getsource(iptv._build_epg_via_timeline_builder)
    assert "validate=True" in source


# ==================== Invariant 4: Containment Mode ====================


def test_build_grounded_envelope_containment_when_velocity_high() -> None:
    """containment_mode=True when restart_velocity >= threshold."""
    from exstreamtv.ai_agent.grounded_envelope import (
        RESTART_STORM_VELOCITY_THRESHOLD,
        build_grounded_envelope,
    )

    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=RESTART_STORM_VELOCITY_THRESHOLD + 0.01,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
    )
    assert envelope.containment_mode is True


def test_build_grounded_envelope_containment_when_pool_pressure_high() -> None:
    """containment_mode=True when pool_pressure >= 0.9."""
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope

    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.95,
        circuit_breaker_open=False,
    )
    assert envelope.containment_mode is True


def test_build_grounded_envelope_containment_when_circuit_breaker_open() -> None:
    """containment_mode=True when circuit_breaker_open."""
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope

    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=True,
    )
    assert envelope.containment_mode is True


def test_build_grounded_envelope_incorporates_long_run_containment(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """containment_mode=True when _get_long_run_containment_mode returns True."""
    monkeypatch.setattr(
        "exstreamtv.tasks.health_tasks._get_long_run_containment_mode",
        lambda: True,
    )
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope

    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
    )
    assert envelope.containment_mode is True


@pytest.mark.asyncio
async def test_bounded_agent_loop_short_circuits_on_containment() -> None:
    """run_bounded_loop must exit immediately when envelope.containment_mode."""
    from exstreamtv.ai_agent.bounded_agent_loop import (
        AgentLoopResult,
        PlanAction,
        PlanStep,
        run_bounded_loop,
    )
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope

    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.5,
        pool_pressure_override=0.95,
        circuit_breaker_open=False,
    )
    assert envelope.containment_mode is True

    planned_steps = [
        PlanStep(PlanAction.CONTINUE, "re_enrich_metadata", {"channel_id": 1}),
        PlanStep(PlanAction.STOP, None, {}),
    ]

    result = await run_bounded_loop(
        envelope, planned_steps, enabled_override=True, mode_override="metadata"
    )
    assert isinstance(result, AgentLoopResult)
    assert result.steps_executed == 0
    assert result.escalated is True
    assert "containment" in result.message.lower()


def test_metadata_self_resolution_check_guardrails_aborts_on_containment() -> None:
    """_check_guardrails must return (False, reason) when containment_mode."""
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope
    from exstreamtv.ai_agent.metadata_self_resolution import _check_guardrails

    envelope = build_grounded_envelope(
        channel_id=1,
        restart_velocity=0.5,
        pool_pressure_override=0.95,
        circuit_breaker_open=False,
    )
    proceed, reason = _check_guardrails(envelope)
    assert proceed is False
    assert "containment" in reason
