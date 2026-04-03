#!/usr/bin/env python3
"""
Section E — Restart Path Verification CI Check.

Verifies: All restart paths route through request_channel_restart().
No direct stop_channel/start_channel calls except in:
- channel_manager.py (definitions)
- health_tasks.py (only caller for restart path)
- hdhomerun/api_v2.py (start_channel for initial tune only - not restart)
- tests (mocks and invariant checks)
"""

import re
import sys
from pathlib import Path


ALLOWED_PATTERNS = [
    r"channel_manager\.py",
    r"health_tasks\.py",
    r"hdhomerun[/\\]api_v2\.py",  # start_channel for initial tune, not restart
    r"patterns[/\\]state[/\\]channel_context\.py",  # spawn_ffmpeg lifecycle, not agent restart
    r"[/\\]tests[/\\]",
    r"[/\\]Build[/\\]",  # legacy build artifacts
]

EXCLUDED_LINE_PATTERNS = [
    r"^\s*#",           # comment
    r"def\s+\w*stop_channel|async def\s+\w*stop_channel",
    r"def\s+\w*start_channel|async def\s+\w*start_channel",
    r"restart_channel",  # tool name, not direct call
    r'"[^"]*stop_channel[^"]*"',
    r'"[^"]*start_channel[^"]*"',
    r"'\w*stop_channel\w*'",
    r"'\w*start_channel\w*'",
]


def is_allowed_file(filepath: str) -> bool:
    """Check if file is in allowed list."""
    normalized = filepath.replace("\\", "/")
    for pat in ALLOWED_PATTERNS:
        if re.search(pat, normalized):
            return True
    return False


def is_excluded_line(line: str) -> bool:
    """Check if line is excluded (comment, def, string literal)."""
    for pat in EXCLUDED_LINE_PATTERNS:
        if re.search(pat, line):
            return True
    return False


def is_direct_call(line: str) -> bool:
    """Check if line contains direct .stop_channel( or .start_channel( call."""
    if ".stop_channel(" in line or ".start_channel(" in line:
        return True
    return False


def main() -> int:
    """Run restart path verification. Returns 0 if pass, 1 if fail."""
    root = Path(__file__).resolve().parent.parent
    violations: list[tuple[str, int, str]] = []

    for py_path in root.rglob("*.py"):
        if "Build" in str(py_path):
            continue
        rel = str(py_path.relative_to(root)).replace("\\", "/")
        if is_allowed_file(rel):
            continue

        try:
            text = py_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for i, line in enumerate(text.splitlines(), 1):
            if is_excluded_line(line):
                continue
            if is_direct_call(line):
                violations.append((rel, i, line.strip()[:80]))

    if violations:
        print("Restart path verification FAILED.")
        print("Direct stop_channel/start_channel calls must only be in:")
        print("  - channel_manager.py (definitions)")
        print("  - health_tasks.py (_trigger_channel_restart)")
        print("  - hdhomerun/api_v2.py (start_channel for initial tune)")
        print("  - tests (mocks)")
        print()
        for path, num, content in violations:
            print(f"  {path}:{num}: {content}")
        return 1

    print("Restart path verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
