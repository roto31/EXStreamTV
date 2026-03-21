"""
Deterministic playout state machine and exit classification.

All transitions must be explicit and logged.
Advancement allowed ONLY when state == ADVANCING.
"""

from enum import Enum


class StreamState(str, Enum):
    """Explicit playout stream states. All transitions must be logged."""

    IDLE = "idle"
    RESOLVING = "resolving"
    VALIDATING_URL = "validating_url"
    PRECACHING = "precaching"
    STARTING = "starting"
    STREAMING = "streaming"
    PAUSED_NO_CLIENTS = "paused_no_clients"
    RETRYING = "retrying"
    ADVANCING = "advancing"
    JOURNALING = "journaling"
    STOPPING = "stopping"
    ERROR = "error"


class ExitClassification(str, Enum):
    """
    FFmpeg exit classification. Only NATURAL_EOF may transition to ADVANCING directly.
    """

    NATURAL_EOF = "natural_eof"
    """exit_code==0, runtime >= expected_duration - tolerance, bytes >= 1MB"""

    EARLY_EOF = "early_eof"
    """exit_code==0, runtime < 5s OR bytes < 1MB"""

    FAILURE_EXIT = "failure_exit"
    """exit_code != 0"""

    NO_OUTPUT = "no_output"
    """bytes < 1MB regardless of exit code"""

    CLIENT_DISCONNECT = "client_disconnect"
    """All clients disconnected - must NOT advance"""

    CHANNEL_STOP = "channel_stop"
    """Channel stopping - must NOT advance"""

    UNKNOWN = "unknown"
    """Classification failed - treat as retry"""


def can_advance_on_exit(classification: ExitClassification) -> bool:
    """Only NATURAL_EOF may transition to index advancement."""
    return classification == ExitClassification.NATURAL_EOF
