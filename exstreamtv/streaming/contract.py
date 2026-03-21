"""
Streaming Safety Contract Enforcement.

Validates StreamSource before FFmpeg. Prevents HTML, error pages,
and invalid URLs from reaching the stream pipeline.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from exstreamtv.streaming.resolvers.base import SourceType

logger = logging.getLogger(__name__)


class SourceClassification(str, Enum):
    """Classification for stream source handling (retry, precache, etc)."""

    PLEX = "plex"
    FILE = "file"
    URL = "url"
    YOUTUBE = "youtube"
    ARCHIVE = "archive"
    SLATE = "slate"


@dataclass
class StreamSource:
    """
    Fully resolved stream source for FFmpeg.

    DTO only. No ORM. No raw strings without validation.
    """

    url: str
    headers: dict[str, str] = field(default_factory=dict)
    seek_offset: float = 0.0
    probe_required: bool = True
    allow_retry: bool = True
    classification: SourceClassification = SourceClassification.URL
    source_type: SourceType = SourceType.UNKNOWN
    title: str = ""
    canonical_duration: float = 1800.0


@dataclass
class ValidationResult:
    """Result of StreamingContractEnforcer.validate()."""

    valid: bool
    source: StreamSource | None = None
    violation_reason: str | None = None


class StreamingContractEnforcer:
    """
    Validates StreamSource before FFmpeg launch.

    Invalid sources trigger ContractViolation: advance timeline, no restart.
    """

    VALID_SCHEMES = frozenset({"http", "https", "file", "rtsp", "pipe", "udp", "tcp"})
    HTML_INDICATORS = ("<!DOCTYPE", "<html", "<HTML", "Content-Type: text/html")

    def validate(self, source: StreamSource | None) -> ValidationResult:
        """
        Validate StreamSource. Returns ValidationResult.

        If invalid: log once, return ValidationResult(valid=False, violation_reason=...).
        """
        if source is None:
            return ValidationResult(
                valid=False,
                violation_reason="source is None",
            )
        if not source.url or not str(source.url).strip():
            return ValidationResult(
                valid=False,
                source=source,
                violation_reason="url is empty",
            )
        url = source.url.strip()
        if any(ind in url[:200] for ind in self.HTML_INDICATORS):
            return ValidationResult(
                valid=False,
                source=source,
                violation_reason="url appears to be HTML",
            )
        try:
            scheme = url.split(":")[0].lower()
        except (IndexError, AttributeError):
            return ValidationResult(
                valid=False,
                source=source,
                violation_reason="invalid url format",
            )
        if scheme not in self.VALID_SCHEMES:
            return ValidationResult(
                valid=False,
                source=source,
                violation_reason=f"invalid scheme: {scheme}",
            )
        return ValidationResult(valid=True, source=source)
