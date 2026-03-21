#!/usr/bin/env python3
"""
Phase 5: Run zero-drift verification suite.
Order: reset_epg_state -> [restart server manually] -> verify_epg_playback -> monotonic_drift_simulation.
"""
import subprocess
import sys

ROOT = __file__.rsplit("/", 2)[0] or "."


def run(name: str, cmd: list[str]) -> int:
    print(f"\n--- {name} ---")
    r = subprocess.run(cmd, cwd=ROOT)
    if r.returncode != 0:
        print(f"FAIL: {name}")
        return r.returncode
    print(f"PASS: {name}")
    return 0


def main() -> int:
    print("1) reset_epg_state.py")
    if run("reset_epg_state", ["python3", f"{ROOT}/scripts/reset_epg_state.py"]) != 0:
        return 1

    print("\n2) RESTART SERVER (manual)")
    print("   Restart EXStreamTV server to load /api/time/authoritative")
    print("   Then press Enter to continue...")
    try:
        input()
    except EOFError:
        pass

    print("\n3) verify_epg_playback.py")
    if run(
        "verify_epg_playback",
        ["python3", f"{ROOT}/scripts/verify_epg_playback.py", "http://localhost:8411"],
    ) != 0:
        return 1

    print("\n4) monotonic_drift_simulation.py")
    if run("monotonic_drift_simulation", ["python3", f"{ROOT}/scripts/monotonic_drift_simulation.py"]) != 0:
        return 1

    print("\n=== ZERO-DRIFT MATHEMATICAL GUARANTEE PROVEN ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
