"""
Reserved for AI persona / schedule persona entities.

There is no Persona or ScheduleHistory ORM model in the current schema; methods
return empty results until migrations add those tables.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PersonaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, persona_id: str) -> Any | None:
        logger.debug("PersonaRepository.get_by_id: schema has no Persona table")
        return None

    async def list_all(self) -> list[Any]:
        return []

    async def list_by_channel(self, channel_id: str) -> list[Any]:
        return []

    async def save(self, persona: Any) -> Any:
        raise NotImplementedError("Persona model not present in database schema")

    async def update(self, persona: Any, **fields: object) -> Any:
        raise NotImplementedError("Persona model not present in database schema")

    async def delete(self, persona_id: str) -> bool:
        return False

    async def get_history(self, persona_id: str, limit: int = 20) -> list[Any]:
        return []

    async def save_history(self, history: Any) -> Any:
        raise NotImplementedError("ScheduleHistory model not present in database schema")
