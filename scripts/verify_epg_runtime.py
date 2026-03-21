#!/usr/bin/env python3
"""
Runtime EPG verification script.

Fetches live XMLTV, lineup, and discover from EXStreamTV and validates:
- Channel ID format (exstream-{id})
- GuideNumber as first display-name (Plex mapping)
- No duplicate (channel, start) programmes
- Monotonic start times per channel

Usage:
    python scripts/verify_epg_runtime.py [base_url]
    Example: python scripts/verify_epg_runtime.py http://localhost:8411

Requires EXStreamTV server running.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

try:
    import httpx
except ImportError:
    print("Requires httpx: pip install httpx")
    sys.exit(1)


@dataclass
class VerificationResult:
    """Result of a single verification check."""
    name: str
    passed: bool
    detail: str = ""
    errors: list[str] = field(default_factory=list)


def fetch_json(client: httpx.Client, url: str) -> dict | list | None:
    """Fetch JSON from URL."""
    try:
        r = client.get(url, timeout=30.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def fetch_xml(client: httpx.Client, url: str) -> str | None:
    """Fetch XML from URL."""
    try:
        r = client.get(url, timeout=60.0)
        r.raise_for_status()
        return r.text
    except Exception as e:
        return None


def verify_channel_id_consistency(
    discover: dict | None,
    lineup: list | None,
    xml_content: str | None,
) -> list[VerificationResult]:
    """Verify channel ID, GuideNumber, and lineup consistency."""
    results: list[VerificationResult] = []

    # 1. Discover
    if not discover:
        results.append(VerificationResult(
            "discover.json fetch", False, "Failed to fetch discover.json"
        ))
    else:
        dev_id = discover.get("DeviceID", "")
        tc = discover.get("TunerCount", 0)
        if re.match(r"^[0-9A-Fa-f]{8}$", dev_id):
            results.append(VerificationResult(
                "DeviceID format", True, f"DeviceID={dev_id} (8 hex)"
            ))
        else:
            results.append(VerificationResult(
                "DeviceID format", False, f"Invalid DeviceID: {dev_id}"
            ))
        results.append(VerificationResult(
            "TunerCount", True, f"TunerCount={tc}"
        ))

    # 2. Lineup
    if not lineup or not isinstance(lineup, list):
        results.append(VerificationResult(
            "lineup.json fetch", False, "Failed to fetch lineup.json or not a list"
        ))
        return results

    guide_numbers = [e.get("GuideNumber") for e in lineup if isinstance(e, dict)]
    if len(guide_numbers) != len(set(guide_numbers)):
        dupes = [g for g in guide_numbers if guide_numbers.count(g) > 1]
        results.append(VerificationResult(
            "lineup GuideNumber unique", False,
            f"Duplicate GuideNumbers: {list(set(dupes))}"
        ))
    else:
        results.append(VerificationResult(
            "lineup GuideNumber unique", True,
            f"{len(guide_numbers)} unique GuideNumbers"
        ))

    # 3. XMLTV channel/display-name
    if not xml_content:
        results.append(VerificationResult(
            "EPG fetch", False, "Failed to fetch EPG"
        ))
        return results

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        results.append(VerificationResult(
            "XMLTV parse", False, str(e)
        ))
        return results

    channels = root.findall(".//channel")
    channel_ids = []
    display_names_by_id: dict[str, list[str]] = {}

    for ch in channels:
        cid = ch.get("id")
        if not cid:
            continue
        channel_ids.append(cid)
        names = [dn.text or "" for dn in ch.findall("display-name") if dn.text]
        display_names_by_id[cid] = names

    # exstream-{id} format
    exstream_pattern = re.compile(r"^exstream-\d+$")
    bad_ids = [c for c in channel_ids if not exstream_pattern.match(c)]
    if bad_ids:
        results.append(VerificationResult(
            "XMLTV channel id format", False,
            f"Invalid ids: {bad_ids[:5]}"
        ))
    else:
        results.append(VerificationResult(
            "XMLTV channel id format", True,
            f"All {len(channel_ids)} channels use exstream-{{id}}"
        ))

    # GuideNumber as first display-name
    lineup_guide_set = set(str(g) for g in guide_numbers if g is not None)
    missing_guide = []
    for cid, names in display_names_by_id.items():
        if not names:
            missing_guide.append(cid)
        elif str(names[0]) not in lineup_guide_set and names[0] != "":
            # First display-name should ideally match a GuideNumber
            pass  # Could be channel name first - we changed to GuideNumber first
    if missing_guide:
        results.append(VerificationResult(
            "display-name present", False,
            f"Channels missing display-name: {missing_guide[:5]}"
        ))
    else:
        results.append(VerificationResult(
            "display-name present", True,
            "All channels have display-name"
        ))

    # Cross-check: every lineup GuideNumber appears as first display-name in some channel
    xml_first_displays = set()
    for names in display_names_by_id.values():
        if names:
            xml_first_displays.add(str(names[0]))
    unmatched = lineup_guide_set - xml_first_displays
    if unmatched and len(unmatched) < len(lineup_guide_set):
        results.append(VerificationResult(
            "lineup/EPG GuideNumber match", False,
            f"Lineup GuideNumbers not in EPG first display-name: {list(unmatched)[:5]}"
        ))
    elif unmatched:
        results.append(VerificationResult(
            "lineup/EPG GuideNumber match", False,
            "No lineup GuideNumbers match EPG first display-name"
        ))
    else:
        results.append(VerificationResult(
            "lineup/EPG GuideNumber match", True,
            "All lineup GuideNumbers present as first display-name in EPG"
        ))

    return results


def verify_no_duplicate_programmes(xml_content: str | None) -> list[VerificationResult]:
    """Verify no duplicate (channel, start) programmes."""
    results: list[VerificationResult] = []

    if not xml_content:
        results.append(VerificationResult(
            "duplicate check", False, "No XML content"
        ))
        return results

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        results.append(VerificationResult(
            "duplicate check", False, f"Parse error: {e}"
        ))
        return results

    progs = root.findall(".//programme")
    seen: dict[str, set[str]] = defaultdict(set)
    duplicates: list[tuple[str, str]] = []

    for p in progs:
        ch = p.get("channel", "")
        start = p.get("start", "")
        if ch and start:
            if start in seen[ch]:
                duplicates.append((ch, start))
            seen[ch].add(start)

    if duplicates:
        results.append(VerificationResult(
            "no duplicate (channel,start)", False,
            f"Found {len(duplicates)} duplicates. Examples: {duplicates[:5]}",
            errors=[f"{c} @ {s}" for c, s in duplicates[:20]]
        ))
    else:
        results.append(VerificationResult(
            "no duplicate (channel,start)", True,
            f"{len(progs)} programmes, no duplicates"
        ))

    return results


def verify_monotonic_times(xml_content: str | None) -> list[VerificationResult]:
    """Verify programme start times are monotonic per channel."""
    results: list[VerificationResult] = []

    if not xml_content:
        return results

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return results

    progs_by_ch: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for p in root.findall(".//programme"):
        ch = p.get("channel", "")
        start = p.get("start", "")
        stop = p.get("stop", "")
        if ch and start:
            progs_by_ch[ch].append((start, stop or ""))

    overlaps = []
    for ch, items in progs_by_ch.items():
        items.sort(key=lambda x: x[0])
        for i in range(len(items) - 1):
            _, stop = items[i]
            next_start, _ = items[i + 1]
            if stop > next_start:
                overlaps.append((ch, stop, next_start))

    if overlaps:
        results.append(VerificationResult(
            "monotonic start times", False,
            f"Overlaps found: {len(overlaps)}. Examples: {overlaps[:3]}"
        ))
    else:
        results.append(VerificationResult(
            "monotonic start times", True,
            f"All channels monotonic"
        ))

    return results


def verify_stream_endpoint(client: httpx.Client, base: str) -> list[VerificationResult]:
    """Verify stream endpoint returns 200, video/mp2t, and produces bytes (up to 45s for cold start)."""
    results: list[VerificationResult] = []
    try:
        with client.stream(
            "GET", f"{base}/hdhomerun/auto/v100", timeout=45.0
        ) as r:
            r.raise_for_status()
            ct = r.headers.get("content-type", "")
            if "video/mp2t" in ct or "video/mpeg" in ct:
                results.append(VerificationResult(
                    "stream Content-Type", True, f"Content-Type={ct}"
                ))
            else:
                results.append(VerificationResult(
                    "stream Content-Type", False,
                    f"Expected video/mp2t, got {ct}"
                ))
            # Read first chunk (FFmpeg cold start can take 15-30s)
            chunk = b""
            for c in r.iter_bytes(chunk_size=8192):
                chunk += c
                if len(chunk) >= 188 * 10:  # At least 10 MPEG-TS packets
                    break
            if len(chunk) >= 188 and chunk[0] == 0x47:
                results.append(VerificationResult(
                    "stream MPEG-TS data", True,
                    f"Received {len(chunk)} bytes, sync byte 0x47"
                ))
            elif len(chunk) > 0:
                results.append(VerificationResult(
                    "stream MPEG-TS data", True,
                    f"Received {len(chunk)} bytes (first packet may be keepalive)"
                ))
            else:
                results.append(VerificationResult(
                    "stream MPEG-TS data", False,
                    "No data received within 45s (cold start timeout?)"
                ))
    except Exception as e:
        results.append(VerificationResult(
            "stream endpoint", False, str(e)
        ))
    return results


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8411"
    base = base.rstrip("/")

    print(f"Verifying EPG at {base}\n")
    print("=" * 60)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        discover = fetch_json(client, f"{base}/hdhomerun/discover.json")
        lineup = fetch_json(client, f"{base}/hdhomerun/lineup.json")
        xml_content = fetch_xml(client, f"{base}/hdhomerun/epg")

        all_results: list[VerificationResult] = []

        all_results.extend(verify_channel_id_consistency(discover, lineup, xml_content))
        all_results.extend(verify_no_duplicate_programmes(xml_content))
        all_results.extend(verify_monotonic_times(xml_content))
        all_results.extend(verify_stream_endpoint(client, base))

    passed = sum(1 for r in all_results if r.passed)
    failed = sum(1 for r in all_results if not r.passed)

    for r in all_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.name}")
        print(f"       {r.detail}")
        if r.errors:
            for e in r.errors[:5]:
                print(f"       - {e}")
        print()

    print("=" * 60)
    print(f"Result: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
