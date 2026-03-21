"""Dual Authority Detector - Fail if index/journal authority detected."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

FORBIDDEN = ["_current_item_index", "_advance_atomic"]
EXCLUDE_PATHS = ("streaming/playout/journal.py", "database/", "migrations/")


def scan_for_dual_authority(project_root: Path | None = None) -> tuple[bool, list[str]]:
    root = project_root or Path(__file__).resolve().parent.parent.parent
    violations = []
    exstreamtv_src = root / "exstreamtv"
    if not exstreamtv_src.exists():
        return True, []
    scan_dirs = ["streaming", "scheduling", "api"]
    for py_file in exstreamtv_src.rglob("*.py"):
        if "tests" in str(py_file) or "Build" in str(py_file):
            continue
        rel = py_file.relative_to(root)
        path_str = str(rel)
        if not any(path_str.startswith(f"exstreamtv/{d}") for d in scan_dirs):
            continue
        if any(ep in path_str for ep in EXCLUDE_PATHS):
            continue
        try:
            content = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(content.splitlines(), 1):
                for pat in FORBIDDEN:
                    if pat in line and not line.strip().startswith("#"):
                        violations.append(f"{rel}:{i}: {pat}")
        except Exception as e:
            violations.append(f"{py_file}: {e}")
    return len(violations) == 0, violations
