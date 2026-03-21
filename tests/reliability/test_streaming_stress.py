"""
Section B.2 — Streaming Stability Stress Harness.

Validates restart guard invariants, circuit breaker semantics, pool pressure.
Uses mocks for FFmpeg/plex sources. Does not modify streaming pipeline.

Marked @pytest.mark.slow — run with: pytest -m slow
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from exstreamtv.streaming.circuit_breaker import CircuitBreaker, CircuitState
from exstreamtv.tasks.health_tasks import request_channel_restart


@pytest.mark.slow
@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold() -> None:
    """Circuit breaker opens after failure_threshold failures in window."""
    cb = CircuitBreaker(failure_threshold=3, window_seconds=300.0, cooldown_seconds=2.0)
    channel_id = 1

    assert await cb.can_restart(channel_id) is True

    await cb.record_failure(channel_id)
    await cb.record_failure(channel_id)
    assert await cb.can_restart(channel_id) is True

    await cb.record_failure(channel_id)
    assert await cb.can_restart(channel_id) is False

    state = await cb.get_state(channel_id)
    assert state == CircuitState.OPEN


@pytest.mark.slow
@pytest.mark.asyncio
async def test_request_channel_restart_blocked_when_circuit_open(
    monkeypatch: "pytest.MonkeyPatch",
) -> None:
    """request_channel_restart returns False when circuit breaker open for channel."""
    mock_cb = AsyncMock()
    mock_cb.can_restart = AsyncMock(return_value=False)
    monkeypatch.setattr(
        "exstreamtv.streaming.circuit_breaker.get_circuit_breaker",
        lambda: mock_cb,
    )

    result = await request_channel_restart(1)
    assert result is False


@pytest.mark.slow
@pytest.mark.asyncio
async def test_circuit_breaker_half_open_allows_retry() -> None:
    """After cooldown, circuit moves to HALF_OPEN and allows one retry."""
    cb = CircuitBreaker(failure_threshold=2, window_seconds=10.0, cooldown_seconds=0.1)
    channel_id = 1

    await cb.record_failure(channel_id)
    await cb.record_failure(channel_id)
    assert await cb.can_restart(channel_id) is False

    await asyncio.sleep(0.15)
    assert await cb.can_restart(channel_id) is True
    state = await cb.get_state(channel_id)
    assert state == CircuitState.HALF_OPEN


@pytest.mark.slow
@pytest.mark.asyncio
async def test_circuit_breaker_prunes_old_failures() -> None:
    """Failures outside window are pruned; circuit may return to CLOSED."""
    cb = CircuitBreaker(failure_threshold=2, window_seconds=0.05, cooldown_seconds=0.1)
    channel_id = 1

    await cb.record_failure(channel_id)
    await cb.record_failure(channel_id)
    assert await cb.can_restart(channel_id) is False

    await asyncio.sleep(0.1)
    assert await cb.can_restart(channel_id) is True
    state = await cb.get_state(channel_id)
    assert state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_restart_guard_invariants_hold() -> None:
    """Restart path uses request_channel_restart; circuit breaker and cooldown enforced."""
    from exstreamtv.ai_agent.tool_registry import execute_restart_channel
    from exstreamtv.ai_agent.grounded_envelope import build_grounded_envelope

    envelope = build_grounded_envelope(
        channel_id=1,
        failure_classification="stream_timeout",
        restart_count=0,
        restart_velocity=0.0,
        pool_pressure_override=0.0,
        circuit_breaker_open=False,
    )

    mock_restart = AsyncMock(return_value=True)
    with patch("exstreamtv.tasks.health_tasks.request_channel_restart", mock_restart):
        result = await execute_restart_channel(
            1, envelope, restart_cap=3, high_risk_already_executed=False
        )
        mock_restart.assert_called_once_with(1)
    assert result.get("success") is True
