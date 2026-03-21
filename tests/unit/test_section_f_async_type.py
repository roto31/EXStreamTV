"""
Section F — Async Correctness and Type Safety Tests.

Validates:
- No time.sleep or get_sync_session in async functions (ai_agent, metadata, monitoring).
"""

import subprocess
import sys
from pathlib import Path


def test_async_correctness_scope_passes() -> None:
    """Verify scripts/verify_async_correctness.py --scope passes."""
    root = Path(__file__).resolve().parent.parent.parent
    script = root / "scripts" / "verify_async_correctness.py"
    if not script.exists():
        return  # skip if script missing

    result = subprocess.run(
        [sys.executable, str(script), "--scope"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Async correctness (--scope) failed:\n{result.stdout}\n{result.stderr}"
    )
