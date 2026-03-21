#!/usr/bin/env python3
"""
Parse EXStreamTV debug log and print what is currently streaming per channel.

Compares "Actually streaming" (from the channel stream loop) with "Guide/EPG says"
(from the xmltv EPG first programme) for troubleshooting guide sync issues.

Usage:
    python scripts/parse_stream_vs_guide.py
    python scripts/parse_stream_vs_guide.py --log /path/to/debug.log
    python scripts/parse_stream_vs_guide.py --streaming-only   # only show actual stream titles
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

# Project root (parent of scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG = PROJECT_ROOT / ".cursor" / "debug.log"

# Log message identifiers
STREAM_LOOP_PLAYING = "channel_manager.py:_stream_loop:playing"
EPG_FIRST_PROGRAMME = "iptv.py:xmltv:db_path_first_programme"


def parse_log(log_path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """
    Parse debug log and return last "Now playing" and last "first programme" per channel.

    Returns:
        Tuple of (playing_by_channel, guide_by_channel). Each dict key is channel_number (str);
        values are the data dicts from the log (title/first_title, timestamps, etc.).
    """
    playing_by_channel: dict[str, dict[str, Any]] = {}
    guide_by_channel: dict[str, dict[str, Any]] = {}

    if not log_path.exists():
        return playing_by_channel, guide_by_channel

    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            loc = obj.get("location", "")
            data = obj.get("data", {})
            ch = data.get("channel_number")
            if ch is None:
                continue
            ch_str = str(ch)

            if STREAM_LOOP_PLAYING in loc and obj.get("message") == "Now playing item":
                playing_by_channel[ch_str] = {
                    "title": data.get("title"),
                    "current_item_index": data.get("current_item_index"),
                    "timestamp": obj.get("timestamp"),
                }
            if EPG_FIRST_PROGRAMME in loc:
                guide_by_channel[ch_str] = {
                    "first_title": data.get("first_title"),
                    "current_item_start": data.get("current_item_start"),
                    "time_into_item": data.get("time_into_item"),
                    "timestamp": obj.get("timestamp"),
                }

    return playing_by_channel, guide_by_channel


def channel_sort_key(ch: str) -> tuple[int, float]:
    """Sort channel numbers numerically where possible, else lexicographically."""
    try:
        return (0, float(ch))
    except ValueError:
        return (1, float("inf"))  # non-numeric at end


def truncate(s: str, max_len: int) -> str:
    """Truncate string with ellipsis if over max_len."""
    if not s:
        return "—"
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def print_table(
    playing: dict[str, dict[str, Any]],
    guide: dict[str, dict[str, Any]],
    streaming_only: bool = False,
) -> None:
    """Print a table of channel vs streaming title and (optionally) guide title."""
    channels = sorted(set(playing) | set(guide), key=channel_sort_key)
    if not channels:
        print("No channel data found in log.")
        return

    width = 100
    if streaming_only:
        print("=" * 70)
        print("CURRENTLY STREAMING (from stream loop) – reference for troubleshooting")
        print("=" * 70)
        print(f"{'Channel':<12} {'Title':<55}")
        print("-" * 70)
        for ch in channels:
            p = playing.get(ch)
            title = truncate((p.get("title") or "—") if p else "—", 52)
            print(f"{ch:<12} {title:<55}")
    else:
        print("=" * width)
        print(
            "CURRENTLY STREAMING (from stream loop) vs GUIDE (EPG first programme) – "
            "reference for troubleshooting"
        )
        print("=" * width)
        print(
            f"{'Channel':<10} {'Actually streaming (title)':<52} {'Guide/EPG says (first_title)':<48} {'Match'}"
        )
        print("-" * width)
        for ch in channels:
            p = playing.get(ch)
            g = guide.get(ch)
            stream_title = truncate((p.get("title") or "—") if p else "—", 49)
            guide_title = truncate((g.get("first_title") or "—") if g else "—", 45)
            match = "✓" if (p and g and (p.get("title") == g.get("first_title"))) else ""
            print(f"{ch:<10} {stream_title:<52} {guide_title:<48} {match}")
        print("-" * width)
        print(
            "If \"Actually streaming\" and \"Guide/EPG says\" differ for a channel, "
            "the guide is out of sync."
        )


def main() -> int:
    """Run the parser and print the table."""
    parser = argparse.ArgumentParser(
        description="Parse EXStreamTV debug log and show what is playing per channel."
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=DEFAULT_LOG,
        help=f"Path to debug log (default: {DEFAULT_LOG})",
    )
    parser.add_argument(
        "--streaming-only",
        action="store_true",
        help="Only print what is actually streaming; do not compare with guide.",
    )
    args = parser.parse_args()

    log_path = args.log if args.log.is_absolute() else PROJECT_ROOT / args.log
    playing, guide = parse_log(log_path)
    print_table(playing, guide, streaming_only=args.streaming_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
