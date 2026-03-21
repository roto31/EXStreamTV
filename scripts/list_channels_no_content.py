#!/usr/bin/env python3
"""
List channels that have no streamable content (won't stream when tuned).

Channels need either:
- An active playout with at least one playout item, OR
- A fallback filler preset with at least one filler item (or collection)

This script reports enabled channels that have neither, so you can fix them
(e.g. assign a schedule, add playout items, or set a filler preset).

Usage:
    python scripts/list_channels_no_content.py [--db-path PATH]

Options:
    --db-path    Path to exstreamtv.db (auto-detected if not specified)
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional


def get_db_path(override: Optional[Path] = None) -> Path:
    """Get the EXStreamTV database path."""
    if override and override.exists():
        return override
    locations = [
        Path("exstreamtv.db"),
        Path(__file__).resolve().parent.parent / "exstreamtv.db",
    ]
    for path in locations:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find exstreamtv.db")


def list_channels_no_content(db_path: Path) -> List[dict]:
    """
    Find enabled channels that have no streamable content.

    Returns list of dicts with channel_id, number, name, reason.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Enabled channels
    cursor.execute("""
        SELECT id, number, name
        FROM channels
        WHERE enabled = 1
        ORDER BY CAST(number AS INTEGER), number
    """)
    channels = [dict(row) for row in cursor.fetchall()]

    no_content = []
    for ch in channels:
        cid = ch["id"]
        # Has active playout with at least one item?
        cursor.execute("""
            SELECT 1
            FROM playouts p
            JOIN playout_items pi ON pi.playout_id = p.id
            WHERE p.channel_id = ? AND p.is_active = 1
            LIMIT 1
        """, (cid,))
        if cursor.fetchone():
            continue
        # Has filler? (fallback_filler_id with preset items or collection)
        cursor.execute(
            "SELECT fallback_filler_id FROM channels WHERE id = ?",
            (cid,),
        )
        row = cursor.fetchone()
        filler_id = row[0] if row else None
        if filler_id:
            cursor.execute("""
                SELECT 1 FROM filler_preset_items
                WHERE preset_id = ?
                LIMIT 1
            """, (filler_id,))
            if cursor.fetchone():
                continue
            cursor.execute("""
                SELECT collection_id FROM filler_presets WHERE id = ?
            """, (filler_id,))
            row = cursor.fetchone()
            coll_id = row[0] if row else None
            if coll_id:
                cursor.execute("""
                    SELECT 1 FROM playlist_items
                    WHERE playlist_id = ?
                    LIMIT 1
                """, (coll_id,))
                if cursor.fetchone():
                    continue
        # No active playout with items, and no usable filler
        ch["reason"] = "no active playout with items and no usable filler"
        no_content.append(ch)

    conn.close()
    return no_content


def main():
    parser = argparse.ArgumentParser(
        description="List enabled channels that have no streamable content"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to exstreamtv.db (auto-detected if not specified)",
    )
    args = parser.parse_args()

    try:
        db_path = get_db_path(args.db_path)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    no_content = list_channels_no_content(db_path)
    if not no_content:
        print("All enabled channels have streamable content (playout items or filler).")
        return

    print(f"Channels with no streamable content ({len(no_content)}):")
    print("-" * 60)
    for ch in no_content:
        print(f"  #{ch['number']} (id={ch['id']}) {ch['name']}")
        print(f"    -> {ch['reason']}")
    print("-" * 60)
    print("Fix by: assigning a program schedule, adding playout items, or setting a filler preset.")
    sys.exit(0)


if __name__ == "__main__":
    main()
