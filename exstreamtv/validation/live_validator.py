"""Live YAML validation with caching and fix suggestions"""

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .validator import ValidationError, YAMLValidator
from .yaml_watcher import YAMLWatcher

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a validation"""

    def __init__(
        self,
        file_path: Path,
        valid: bool,
        errors: list[str],
        validated_at: datetime,
        suggestions: list[str] | None = None,
    ):
        self.file_path = file_path
        self.valid = valid
        self.errors = errors
        self.validated_at = validated_at
        self.suggestions = suggestions or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "file_path": str(self.file_path),
            "valid": self.valid,
            "errors": self.errors,
            "validated_at": self.validated_at.isoformat(),
            "suggestions": self.suggestions,
        }


class LiveValidator:
    """Continuous YAML validation with caching"""

    def __init__(self, watch_directories: list[Path], cache_ttl_seconds: int = 300):
        """
        Initialize live validator

        Args:
            watch_directories: Directories to watch for YAML files
            cache_ttl_seconds: Cache TTL in seconds (default 5 minutes)
        """
        self.watch_directories = [Path(d) for d in watch_directories]
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.validator = YAMLValidator()
        self.cache: dict[str, ValidationResult] = {}
        self._lock = threading.Lock()
        self.watcher: YAMLWatcher | None = None
        self._validation_callbacks: list[Callable[[ValidationResult], None]] = []

    def _get_file_type(self, file_path: Path) -> str | None:
        """Determine file type (channel or schedule)"""
        file_str = str(file_path).lower()

        # Check if it's a channel file
        if "channel" in file_str or file_path.name.startswith("channel-"):
            return "channel"

        # Check if it's a schedule file
        if "schedule" in file_str or "schedules" in str(file_path.parent).lower():
            return "schedule"

        # Try to infer from directory structure
        parent_str = str(file_path.parent).lower()
        if "schedules" in parent_str:
            return "schedule"
        if "channels" in parent_str or "data" in parent_str:
            return "channel"

        return None

    def _suggest_fixes(self, file_path: Path, errors: list[str]) -> list[str]:
        """Suggest fixes for common YAML errors"""
        suggestions = []

        for error in errors:
            error_lower = error.lower()

            # Date format issues
            if "date" in error_lower and ("pattern" in error_lower or "format" in error_lower):
                suggestions.append(
                    "Fix date format: Use YYYY-MM-DD format (e.g., 1980-01-15) instead of other formats"
                )

            # Duration format issues
            if "duration" in error_lower and ("pattern" in error_lower or "format" in error_lower):
                suggestions.append(
                    "Fix duration format: Use HH:MM:SS format (e.g., 00:30:00) or ISO 8601 (PT30M)"
                )

            # URL format issues
            if "url" in error_lower and ("pattern" in error_lower or "uri" in error_lower):
                suggestions.append(
                    "Fix URL format: Ensure URL starts with http:// or https:// and is properly formatted"
                )

            # Required field missing
            if "required" in error_lower or "missing" in error_lower:
                field_match = None
                for field in ["number", "name", "key", "collection", "sequence", "playout"]:
                    if field in error_lower:
                        field_match = field
                        break

                if field_match:
                    suggestions.append(
                        f"Add missing required field: '{field_match}' is required but not present"
                    )

            # Enum value issues
            if "enum" in error_lower or "not one of" in error_lower:
                suggestions.append(
                    "Fix enum value: Check that the value matches one of the allowed options"
                )

            # Type mismatch
            if "type" in error_lower and ("expected" in error_lower or "got" in error_lower):
                suggestions.append(
                    "Fix type mismatch: Ensure the value matches the expected data type (string, number, boolean, etc.)"
                )

        return suggestions

    def validate_file(self, file_path: Path, force: bool = False) -> ValidationResult:
        """
        Validate a YAML file

        Args:
            file_path: Path to YAML file
            force: Force re-validation even if cached

        Returns:
            ValidationResult
        """
        file_str = str(file_path)
        now = datetime.now()

        # Check cache
        if not force and file_str in self.cache:
            cached_result = self.cache[file_str]
            if now - cached_result.validated_at < self.cache_ttl:
                logger.debug(f"Using cached validation result for {file_path.name}")
                return cached_result

        # Determine file type
        file_type = self._get_file_type(file_path)

        if not file_type:
            logger.warning(f"Could not determine file type for {file_path}")
            result = ValidationResult(
                file_path=file_path,
                valid=False,
                errors=[f"Unknown file type: {file_path}"],
                validated_at=now,
                suggestions=[
                    "Ensure file is in a 'schedules' or 'channels' directory, or has 'channel' or 'schedule' in its name"
                ],
            )
        else:
            # Validate based on type
            try:
                if file_type == "channel":
                    validation_result = self.validator.validate_channel_file(file_path)
                else:  # schedule
                    validation_result = self.validator.validate_schedule_file(file_path)

                errors = validation_result.get("errors", [])
                suggestions = self._suggest_fixes(file_path, errors) if errors else []

                result = ValidationResult(
                    file_path=file_path,
                    valid=validation_result.get("valid", False),
                    errors=errors,
                    validated_at=now,
                    suggestions=suggestions,
                )

            except ValidationError as e:
                errors = e.errors if hasattr(e, "errors") else [str(e)]
                suggestions = self._suggest_fixes(file_path, errors)

                result = ValidationResult(
                    file_path=file_path,
                    valid=False,
                    errors=errors,
                    validated_at=now,
                    suggestions=suggestions,
                )
            except Exception as e:
                logger.error(f"Unexpected error validating {file_path}: {e}", exc_info=True)
                result = ValidationResult(
                    file_path=file_path,
                    valid=False,
                    errors=[f"Unexpected error: {e!s}"],
                    validated_at=now,
                    suggestions=["Check file syntax and ensure it's valid YAML"],
                )

        # Update cache
        with self._lock:
            self.cache[file_str] = result

        # Notify callbacks
        for callback in self._validation_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.error(f"Error in validation callback: {e}", exc_info=True)

        return result

    def _on_file_changed(self, file_path: Path, event_type: str):
        """Handle file change event"""
        logger.info(f"File {event_type}: {file_path}")

        if event_type == "deleted":
            # Remove from cache
            with self._lock:
                self.cache.pop(str(file_path), None)
            return

        # Validate the file
        self.validate_file(file_path, force=True)

    def start_watching(self):
        """Start watching for file changes"""
        if self.watcher and self.watcher.is_running():
            logger.warning("Watcher already running")
            return

        self.watcher = YAMLWatcher(
            watch_directories=self.watch_directories, callback=self._on_file_changed
        )
        self.watcher.start()
        logger.info("Live validator started watching")

    def stop_watching(self):
        """Stop watching for file changes"""
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
            logger.info("Live validator stopped watching")

    def add_validation_callback(self, callback: Callable[[ValidationResult], None]):
        """Add callback for validation events"""
        self._validation_callbacks.append(callback)

    def remove_validation_callback(self, callback: Callable[[ValidationResult], None]):
        """Remove validation callback"""
        if callback in self._validation_callbacks:
            self._validation_callbacks.remove(callback)

    def get_validation_result(self, file_path: Path) -> ValidationResult | None:
        """Get cached validation result"""
        return self.cache.get(str(file_path))

    def get_all_results(self) -> dict[str, ValidationResult]:
        """Get all cached validation results"""
        with self._lock:
            return self.cache.copy()

    def clear_cache(self):
        """Clear validation cache"""
        with self._lock:
            self.cache.clear()
        logger.info("Validation cache cleared")

    def validate_all_files(self) -> dict[str, ValidationResult]:
        """Validate all YAML files in watch directories"""
        results = {}

        for directory in self.watch_directories:
            if not directory.exists():
                logger.warning(f"Directory does not exist: {directory}")
                continue

            # Find all YAML files
            for yaml_file in directory.rglob("*.yml"):
                try:
                    result = self.validate_file(yaml_file)
                    results[str(yaml_file)] = result
                except Exception as e:
                    logger.error(f"Error validating {yaml_file}: {e}", exc_info=True)

            for yaml_file in directory.rglob("*.yaml"):
                try:
                    result = self.validate_file(yaml_file)
                    results[str(yaml_file)] = result
                except Exception as e:
                    logger.error(f"Error validating {yaml_file}: {e}", exc_info=True)

        return results
