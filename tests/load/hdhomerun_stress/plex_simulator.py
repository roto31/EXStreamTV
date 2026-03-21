"""Plex Live TV Simulator - Wraps plex_validator for load tests."""

from tests.integration.broadcast_alignment.plex_validator import (
    PlexSimulationResult,
    simulate_plex_tune,
)

__all__ = ["simulate_plex_tune", "PlexSimulationResult"]
