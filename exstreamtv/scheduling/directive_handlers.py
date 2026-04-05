"""
Strategy-based dispatch for schedule sequence directives.

Replaces the if/elif cascade in ``ScheduleEngine.resolve_sequence_item``
with a registry of directive handlers, each encapsulating one ErsatzTV
schedule directive (padToNext, padUntil, waitUntil, skipItems, etc.).

Decision-tree path (from design-pattern-decision-tree):
    Behaviour → accumulating conditionals per directive type
    → each branch is an independent resolution strategy
    → Strategy pattern (keyed registry, first-match wins)

Each handler receives the same context and returns ``list[dict]``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

from exstreamtv.scheduling.parser import ParsedSchedule

if TYPE_CHECKING:
    from exstreamtv.scheduling.engine import ScheduleEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract handler & context
# ---------------------------------------------------------------------------

class DirectiveHandler(ABC):
    """Strategy interface for one schedule-item directive."""

    @abstractmethod
    def can_handle(self, item: dict[str, Any]) -> bool:
        """Return True if *item* contains the key this handler owns."""

    @abstractmethod
    def handle(
        self,
        item: dict[str, Any],
        schedule: ParsedSchedule,
        current_time: datetime,
        engine: ScheduleEngine,
    ) -> list[dict[str, Any]]:
        """Resolve the directive to a (possibly empty) list of media dicts."""


# ---------------------------------------------------------------------------
# Concrete handlers — one per directive type
# ---------------------------------------------------------------------------

class PadToNextHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "padToNext" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        return engine._handle_pad_to_next(item, schedule, current_time)


class PadUntilHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "padUntil" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        return engine._handle_pad_until(item, schedule, current_time)


class WaitUntilHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "waitUntil" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        return engine._handle_wait_until(item, current_time)


class SkipItemsHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "skipItems" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        return engine._handle_skip_items(item, schedule)


class ShuffleSequenceHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "shuffleSequence" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        return engine._handle_shuffle_sequence(item, schedule)


class RollFlagHandler(DirectiveHandler):
    """Handles pre_roll / mid_roll / post_roll flag items (no media output)."""

    _KEYS = frozenset({"pre_roll", "mid_roll", "post_roll"})

    def can_handle(self, item: dict[str, Any]) -> bool:
        return bool(self._KEYS & item.keys())

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        return []


class SequenceReferenceHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "sequence" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        sequence_key = item["sequence"]
        media_items = engine.get_sequence_media(sequence_key, schedule)
        resolved: list[dict[str, Any]] = []
        for media_item in media_items:
            metadata = engine._extract_metadata_from_media_item(media_item)
            resolved.append({
                "media_item": media_item,
                "custom_title": item.get("custom_title"),
                "filler_kind": item.get("filler_kind"),
                "start_time": current_time,
                "metadata": metadata,
            })
        return resolved


class AllContentHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "all" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        content_key = item["all"]
        if content_key not in schedule.content_map:
            return []
        collection_name = schedule.content_map[content_key]["collection"]
        media_items = engine.get_collection_media(collection_name)
        order = schedule.content_map[content_key].get("order", "chronological")
        if order == "shuffle":
            media_items = media_items.copy()
            engine._random.shuffle(media_items)
        return [
            {
                "media_item": mi,
                "custom_title": item.get("custom_title"),
                "filler_kind": item.get("filler_kind"),
                "start_time": current_time,
            }
            for mi in media_items
        ]


class DurationFillerHandler(DirectiveHandler):
    def can_handle(self, item: dict[str, Any]) -> bool:
        return "duration" in item and "content" in item

    def handle(self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime, engine: ScheduleEngine) -> list[dict[str, Any]]:
        from exstreamtv.scheduling.parser import ScheduleParser

        content_key = item["content"]
        duration_str = item["duration"]
        duration_seconds = ScheduleParser.parse_duration(duration_str)

        if not duration_seconds or content_key not in schedule.content_map:
            return []

        collection_name = schedule.content_map[content_key]["collection"]
        media_items = engine.get_collection_media(collection_name)
        order = schedule.content_map[content_key].get("order", "shuffle")
        if order == "shuffle":
            media_items = media_items.copy()
            engine._random.shuffle(media_items)

        selected: list = []
        total_duration = 0.0
        discard_attempts = item.get("discard_attempts", 0)
        attempts = 0

        for media_item in media_items:
            if total_duration >= duration_seconds:
                break
            item_dur = media_item.duration or 0
            if item_dur > 0:
                if total_duration + item_dur <= duration_seconds * 1.1:
                    selected.append(media_item)
                    total_duration += item_dur
                elif attempts < discard_attempts:
                    attempts += 1
                    continue
                else:
                    break

        return [
            {
                "media_item": mi,
                "custom_title": item.get("custom_title"),
                "filler_kind": item.get("filler_kind", "Commercial"),
                "start_time": current_time,
            }
            for mi in selected
        ]


# ---------------------------------------------------------------------------
# Registry (canonical order)
# ---------------------------------------------------------------------------

def build_directive_handlers() -> list[DirectiveHandler]:
    """Return the default handler list in priority order.

    ErsatzTV advanced directives are checked first, then roll flags,
    then content-producing items.
    """
    return [
        PadToNextHandler(),
        PadUntilHandler(),
        WaitUntilHandler(),
        SkipItemsHandler(),
        ShuffleSequenceHandler(),
        RollFlagHandler(),
        SequenceReferenceHandler(),
        AllContentHandler(),
        DurationFillerHandler(),
    ]
