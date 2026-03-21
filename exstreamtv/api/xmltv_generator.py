"""
XMLTVGenerator with validation for EPG output.

Validates programmes (monotonic, no overlaps, start < stop, required fields)
before serving. Hard structural validation. Robust datetime parsing.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, List, Tuple
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

from exstreamtv.api.timeline_builder import TimelineProgramme
from exstreamtv.constants import EXSTREAM_CHANNEL_ID_PREFIX
from exstreamtv.utils.xmltv_parse import parse_xmltv_datetime_to_epoch, parse_xmltv_start_stop

logger = logging.getLogger(__name__)

BULK_FAILURE_THRESHOLD = 0.05  # >5% parse failures -> abort ingestion
_PLACEHOLDER_RE = re.compile(r"^Item \d+$")


class XMLTVValidationError(Exception):
    """Raised when XMLTV validation fails."""
    def __init__(self, message: str, details: List[str] | None = None):
        self.details = details or []
        super().__init__(message)


def validate_xmltv_structure(xml_content: str, channel_ids: set[str]) -> Tuple[bool, List[str]]:
    """
    Hard structural validation of XMLTV before serving.
    Robust parse: YYYYMMDDHHMMSS +zzzz, compact, ISO8601. Bulk failure >5% aborts.
    Returns (valid, errors).
    """
    errors: List[str] = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        return False, [f"Parse error: {e}"]
    if root.tag != "tv":
        errors.append("Root <tv> missing")
    channels = root.findall(".//channel")
    seen_ch_ids = {ch.get("id", "") for ch in channels if ch.get("id")}
    for cid in channel_ids:
        if cid not in seen_ch_ids:
            errors.append(f"Channel id '{cid}' not in XMLTV")
    programmes = root.findall(".//programme")
    if not programmes:
        errors.append("Programme count is 0")
    prev_stop_epoch: dict[str, float] = {}
    parse_fail_count = 0
    for i, prog in enumerate(programmes):
        start_s = prog.get("start", "")
        stop_s = prog.get("stop", "")
        ch = prog.get("channel", "")
        if not ch:
            errors.append(f"Programme {i}: missing channel")
        if not start_s or not stop_s:
            errors.append(f"Programme {i}: invalid start/stop format")
            parse_fail_count += 1
            continue
        parsed = parse_xmltv_start_stop(start_s, stop_s)
        if parsed is None:
            start_epoch = parse_xmltv_datetime_to_epoch(start_s)
            stop_epoch = parse_xmltv_datetime_to_epoch(stop_s)
            if start_epoch is None:
                errors.append(f"Programme {i}: cannot parse datetime (start={start_s[:50]!r})")
                logger.warning("xmltv parse failed programme %d start=%r", i, start_s[:80])
                parse_fail_count += 1
                continue
            if stop_epoch is None:
                errors.append(f"Programme {i}: cannot parse datetime (stop={stop_s[:50]!r})")
                logger.warning("xmltv parse failed programme %d stop=%r", i, stop_s[:80])
                parse_fail_count += 1
                continue
            errors.append(f"Programme {i}: stop <= start")
            continue
        start_epoch, stop_epoch = parsed
        last = prev_stop_epoch.get(ch, 0)
        if start_epoch < last:
            errors.append(f"Programme {i}: overlap (start {start_epoch} < prev stop {last})")
        prev_stop_epoch[ch] = stop_epoch

    if programmes and parse_fail_count / len(programmes) > BULK_FAILURE_THRESHOLD:
        logger.error(
            "xmltv bulk parse failure: %d/%d programmes (>.05), abort ingestion",
            parse_fail_count, len(programmes),
        )
        errors.insert(0, f"BULK_FAILURE: {parse_fail_count}/{len(programmes)} programmes failed parse")
        return False, errors

    return len(errors) == 0, errors


def _xml(val: Any) -> str:
    """Safely escape XML text."""
    if val is None:
        return ""
    return xml_escape(str(val), {'"': "&quot;", "'": "&apos;"})


def _format_xmltv_datetime(dt: datetime) -> str:
    """Format datetime for XMLTV (YYYYMMDDHHMMSS +0000). Assumes UTC."""
    return dt.strftime("%Y%m%d%H%M%S") + " +0000"


class XMLTVGenerator:
    """
    Generates XMLTV with validation.

    Validates: monotonic times, no overlaps, start < stop, required fields.
    """

    def generate(
        self,
        channels: List[Any],
        programmes_by_channel: dict[int | str, List[TimelineProgramme]],
        base_url: str = "http://localhost:8411",
        validate: bool = True,
    ) -> str:
        """
        Generate XMLTV string.

        Args:
            channels: List of Channel objects.
            programmes_by_channel: Channel id -> list of TimelineProgramme.
            base_url: Base URL for logo/links.
            validate: If True, validate before emit.

        Returns:
            XMLTV XML string.

        Raises:
            XMLTVValidationError: If validation fails.
        """
        if validate:
            self._validate(channels, programmes_by_channel)

        lines: List[str] = []
        lines.append('<?xml version="1.0" encoding="UTF-8"?>')
        lines.append('<tv generator-info-name="EXStreamTV">')

        for ch in channels:
            ch_id = _channel_xmltv_id(ch)
            name = _xml(ch.name if hasattr(ch, "name") else str(ch))
            lines.append(f'  <channel id="{ch_id}">')
            lines.append(f'    <display-name>{name}</display-name>')
            logo = getattr(ch, "logo_path", None) or getattr(ch, "logo_url", None)
            if logo:
                if not str(logo).startswith("http"):
                    logo = f"{base_url.rstrip('/')}/{logo.lstrip('/')}"
                lines.append(f'    <icon src="{_xml(logo)}"/>')
            lines.append("  </channel>")

        for ch in channels:
            ch_id = ch.id if hasattr(ch, "id") else ch
            progs = programmes_by_channel.get(ch_id, [])
            for p in progs:
                title_raw = (p.title or "").strip()
                if not title_raw or _PLACEHOLDER_RE.match(title_raw):
                    mi = getattr(p, "media_item", None)
                    logger.critical(
                        "XMLTV invariant violation: channel=%s item_index=%s title=%r media_id=%s — skipped",
                        ch_id, getattr(p, "index", "?"), title_raw,
                        getattr(mi, "id", "?") if mi else "?",
                    )
                    continue
                ch_xmltv_id = _channel_xmltv_id(ch)
                start_str = _format_xmltv_datetime(p.start_time)
                stop_str = _format_xmltv_datetime(p.stop_time)
                title = _xml(title_raw)
                lines.append(f'  <programme start="{start_str}" stop="{stop_str}" channel="{ch_xmltv_id}">')
                lines.append(f"    <title>{title}</title>")
                lines.append("  </programme>")

        lines.append("</tv>")
        return "\n".join(lines)

    def _validate(
        self,
        channels: List[Any],
        programmes_by_channel: dict[int | str, List[TimelineProgramme]],
    ) -> None:
        """Validate programmes before emit. Raises XMLTVValidationError if invalid."""
        errors: List[str] = []

        for ch in channels:
            ch_id = ch.id if hasattr(ch, "id") else ch
            progs = programmes_by_channel.get(ch_id, [])

            for i, p in enumerate(progs):
                if p.start_time >= p.stop_time:
                    errors.append(
                        f"Channel {ch_id} programme {i}: start >= stop "
                        f"({p.start_time} >= {p.stop_time})"
                    )
                t = (p.title or "").strip()
                if not t or _PLACEHOLDER_RE.match(t):
                    errors.append(
                        f"Channel {ch_id} programme {i}: invalid title {t!r}"
                    )
                if i + 1 < len(progs):
                    next_p = progs[i + 1]
                    if p.stop_time != next_p.start_time:
                        # Allow small gap but not overlap
                        if p.stop_time > next_p.start_time:
                            errors.append(
                                f"Channel {ch_id} overlap: programme {i} stop {p.stop_time} > "
                                f"next start {next_p.start_time}"
                            )

        if errors:
            raise XMLTVValidationError("XMLTV validation failed", details=errors)


def _channel_xmltv_id(ch: Any) -> str:
    """
    Stable channel ID for XMLTV. Must match M3U tvg-id. Uses dot format (exstream.1)
    for Plex XMLTV compliance: /^[-a-zA-Z0-9]+(\\.[-a-zA-Z0-9]+)+$/
    """
    ch_id = ch.id if hasattr(ch, "id") else str(ch)
    return f"{EXSTREAM_CHANNEL_ID_PREFIX}.{ch_id}"
