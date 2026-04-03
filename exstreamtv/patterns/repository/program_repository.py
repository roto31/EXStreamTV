"""
Playout timeline items (maps prompt's Program to PlayoutItem + Playout.channel_id).
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from exstreamtv.database.models.playout import Playout, PlayoutItem

logger = logging.getLogger(__name__)


def _coerce_program_id(program_id: str | int) -> int:
    if isinstance(program_id, int):
        return program_id
    return int(program_id)


class ProgramRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, program_id: str | int) -> PlayoutItem | None:
        pid = _coerce_program_id(program_id)
        return await self._db.get(PlayoutItem, pid)

    async def list_by_channel(self, channel_id: str | int) -> list[PlayoutItem]:
        cid = int(channel_id) if not isinstance(channel_id, int) else channel_id
        playout_ids = select(Playout.id).where(Playout.channel_id == cid)
        result = await self._db.execute(
            select(PlayoutItem)
            .where(PlayoutItem.playout_id.in_(playout_ids))
            .order_by(PlayoutItem.start_time)
        )
        return list(result.scalars().all())

    async def list_current(
        self, channel_id: str | int, at: datetime
    ) -> PlayoutItem | None:
        items = await self.list_by_channel(channel_id)
        for item in items:
            if item.start_time <= at < item.finish_time:
                return item
        return None

    async def list_upcoming(
        self, channel_id: str | int, from_dt: datetime, limit: int = 10
    ) -> list[PlayoutItem]:
        cid = int(channel_id) if not isinstance(channel_id, int) else channel_id
        playout_ids = select(Playout.id).where(Playout.channel_id == cid)
        result = await self._db.execute(
            select(PlayoutItem)
            .where(PlayoutItem.playout_id.in_(playout_ids))
            .where(PlayoutItem.start_time >= from_dt)
            .order_by(PlayoutItem.start_time)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def save(self, program: PlayoutItem) -> PlayoutItem:
        self._db.add(program)
        await self._db.commit()
        await self._db.refresh(program)
        return program

    async def save_many(self, programs: list[PlayoutItem]) -> int:
        for p in programs:
            self._db.add(p)
        await self._db.commit()
        return len(programs)

    async def delete_by_channel(self, channel_id: str | int) -> int:
        cid = int(channel_id) if not isinstance(channel_id, int) else channel_id
        playout_ids = select(Playout.id).where(Playout.channel_id == cid)
        result = await self._db.execute(
            delete(PlayoutItem).where(PlayoutItem.playout_id.in_(playout_ids))
        )
        await self._db.commit()
        return result.rowcount or 0

    async def delete_ai_generated(self, channel_id: str | int) -> int:
        """No dedicated ai_generated column on PlayoutItem; reserved for future."""
        logger.debug(
            "delete_ai_generated: no schema flag; returning 0 for channel %s",
            channel_id,
        )
        return 0
