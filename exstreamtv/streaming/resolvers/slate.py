"""
Slate Resolver — Fallback for contract violations and errors.

Returns a reference to the error screen generator. Used when:
- Resolver fails
- Contract validation fails
- Recovery fallback needed

Does not return a stream URL; callers use ErrorScreenGenerator for TS output.
"""

import logging
from typing import Any

from exstreamtv.streaming.contract import SourceClassification, StreamSource
from exstreamtv.streaming.resolvers.base import SourceType

logger = logging.getLogger(__name__)


class SlateResolver:
    """
    Fallback when resolution fails or contract violated.

    Does not resolve to a URL. Callers must use ErrorScreenGenerator
    to produce MPEG-TS slate. This resolver exists for the registry
    pattern; it returns a sentinel StreamSource that indicates "use slate".
    """

    source_type = SourceType.UNKNOWN

    def get_slate_stream_source(self, title: str = "Technical Difficulties") -> StreamSource:
        """
        Return a StreamSource that signals "emit slate".

        url is a sentinel; FFmpeg must NOT be launched. Caller emits slate instead.
        """
        return StreamSource(
            url="",  # Sentinel: empty means use slate
            headers={},
            seek_offset=0.0,
            probe_required=False,
            allow_retry=False,
            classification=SourceClassification.SLATE,
            source_type=SourceType.UNKNOWN,
            title=title,
            canonical_duration=5.0,
        )
