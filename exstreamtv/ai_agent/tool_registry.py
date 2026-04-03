"""Tool names exposed to the AI agent (metadata vs operational modes)."""

from __future__ import annotations

from typing import Any, FrozenSet

from exstreamtv.ai_agent import metadata_tools_impl
from exstreamtv.ai_agent.grounded_envelope import GroundedEnvelope

METADATA_ONLY_TOOLS: FrozenSet[str] = frozenset(
    {
        "re_enrich_metadata",
        "refresh_plex_metadata",
        "rebuild_xmltv",
        "reparse_filename_metadata",
        "fetch_metadata_logs",
    }
)


def get_tools_for_mode(mode: str) -> FrozenSet[str]:
    if mode == "metadata":
        return METADATA_ONLY_TOOLS
    return frozenset()


async def execute_restart_channel(
    channel_id: int,
    envelope: GroundedEnvelope,
    *,
    restart_cap: int = 3,
    high_risk_already_executed: bool = False,
) -> dict[str, Any]:
    _ = envelope, restart_cap, high_risk_already_executed
    from exstreamtv.tasks.health_tasks import request_channel_restart

    await request_channel_restart(channel_id)
    return {"success": True}


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "re_enrich_metadata":
        channel_id = int(arguments.get("channel_id", 0))
        return await metadata_tools_impl.execute_re_enrich_metadata(channel_id)
    return {"success": False, "message": f"unknown tool: {name}"}
