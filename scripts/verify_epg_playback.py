#!/usr/bin/env python3
"""
Verify EPG vs playback alignment.
Strict comparator: start_epoch <= now_epoch < stop_epoch
"""
import asyncio
import sys
import time
from xml.etree import ElementTree as ET

sys.path.insert(0, str(__file__).rsplit("/", 2)[0] or ".")


def _parse_xmltv_epoch(s: str) -> float | None:
    """Parse XMLTV datetime to UTC epoch (robust: canonical, compact, ISO8601)."""
    try:
        from exstreamtv.utils.xmltv_parse import parse_xmltv_datetime_to_epoch
        return parse_xmltv_datetime_to_epoch(s)
    except ImportError:
        return None


async def main(base_url: str = "http://localhost:8411") -> tuple[bool, str]:
    base_url = base_url.rstrip("/")
    epg_url = f"{base_url}/iptv/xmltv.xml"

    from datetime import datetime, timezone
    from urllib.request import urlopen, Request

    req_auth = Request(
        f"{base_url}/api/time/authoritative",
        headers={"User-Agent": "EXStreamTV-Verify/1.0"},
    )
    with urlopen(req_auth, timeout=5) as ra:
        data = __import__("json").loads(ra.read().decode())
        now_epoch = float(data["now_epoch"])
    utc_now = datetime.now(timezone.utc)
    monotonic_now = time.monotonic()

    req = Request(epg_url, headers={"User-Agent": "EXStreamTV-Verify/1.0"})
    with urlopen(req, timeout=15) as r:
        xml_text = r.read().decode("utf-8", errors="replace")

    root = ET.fromstring(xml_text)
    programmes = root.findall(".//programme")

    current_by_channel: dict[str, str] = {}
    for prog in programmes:
        start = prog.get("start", "")
        stop = prog.get("stop", "")
        channel = prog.get("channel", "")
        title_el = prog.find("title")
        title = title_el.text if title_el is not None and title_el.text else ""

        if not channel:
            continue
        start_epoch = _parse_xmltv_epoch(start)
        stop_epoch = _parse_xmltv_epoch(stop)
        if start_epoch is None or stop_epoch is None:
            continue
        if start_epoch <= now_epoch < stop_epoch:
            current_by_channel[channel] = title

    from exstreamtv.database import get_sync_session, get_sync_session_factory
    from exstreamtv.database.models import Channel
    from exstreamtv.streaming.resolution_service import get_resolution_service

    factory = get_sync_session_factory()
    svc = get_resolution_service(factory)

    with get_sync_session() as session:
        channels = session.query(Channel).filter(Channel.enabled == True).order_by(Channel.number).all()

    all_match = True
    buf = ["EPG vs Playback alignment:\n", f"{'Channel':<12} {'EPG Title':<40} {'Playback':<40} {'Match'}", "-" * 100]

    for ch in channels:
        ch_id_xmltv = str(ch.number) if ch.number else f"exstream-{ch.id}"
        epg_title = current_by_channel.get(ch_id_xmltv, "(no programme)")
        playback_title = "(unavailable)"
        active_item = None
        try:
            result = await svc.resolve_for_streaming(ch.id)
            if result and result.stream_source:
                playback_title = result.title or "(unknown)"
                active_item = result.title
            else:
                playback_title = "(no stream)"
        except Exception as e:
            playback_title = f"(error: {e!s})"
        match = "OK" if epg_title == playback_title else "MISMATCH"
        if match == "MISMATCH":
            all_match = False
        buf.append(f"{ch.number!s:<12} {epg_title[:38]:<40} {playback_title[:38]:<40} {match}")

    print("\n".join(buf))
    if not all_match:
        print("\n[DIAGNOSTIC]")
        print(f"utc_now: {utc_now.isoformat()}")
        print(f"monotonic_now: {monotonic_now}")
        print(f"now_epoch: {now_epoch}")
        for ch in channels:
            ch_id = str(ch.number) if ch.number else f"exstream-{ch.id}"
            epg = current_by_channel.get(ch_id, "(none)")
            print(f"  ch {ch.number}: XMLTV active='{epg}'")
    print("\nDone.")
    return all_match, "PASS" if all_match else "FAIL"


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8411"
    ok, status = asyncio.run(main(url))
    sys.exit(0 if ok else 1)
