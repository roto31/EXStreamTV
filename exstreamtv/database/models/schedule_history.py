"""Schedule apply / revert history (memento persistence)."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from exstreamtv.database.models.base import Base, TimestampMixin


class ScheduleHistory(Base, TimestampMixin):
    """
    Stores JSON snapshot of playout items before a bulk schedule apply.
    Used with ScheduleSnapshotPayload revert flow.
    """

    __tablename__ = "schedule_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pre_apply_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
