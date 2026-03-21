#!/usr/bin/env python3
"""
Section F — Async Correctness Verification.

Scans for:
- time.sleep in async functions (should use asyncio.sleep)
- get_sync_session in async functions (blocks event loop; use run_in_executor or async engine)

Usage:
  python verify_async_correctness.py           # Scan all, report, exit 1 if violations
  python verify_async_correctness.py --scope    # Only ai_agent, metadata, monitoring
  python verify_async_correctness.py --baseline N  # Fail if violation count > N
"""

import argparse
import ast
import sys
from pathlib import Path

SCOPE_PATHS = ("exstreamtv/ai_agent", "exstreamtv/metadata", "exstreamtv/monitoring")


def _in_scope(rel: str, scope_only: bool) -> bool:
    if not scope_only:
        return True
    return any(rel.replace("\\", "/").startswith(p) for p in SCOPE_PATHS)


def find_async_functions_with_violations(
    root: Path,
    scope_only: bool = False,
) -> list[tuple[str, int, str]]:
    """Find async functions containing time.sleep or get_sync_session."""
    violations: list[tuple[str, int, str]] = []

    for py_path in root.rglob("*.py"):
        if "Build" in str(py_path) or "__pycache__" in str(py_path):
            continue
        rel = str(py_path.relative_to(root)).replace("\\", "/")
        if not _in_scope(rel, scope_only):
            continue

        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef):
                source_slice = ast.get_source_segment(
                    py_path.read_text(encoding="utf-8", errors="replace"),
                    node,
                    padded=True,
                ) or ""
                if "time.sleep" in source_slice:
                    violations.append((rel, node.lineno, "time.sleep in async function"))
                if "get_sync_session" in source_slice:
                    violations.append(
                        (rel, node.lineno, "get_sync_session in async function")
                    )

    return violations


def main() -> int:
    """Run async correctness scan."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scope",
        action="store_true",
        help="Only scan ai_agent, metadata, monitoring",
    )
    parser.add_argument(
        "--baseline",
        type=int,
        default=None,
        help="Pass if violation count <= baseline (for CI)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    violations = find_async_functions_with_violations(root, scope_only=args.scope)

    if violations:
        print("Async correctness violations:")
        for path, line, msg in violations:
            print(f"  {path}:{line}: {msg}")
        print(f"Total: {len(violations)}")
        if args.baseline is not None:
            if len(violations) > args.baseline:
                print(f"FAIL: {len(violations)} > baseline {args.baseline}")
                return 1
            return 0
        return 1

    print("Async correctness verification passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
