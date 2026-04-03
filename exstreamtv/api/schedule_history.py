"""Schedule snapshot (memento) capture and revert API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.database import get_db
from exstreamtv.database.models import ScheduleHistory
from exstreamtv.services.schedule_snapshot_service import (
    capture_channels_snapshot_json,
    create_history_record,
    revert_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/schedule-history", tags=["Schedule history"])


class CaptureBody(BaseModel):
    channel_ids: list[int] = Field(..., min_length=1)
    persona_id: str | None = None
    label: str | None = None


@router.post("/capture", status_code=status.HTTP_201_CREATED)
async def capture_schedule_snapshot(
    body: CaptureBody,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    snap = await capture_channels_snapshot_json(db, body.channel_ids)
    row = await create_history_record(
        db, snap, persona_id=body.persona_id, label=body.label
    )
    return {"id": row.id, "persona_id": row.persona_id, "label": row.label}


@router.post("/{history_id}/revert", status_code=status.HTTP_200_OK)
async def revert_schedule_history(
    history_id: int,
    persona_id: str | None = Query(None, description="Optional; must match row if set"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await db.execute(select(ScheduleHistory).where(ScheduleHistory.id == history_id))
    history = result.scalar_one_or_none()
    if history is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    if persona_id is not None and history.persona_id != persona_id:
        raise HTTPException(status_code=404, detail="History entry not found")
    if not history.applied:
        raise HTTPException(
            status_code=409, detail="Entry was not marked applied — nothing to revert"
        )
    if not history.pre_apply_snapshot:
        raise HTTPException(status_code=409, detail="No pre-apply snapshot stored")
    try:
        n = await revert_snapshot(db, history)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        logger.error("revert_snapshot failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Revert failed") from e
    return {"status": "ok", "items_restored": n}
