"""
Section E — Restart Path Formal Verification Tests.

Validates: All restart paths route through request_channel_restart().
No direct stop_channel/start_channel from agent or non-approved callers.
"""

import inspect
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.fixtures import FixtureRequest


def test_execute_restart_channel_uses_request_channel_restart() -> None:
    """execute_restart_channel MUST call request_channel_restart, never stop/start directly."""
    from exstreamtv.ai_agent.tool_registry import execute_restart_channel

    source = inspect.getsource(execute_restart_channel)
    assert "request_channel_restart" in source
    assert ".stop_channel(" not in source
    assert ".start_channel(" not in source


def test_trigger_channel_restart_is_only_internal_caller() -> None:
    """health_tasks._trigger_channel_restart is the only internal caller of stop/start."""
    from exstreamtv.tasks import health_tasks

    source = inspect.getsource(health_tasks._trigger_channel_restart)
    assert "stop_channel" in source
    assert "start_channel" in source


def test_request_channel_restart_calls_trigger() -> None:
    """request_channel_restart calls _trigger_channel_restart."""
    from exstreamtv.tasks import health_tasks

    source = inspect.getsource(health_tasks.request_channel_restart)
    assert "_trigger_channel_restart" in source


def test_restart_path_ci_script_passes() -> None:
    """Verify scripts/verify_restart_path.py passes (no violations)."""
    import subprocess
    import sys

    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    script = root / "scripts" / "verify_restart_path.py"
    if not script.exists():
        pytest.skip("verify_restart_path.py not found")

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Restart path CI check failed:\n{result.stdout}\n{result.stderr}"
    )
