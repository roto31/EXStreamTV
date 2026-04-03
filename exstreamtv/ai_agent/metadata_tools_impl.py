"""Concrete async implementations for metadata-only agent tools."""

from __future__ import annotations

from typing import Any


async def execute_re_enrich_metadata(channel_id: int, **kwargs: Any) -> dict[str, Any]:
    """Re-run metadata enrichment for a channel (stub for tests / future wiring)."""
    _ = kwargs
    return {"success": True, "message": "ok", "channel_id": channel_id}
