"""
Persistent playout journal — telemetry only.

Stores bytes_sent, last_exit_classification, last_known_state for diagnostics.
Never used as schedule source. Index/recovery logic retired.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Module-level cache: channel_id -> latest journal row (in-memory for quick reads)
_journal_cache: dict[int, dict[str, Any]] = {}
_cache_lock: Any = None  # Set at runtime if needed


def _get_session_factory():
    """Lazy import to avoid circular deps."""
    from exstreamtv.database.session import get_sync_session
    return get_sync_session


async def write_journal_async(
    channel_id: int,
    *,
    current_index: int,
    item_id: Optional[int] = None,
    accumulated_valid_play_time: float = 0.0,
    retry_count: int = 0,
    bytes_sent: int = 0,
    last_known_state: str = "idle",
    last_exit_classification: Optional[str] = None,
    last_stderr_snippet: Optional[str] = None,
) -> None:
    """
    Write journal entry (async). Uses sync session in executor to avoid blocking.
    """
    import asyncio
    from exstreamtv.database.models.playout_journal import PlayoutJournal

    def _write(db_session_factory) -> None:
        with db_session_factory() as session:
            row = PlayoutJournal(
                channel_id=channel_id,
                current_index=current_index,
                item_id=item_id,
                accumulated_valid_play_time=accumulated_valid_play_time,
                retry_count=retry_count,
                bytes_sent=bytes_sent,
                last_known_state=last_known_state,
                last_exit_classification=last_exit_classification,
                last_stderr_snippet=last_stderr_snippet[:500] if last_stderr_snippet else None,
                journal_updated_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
            logger.debug(
                f"Journal written ch={channel_id} idx={current_index} "
                f"state={last_known_state} exit={last_exit_classification}"
            )

    session_factory = _get_session_factory()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: _write(session_factory))


def write_journal_sync(
    db_session_factory,
    channel_id: int,
    *,
    current_index: int = 0,
    item_id: Optional[int] = None,
    accumulated_valid_play_time: float = 0.0,
    retry_count: int = 0,
    bytes_sent: int = 0,
    last_known_state: str = "idle",
    last_exit_classification: Optional[str] = None,
    last_stderr_snippet: Optional[str] = None,
) -> None:
    """Write journal entry (sync). Telemetry only — index never used for schedule."""
    from exstreamtv.database.models.playout_journal import PlayoutJournal

    session = db_session_factory()
    try:
        row = PlayoutJournal(
            channel_id=channel_id,
            current_index=current_index,
            item_id=item_id,
            accumulated_valid_play_time=accumulated_valid_play_time,
            retry_count=retry_count,
            bytes_sent=bytes_sent,
            last_known_state=last_known_state,
            last_exit_classification=last_exit_classification,
            last_stderr_snippet=last_stderr_snippet[:500] if last_stderr_snippet else None,
            journal_updated_at=datetime.utcnow(),
        )
        session.add(row)
        session.commit()
        logger.debug(
            f"Journal written ch={channel_id} state={last_known_state} exit={last_exit_classification}"
        )
    finally:
        session.close()


def write_journal_telemetry(
    db_session_factory,
    channel_id: int,
    *,
    bytes_sent: int = 0,
    last_known_state: str = "idle",
    last_exit_classification: Optional[str] = None,
) -> None:
    """Write telemetry-only journal entry (no index)."""
    write_journal_sync(
        db_session_factory,
        channel_id,
        current_index=0,
        bytes_sent=bytes_sent,
        last_known_state=last_known_state,
        last_exit_classification=last_exit_classification,
    )


def load_latest_journal(db_session_factory, channel_id: int) -> Optional[dict[str, Any]]:
    """
    Load latest journal entry for channel. Returns None if none exists.
    """
    from exstreamtv.database.models.playout_journal import PlayoutJournal

    session = db_session_factory()
    try:
        stmt = (
            select(PlayoutJournal)
            .where(PlayoutJournal.channel_id == channel_id)
            .order_by(PlayoutJournal.journal_updated_at.desc())
            .limit(1)
        )
        result = session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        j = row  # PlayoutJournal instance
        return {
            "current_index": j.current_index,
            "item_id": j.item_id,
            "accumulated_valid_play_time": j.accumulated_valid_play_time,
            "retry_count": j.retry_count,
            "bytes_sent": j.bytes_sent,
            "last_known_state": j.last_known_state,
            "last_exit_classification": j.last_exit_classification,
            "journal_updated_at": j.journal_updated_at,
        }
    finally:
        session.close()


def get_playout_journal(db_session_factory):
    """Return journal operations bound to session factory."""
    class JournalOps:
        def write(
            self,
            channel_id: int,
            *,
            current_index: int,
            item_id: Optional[int] = None,
            accumulated_valid_play_time: float = 0.0,
            retry_count: int = 0,
            bytes_sent: int = 0,
            last_known_state: str = "idle",
            last_exit_classification: Optional[str] = None,
            last_stderr_snippet: Optional[str] = None,
        ) -> None:
            write_journal_sync(
                db_session_factory,
                channel_id,
                current_index=current_index,
                item_id=item_id,
                accumulated_valid_play_time=accumulated_valid_play_time,
                retry_count=retry_count,
                bytes_sent=bytes_sent,
                last_known_state=last_known_state,
                last_exit_classification=last_exit_classification,
                last_stderr_snippet=last_stderr_snippet,
            )

        def load(self, channel_id: int) -> Optional[dict[str, Any]]:
            return load_latest_journal(db_session_factory, channel_id)

    return JournalOps()
