#!/usr/bin/env python3
"""
IPTV diagnostic script for "Stream Unavailable" troubleshooting.

Usage:
  python scripts/iptv_diagnostic.py [base_url]

Examples:
  python scripts/iptv_diagnostic.py
  python scripts/iptv_diagnostic.py http://192.168.1.120:8411
"""
import json
import sys
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


def check(base_url: str) -> None:
    base_url = base_url.rstrip("/")
    playlist_url = f"{base_url}/iptv/channels.m3u"
    xmltv_url = f"{base_url}/iptv/xmltv.xml"
    health_url = f"{base_url}/api/health/detailed"

    print(f"Checking IPTV endpoints at {base_url}\n")

    # 0. Health (ChannelManager status)
    print("0. Health / ChannelManager")
    try:
        req = Request(health_url, headers={"User-Agent": "EXStreamTV-Diagnostic/1.0"})
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        cm = data.get("components", {}).get("channel_manager", {})
        status = cm.get("status", "unknown")
        print(f"   ChannelManager: {status}")
        if status == "not-initialized":
            print("   CAUSE: ChannelManager failed at startup - check server logs for traceback")
    except Exception as e:
        print(f"   ERROR: {e}")

    # 1. Playlist
    print("1. Playlist (/iptv/channels.m3u)")
    try:
        req = Request(playlist_url, headers={"User-Agent": "EXStreamTV-Diagnostic/1.0"})
        with urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
            ct = r.headers.get("Content-Type", "")
            status = r.status

        print(f"   Status: {status}")
        print(f"   Content-Type: {ct}")

        if "mpegurl" not in ct.lower() and "m3u" not in ct.lower():
            print(f"   WARNING: Expected audio/x-mpegurl or application/vnd.apple.mpegurl")

        if not content.strip().startswith("#EXTM3U"):
            print(f"   ERROR: Missing #EXTM3U header")
        else:
            lines = content.strip().split("\n")
            extinf = [l for l in lines if l.startswith("#EXTINF")]
            print(f"   Channels: {len(extinf)}")

        # Check first stream URL
        for i, line in enumerate(lines):
            line = line.strip()
            if line and not line.startswith("#") and line.startswith("http"):
                print(f"   Sample stream URL: {line[:80]}...")
                if "localhost" in line or "127.0.0.1" in line:
                    print(f"   WARNING: Stream URL uses localhost - may fail when client is on different machine")
                break
    except HTTPError as e:
        print(f"   ERROR: HTTP {e.code} - {e.reason}")
    except URLError as e:
        print(f"   ERROR: {e.reason}")

    # 2. XMLTV
    print("\n2. XMLTV (/iptv/xmltv.xml)")
    try:
        req = Request(xmltv_url, headers={"User-Agent": "EXStreamTV-Diagnostic/1.0"})
        with urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
            status = r.status
        print(f"   Status: {status}")
        if "<tv" in content:
            print(f"   OK: Valid XMLTV")
        else:
            print(f"   WARNING: Unexpected content")
    except HTTPError as e:
        print(f"   ERROR: HTTP {e.code} - {e.reason}")
    except URLError as e:
        print(f"   ERROR: {e.reason}")

    # 3. Stream probe (optional - just HEAD)
    print("\n3. Stream probe (first channel .ts)")
    try:
        req = Request(playlist_url, headers={"User-Agent": "EXStreamTV-Diagnostic/1.0"})
        with urlopen(req, timeout=10) as r:
            content = r.read().decode("utf-8", errors="replace")
        lines = content.strip().split("\n")
        stream_url = None
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and ".ts" in line and line.startswith("http"):
                stream_url = line.split("?")[0]
                break
        if stream_url:
            req = Request(stream_url, method="HEAD", headers={"User-Agent": "EXStreamTV-Diagnostic/1.0"})
            try:
                with urlopen(req, timeout=5) as r:
                    print(f"   Status: {r.status}")
                    if r.status == 503:
                        print(f"   CAUSE: ChannelManager not initialized - check server startup logs")
                    elif r.status == 200:
                        print(f"   OK: Stream reachable")
            except HTTPError as he:
                if he.code == 405:
                    print(f"   Status: 405 (HEAD not supported - server may need restart)")
                    print(f"   Fallback: Trying GET...")
                    req_get = Request(stream_url, headers={"User-Agent": "EXStreamTV-Diagnostic/1.0"})
                    try:
                        with urlopen(req_get, timeout=5) as rg:
                            print(f"   GET Status: {rg.status}")
                            if rg.status == 200:
                                print(f"   OK: Stream reachable (restart server for HEAD support)")
                    except HTTPError as ge:
                        print(f"   GET Status: {ge.code} - {ge.reason}")
                else:
                    raise
        else:
            print(f"   Skip: No .ts stream URL in playlist")
    except HTTPError as e:
        print(f"   Status: {e.code}")
        if e.code == 503:
            hdr = e.headers.get("X-EXStreamTV-ChannelManager", "")
            if hdr == "not-initialized":
                print("   CAUSE: ChannelManager not initialized - check server startup logs")
            else:
                print("   CAUSE: Service unavailable - check server logs")
        elif e.code == 404:
            print("   CAUSE: Channel not found or not enabled")
    except URLError as e:
        print(f"   ERROR: {e.reason}")

    print("\nDone.")


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8411"
    check(base)
