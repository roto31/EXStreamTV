"""YAML file validation using JSON schemas"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from jsonschema import ValidationError as JSONSchemaValidationError

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom validation error with detailed message"""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(self.message)


class YAMLValidator:
    """Validate YAML files against JSON schemas"""

    def __init__(self):
        self.schemas = {}
        self._load_schemas()

    def _load_schemas(self):
        """Load JSON schemas from schemas directory"""
        schemas_dir = Path(__file__).parent.parent.parent / "schemas"

        if not schemas_dir.exists():
            logger.warning(f"Schemas directory not found: {schemas_dir}")
            return

        # Load channel schema
        channel_schema_path = schemas_dir / "channel.schema.json"
        if channel_schema_path.exists():
            with open(channel_schema_path) as f:
                self.schemas["channel"] = json.load(f)
            logger.info("Loaded channel schema")

        # Load schedule schema
        schedule_schema_path = schemas_dir / "schedule.schema.json"
        if schedule_schema_path.exists():
            with open(schedule_schema_path) as f:
                self.schemas["schedule"] = json.load(f)
            logger.info("Loaded schedule schema")

    def validate_channel_file(self, file_path: Path) -> dict[str, Any]:
        """
        Validate a channel YAML file

        Returns:
            Dict with 'valid' (bool) and 'errors' (list) keys

        Raises:
            ValidationError: If validation fails
        """
        if "channel" not in self.schemas:
            raise ValidationError("Channel schema not loaded")

        return self._validate_file(file_path, self.schemas["channel"], "channel")

    def validate_schedule_file(self, file_path: Path) -> dict[str, Any]:
        """
        Validate a schedule YAML file

        Returns:
            Dict with 'valid' (bool) and 'errors' (list) keys

        Raises:
            ValidationError: If validation fails
        """
        if "schedule" not in self.schemas:
            raise ValidationError("Schedule schema not loaded")

        return self._validate_file(file_path, self.schemas["schedule"], "schedule")

    def _validate_file(
        self, file_path: Path, schema: dict[str, Any], schema_type: str
    ) -> dict[str, Any]:
        """Validate a YAML file against a schema"""
        if not file_path.exists():
            raise ValidationError(f"File not found: {file_path}")

        try:
            # Load and parse YAML
            with open(file_path) as f:
                yaml_data = yaml.safe_load(f)

            if yaml_data is None:
                raise ValidationError(f"Empty or invalid YAML file: {file_path}")

            # Convert Python date objects to strings for validation (YAML parser converts dates)
            yaml_data = self._normalize_data(yaml_data)

            # Validate against schema
            errors = []
            validator = Draft7Validator(schema)

            for error in validator.iter_errors(yaml_data):
                error_path = " -> ".join(str(p) for p in error.path)
                error_msg = f"{error_path}: {error.message}"
                # Add more context for pattern validation errors
                if "pattern" in error.message.lower() or "did not match" in error.message.lower():
                    # Include the actual value that failed
                    if error.instance is not None:
                        error_msg = f"{error_path}: {error.message} (value: '{error.instance}')"
                errors.append(error_msg)
                logger.debug(f"Validation error: {error_msg}")

            if errors:
                error_message = (
                    f"Validation failed for {file_path.name} ({schema_type}):\n"
                    + "\n".join(f"  - {e}" for e in errors)
                )
                raise ValidationError(error_message, errors)

            logger.info(f"✓ Validated {file_path.name} ({schema_type})")
            return {"valid": True, "errors": [], "data": yaml_data}

        except yaml.YAMLError as e:
            raise ValidationError(f"YAML parsing error in {file_path.name}: {e!s}")
        except JSONSchemaValidationError as e:
            raise ValidationError(f"Schema validation error in {file_path.name}: {e!s}")
        except Exception as e:
            raise ValidationError(f"Unexpected error validating {file_path.name}: {e!s}")

    def _normalize_data(self, data: Any) -> Any:
        """Normalize YAML data for JSON schema validation (convert dates, etc.)"""
        from datetime import date, datetime

        if isinstance(data, dict):
            normalized = {}
            for k, v in data.items():
                # Skip empty strings for optional fields to avoid pattern validation errors
                if v == "" or v is None:
                    # Don't include empty/null values in normalized data for optional fields
                    # This prevents pattern validation on empty strings
                    continue
                # Special handling for broadcast_date - normalize to YYYY-MM-DD format
                if k == "broadcast_date" and isinstance(v, str):
                    normalized[k] = self._normalize_date_string(v)
                else:
                    normalized[k] = self._normalize_data(v)
            return normalized
        elif isinstance(data, list):
            return [self._normalize_data(item) for item in data]
        elif isinstance(data, (date, datetime)):
            # Convert date/datetime to ISO format string (YYYY-MM-DD)
            return data.isoformat()[:10]  # Take only date part, not time
        else:
            return data

    def _normalize_date_string(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format"""
        if not date_str:
            return date_str

        # Try to parse various date formats and convert to YYYY-MM-DD
        from datetime import datetime

        # Common date formats
        date_formats = [
            "%Y-%m-%d",  # Already correct
            "%Y-%m-%dT%H:%M:%S",  # ISO with time
            "%Y-%m-%dT%H:%M:%S.%f",  # ISO with microseconds
            "%Y-%m-%dT%H:%M:%SZ",  # ISO with Z
            "%Y/%m/%d",  # Slash format
            "%m/%d/%Y",  # US format
            "%d/%m/%Y",  # European format
        ]

        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        # If no format matches, try to extract YYYY-MM-DD pattern
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_str)
        if match:
            return match.group(0)

        # If still no match, return as-is (validation will catch it)
        return date_str

    def validate_channel_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate channel data (already parsed YAML)"""
        if "channel" not in self.schemas:
            raise ValidationError("Channel schema not loaded")

        errors = []
        validator = Draft7Validator(self.schemas["channel"])

        for error in validator.iter_errors(data):
            error_path = " -> ".join(str(p) for p in error.path)
            errors.append(f"{error_path}: {error.message}")

        if errors:
            raise ValidationError("Channel data validation failed", errors)

        return {"valid": True, "errors": []}

    def validate_schedule_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate schedule data (already parsed YAML)"""
        if "schedule" not in self.schemas:
            raise ValidationError("Schedule schema not loaded")

        errors = []
        validator = Draft7Validator(self.schemas["schedule"])

        for error in validator.iter_errors(data):
            error_path = " -> ".join(str(p) for p in error.path)
            errors.append(f"{error_path}: {error.message}")

        if errors:
            raise ValidationError("Schedule data validation failed", errors)

        return {"valid": True, "errors": []}
