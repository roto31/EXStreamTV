"""Channel data access (repository). Channel PK is int per schema."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from exstreamtv.database.models.channel import Channel


def _coerce_channel_id(channel_id: str | int) -> int:
    if isinstance(channel_id, int):
        return channel_id
    return int(channel_id)


class ChannelRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, channel_id: str | int) -> Channel | None:
        cid = _coerce_channel_id(channel_id)
        return await self._db.get(Channel, cid)

    async def get_by_number(self, number: int | str) -> Channel | None:
        num = str(number)
        result = await self._db.execute(select(Channel).where(Channel.number == num))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Channel]:
        result = await self._db.execute(
            select(Channel).order_by(Channel.sort_number, Channel.number)
        )
        return list(result.scalars().all())

    async def list_all_with_profiles(self) -> list[Channel]:
        result = await self._db.execute(
            select(Channel)
            .options(
                selectinload(Channel.ffmpeg_profile),
                selectinload(Channel.watermark),
            )
            .order_by(Channel.sort_number, Channel.number)
        )
        return list(result.scalars().all())

    async def list_enabled(self) -> list[Channel]:
        result = await self._db.execute(
            select(Channel)
            .where(Channel.enabled.is_(True))
            .order_by(Channel.sort_number, Channel.number)
        )
        return list(result.scalars().all())

    async def list_by_group(self, group: str) -> list[Channel]:
        result = await self._db.execute(
            select(Channel)
            .where(Channel.group == group)
            .order_by(Channel.sort_number, Channel.number)
        )
        return list(result.scalars().all())

    async def save(self, channel: Channel) -> Channel:
        self._db.add(channel)
        await self._db.commit()
        await self._db.refresh(channel)
        return channel

    async def update(self, channel: Channel, **fields: object) -> Channel:
        for k, v in fields.items():
            if hasattr(channel, k):
                setattr(channel, k, v)
        await self._db.commit()
        await self._db.refresh(channel)
        return channel

    async def delete(self, channel_id: str | int) -> bool:
        ch = await self.get_by_id(channel_id)
        if ch is None:
            return False
        await self._db.delete(ch)
        await self._db.commit()
        return True

    async def exists(self, channel_id: str | int) -> bool:
        return await self.get_by_id(channel_id) is not None

    async def count(self) -> int:
        result = await self._db.execute(select(func.count()).select_from(Channel))
        return int(result.scalar_one())

    async def count_enabled(self) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(Channel).where(Channel.enabled.is_(True))
        )
        return int(result.scalar_one())
