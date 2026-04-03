"""Bounded execution of planned agent steps with containment and confidence gating."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import asyncio

from exstreamtv.ai_agent.grounded_envelope import GroundedEnvelope
from exstreamtv.ai_agent.tool_registry import METADATA_ONLY_TOOLS, execute_tool

METADATA_CONFIDENCE_MIN = 0.3
CONFIDENCE_DECAY = 0.8
CONSECUTIVE_FAILURE_SHUTDOWN = 3


class PlanAction(str, Enum):
    CONTINUE = "continue"
    STOP = "stop"


@dataclass
class PlanStep:
    action: PlanAction
    tool_name: Optional[str]
    arguments: dict[str, Any]


@dataclass
class PersonaConfig:
    planning_depth_max: int = 10


@dataclass
class AgentLoopResult:
    steps_executed: int
    success: bool
    final_envelope: GroundedEnvelope
    escalated: bool
    message: str


async def run_bounded_loop(
    envelope: GroundedEnvelope,
    planned_steps: list[PlanStep],
    *,
    persona: Optional[PersonaConfig] = None,
    enabled_override: bool = True,
    mode_override: str = "metadata",
    force_confidence_gate: bool = False,
) -> AgentLoopResult:
    if not enabled_override:
        return AgentLoopResult(
            0,
            False,
            envelope,
            True,
            "agent disabled",
        )

    if envelope.containment_mode:
        return AgentLoopResult(
            0,
            False,
            envelope,
            True,
            "Aborted: containment mode active",
        )

    max_exec = persona.planning_depth_max if persona else 10**6
    env = GroundedEnvelope(
        channel_id=envelope.channel_id,
        restart_velocity=envelope.restart_velocity,
        pool_pressure_override=envelope.pool_pressure_override,
        circuit_breaker_open=envelope.circuit_breaker_open,
        containment_mode=envelope.containment_mode,
        confidence=envelope.confidence,
        failure_classification=envelope.failure_classification,
        restart_count=envelope.restart_count,
    )

    steps_executed = 0
    consecutive_failures = 0

    for step in planned_steps:
        if step.action == PlanAction.STOP:
            break
        if step.tool_name is None:
            continue

        is_metadata_tool = step.tool_name in METADATA_ONLY_TOOLS
        if (
            mode_override == "metadata"
            and is_metadata_tool
            and not force_confidence_gate
            and 0 < env.confidence < METADATA_CONFIDENCE_MIN
        ):
            continue

        if steps_executed >= max_exec:
            break

        result = await execute_tool(step.tool_name, step.arguments)
        steps_executed += 1

        if result.get("success"):
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            env.confidence *= CONFIDENCE_DECAY
            if consecutive_failures >= CONSECUTIVE_FAILURE_SHUTDOWN:
                return AgentLoopResult(
                    steps_executed,
                    False,
                    env,
                    True,
                    f"Consecutive metadata failures >= {CONSECUTIVE_FAILURE_SHUTDOWN}; escalating",
                )

        await asyncio.sleep(0)

    return AgentLoopResult(
        steps_executed,
        steps_executed > 0,
        env,
        False,
        "ok",
    )
