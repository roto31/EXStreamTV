#!/usr/bin/env python3
"""
Automatically fix enabled channels that have no streamable content.

For each empty channel (no active playout with items and no usable filler):
- Prefer assigning an existing filler preset that has items or a collection.
- If no such preset exists, create a default filler preset using a playlist
  that has items and assign it to the channel.

Usage:
    python3 scripts/fix_empty_channels.py [--db-path PATH] [--dry-run]

Options:
    --db-path    Path to exstreamtv.db (auto-detected if not specified)
    --dry-run    Only report what would be done; do not modify the database
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

# Allow importing list_channels_no_content when run as scripts/fix_empty_channels.py
sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_channels_no_content import get_db_path, list_channels_no_content


def get_playlist_with_items(cursor: sqlite3.Cursor) -> Optional[int]:
    """Return a playlist_id that has at least one playlist_item, or None."""
    cursor.execute("""
        SELECT playlist_id
        FROM playlist_items
        GROUP BY playlist_id
        ORDER BY COUNT(*) DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    return row[0] if row else None


def get_filler_preset_with_content(cursor: sqlite3.Cursor) -> Optional[int]:
    """
    Return a filler preset id that has either preset items or a collection
    with playlist items. Otherwise None.
    """
    cursor.execute("SELECT id, name, collection_id FROM filler_presets")
    for row in cursor.fetchall():
        preset_id, _name, collection_id = row
        cursor.execute(
            "SELECT 1 FROM filler_preset_items WHERE preset_id = ? LIMIT 1",
            (preset_id,),
        )
        if cursor.fetchone():
            return preset_id
        if collection_id:
            cursor.execute(
                "SELECT 1 FROM playlist_items WHERE playlist_id = ? LIMIT 1",
                (collection_id,),
            )
            if cursor.fetchone():
                return preset_id
    return None


def create_default_filler_preset(
    conn: sqlite3.Connection,
    playlist_id: int,
    name: str = "Default Filler (auto)",
) -> int:
    """
    Create a filler preset that uses the given playlist as collection.
    Returns the new preset id.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO filler_presets (
            name, filler_mode, playback_order, allow_repeats, allow_watermarks,
            collection_id, created_at, updated_at
        ) VALUES (?, 'duration', 'shuffled', 1, 1, ?, ?, ?)
        """,
        (name, playlist_id, now, now),
    )
    conn.commit()
    return cursor.lastrowid


def assign_filler_to_channel(
    conn: sqlite3.Connection,
    channel_id: int,
    filler_preset_id: int,
) -> None:
    """Set channel fallback_filler_id to the given preset."""
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE channels SET fallback_filler_id = ? WHERE id = ?",
        (filler_preset_id, channel_id),
    )
    conn.commit()


def fix_empty_channels(
    db_path: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Detect empty channels and fix them by assigning filler (or creating one).

    Returns a report dict: fixed, fallbacks_applied, still_empty, actions, log.
    """
    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "dry_run": dry_run,
        "fixed": [],
        "fallbacks_applied": [],
        "still_empty": [],
        "actions": [],
        "log": [],
    }

    def log(msg: str) -> None:
        report["log"].append(msg)

    no_content = list_channels_no_content(db_path)
    if not no_content:
        log("No channels with no content; nothing to fix.")
        return report

    channel_ids = [ch["id"] for ch in no_content]
    log(f"Found {len(no_content)} channel(s) with no content: {[ch['number'] for ch in no_content]}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Prefer reusing an existing filler preset that has content
        existing_preset_id = get_filler_preset_with_content(cursor)
        preset_id: Optional[int] = None
        preset_created = False

        if existing_preset_id:
            cursor.execute(
                "SELECT name FROM filler_presets WHERE id = ?",
                (existing_preset_id,),
            )
            row = cursor.fetchone()
            preset_name = row[0] if row else "Filler"
            preset_id = existing_preset_id
            log(f"Using existing filler preset id={existing_preset_id} ({preset_name})")
        else:
            # Create a new preset from a playlist that has items
            playlist_id = get_playlist_with_items(cursor)
            if not playlist_id:
                log("No playlist with items found; cannot create filler preset.")
                report["still_empty"] = [dict(ch) for ch in no_content]
                return report
            if dry_run:
                report["actions"].append(
                    f"Would create filler preset with collection_id={playlist_id} and assign to channel(s) {channel_ids}"
                )
                log("Dry run: would create default filler preset and assign to empty channels.")
                return report
            preset_id = create_default_filler_preset(conn, playlist_id)
            preset_created = True
            report["fallbacks_applied"].append(
                {"preset_id": preset_id, "collection_id": playlist_id, "created": True}
            )
            log(f"Created filler preset id={preset_id} with collection_id={playlist_id}")

        if preset_id and not dry_run:
            for ch in no_content:
                cid = ch["id"]
                assign_filler_to_channel(conn, cid, preset_id)
                report["fixed"].append(
                    {"channel_id": cid, "number": ch["number"], "name": ch["name"], "filler_preset_id": preset_id}
                )
                report["actions"].append(
                    f"Assigned filler preset {preset_id} to channel #{ch['number']} (id={cid}) {ch['name']}"
                )
                log(f"Assigned filler preset {preset_id} to channel {cid} (#{ch['number']})")

    finally:
        conn.close()

    # Re-validate
    still = list_channels_no_content(db_path)
    report["still_empty"] = [dict(ch) for ch in still]
    if still:
        log(f"After fix: {len(still)} channel(s) still have no content (validation).")
    else:
        log("All previously empty channels now have content (filler).")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fix enabled channels with no streamable content by assigning filler"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to exstreamtv.db (auto-detected if not specified)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done",
    )
    parser.add_argument(
        "--report",
        type=Path,
        metavar="FILE",
        help="Write JSON report to FILE for QA tracking",
    )
    args = parser.parse_args()

    try:
        db_path = get_db_path(args.db_path)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1

    report = fix_empty_channels(db_path, dry_run=args.dry_run)

    if getattr(args, "report", None):
        import json
        report_path = args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(
                {
                    "timestamp": report["timestamp"],
                    "db_path": report["db_path"],
                    "dry_run": report["dry_run"],
                    "fixed": report["fixed"],
                    "fallbacks_applied": report["fallbacks_applied"],
                    "still_empty": report["still_empty"],
                    "actions": report["actions"],
                    "log": report["log"],
                },
                f,
                indent=2,
            )
        print(f"Report written to {report_path}", file=sys.stderr)

    print("Fix Empty Channels Report")
    print("=" * 60)
    print(f"Time:     {report['timestamp']}")
    print(f"DB:       {report['db_path']}")
    print(f"Dry run:  {report['dry_run']}")
    print()
    for line in report["log"]:
        print(f"  {line}")
    print()
    if report["fixed"]:
        print("Channels fixed:")
        for x in report["fixed"]:
            print(f"  #{x['number']} (id={x['channel_id']}) {x['name']} -> filler_preset_id={x['filler_preset_id']}")
    if report["fallbacks_applied"]:
        print("Fallbacks applied:")
        for x in report["fallbacks_applied"]:
            print(f"  Preset id={x.get('preset_id')} collection_id={x.get('collection_id')} created={x.get('created', False)}")
    if report["still_empty"]:
        print("Channels still empty:")
        for ch in report["still_empty"]:
            print(f"  #{ch['number']} (id={ch['id']}) {ch['name']} -> {ch.get('reason', '')}")
    print("=" * 60)

    return 0 if not report["still_empty"] else 2


if __name__ == "__main__":
    sys.exit(main())
