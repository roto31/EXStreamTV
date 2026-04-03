"""
In-memory schedule snapshot (persist to DB when ScheduleHistory exists).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ScheduleMemento:
    channel_id: str
    snapshot_json: str
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    label: str = ""


class ScheduleOriginator:
    """Capture/restore schedule state without ORM until schema supports history."""

    def __init__(self, channel_id: str) -> None:
        self._channel_id = channel_id
        self._state: dict[str, Any] = {}

    def set_state(self, data: dict[str, Any]) -> None:
        self._state = dict(data)

    def create_memento(self, label: str = "") -> ScheduleMemento:
        import json

        return ScheduleMemento(
            channel_id=self._channel_id,
            snapshot_json=json.dumps(self._state, default=str),
            label=label,
        )

    def restore(self, memento: ScheduleMemento) -> None:
        import json

        self._state = json.loads(memento.snapshot_json)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._state)
