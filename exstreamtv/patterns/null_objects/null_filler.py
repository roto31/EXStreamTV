from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any

from exstreamtv.database.models.channel import Channel
from exstreamtv.database.models.filler import FillerPresetItem


class BaseFillerLibrary(ABC):
    """Filler selection API — real preset or null object."""

    @abstractmethod
    def get_item_for_duration(self, target_seconds: int) -> FillerPresetItem | None:
        """Longest item that fits in target_seconds (by max_duration or weight proxy)."""

    @abstractmethod
    def get_random_item(self) -> FillerPresetItem | None:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...

    def __bool__(self) -> bool:
        return len(self) > 0


def _item_duration_estimate(item: FillerPresetItem) -> int:
    if item.max_duration_seconds is not None:
        return int(item.max_duration_seconds)
    if item.min_duration_seconds is not None:
        return int(item.min_duration_seconds)
    return 60


class NullFillerLibrary(BaseFillerLibrary):
    """No filler configured — callers always get None, never branch on preset missing."""

    def get_item_for_duration(self, target_seconds: int) -> FillerPresetItem | None:
        return None

    def get_random_item(self) -> FillerPresetItem | None:
        return None

    def __len__(self) -> int:
        return 0

    def __repr__(self) -> str:
        return "NullFillerLibrary()"

    def list_items(self) -> list[FillerPresetItem]:
        return []

    def pick_next(self) -> FillerPresetItem | None:
        return None

    def duration_seconds(self) -> int:
        return 0

    def as_preset_dict(self) -> dict[str, Any]:
        return {"name": "null", "items": []}


class FillerLibrary(BaseFillerLibrary):
    """Concrete library from preset rows."""

    def __init__(self, items: list[FillerPresetItem]) -> None:
        self._items = sorted(items, key=_item_duration_estimate)

    def get_item_for_duration(self, target_seconds: int) -> FillerPresetItem | None:
        candidates = [i for i in self._items if _item_duration_estimate(i) <= target_seconds]
        return candidates[-1] if candidates else None

    def get_random_item(self) -> FillerPresetItem | None:
        if not self._items:
            return None
        return random.choice(self._items)

    def __len__(self) -> int:
        return len(self._items)


def get_filler_library_for_channel(
    channel: Channel,
    items: list[FillerPresetItem],
) -> BaseFillerLibrary:
    if channel.fallback_filler_id is None or not items:
        return NullFillerLibrary()
    return FillerLibrary(items)
