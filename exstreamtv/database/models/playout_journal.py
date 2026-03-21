"""
Persistent playout journal for crash-safe resume.

Stores channel playout state with atomic guarantees.
Recovery: if last_known_state != STOPPING and last_exit_classification != NATURAL_EOF,
restore current_index and retry_count, DO NOT advance.
"""

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from exstreamtv.database.models.base import Base, TimestampMixin


class PlayoutJournal(Base, TimestampMixin):
    """
    Crash-safe playout state journal.

    Written on every state transition, every 10s during STREAMING,
    before index advancement, after retry increment, before shutdown.
    """

    __tablename__ = "playout_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Position
    current_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # media_item_id or playout_item id

    # Accumulated metrics
    accumulated_valid_play_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # State
    last_known_state: Mapped[str] = mapped_column(String(50), nullable=False, default="idle")
    last_exit_classification: Mapped[str] = mapped_column(String(50), nullable=True)

    # Optional stderr snippet for debugging
    last_stderr_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp of this journal entry
    journal_updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<PlayoutJournal ch={self.channel_id} idx={self.current_index} "
            f"state={self.last_known_state} exit={self.last_exit_classification}>"
        )
