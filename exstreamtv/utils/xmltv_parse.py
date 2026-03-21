"""
Robust XMLTV datetime parsing. Parse only; no clock logic.
Returns UTC epoch. Rejects empty, non-numeric, stop<=start.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Canonical XMLTV: YYYYMMDDHHMMSS +zzzz
PATTERN_CANONICAL = re.compile(r"^(\d{14})\s*([+-]\d{4})?$")
# Compact: YYYYMMDDHHMMSS+zzzz
PATTERN_COMPACT = re.compile(r"^(\d{14})([+-]\d{4})?$")
# ISO8601: 2026-03-01T06:00:00Z or 2026-03-01T06:00:00+00:00
PATTERN_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})?$")


def _parse_offset(tz_part: str) -> int:
    """Parse +0000 or -0600 to offset seconds (positive = east of UTC)."""
    if not tz_part or tz_part.upper() == "Z":
        return 0
    tz_part = tz_part.replace(":", "").strip()
    if len(tz_part) < 5:
        return 0
    sign = 1 if tz_part[0] == "+" else -1
    try:
        h = int(tz_part[1:3])
        m = int(tz_part[3:5])
        return sign * (h * 3600 + m * 60)
    except ValueError:
        return 0


def _dt_utc_epoch(dt: datetime, offset_sec: int) -> float:
    """Convert naive dt (in given offset) to UTC epoch."""
    tz = timezone(timedelta(seconds=offset_sec))
    return dt.replace(tzinfo=tz).timestamp()


def parse_xmltv_datetime_to_epoch(s: str) -> Optional[float]:
    """
    Parse XMLTV datetime string to UTC epoch. Handles:
    - YYYYMMDDHHMMSS +0000
    - YYYYMMDDHHMMSS+0000
    - ISO8601 (2026-03-01T06:00:00Z)
    Missing timezone -> assume UTC. Logs original on failure.
    """
    if not s or not isinstance(s, str):
        return None
    raw = s.strip()
    if not raw or not raw[0].isdigit():
        logger.debug("xmltv parse reject non-numeric/empty: %r", s[:50] if s else "")
        return None

    # 1) Canonical: YYYYMMDDHHMMSS +zzzz
    m = PATTERN_CANONICAL.match(raw)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
            offset_sec = _parse_offset(m.group(2) or "+0000")
            return _dt_utc_epoch(dt, offset_sec)
        except ValueError:
            logger.debug("xmltv parse failed canonical %r", s[:50])
            return None

    # 2) Compact: YYYYMMDDHHMMSS+zzzz
    m = PATTERN_COMPACT.match(raw)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
            offset_sec = _parse_offset(m.group(2) or "+0000")
            return _dt_utc_epoch(dt, offset_sec)
        except ValueError:
            logger.debug("xmltv parse failed compact %r", s[:50])
            return None

    # 3) ISO8601
    m = PATTERN_ISO.match(raw)
    if m:
        try:
            y, mo, d, h, mi, sec = map(int, m.group(1, 2, 3, 4, 5, 6))
            frac = m.group(7)
            ms = int(frac[:6].ljust(6, "0")) if frac else 0
            tz_str = m.group(8) or "Z"
            offset_sec = _parse_offset(tz_str) if tz_str.upper() != "Z" else 0
            dt = datetime(y, mo, d, h, mi, sec, ms)
            return _dt_utc_epoch(dt, offset_sec)
        except (ValueError, TypeError):
            logger.debug("xmltv parse failed iso %r", s[:50])
            return None

    logger.debug("xmltv parse no match: %r", s[:50])
    return None


def parse_xmltv_start_stop(start_s: str, stop_s: str) -> Optional[Tuple[float, float]]:
    """
    Parse start/stop pair. Returns (start_epoch, stop_epoch) or None.
    Rejects stop <= start.
    """
    start_epoch = parse_xmltv_datetime_to_epoch(start_s)
    stop_epoch = parse_xmltv_datetime_to_epoch(stop_s)
    if start_epoch is None or stop_epoch is None:
        return None
    if stop_epoch <= start_epoch:
        return None
    return (start_epoch, stop_epoch)
