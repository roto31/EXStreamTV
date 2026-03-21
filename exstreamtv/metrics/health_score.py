"""
Health score (0-100). Updated by health tasks. Read by adaptive controller.
"""

_health_score: float = 90.0


def set_health_score(score: float) -> None:
    global _health_score
    _health_score = max(0, min(100, score))


def get_health_score() -> float:
    return _health_score
