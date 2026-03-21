#!/usr/bin/env python3
"""
Run Broadcast Alignment Validation Harness.

Usage:
  python scripts/run_alignment_validation.py [--base-url URL] [--output-dir DIR]
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8411")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/alignment"))
    parser.add_argument("--drift", action="store_true", help="Run full drift monitor (10 min)")
    args = parser.parse_args()

    from tests.integration.broadcast_alignment.alignment_runner import run_alignment_validation

    summary = await run_alignment_validation(
        base_url=args.base_url,
        output_dir=args.output_dir,
        run_drift_monitor_full=args.drift,
    )
    print("Summary:", summary)
    return 0 if summary.get("passed", False) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
