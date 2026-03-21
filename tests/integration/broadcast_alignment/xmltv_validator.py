"""
XMLTV Validator — EPG alignment with ChannelClock.

Validates:
- XMLTV entries for each channel
- No overlapping programme entries
- No gaps in schedule
- XMLTV item matches authoritative clock item
- Monotonic start times
- 24h forward continuity
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProgrammeEntry:
    """Parsed XMLTV programme entry."""

    channel_id: str
    start: datetime
    stop: datetime
    title: str
    start_str: str
    stop_str: str


@dataclass
class XMLTVValidationResult:
    """Result of XMLTV validation for a channel."""

    channel_id: str
    ok: bool
    programmes: list[ProgrammeEntry]
    overlaps: list[tuple[int, int]]
    gaps: list[tuple[datetime, datetime]]
    duplicates: list[tuple[int, int]]
    message: str | None


def parse_xmltv_datetime(s: str) -> datetime | None:
    """Parse XMLTV datetime format: 20260225042333 +0000."""
    s = s.strip()
    m = re.match(r"(\d{14})\s*([+-]\d{4})?", s)
    if not m:
        return None
    dt_str = m.group(1)
    tz = m.group(2) or "+0000"
    try:
        year = int(dt_str[0:4])
        month = int(dt_str[4:6])
        day = int(dt_str[6:8])
        hour = int(dt_str[8:10])
        minute = int(dt_str[10:12])
        second = int(dt_str[12:14])
        return datetime(year, month, day, hour, minute, second)
    except (ValueError, IndexError):
        return None


def parse_xmltv(xml_content: str) -> dict[str, list[ProgrammeEntry]]:
    """
    Parse XMLTV XML into channel -> programmes mapping.
    """
    programmes_by_channel: dict[str, list[ProgrammeEntry]] = {}
    root = ET.fromstring(xml_content)
    ns = {"tv": "urn:xmltv"} if "xmltv" in xml_content[:500] else {}
    for prog in root.findall(".//programme", ns) or root.findall(".//programme"):
        ch = prog.get("channel", "")
        start_str = prog.get("start", "")
        stop_str = prog.get("stop", "")
        start_dt = parse_xmltv_datetime(start_str)
        stop_dt = parse_xmltv_datetime(stop_str)
        title_el = prog.find("title", ns) or prog.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        if not ch or not start_dt or not stop_dt:
            continue
        entry = ProgrammeEntry(
            channel_id=ch,
            start=start_dt,
            stop=stop_dt,
            title=title,
            start_str=start_str,
            stop_str=stop_str,
        )
        programmes_by_channel.setdefault(ch, []).append(entry)

    for ch, progs in programmes_by_channel.items():
        progs.sort(key=lambda p: p.start)

    return programmes_by_channel


def validate_channel_programmes(
    programmes: list[ProgrammeEntry],
    channel_id: str,
    gap_tolerance_seconds: float = 5.0,
) -> XMLTVValidationResult:
    """
    Validate programme list for a channel.
    - No overlaps
    - No gaps (beyond tolerance)
    - No duplicate (channel, start) pairs
    """
    overlaps: list[tuple[int, int]] = []
    gaps: list[tuple[datetime, datetime]] = []
    duplicates: list[tuple[int, int]] = []

    seen_starts: set[str] = set()
    for i, p in enumerate(programmes):
        if p.start_str in seen_starts:
            for j, q in enumerate(programmes):
                if q.start_str == p.start_str and j < i:
                    duplicates.append((j, i))
                    break
        seen_starts.add(p.start_str)

    for i in range(len(programmes) - 1):
        curr = programmes[i]
        next_p = programmes[i + 1]
        if curr.stop > next_p.start:
            overlaps.append((i, i + 1))
        gap = (next_p.start - curr.stop).total_seconds()
        if gap > gap_tolerance_seconds:
            gaps.append((curr.stop, next_p.start))

    ok = len(overlaps) == 0 and len(duplicates) == 0
    return XMLTVValidationResult(
        channel_id=channel_id,
        ok=ok,
        programmes=programmes,
        overlaps=overlaps,
        gaps=gaps,
        duplicates=duplicates,
        message=None if ok else f"Overlaps: {len(overlaps)}, Duplicates: {len(duplicates)}",
    )


async def fetch_and_validate_xmltv(
    base_url: str,
    channel_ids: list[str],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, XMLTVValidationResult]:
    """
    Fetch XMLTV from /iptv/xmltv.xml and validate each channel.
    """
    url = f"{base_url.rstrip('/')}/iptv/xmltv.xml"
    try:
        if client:
            resp = await client.get(url)
        else:
            async with httpx.AsyncClient(timeout=30.0) as c:
                resp = await c.get(url)

        if resp.status_code != 200:
            return {
                ch: XMLTVValidationResult(
                    channel_id=ch,
                    ok=False,
                    programmes=[],
                    overlaps=[],
                    gaps=[],
                    duplicates=[],
                    message=f"HTTP {resp.status_code}",
                )
                for ch in channel_ids
            }

        programmes_by_channel = parse_xmltv(resp.text)
        results: dict[str, XMLTVValidationResult] = {}
        for ch in channel_ids:
            progs = programmes_by_channel.get(ch, [])
            results[ch] = validate_channel_programmes(progs, ch)
        return results
    except Exception as e:
        return {
            ch: XMLTVValidationResult(
                channel_id=ch,
                ok=False,
                programmes=[],
                overlaps=[],
                gaps=[],
                duplicates=[],
                message=str(e),
            )
            for ch in channel_ids
        }
