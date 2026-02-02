"""YAML to JSON converter for API endpoints"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def yaml_to_json(file_path: Path) -> dict[str, Any]:
    """
    Convert YAML file to JSON-compatible dictionary

    Args:
        file_path: Path to YAML file

    Returns:
        Dictionary representation of YAML data

    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML parsing fails
    """
    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")

    with open(file_path) as f:
        yaml_data = yaml.safe_load(f)

    if yaml_data is None:
        return {}

    return yaml_data


def yaml_string_to_json(yaml_string: str) -> dict[str, Any]:
    """
    Convert YAML string to JSON-compatible dictionary

    Args:
        yaml_string: YAML content as string

    Returns:
        Dictionary representation of YAML data

    Raises:
        yaml.YAMLError: If YAML parsing fails
    """
    yaml_data = yaml.safe_load(yaml_string)

    if yaml_data is None:
        return {}

    return yaml_data


def json_to_yaml(data: dict[str, Any], file_path: Path | None = None) -> str:
    """
    Convert JSON-compatible dictionary to YAML string

    Args:
        data: Dictionary to convert
        file_path: Optional path to write YAML file

    Returns:
        YAML string representation

    Raises:
        IOError: If file write fails
    """
    yaml_string = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    if file_path:
        with open(file_path, "w") as f:
            f.write(yaml_string)
        logger.info(f"Converted JSON to YAML and saved to {file_path}")

    return yaml_string
