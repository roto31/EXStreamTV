"""Capture and restore playout items (schedule memento) for revert."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.database.models import PlayoutItem, ScheduleHistory
from exstreamtv.patterns.repository.program_repository import ProgramRepository

logger = logging.getLogger(__name__)


def _serialize_item(item: PlayoutItem) -> dict[str, Any]:
    return {
        "playout_id": item.playout_id,
        "media_item_id": item.media_item_id,
        "source_url": item.source_url,
        "start_time": item.start_time.isoformat(),
        "finish_time": item.finish_time.isoformat(),
        "title": item.title,
        "episode_title": item.episode_title,
        "filler_kind": item.filler_kind,
        "guide_group": item.guide_group,
        "custom_title": item.custom_title,
        "block_id": item.block_id,
        "in_point_seconds": item.in_point.total_seconds() if item.in_point else None,
        "out_point_seconds": item.out_point.total_seconds() if item.out_point else None,
    }


async def capture_channels_snapshot_json(db: AsyncSession, channel_ids: list[int]) -> str:
    repo = ProgramRepository(db)
    payload: dict[str, Any] = {
        "captured_at": datetime.now(tz=timezone.utc).isoformat(),
        "channels": {},
    }
    for cid in channel_ids:
        items = await repo.list_by_channel(cid)
        payload["channels"][str(cid)] = [_serialize_item(i) for i in items]
    return json.dumps(payload)


async def create_history_record(
    db: AsyncSession,
    snapshot_json: str,
    persona_id: str | None = None,
    label: str | None = None,
) -> ScheduleHistory:
    row = ScheduleHistory(
        persona_id=persona_id,
        label=label,
        applied=True,
        pre_apply_snapshot=snapshot_json,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def revert_snapshot(db: AsyncSession, history: ScheduleHistory) -> int:
    if not history.pre_apply_snapshot:
        raise ValueError("no pre_apply_snapshot")
    if not history.applied:
        raise ValueError("history entry was not applied")
    data = json.loads(history.pre_apply_snapshot)
    channels: dict[str, list[dict[str, Any]]] = data.get("channels") or {}
    restored = 0
    for _cid_str, rows in channels.items():
        by_playout: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            pid = int(row["playout_id"])
            by_playout.setdefault(pid, []).append(row)
        for playout_id, plist in by_playout.items():
            await db.execute(
                delete(PlayoutItem).where(PlayoutItem.playout_id == playout_id)
            )
            for row in plist:
                in_pt = (
                    timedelta(seconds=float(row["in_point_seconds"]))
                    if row.get("in_point_seconds") is not None
                    else None
                )
                out_pt = (
                    timedelta(seconds=float(row["out_point_seconds"]))
                    if row.get("out_point_seconds") is not None
                    else None
                )
                pi = PlayoutItem(
                    playout_id=playout_id,
                    media_item_id=row.get("media_item_id"),
                    source_url=row.get("source_url"),
                    start_time=datetime.fromisoformat(row["start_time"]),
                    finish_time=datetime.fromisoformat(row["finish_time"]),
                    title=row["title"],
                    episode_title=row.get("episode_title"),
                    filler_kind=row.get("filler_kind"),
                    guide_group=row.get("guide_group"),
                    custom_title=row.get("custom_title"),
                    block_id=row.get("block_id"),
                    in_point=in_pt,
                    out_point=out_pt,
                )
                db.add(pi)
                restored += 1
    await db.commit()
    return restored
