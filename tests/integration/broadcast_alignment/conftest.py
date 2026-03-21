"""Fixtures for broadcast alignment tests."""

import pytest


@pytest.fixture
def base_url() -> str:
    """Default EXStreamTV base URL."""
    return "http://127.0.0.1:8411"


@pytest.fixture
def sample_guide_numbers() -> list[str]:
    """Sample GuideNumbers for testing."""
    return ["100", "101", "102"]


@pytest.fixture
def sample_channel_ids() -> list[int]:
    """Sample channel IDs for testing."""
    return [100, 101, 102]
