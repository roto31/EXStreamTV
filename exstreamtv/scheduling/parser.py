"""Schedule YAML file parser"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class ParsedSchedule:
    """Parsed schedule data structure (ErsatzTV-compatible)"""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.content_map: dict[str, dict[str, Any]] = {}  # key -> content definition
        self.sequences: dict[str, list[dict[str, Any]]] = {}  # sequence_key -> items
        self.playout: list[dict[str, Any]] = []  # playout instructions
        self.main_sequence_key: str | None = None
        self.imports: list[str] = []  # Import other YAML files (ErsatzTV feature)
        self.reset: list[dict[str, Any]] = []  # Reset instructions (ErsatzTV feature)


class ScheduleParser:
    """Parser for schedule YAML files"""

    @staticmethod
    def parse_duration(duration_str: str) -> int | None:
        """Parse duration string (HH:MM:SS or MM:SS) to seconds"""
        if not duration_str:
            return None

        try:
            # Handle ISO 8601 format (PT3M44S) if needed
            if duration_str.startswith("PT"):
                duration_str = duration_str.replace("PT", "")
                total_seconds = 0

                hours_match = re.search(r"(\d+)H", duration_str)
                if hours_match:
                    total_seconds += int(hours_match.group(1)) * 3600

                minutes_match = re.search(r"(\d+)M", duration_str)
                if minutes_match:
                    total_seconds += int(minutes_match.group(1)) * 60

                seconds_match = re.search(r"(\d+)S", duration_str)
                if seconds_match:
                    total_seconds += int(seconds_match.group(1))

                return total_seconds if total_seconds > 0 else None
            else:
                # Handle HH:MM:SS or MM:SS format
                parts = duration_str.split(":")
                if len(parts) == 3:  # HH:MM:SS
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds
                elif len(parts) == 2:  # MM:SS
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds
                else:
                    return None
        except (ValueError, AttributeError):
            logger.warning(f"Could not parse duration: {duration_str}")
            return None

    @staticmethod
    def parse_file(
        file_path: Path, base_dir: Path | None = None, validate: bool = True
    ) -> ParsedSchedule:
        """
        Parse a schedule YAML file (ErsatzTV-compatible with import support)

        Args:
            file_path: Path to schedule file
            base_dir: Base directory for resolving imports
            validate: Whether to validate the file before parsing (default: True)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Schedule file not found: {file_path}")

        # Validate before parsing if requested
        if validate:
            try:
                # Try to get live validator from app state if available (avoids circular imports)
                validator = None
                try:
                    import sys

                    if "streamtv.main" in sys.modules:
                        from exstreamtv.main import app

                        if hasattr(app, "state") and hasattr(app.state, "live_validator"):
                            validator = app.state.live_validator
                except (ImportError, AttributeError):
                    pass

                # Fallback: try to get from validation module directly
                if not validator:
                    try:
                        from ..api.validation import _live_validator

                        validator = _live_validator
                    except (ImportError, AttributeError):
                        pass
                if validator:
                    result = validator.validate_file(file_path, force=False)
                    if not result.valid:
                        error_msg = (
                            f"Schedule file validation failed: {file_path.name}\n"
                            + "\n".join(f"  - {e}" for e in result.errors[:5])
                        )
                        if len(result.errors) > 5:
                            error_msg += f"\n  ... and {len(result.errors) - 5} more errors"
                        logger.warning(error_msg)
                        # Don't raise - allow parsing to continue but log the warning
                        # This ensures streams don't break due to validation errors
                else:
                    # Fallback to basic validator if live validator not available
                    from ..validation import YAMLValidator

                    try:
                        basic_validator = YAMLValidator()
                        basic_validator.validate_schedule_file(file_path)
                    except Exception as e:
                        logger.warning(f"Schedule validation warning (non-blocking): {e}")
            except Exception as e:
                # Don't break parsing on validation errors
                logger.warning(f"Validation check failed (non-blocking): {e}")

        if base_dir is None:
            base_dir = file_path.parent

        with open(file_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty or invalid YAML file: {file_path}")

        name = data.get("name", "Unknown Schedule")
        description = data.get("description", "")

        schedule = ParsedSchedule(name, description)

        # Parse imports (ErsatzTV feature)
        imports = data.get("import", [])
        if isinstance(imports, list):
            schedule.imports = imports
        elif isinstance(imports, str):
            schedule.imports = [imports]

        # Process imports first (ErsatzTV merges imported content)
        for import_path in schedule.imports:
            try:
                # Resolve import path (relative to current file or absolute)
                if not Path(import_path).is_absolute():
                    import_file = base_dir / import_path
                else:
                    import_file = Path(import_path)

                if import_file.exists():
                    imported_schedule = ScheduleParser.parse_file(import_file, base_dir)
                    # Merge imported content (only if not already present)
                    for key, content_def in imported_schedule.content_map.items():
                        if key not in schedule.content_map:
                            schedule.content_map[key] = content_def
                    # Merge imported sequences (only if not already present)
                    for key, sequence_items in imported_schedule.sequences.items():
                        if key not in schedule.sequences:
                            schedule.sequences[key] = sequence_items
                    logger.info(
                        f"Imported {len(imported_schedule.content_map)} content items and {len(imported_schedule.sequences)} sequences from {import_path}"
                    )
                else:
                    logger.warning(f"Import file not found: {import_path}")
            except Exception as e:
                logger.warning(f"Failed to import {import_path}: {e}")

        # Parse content definitions
        content_list = data.get("content", [])
        for content_def in content_list:
            key = content_def.get("key")
            if key:
                schedule.content_map[key] = {
                    "collection": content_def.get("collection"),
                    "order": content_def.get("order", "chronological"),
                }

        # Parse sequences
        sequence_list = data.get("sequence", [])
        for seq_def in sequence_list:
            key = seq_def.get("key")
            if key:
                schedule.sequences[key] = seq_def.get("items", [])

        # Parse reset instructions (ErsatzTV feature)
        reset_list = data.get("reset", [])
        if reset_list:
            schedule.reset = reset_list

        # Parse playout instructions
        playout_list = data.get("playout", [])
        for playout_item in playout_list:
            if "sequence" in playout_item:
                schedule.main_sequence_key = playout_item["sequence"]
            schedule.playout.append(playout_item)

        logger.info(
            f"Parsed schedule: {name} with {len(schedule.content_map)} content items, {len(schedule.sequences)} sequences, and {len(schedule.playout)} playout instructions"
        )

        return schedule

    @staticmethod
    def find_schedule_file(channel_number: str) -> Path | None:
        """Find schedule file for a channel number"""
        schedules_dir = Path(__file__).parent.parent.parent / "schedules"

        # Try to find matching schedule file
        possible_names = [
            f"mn-olympics-{channel_number}.yml",
            f"mn-olympics-{channel_number}.yaml",
            f"{channel_number}.yml",
            f"{channel_number}.yaml",
        ]

        for name in possible_names:
            file_path = schedules_dir / name
            if file_path.exists():
                return file_path

        return None
