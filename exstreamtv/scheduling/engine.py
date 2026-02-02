"""Schedule engine for executing schedule sequences (ErsatzTV-compatible)"""

import json
import logging
import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from exstreamtv.database import Channel, Collection, CollectionItem, MediaItem, Playlist, PlaylistItem

from .parser import ParsedSchedule, ScheduleParser

logger = logging.getLogger(__name__)


class ScheduleEngine:
    """Engine for executing schedule sequences (ErsatzTV-compatible)"""

    def __init__(self, db: Session, seed: int | None = None):
        self.db = db
        self._collection_cache: dict[str, list[MediaItem]] = {}
        self._playlist_cache: dict[str, Playlist] = {}
        self._seed = seed or random.randint(1, 1000000)
        self._random = random.Random(self._seed)
        self._shuffled_sequences: dict[str, list[dict[str, Any]]] = {}  # Cache shuffled sequences

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
                .all()
            )

            media_items = []
            for item in items:
                media_item = (
                    self.db.query(MediaItem).filter(MediaItem.id == item.media_item_id).first()
                )
                if media_item:
                    media_items.append(media_item)

            # Sort by order if available
            media_items.sort(
                key=lambda m: next((ci.order for ci in items if ci.media_item_id == m.id), 0)
            )

            self._collection_cache[collection_name] = media_items
            return media_items

        # Fallback: try to find playlist with same name
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

        # Provide helpful error message with suggestions (only log once per collection to avoid spam)
        if collection_name not in self._collection_cache:
            # Mark as checked (even though it's empty) to prevent repeated logging
            self._collection_cache[collection_name] = []

        logger.warning(f"Collection/Playlist not found: {collection_name}")

        # List available collections/playlists to help with debugging
        all_collections = self.db.query(Collection).all()
        all_playlists = self.db.query(Playlist).all()

        if all_collections or all_playlists:
            available_names = [c.name for c in all_collections] + [p.name for p in all_playlists]
            # Find similar names (case-insensitive partial match)
            similar = [
                name
                for name in available_names
                if collection_name.lower() in name.lower()
                or name.lower() in collection_name.lower()
            ]
            if similar:
                # Remove duplicates while preserving order
                seen = set()
                unique_similar = []
                for name in similar:
                    if name not in seen:
                        seen.add(name)
                        unique_similar.append(name)
                logger.info(
                    f"  Similar collections/playlists found: {', '.join(unique_similar[:5])}"
                )
            else:
                logger.info(
                    f"  Available collections/playlists ({len(available_names)} total): {', '.join(sorted(available_names)[:10])}"
                )
                if len(available_names) > 10:
                    logger.info(f"  ... and {len(available_names) - 10} more")

        return []

    def get_sequence_media(self, sequence_key: str, schedule: ParsedSchedule) -> list[MediaItem]:
        """Get media items for a sequence"""
        if sequence_key not in schedule.sequences:
            return []

        sequence_items = schedule.sequences[sequence_key]
        media_items = []

        for item in sequence_items:
            content_key = item.get("content")
            if content_key and content_key in schedule.content_map:
                collection_name = schedule.content_map[content_key]["collection"]
                items = self.get_collection_media(collection_name)

                # Handle order
                order = schedule.content_map[content_key].get("order", "chronological")
                if order == "shuffle":
                    import random

                    items = items.copy()
                    random.shuffle(items)

                media_items.extend(items)

        return media_items

    def resolve_sequence_item(
        self,
        item: dict[str, Any],
        schedule: ParsedSchedule,
        current_time: datetime,
        pre_roll_active: bool = False,
        mid_roll_active: bool = False,
        post_roll_active: bool = False,
    ) -> list[dict[str, Any]]:
        """Resolve a single sequence item to media items with metadata (ErsatzTV-compatible)"""
        resolved = []

        # Handle ErsatzTV-style advanced directives first
        if "padToNext" in item:
            # Pad to next hour/half-hour boundary (ErsatzTV feature)
            return self._handle_pad_to_next(item, schedule, current_time)

        if "padUntil" in item:
            # Pad until a specific time (ErsatzTV feature)
            return self._handle_pad_until(item, schedule, current_time)

        if "waitUntil" in item:
            # Wait until a specific time (ErsatzTV feature) - returns empty, updates time
            return self._handle_wait_until(item, current_time)

        if "skipItems" in item:
            # Skip items from a collection (ErsatzTV feature)
            return self._handle_skip_items(item, schedule)

        if "shuffleSequence" in item:
            # Shuffle a sequence (ErsatzTV feature)
            return self._handle_shuffle_sequence(item, schedule)

        # Handle pre-roll, mid-roll, post-roll flags
        if "pre_roll" in item:
            # This is a flag, not a media item
            return []

        if "mid_roll" in item:
            # This is a flag, not a media item
            return []

        if "post_roll" in item:
            # This is a flag, not a media item
            return []

        # Handle sequence reference
        if "sequence" in item:
            sequence_key = item["sequence"]
            media_items = self.get_sequence_media(sequence_key, schedule)

            for media_item in media_items:
                # Extract metadata from media_item
                metadata = self._extract_metadata_from_media_item(media_item)

                resolved.append(
                    {
                        "media_item": media_item,
                        "custom_title": item.get("custom_title"),
                        "filler_kind": item.get("filler_kind"),
                        "start_time": current_time,
                        "metadata": metadata,
                    }
                )

            return resolved

        # Handle content reference (all items from a collection)
        if "all" in item:
            content_key = item["all"]
            if content_key in schedule.content_map:
                collection_name = schedule.content_map[content_key]["collection"]
                media_items = self.get_collection_media(collection_name)

                # Handle order
                order = schedule.content_map[content_key].get("order", "chronological")
                if order == "shuffle":
                    import random

                    media_items = media_items.copy()
                    random.shuffle(media_items)

                for media_item in media_items:
                    resolved.append(
                        {
                            "media_item": media_item,
                            "custom_title": item.get("custom_title"),
                            "filler_kind": item.get("filler_kind"),
                            "start_time": current_time,
                        }
                    )

            return resolved

        # Handle duration-based filler
        if "duration" in item and "content" in item:
            content_key = item["content"]
            duration_str = item["duration"]
            duration_seconds = ScheduleParser.parse_duration(duration_str)

            if duration_seconds and content_key in schedule.content_map:
                collection_name = schedule.content_map[content_key]["collection"]
                media_items = self.get_collection_media(collection_name)

                # Handle order
                order = schedule.content_map[content_key].get("order", "shuffle")
                if order == "shuffle":
                    import random

                    media_items = media_items.copy()
                    random.shuffle(media_items)

                # Select items to fill the duration
                selected_items = []
                total_duration = 0
                discard_attempts = item.get("discard_attempts", 0)
                attempts = 0

                for media_item in media_items:
                    if total_duration >= duration_seconds:
                        break

                    item_duration = media_item.duration or 0
                    if item_duration > 0:
                        if (
                            total_duration + item_duration <= duration_seconds * 1.1
                        ):  # 10% tolerance
                            selected_items.append(media_item)
                            total_duration += item_duration
                        elif attempts < discard_attempts:
                            attempts += 1
                            continue
                        else:
                            break

                for media_item in selected_items:
                    resolved.append(
                        {
                            "media_item": media_item,
                            "custom_title": item.get("custom_title"),
                            "filler_kind": item.get("filler_kind", "Commercial"),
                            "start_time": current_time,
                        }
                    )

            return resolved

        return resolved

    def _extract_metadata_from_media_item(self, media_item) -> dict[str, Any]:
        """
        Extract metadata from a MediaItem for use in schedule items.

        Args:
            media_item: MediaItem instance

        Returns:
            Dictionary with metadata fields
        """
        if not media_item:
            return {}

        # Use getattr with defaults for attributes that may not exist on all MediaItem versions
        # MediaItem model uses: show_title (not series_title), release_date (not episode_air_date)
        metadata = {
            "title": getattr(media_item, 'title', None),
            "description": getattr(media_item, 'description', None),
            "series_title": getattr(media_item, 'series_title', None) or getattr(media_item, 'show_title', None),
            "episode_title": getattr(media_item, 'episode_title', None),
            "season_number": getattr(media_item, 'season_number', None),
            "episode_number": getattr(media_item, 'episode_number', None),
            "episode_air_date": getattr(media_item, 'episode_air_date', None) or getattr(media_item, 'release_date', None),
            "content_rating": getattr(media_item, 'content_rating', None),
            "thumbnail": getattr(media_item, 'thumbnail', None),
        }

        # Parse JSON fields
        import json

        genres = getattr(media_item, 'genres', None)
        if genres:
            try:
                metadata["genres"] = (
                    json.loads(genres)
                    if isinstance(genres, str)
                    else genres
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                metadata["genres"] = []

        actors = getattr(media_item, 'actors', None)
        if actors:
            try:
                metadata["actors"] = (
                    json.loads(actors)
                    if isinstance(actors, str)
                    else actors
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                metadata["actors"] = []

        directors = getattr(media_item, 'directors', None)
        if directors:
            try:
                metadata["directors"] = (
                    json.loads(directors)
                    if isinstance(directors, str)
                    else directors
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                metadata["directors"] = []

        guids = getattr(media_item, 'guids', None)
        if guids:
            try:
                metadata["guids"] = (
                    json.loads(guids)
                    if isinstance(guids, str)
                    else guids
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                metadata["guids"] = {}

        return metadata

    def generate_playlist_from_schedule(
        self, channel: Channel, schedule: ParsedSchedule, max_items: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Generate a playlist from a schedule (ErsatzTV-compatible approach).
        Ensures continuous playback by generating all items in sequence.
        """
        if not schedule.main_sequence_key:
            logger.warning(f"No main sequence found in schedule: {schedule.name}")
            return []

        main_sequence = schedule.sequences.get(schedule.main_sequence_key, [])
        if not main_sequence:
            logger.warning(f"Main sequence {schedule.main_sequence_key} is empty")
            return []

        # Track state for repeat
        repeat = any(p.get("repeat") for p in schedule.playout)

        # Generate base playlist (will be repeated if needed)
        base_playlist_items = self._generate_sequence_playlist(
            main_sequence,
            schedule,
            max_items=None,  # Generate full sequence first
        )

        if not base_playlist_items:
            logger.warning(f"No items generated from sequence: {schedule.main_sequence_key}")
            # Provide helpful debugging info
            if schedule.main_sequence_key in schedule.sequences:
                sequence_items = schedule.sequences[schedule.main_sequence_key]
                logger.info(f"  Sequence has {len(sequence_items)} items defined")
                # Check if content keys exist
                for item in sequence_items:
                    content_key = item.get("content") or item.get("all")
                    if content_key:
                        if content_key in schedule.content_map:
                            collection_name = schedule.content_map[content_key].get("collection")
                            media_count = len(self.get_collection_media(collection_name))
                            logger.info(
                                f"  Content key '{content_key}' -> collection '{collection_name}': {media_count} items"
                            )
                        else:
                            logger.warning(
                                f"  Content key '{content_key}' not found in content_map"
                            )
            return []

        # Handle repeat logic (ErsatzTV-style)
        if repeat and max_items:
            # Repeat the sequence until we reach max_items
            playlist_items = []
            while len(playlist_items) < max_items:
                for item in base_playlist_items:
                    playlist_items.append(item)
                    if len(playlist_items) >= max_items:
                        break
                if len(playlist_items) >= max_items:
                    break
        elif max_items:
            # Just take first max_items
            playlist_items = base_playlist_items[:max_items]
        else:
            playlist_items = base_playlist_items

        logger.info(
            f"Generated {len(playlist_items)} items from schedule: {schedule.name} (repeat={repeat})"
        )

        return playlist_items

    def _generate_sequence_playlist(
        self, sequence: list[dict[str, Any]], schedule: ParsedSchedule, max_items: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Generate playlist items from a sequence (ErsatzTV-style processing).
        Handles pre-roll, mid-roll, post-roll, and content items in order.
        """
        playlist_items = []
        pre_roll_sequence = None
        mid_roll_sequence = None
        post_roll_sequence = None
        current_time = datetime.utcnow()

        # Process sequence items in order (ErsatzTV processes sequentially)
        for item in sequence:
            # Handle waitUntil directive (ErsatzTV feature) - updates current_time
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
                                elif item.get("rewindOnReset", False):
                                    pass  # Keep today's time

                            current_time = target_time
                            logger.debug(f"WaitUntil: Updated current_time to {current_time}")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Invalid waitUntil time format: {wait_until_str} - {e}")
                continue

            # Handle pre-roll, mid-roll, post-roll sequence references (ErsatzTV-style flags)
            if "pre_roll" in item:
                if item["pre_roll"] and "sequence" in item:
                    pre_roll_sequence = item["sequence"]
                    logger.debug(f"Pre-roll sequence activated: {pre_roll_sequence}")
                elif not item["pre_roll"]:
                    pre_roll_sequence = None
                    logger.debug("Pre-roll sequence deactivated")
                continue

            if "mid_roll" in item:
                if item["mid_roll"] and "sequence" in item:
                    mid_roll_sequence = item["sequence"]
                    logger.debug(f"Mid-roll sequence activated: {mid_roll_sequence}")
                elif not item["mid_roll"]:
                    mid_roll_sequence = None
                    logger.debug("Mid-roll sequence deactivated")
                continue

            if "post_roll" in item:
                if item["post_roll"] and "sequence" in item:
                    post_roll_sequence = item["sequence"]
                    logger.debug(f"Post-roll sequence activated: {post_roll_sequence}")
                elif not item["post_roll"]:
                    post_roll_sequence = None
                    logger.debug("Post-roll sequence deactivated")
                continue

            # Add pre-roll items if active (before main content)
            if pre_roll_sequence:
                pre_roll_resolved = self._resolve_sequence_reference(
                    pre_roll_sequence, schedule, current_time
                )
                for resolved_item in pre_roll_resolved:
                    playlist_items.append(resolved_item)
                    # Update current_time for next item
                    media_item = resolved_item["media_item"]
                    if media_item and media_item.duration:
                        current_time += timedelta(seconds=media_item.duration)
                    if max_items and len(playlist_items) >= max_items:
                        break
                if max_items and len(playlist_items) >= max_items:
                    break

            # Resolve main content item to media items (ErsatzTV processes all items)
            resolved = self.resolve_sequence_item(
                item,
                schedule,
                current_time,
                pre_roll_sequence is not None,
                mid_roll_sequence is not None,
                post_roll_sequence is not None,
            )

            # Add resolved items sequentially (ErsatzTV ensures continuous playback)
            for i, resolved_item in enumerate(resolved):
                playlist_items.append(resolved_item)

                # Update current_time for next item
                media_item = resolved_item["media_item"]
                if media_item and media_item.duration:
                    current_time += timedelta(seconds=media_item.duration)

                # Add mid-roll after first item if active (ErsatzTV inserts mid-roll between content)
                if mid_roll_sequence and i == 0 and len(resolved) > 1:
                    mid_roll_resolved = self._resolve_sequence_reference(
                        mid_roll_sequence, schedule, current_time
                    )
                    for mid_item in mid_roll_resolved[:1]:  # Add one mid-roll item
                        playlist_items.append(mid_item)
                        mid_media = mid_item["media_item"]
                        if mid_media and mid_media.duration:
                            current_time += timedelta(seconds=mid_media.duration)
                        if max_items and len(playlist_items) >= max_items:
                            break

                if max_items and len(playlist_items) >= max_items:
                    break

            if max_items and len(playlist_items) >= max_items:
                break

            # Add post-roll items if active (after main content)
            if post_roll_sequence:
                post_roll_resolved = self._resolve_sequence_reference(
                    post_roll_sequence, schedule, current_time
                )
                for resolved_item in post_roll_resolved:
                    playlist_items.append(resolved_item)
                    media_item = resolved_item["media_item"]
                    if media_item and media_item.duration:
                        current_time += timedelta(seconds=media_item.duration)
                    if max_items and len(playlist_items) >= max_items:
                        break
                if max_items and len(playlist_items) >= max_items:
                    break

        return playlist_items

    def _resolve_sequence_reference(
        self, sequence_key: str, schedule: ParsedSchedule, current_time: datetime
    ) -> list[dict[str, Any]]:
        """Resolve a sequence reference to playlist items (ErsatzTV-style)"""
        if sequence_key not in schedule.sequences:
            logger.warning(f"Sequence not found: {sequence_key}")
            return []

        sequence = schedule.sequences[sequence_key]
        resolved_items = []

        for item in sequence:
            item_resolved = self.resolve_sequence_item(
                item, schedule, current_time, False, False, False
            )
            resolved_items.extend(item_resolved)

            # Update current_time
            for resolved_item in item_resolved:
                media_item = resolved_item["media_item"]
                if media_item and media_item.duration:
                    current_time += timedelta(seconds=media_item.duration)

        return resolved_items

    def _handle_pad_to_next(
        self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime
    ) -> list[dict[str, Any]]:
        """Handle padToNext directive - pad to next hour/half-hour boundary (ErsatzTV feature)"""
        pad_to_next = item.get("padToNext", 60)  # Default to 60 minutes (hour)
        content_key = item.get("content")
        fallback_key = item.get("fallback")

        # Calculate target time (next boundary)
        current_minute = current_time.minute
        target_minute = ((current_minute + pad_to_next - 1) // pad_to_next) * pad_to_next

        # Create target time at the boundary
        target_time = current_time.replace(minute=0, second=0, microsecond=0)
        target_time += timedelta(minutes=target_minute)

        # Ensure target is in the future
        if target_time <= current_time:
            target_time += timedelta(minutes=pad_to_next)

        # Calculate duration to fill
        duration_seconds = int((target_time - current_time).total_seconds())

        if duration_seconds <= 0:
            return []

        # Use duration-based filler logic
        filler_item = {
            "duration": f"00:{duration_seconds // 60:02d}:{duration_seconds % 60:02d}",
            "content": content_key or fallback_key,
            "filler_kind": item.get("filler_kind", "Commercial"),
            "trim": item.get("trim", True),
            "discard_attempts": item.get("discard_attempts", 3),
        }

        return self.resolve_sequence_item(filler_item, schedule, current_time, False, False, False)

    def _handle_pad_until(
        self, item: dict[str, Any], schedule: ParsedSchedule, current_time: datetime
    ) -> list[dict[str, Any]]:
        """Handle padUntil directive - pad until a specific time (ErsatzTV feature)"""
        pad_until_str = item.get("padUntil")
        if not pad_until_str:
            return []

        try:
            # Parse time (HH:MM or HH:MM:SS format)
            time_parts = pad_until_str.split(":")
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0

                # Create target time (today or tomorrow if time has passed)
                target_time = current_time.replace(
                    hour=hour, minute=minute, second=second, microsecond=0
                )
                if target_time <= current_time:
                    target_time += timedelta(days=1)

                # Calculate duration to fill
                duration_seconds = int((target_time - current_time).total_seconds())

                if duration_seconds <= 0:
                    return []

                content_key = item.get("content") or item.get("fallback")
                if not content_key:
                    return []

                # Use duration-based filler logic
                filler_item = {
                    "duration": f"00:{duration_seconds // 60:02d}:{duration_seconds % 60:02d}",
                    "content": content_key,
                    "filler_kind": item.get("filler_kind", "Commercial"),
                    "trim": item.get("trim", True),
                    "discard_attempts": item.get("discard_attempts", 3),
                }

                return self.resolve_sequence_item(
                    filler_item, schedule, current_time, False, False, False
                )
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid padUntil time format: {pad_until_str} - {e}")
            return []

    def _handle_wait_until(
        self, item: dict[str, Any], current_time: datetime
    ) -> list[dict[str, Any]]:
        """Handle waitUntil directive - wait until a specific time (ErsatzTV feature)"""
        # This doesn't return media items, but updates the current_time
        # The time update is handled in the calling code
        wait_until_str = item.get("waitUntil")
        if not wait_until_str:
            return []

        try:
            # Parse time (HH:MM or HH:MM:SS format)
            time_parts = wait_until_str.split(":")
            if len(time_parts) >= 2:
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                second = int(time_parts[2]) if len(time_parts) > 2 else 0

                # Create target time (today or tomorrow if time has passed)
                target_time = current_time.replace(
                    hour=hour, minute=minute, second=second, microsecond=0
                )
                if target_time <= current_time:
                    if item.get("tomorrow", False):
                        target_time += timedelta(days=1)
                    elif item.get("rewindOnReset", False):
                        # Keep today's time
                        pass

                # Update current_time (this will be handled by the caller)
                # For now, return empty - the caller should update time
                return []
        except (ValueError, IndexError) as e:
            logger.warning(f"Invalid waitUntil time format: {wait_until_str} - {e}")
            return []

    def _handle_skip_items(
        self, item: dict[str, Any], schedule: ParsedSchedule
    ) -> list[dict[str, Any]]:
        """Handle skipItems directive - skip items from a collection (ErsatzTV feature)"""
        # This modifies the collection cache to skip items
        # Returns empty as it's a state change, not media items
        content_key = item.get("content")
        skip_items_expr = item.get("skipItems", "0")

        if not content_key or content_key not in schedule.content_map:
            return []

        collection_name = schedule.content_map[content_key]["collection"]

        # Evaluate skip expression (simple integer or expression like "count/2")
        try:
            # Simple integer
            skip_count = int(skip_items_expr)
        except ValueError:
            # Try to evaluate as expression
            try:
                # Simple expressions like "count/2" or "random"
                if "count" in skip_items_expr.lower():
                    media_items = self.get_collection_media(collection_name)
                    count = len(media_items)
                    # Evaluate simple division like "count/2"
                    if "/" in skip_items_expr:
                        parts = skip_items_expr.split("/")
                        if len(parts) == 2:
                            divisor = int(parts[1].strip())
                            skip_count = count // divisor
                        else:
                            skip_count = 0
                    else:
                        skip_count = count
                elif "random" in skip_items_expr.lower():
                    media_items = self.get_collection_media(collection_name)
                    skip_count = self._random.randint(0, len(media_items) - 1) if media_items else 0
                else:
                    skip_count = 0
            except (ValueError, TypeError, AttributeError):
                skip_count = 0

        # Skip items by modifying cache (remove first N items)
        if collection_name in self._collection_cache:
            media_items = self._collection_cache[collection_name]
            skip_count = min(skip_count, len(media_items))
            self._collection_cache[collection_name] = media_items[skip_count:]
            logger.debug(f"Skipped {skip_count} items from collection: {collection_name}")

        return []

    def _handle_shuffle_sequence(
        self, item: dict[str, Any], schedule: ParsedSchedule
    ) -> list[dict[str, Any]]:
        """Handle shuffleSequence directive - shuffle a sequence (ErsatzTV feature)"""
        sequence_key = item.get("shuffleSequence")
        if not sequence_key or sequence_key not in schedule.sequences:
            return []

        # Shuffle the sequence items
        sequence = schedule.sequences[sequence_key].copy()

        # Use seeded random for consistency
        self._random.shuffle(sequence)

        # Update the sequence in the schedule
        schedule.sequences[sequence_key] = sequence

        logger.debug(f"Shuffled sequence: {sequence_key}")
        return []
