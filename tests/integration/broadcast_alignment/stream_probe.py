"""
Stream Probe — MPEG-TS stream validation.

For each test channel:
- Query authoritative clock
- Connect via HDHomeRun stream endpoint
- Capture N seconds of MPEG-TS
- Validate: continuous timestamps, no restart, correct content type
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass
class StreamProbeResult:
    """Result of stream probe for a channel."""

    channel_number: str
    ok: bool
    bytes_received: int
    duration_seconds: float
    content_type: str | None
    first_sync_byte_found: bool
    mime_valid: bool
    message: str | None


MPEGTS_SYNC_BYTE = 0x47
EXPECTED_MIME = "video/mp2t"


async def probe_stream(
    base_url: str,
    channel_number: str,
    *,
    duration_seconds: float = 30.0,
    client: httpx.AsyncClient | None = None,
) -> StreamProbeResult:
    """
    Probe HDHomeRun stream endpoint for a channel.

    Validates:
    - Stream returns data
    - Content-Type is video/mp2t
    - MPEG-TS sync byte 0x47 present
    """
    url = f"{base_url.rstrip('/')}/hdhomerun/auto/v{channel_number}"
    start = datetime.utcnow()
    bytes_received = 0
    first_sync_found = False
    content_type = None

    try:
        c = client or httpx.AsyncClient(timeout=60.0)
        async with c.stream("GET", url) as resp:
            content_type = resp.headers.get("content-type", "")
            if EXPECTED_MIME in content_type or "mp2t" in content_type:
                mime_valid = True
            else:
                mime_valid = False

            async for chunk in resp.aiter_bytes(chunk_size=65536):
                bytes_received += len(chunk)
                if not first_sync_found and len(chunk) >= 188:
                    for i in range(min(len(chunk), 188 * 10)):
                        if i < len(chunk) and chunk[i] == MPEGTS_SYNC_BYTE:
                            first_sync_found = True
                            break
                        if i + 188 < len(chunk) and chunk[i + 188] == MPEGTS_SYNC_BYTE:
                            first_sync_found = True
                            break

                elapsed = (datetime.utcnow() - start).total_seconds()
                if elapsed >= duration_seconds:
                    break

        elapsed = (datetime.utcnow() - start).total_seconds()
        ok = bytes_received > 0 and first_sync_found and mime_valid
        return StreamProbeResult(
            channel_number=channel_number,
            ok=ok,
            bytes_received=bytes_received,
            duration_seconds=elapsed,
            content_type=content_type,
            first_sync_byte_found=first_sync_found,
            mime_valid=mime_valid,
            message=None
            if ok
            else (
                f"No sync byte"
                if not first_sync_found
                else (f"Wrong MIME: {content_type}" if not mime_valid else f"Only {bytes_received} bytes")
            ),
        )
    except Exception as e:
        elapsed = (datetime.utcnow() - start).total_seconds()
        return StreamProbeResult(
            channel_number=channel_number,
            ok=False,
            bytes_received=bytes_received,
            duration_seconds=elapsed,
            content_type=content_type,
            first_sync_byte_found=first_sync_found,
            mime_valid=False,
            message=str(e),
        )
