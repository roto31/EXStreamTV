"""Background services for EXStreamTV."""

from __future__ import annotations

from typing import Any

__all__ = ["M3UTestingService"]


def __getattr__(name: str) -> Any:
    if name == "M3UTestingService":
        from .m3u_testing_service import M3UTestingService

        return M3UTestingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
