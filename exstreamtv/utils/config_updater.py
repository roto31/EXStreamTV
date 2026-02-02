"""Utility for updating configuration at runtime"""

import logging
from pathlib import Path
from typing import Any

import yaml

from ..config import config

logger = logging.getLogger(__name__)


class ConfigUpdater:
    """Update configuration without full restart"""

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path("config.yaml")
        self.config_path = config_path

    def update_m3u_config(
        self,
        enabled: bool | None = None,
        enable_library: bool | None = None,
        enable_testing: bool | None = None,
        testing_interval_hours: int | None = None,
    ) -> None:
        """
        Update M3U module configuration.

        Args:
            enabled: Enable/disable M3U module
            enable_library: Enable/disable stream library
            enable_testing: Enable/disable testing service
            testing_interval_hours: Testing interval in hours
        """
        # Read existing config
        if self.config_path.exists():
            with open(self.config_path) as f:
                config_data = yaml.safe_load(f) or {}
        else:
            config_data = {}

        # Initialize m3u section if needed
        if "m3u" not in config_data:
            config_data["m3u"] = {}

        # Update values
        if enabled is not None:
            config_data["m3u"]["enabled"] = enabled
        if enable_library is not None:
            config_data["m3u"]["enable_library"] = enable_library
        if enable_testing is not None:
            config_data["m3u"]["enable_testing_service"] = enable_testing
        if testing_interval_hours is not None:
            config_data["m3u"]["testing_interval_hours"] = testing_interval_hours

        # Write back to file
        self.write_config(config_data)

        # Update in-memory config (will take effect after restart)
        if enabled is not None:
            config.m3u.enabled = enabled
        if enable_library is not None:
            config.m3u.enable_library = enable_library
        if enable_testing is not None:
            config.m3u.enable_testing_service = enable_testing
        if testing_interval_hours is not None:
            config.m3u.testing_interval_hours = testing_interval_hours

    def write_config(self, config_data: dict[str, Any]) -> None:
        """
        Write configuration to file.

        Args:
            config_data: Configuration dictionary
        """
        # Validate config before writing
        self.validate_config(config_data)

        # Write to file
        with open(self.config_path, "w") as f:
            yaml.safe_dump(
                config_data, f, sort_keys=False, default_flow_style=False, allow_unicode=True
            )

        logger.info(f"Configuration updated: {self.config_path}")

    def validate_config(self, config_data: dict[str, Any]) -> None:
        """
        Validate configuration before writing.

        Args:
            config_data: Configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Basic validation
        if not isinstance(config_data, dict):
            raise ValueError("Configuration must be a dictionary")

        # Validate M3U config if present
        if "m3u" in config_data:
            m3u_config = config_data["m3u"]
            if not isinstance(m3u_config, dict):
                raise ValueError("M3U configuration must be a dictionary")

            if "enabled" in m3u_config and not isinstance(m3u_config["enabled"], bool):
                raise ValueError("M3U enabled must be a boolean")

            if "testing_interval_hours" in m3u_config:
                interval = m3u_config["testing_interval_hours"]
                if not isinstance(interval, int) or interval < 1:
                    raise ValueError("testing_interval_hours must be a positive integer")
