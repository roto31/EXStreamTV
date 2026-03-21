#!/usr/bin/env python3
"""
Clock Authority Validation Script.

Validates clock duration integrity after Broadcast Clock Authority cutover.
Run with server stopped or against running instance (uses DB + authority).

Usage:
  python scripts/validate_clock_authority.py
  EXSTREAMTV_VALIDATE_DURATIONS=1 python -m exstreamtv.main  # Run with assertions
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def validate_clock_duration_integrity() -> dict:
    """
    Phase 1: Clock Duration Integrity Validation.

    For ALL channels:
    - Call auth.ensure_clock(channel_id)
    - Validate total_cycle_duration > 0
    - Validate sum(canonical_duration) ≈ total_cycle_duration
    - Validate no canonical_duration == 0
    """
    from exstreamtv.database import get_sync_session_factory
    from exstreamtv.database.models import Channel
    from exstreamtv.scheduling import get_authority
    from sqlalchemy import select

    factory = get_sync_session_factory()
    session = factory()
    try:
        result = session.execute(select(Channel).where(Channel.enabled == True))
        channels = result.scalars().all()
    finally:
        session.close()

    auth = get_authority(factory)
    results: list[dict] = []
    failures: list[str] = []

    for ch in channels:
        channel_id = ch.id
        try:
            clock = await auth.ensure_clock(channel_id)
            timeline = auth.get_timeline(channel_id)

            if not clock:
                results.append({
                    "channel_id": channel_id,
                    "channel_number": ch.number,
                    "status": "NO_CLOCK",
                    "timeline_len": len(timeline) if timeline else 0,
                    "sum_duration": 0,
                    "total_cycle_duration": 0,
                    "zero_durations": 0,
                })
                continue  # No timeline = N/A for duration validation, not a failure

            sum_dur = sum(t.canonical_duration or 1800 for t in (timeline or []))
            total = clock.total_cycle_duration
            zero_count = sum(1 for t in (timeline or []) if not (t.canonical_duration or 0))
            none_count = sum(1 for t in (timeline or []) if t.canonical_duration is None)

            entry = {
                "channel_id": channel_id,
                "channel_number": ch.number,
                "status": "OK",
                "timeline_len": len(timeline) if timeline else 0,
                "sum_duration": round(sum_dur, 1),
                "total_cycle_duration": round(total, 1),
                "zero_durations": zero_count,
                "none_durations": none_count,
            }

            if total <= 0:
                entry["status"] = "FAIL"
                failures.append(f"ch{channel_id}: total_cycle_duration={total} <= 0")
            elif abs(sum_dur - total) > 1.0:
                entry["status"] = "DRIFT"
                failures.append(
                    f"ch{channel_id}: sum({sum_dur}) != total({total}), drift={abs(sum_dur - total):.1f}"
                )
            elif zero_count > 0:
                entry["status"] = "ZERO_DUR"
                failures.append(f"ch{channel_id}: {zero_count} items have canonical_duration=0")
            elif none_count > 0:
                entry["status"] = "NONE_DUR"
                failures.append(f"ch{channel_id}: {none_count} items have canonical_duration=None")

            results.append(entry)
        except Exception as e:
            results.append({
                "channel_id": channel_id,
                "channel_number": ch.number,
                "status": "ERROR",
                "error": str(e),
            })
            failures.append(f"ch{channel_id}: {e}")

    no_clock = sum(1 for r in results if r.get("status") == "NO_CLOCK")
    return {
        "channels_checked": len(channels),
        "channels_with_clock": len(channels) - no_clock,
        "channels_no_clock": no_clock,
        "results": results,
        "failures": failures,
        "passed": len(failures) == 0,
    }


async def run_rebuild_validation() -> dict:
    """Phase 3: Rebuild logic validation - run rebuild task, expect rebuilt=0 or minimal."""
    from exstreamtv.tasks.playout_tasks import rebuild_playouts_task

    stats = await rebuild_playouts_task()
    total = stats.get("channels_checked", 0)
    rebuilt = stats.get("channels_rebuilt", 0)
    rebuild_pct = (rebuilt / total * 100) if total else 0

    return {
        "channels_checked": total,
        "channels_rebuilt": rebuilt,
        "rebuild_pct": round(rebuild_pct, 2),
        "passed": rebuild_pct <= 5.0,
        "stats": stats,
    }


async def main() -> int:
    print("=" * 60)
    print("CLOCK AUTHORITY VALIDATION")
    print("=" * 60)

    print("\n--- Phase 1: Clock Duration Integrity ---")
    phase1 = await validate_clock_duration_integrity()
    for r in phase1["results"][:20]:
        print(f"  ch{r['channel_id']} ({r.get('channel_number','?')}): "
              f"len={r.get('timeline_len',0)} sum={r.get('sum_duration',0):.0f}s "
              f"total={r.get('total_cycle_duration',0):.0f}s status={r.get('status','?')}")
    if len(phase1["results"]) > 20:
        print(f"  ... and {len(phase1['results']) - 20} more")
    if phase1["failures"]:
        print("  FAILURES:", phase1["failures"])
    else:
        print("  All channels passed (A-E)")

    print("\n--- Phase 3: Rebuild Logic ---")
    phase3 = await run_rebuild_validation()
    print(f"  Checked: {phase3['channels_checked']}, Rebuilt: {phase3['channels_rebuilt']} "
          f"({phase3['rebuild_pct']}%)")
    print(f"  Passed: {phase3['passed']}")

    print("\n" + "=" * 60)
    all_ok = phase1["passed"] and phase3["passed"]
    print("OVERALL:", "PASSED" if all_ok else "FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
