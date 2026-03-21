"""
Deterministic playout engine components.

Provides:
- Persistent playout journal (crash-safe resume)
- Per-source adaptive retry policies
- Media pre-caching (10s validation gate)
- Strict FFmpeg exit classification
- Atomic index advancement control
- Deterministic state machine
"""

from exstreamtv.streaming.playout.state import (
    ExitClassification,
    StreamState,
)
from exstreamtv.database.models.playout_journal import PlayoutJournal
from exstreamtv.streaming.playout.journal import get_playout_journal
from exstreamtv.streaming.playout.retry import (
    RetryPolicy,
    get_retry_policy,
)
from exstreamtv.streaming.playout.exit_classifier import (
    classify_ffmpeg_exit,
    MIN_BYTES_NATURAL_EOF,
    MIN_RUNTIME_NATURAL_EOF,
)

__all__ = [
    "ExitClassification",
    "StreamState",
    "PlayoutJournal",
    "get_playout_journal",
    "RetryPolicy",
    "get_retry_policy",
    "classify_ffmpeg_exit",
    "MIN_BYTES_NATURAL_EOF",
    "MIN_RUNTIME_NATURAL_EOF",
]
