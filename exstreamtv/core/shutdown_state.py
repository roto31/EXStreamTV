"""
Global shutdown state — Single source of truth for graceful shutdown.

Set by main lifespan before stopping channels. Checked by ensure_clock,
EPG builds, and other long-running operations.
"""

_shutting_down = False


def set_shutting_down(value: bool = True) -> None:
    """Set shutdown flag. Called by main lifespan."""
    global _shutting_down
    _shutting_down = value


def is_shutting_down() -> bool:
    """Return True if graceful shutdown is in progress."""
    return _shutting_down
