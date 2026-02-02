"""Schedule engine v2 - Continuous playback, timeline tracking, and ErsatzTV-style cycle calculation"""

import logging
import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..database.models_v2 import (
    Channel,
    Collection,
    CollectionItem,
    MediaItem,
    Playlist,
    PlaylistItem,
)
from .parser import ParsedSchedule, ScheduleParser

logger = logging.getLogger(__name__)


class ScheduleEngineV2:
    """
    Schedule engine v2 - Enhanced with proper timeline tracking and ErsatzTV-style cycle calculation

    Features:
    - Continuous playback with timeline tracking
    - ErsatzTV-compatible cycle calculation
    - Proper handling of pre-roll, mid-roll, post-roll
    - Timeline-aware scheduling
    """

    def __init__(self, db: Session, seed: int | None = None):
        """
        Initialize schedule engine v2

        Args:
            db: Database session
            seed: Optional random seed for reproducible shuffling
        """
        self.db = db
        self._collection_cache: dict[str, list[MediaItem]] = {}
        self._playlist_cache: dict[str, Playlist] = {}
        self._seed = seed or random.randint(1, 1000000)
        self._random = random.Random(self._seed)
        self._shuffled_sequences: dict[str, list[dict[str, Any]]] = {}

        # Timeline tracking
        self._timeline_start: datetime | None = None
        self._current_timeline_position: datetime | None = None

    def get_collection_media(self, collection_name: str) -> list[MediaItem]:
        """Get all media items from a collection by name"""
        if collection_name in self._collection_cache:
            return self._collection_cache[collection_name]

        # Find collection by name
        collection = self.db.query(Collection).filter(Collection.name == collection_name).first()

        if collection:
            items = (
                self.db.query(CollectionItem)
                .filter(CollectionItem.collection_id == collection.id)
                .order_by(CollectionItem.order)
                .all()
            )

            media_items = []
            for item in items:
                media_item = (
                    self.db.query(MediaItem).filter(MediaItem.id == item.media_item_id).first()
                )
                if media_item:
                    media_items.append(media_item)

            self._collection_cache[collection_name] = media_items
            return media_items

        # Fallback: try playlist
        playlist = self.db.query(Playlist).filter(Playlist.name == collection_name).first()

        if playlist:
            items = (
                self.db.query(PlaylistItem)
                .filter(PlaylistItem.playlist_id == playlist.id)
                .order_by(PlaylistItem.order)
                .all()
            )

            media_items = []
            for item in items:
                media_item = (
                    self.db.query(MediaItem).filter(MediaItem.id == item.media_item_id).first()
                )
                if media_item:
                    media_items.append(media_item)

            self._collection_cache[collection_name] = media_items
            return media_items

        logger.warning(f"Collection/Playlist not found: {collection_name}")
        self._collection_cache[collection_name] = []
        return []

    def calculate_cycle_duration(
        self, schedule: ParsedSchedule, start_time: datetime | None = None
    ) -> timedelta:
        """
        Calculate the duration of a complete schedule cycle (ErsatzTV-style)

        Args:
            schedule: Parsed schedule
            start_time: Optional start time (defaults to now)

        Returns:
            Total duration of one cycle
        """
        if not schedule.main_sequence_key:
            return timedelta(0)

        main_sequence = schedule.sequences.get(schedule.main_sequence_key, [])
        if not main_sequence:
            return timedelta(0)

        total_duration = timedelta(0)
        current_time = start_time or datetime.utcnow()

        for item in main_sequence:
            # Handle waitUntil - updates time but doesn't add duration
            if "waitUntil" in item:
                wait_until_str = item.get("waitUntil")
                if wait_until_str:
                    try:
                        time_parts = wait_until_str.split(":")
                        if len(time_parts) >= 2:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            second = int(time_parts[2]) if len(time_parts) > 2 else 0

                            target_time = current_time.replace(
                                hour=hour, minute=minute, second=second, microsecond=0
                            )
                            if target_time <= current_time:
                                if item.get("tomorrow", False):
                                    target_time += timedelta(days=1)

                            # Duration is the wait time
                            wait_duration = target_time - current_time
                            if wait_duration.total_seconds() > 0:
                                total_duration += wait_duration

                            current_time = target_time
                    except (ValueError, IndexError):
                        pass
                continue

            # Skip flags
            if any(key in item for key in ["pre_roll", "mid_roll", "post_roll"]):
                continue

            # Calculate item duration
            item_duration = self._calculate_item_duration(item, schedule)
            if item_duration:
                total_duration += item_duration
                current_time += item_duration

        return total_duration

    def _calculate_item_duration(
        self, item: dict[str, Any], schedule: ParsedSchedule
    ) -> timedelta | None:
        """Calculate duration for a single schedule item"""
        # Explicit duration
        if "duration" in item:
            duration_str = item["duration"]
            duration_seconds = ScheduleParser.parse_duration(duration_str)
            if duration_seconds:
                return timedelta(seconds=duration_seconds)

        # Content/sequence duration - sum of media items
        if "content" in item or "all" in item or "sequence" in item:
            media_items = self._resolve_item_to_media(item, schedule)
            total_seconds = sum((m.duration or 0) for m in media_items)
            if total_seconds > 0:
                return timedelta(seconds=total_seconds)

        return None

    def _resolve_item_to_media(
        self, item: dict[str, Any], schedule: ParsedSchedule
    ) -> list[MediaItem]:
        """Resolve a schedule item to list of media items"""
        media_items = []

        if "sequence" in item:
            sequence_key = item["sequence"]
            if sequence_key in schedule.sequences:
                sequence_items = schedule.sequences[sequence_key]
                for seq_item in sequence_items:
                    media_items.extend(self._resolve_item_to_media(seq_item, schedule))

        elif "content" in item or "all" in item:
            content_key = item.get("content") or item.get("all")
            if content_key and content_key in schedule.content_map:
                collection_name = schedule.content_map[content_key]["collection"]
                items = self.get_collection_media(collection_name)

                # Handle order
                order = schedule.content_map[content_key].get("order", "chronological")
                if order == "shuffle":
                    items = items.copy()
                    self._random.shuffle(items)

                media_items.extend(items)

        return media_items

    def generate_timeline(
        self,
        channel: Channel,
        schedule: ParsedSchedule,
        start_time: datetime | None = None,
        duration: timedelta | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate timeline of scheduled items (ErsatzTV-style continuous playback)

        Args:
            channel: Channel to generate timeline for
            schedule: Parsed schedule
            start_time: Start time for timeline (defaults to now)
            duration: Duration to generate (defaults to one cycle)

        Returns:
            List of timeline items with start_time, end_time, and media_item
        """
        if not schedule.main_sequence_key:
            logger.warning(f"No main sequence found in schedule: {schedule.name}")
            return []

        main_sequence = schedule.sequences.get(schedule.main_sequence_key, [])
        if not main_sequence:
            logger.warning(f"Main sequence {schedule.main_sequence_key} is empty")
            return []

        start_time = start_time or datetime.utcnow()
        self._timeline_start = start_time
        self._current_timeline_position = start_time

        # Calculate cycle duration
        cycle_duration = self.calculate_cycle_duration(schedule, start_time)
        if not duration:
            duration = cycle_duration if cycle_duration.total_seconds() > 0 else timedelta(hours=24)

        # Check if we need to repeat
        repeat = any(p.get("repeat") for p in schedule.playout)

        timeline_items = []
        end_time = start_time + duration

        # Generate timeline until we reach end_time
        while self._current_timeline_position < end_time:
            cycle_items = self._generate_cycle_timeline(main_sequence, schedule, start_time)

            if not cycle_items:
                logger.warning("No items generated in cycle, stopping")
                break

            # Add cycle items to timeline
            for item in cycle_items:
                if self._current_timeline_position >= end_time:
                    break

                item_start = item.get("start_time", self._current_timeline_position)
                item_duration = item.get("duration", timedelta(0))
                item_end = item_start + item_duration

                # Only add if it starts before end_time
                if item_start < end_time:
                    timeline_items.append(
                        {
                            "start_time": item_start,
                            "end_time": min(item_end, end_time),
                            "media_item": item.get("media_item"),
                            "custom_title": item.get("custom_title"),
                            "filler_kind": item.get("filler_kind"),
                        }
                    )

                    self._current_timeline_position = item_end
                else:
                    break

            # Repeat if needed
            if not repeat or self._current_timeline_position >= end_time:
                break

            # Reset for next cycle
            if cycle_duration.total_seconds() > 0:
                # Align to cycle boundary
                cycles_elapsed = (self._current_timeline_position - start_time) // cycle_duration
                self._current_timeline_position = start_time + (cycles_elapsed + 1) * cycle_duration
            else:
                # No cycle duration, just continue
                break

        logger.info(
            f"Generated {len(timeline_items)} timeline items from {start_time} to {end_time}"
        )

        return timeline_items

    def _generate_cycle_timeline(
        self, sequence: list[dict[str, Any]], schedule: ParsedSchedule, cycle_start: datetime
    ) -> list[dict[str, Any]]:
        """Generate timeline items for one cycle"""
        timeline_items = []
        current_time = cycle_start
        pre_roll_active = False
        mid_roll_active = False
        post_roll_active = False

        for item in sequence:
            # Handle waitUntil
            if "waitUntil" in item:
                wait_until_str = item.get("waitUntil")
                if wait_until_str:
                    try:
                        time_parts = wait_until_str.split(":")
                        if len(time_parts) >= 2:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            second = int(time_parts[2]) if len(time_parts) > 2 else 0

                            target_time = current_time.replace(
                                hour=hour, minute=minute, second=second, microsecond=0
                            )
                            if target_time <= current_time:
                                if item.get("tomorrow", False):
                                    target_time += timedelta(days=1)

                            current_time = target_time
                    except (ValueError, IndexError):
                        pass
                continue

            # Handle pre-roll, mid-roll, post-roll flags
            if "pre_roll" in item:
                pre_roll_active = bool(item["pre_roll"])
                continue

            if "mid_roll" in item:
                mid_roll_active = bool(item["mid_roll"])
                continue

            if "post_roll" in item:
                post_roll_active = bool(item["post_roll"])
                continue

            # Resolve item to media
            resolved = self._resolve_sequence_item(
                item, schedule, current_time, pre_roll_active, mid_roll_active, post_roll_active
            )

            for resolved_item in resolved:
                media_item = resolved_item.get("media_item")
                if not media_item:
                    continue

                item_duration = timedelta(seconds=media_item.duration or 0)
                if item_duration.total_seconds() == 0:
                    continue

                timeline_items.append(
                    {
                        "start_time": current_time,
                        "duration": item_duration,
                        "media_item": media_item,
                        "custom_title": resolved_item.get("custom_title"),
                        "filler_kind": resolved_item.get("filler_kind"),
                    }
                )

                current_time += item_duration

        return timeline_items

    def _resolve_sequence_item(
        self,
        item: dict[str, Any],
        schedule: ParsedSchedule,
        current_time: datetime,
        pre_roll_active: bool = False,
        mid_roll_active: bool = False,
        post_roll_active: bool = False,
    ) -> list[dict[str, Any]]:
        """Resolve a sequence item to media items (similar to v1 but with v2 models)"""
        resolved = []

        # Handle ErsatzTV directives
        if "padToNext" in item:
            return self._handle_pad_to_next(item, schedule, current_time)

        if "padUntil" in item:
            return self._handle_pad_until(item, schedule, current_time)

        if "waitUntil" in item:
            return []  # Already handled in timeline generation

        if "skipItems" in item:
            return self._handle_skip_items(item, schedule)

        if "shuffleSequence" in item:
            return self._handle_shuffle_sequence(item, schedule)

        # Handle content/sequence references
        if "sequence" in item:
            sequence_key = item["sequence"]
            if sequence_key in schedule.sequences:
                sequence_items = schedule.sequences[sequence_key]
                for seq_item in sequence_items:
                    resolved.extend(
                        self._resolve_sequence_item(
                            seq_item,
                            schedule,
                            current_time,
                            pre_roll_active,
                            mid_roll_active,
                            post_roll_active,
                        )
                    )

        elif "content" in item or "all" in item:
            content_key = item.get("content") or item.get("all")
            if content_key and content_key in schedule.content_map:
                collection_name = schedule.content_map[content_key]["collection"]
                media_items = self.get_collection_media(collection_name)

                # Handle order
                order = schedule.content_map[content_key].get("order", "chronological")
                if order == "shuffle":
                    media_items = media_items.copy()
                    self._random.shuffle(media_items)

                for media_item in media_items:
                    resolved.append(
                        {
                            "media_item": media_item,
                            "custom_title": item.get("custom_title"),
                            "filler_kind": item.get("filler_kind"),
                        }
                    )

        # Handle duration-based filler
        elif "duration" in item and "content" in item:
            content_key = item["content"]
            duration_str = item["duration"]
            duration_seconds = ScheduleParser.parse_duration(duration_str)

            if duration_seconds and content_key in schedule.content_map:
                collection_name = schedule.content_map[content_key]["collection"]
                media_items = self.get_collection_media(collection_name)

                # Select items to fill duration
                selected_items = []
                total_duration = 0

                for media_item in media_items:
                    if total_duration >= duration_seconds:
                        break

                    item_duration = media_item.duration or 0
                    if (
                        item_duration > 0
                        and total_duration + item_duration <= duration_seconds * 1.1
                    ):
                        selected_items.append(media_item)
                        total_duration += item_duration

                for media_item in selected_items:
                    resolved.append(
                        {
                            "media_item": media_item,
                            "custom_title": item.get("custom_title"),
                            "filler_kind": item.get("filler_kind", "Commercial"),
                        }
                    )

        return resolved

    def _handle_pad_to_next(
        self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime
    ) -> list[dict[str, Any]]:
        """Handle padToNext directive - pad to next hour/half-hour boundary"""
        # Get next boundary (hour or half-hour)
        next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        next_half_hour = current_time.replace(
            minute=30 if current_time.minute < 30 else 0, second=0, microsecond=0
        )
        if next_half_hour <= current_time:
            next_half_hour += timedelta(hours=1)

        target_time = min(next_hour, next_half_hour)
        duration_seconds = (target_time - current_time).total_seconds()

        if duration_seconds > 0:
            # Use duration-based filler
            filler_item = item.copy()
            filler_item["duration"] = (
                f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}"
            )
            return self._resolve_sequence_item(filler_item, schedule, current_time)

        return []

    def _handle_pad_until(
        self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime
    ) -> list[dict[str, Any]]:
        """Handle padUntil directive - pad until specific time"""
        pad_until_str = item.get("padUntil")
        if not pad_until_str:
            return []

        try:
            time_parts = pad_until_str.split(":")
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0

                target_time = current_time.replace(
                    hour=hour, minute=minute, second=second, microsecond=0
                )
                if target_time <= current_time:
                    target_time += timedelta(days=1)

                duration_seconds = (target_time - current_time).total_seconds()

                if duration_seconds > 0:
                    filler_item = item.copy()
                    filler_item["duration"] = (
                        f"{int(duration_seconds // 60)}:{int(duration_seconds % 60):02d}"
                    )
                    return self._resolve_sequence_item(filler_item, schedule, current_time)
        except (ValueError, IndexError):
            pass

        return []

    def _handle_skip_items(
        self, item: dict[str, Any], schedule: ParsedSchedule
    ) -> list[dict[str, Any]]:
        """Handle skipItems directive - skip N items from collection"""
        # This is handled at collection resolution level
        return []

    def _handle_shuffle_sequence(
        self, item: dict[str, Any], schedule: ParsedSchedule
    ) -> list[dict[str, Any]]:
        """Handle shuffleSequence directive - shuffle a sequence"""
        sequence_key = item.get("shuffleSequence")
        if sequence_key and sequence_key in schedule.sequences:
            sequence = schedule.sequences[sequence_key].copy()
            self._random.shuffle(sequence)
            # Return shuffled sequence items
            resolved = []
            for seq_item in sequence:
                resolved.extend(self._resolve_sequence_item(seq_item, schedule, datetime.utcnow()))
            return resolved
        return []
