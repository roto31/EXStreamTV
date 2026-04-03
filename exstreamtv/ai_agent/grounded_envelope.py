"""Ground truth / safety context passed into bounded agent execution."""

from __future__ import annotations

from dataclasses import dataclass

RESTART_STORM_VELOCITY_THRESHOLD = 2.0


@dataclass
class GroundedEnvelope:
    channel_id: int
    restart_velocity: float = 0.0
    pool_pressure_override: float = 0.0
    circuit_breaker_open: bool = False
    containment_mode: bool = False
    confidence: float = 0.5
    failure_classification: str = ""
    restart_count: int = 0


def build_grounded_envelope(
    channel_id: int,
    *,
    restart_velocity: float = 0.0,
    pool_pressure_override: float = 0.0,
    circuit_breaker_open: bool = False,
    confidence: float | None = None,
    failure_classification: str = "",
    restart_count: int = 0,
) -> GroundedEnvelope:
    from exstreamtv.tasks.health_tasks import _get_long_run_containment_mode

    conf = 0.5 if confidence is None else confidence
    containment_mode = (
        restart_velocity >= RESTART_STORM_VELOCITY_THRESHOLD
        or pool_pressure_override >= 0.9
        or circuit_breaker_open
        or _get_long_run_containment_mode()
    )
    return GroundedEnvelope(
        channel_id=channel_id,
        restart_velocity=restart_velocity,
        pool_pressure_override=pool_pressure_override,
        circuit_breaker_open=circuit_breaker_open,
        containment_mode=containment_mode,
        confidence=conf,
        failure_classification=failure_classification,
        restart_count=restart_count,
    )
