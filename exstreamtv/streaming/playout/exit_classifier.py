"""
Strict FFmpeg exit classification.

Only NATURAL_EOF may transition to ADVANCING directly.
All others must enter RETRYING.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from exstreamtv.streaming.playout.state import ExitClassification

logger = logging.getLogger(__name__)

# Thresholds for NATURAL_EOF
MIN_BYTES_NATURAL_EOF = 1_000_000  # 1MB
MIN_RUNTIME_NATURAL_EOF = 5.0  # seconds
DURATION_TOLERANCE = 30.0  # seconds - allow early exit if within this of expected


@dataclass
class FFmpegExitResult:
    """Captured FFmpeg run outcome."""

    exit_code: Optional[int]
    runtime_seconds: float
    bytes_sent: int
    stderr_snippet: Optional[str] = None
    expected_duration: Optional[float] = None


def classify_ffmpeg_exit(
    exit_code: Optional[int],
    runtime_seconds: float,
    bytes_sent: int,
    expected_duration: Optional[float] = None,
) -> ExitClassification:
    """
    Classify FFmpeg exit strictly.

    NATURAL_EOF: exit_code==0, runtime >= expected_duration - tolerance, bytes >= 1MB
    EARLY_EOF: exit_code==0, runtime < 5s OR bytes < 1MB
    FAILURE_EXIT: exit_code != 0
    NO_OUTPUT: bytes < 1MB
    """
    if exit_code is not None and exit_code != 0:
        logger.debug(
            f"Exit classification: FAILURE_EXIT (exit_code={exit_code}, "
            f"runtime={runtime_seconds:.1f}s, bytes={bytes_sent})"
        )
        return ExitClassification.FAILURE_EXIT

    if bytes_sent < MIN_BYTES_NATURAL_EOF:
        logger.debug(
            f"Exit classification: NO_OUTPUT (bytes={bytes_sent} < {MIN_BYTES_NATURAL_EOF}, "
            f"runtime={runtime_seconds:.1f}s)"
        )
        return ExitClassification.NO_OUTPUT

    if runtime_seconds < MIN_RUNTIME_NATURAL_EOF:
        logger.debug(
            f"Exit classification: EARLY_EOF (runtime={runtime_seconds:.1f}s < {MIN_RUNTIME_NATURAL_EOF}, "
            f"bytes={bytes_sent})"
        )
        return ExitClassification.EARLY_EOF

    if expected_duration is not None and expected_duration > 0:
        min_runtime = max(0, expected_duration - DURATION_TOLERANCE)
        if runtime_seconds < min_runtime:
            logger.debug(
                f"Exit classification: EARLY_EOF (runtime={runtime_seconds:.1f}s < "
                f"expected {expected_duration:.0f}s - {DURATION_TOLERANCE}s)"
            )
            return ExitClassification.EARLY_EOF

    logger.debug(
        f"Exit classification: NATURAL_EOF (exit_code={exit_code}, "
        f"runtime={runtime_seconds:.1f}s, bytes={bytes_sent})"
    )
    return ExitClassification.NATURAL_EOF
