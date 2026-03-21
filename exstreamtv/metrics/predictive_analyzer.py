"""
Predictive anomaly detection. Lightweight deterministic model.
Forecasts health degradation before it occurs.
"""

from typing import Any

DRIFT_SLOPE_WEIGHT = 0.35
MISMATCH_VELOCITY_WEIGHT = 0.35
REBUILD_ACCELERATION_WEIGHT = 0.30


def _linear_regression_slope(x: list[float], y: list[float]) -> float:
    """Least-squares slope. Empty returns 0."""
    n = len(x)
    if n < 2 or len(y) != n:
        return 0.0
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(a * b for a, b in zip(x, y))
    sum_xx = sum(a * a for a in x)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def analyze_health_trend(
    history_events: dict[str, Any],
    metrics_state: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute composite instability score from drift, mismatch, rebuild trends.
    Returns risk_score (0-100), forecast, prediction_text.
    """
    drift_60m = history_events.get("drift_deltas_60m") or []
    mismatch_by_hour = history_events.get("mismatch_by_hour") or []
    rebuild_by_hour = history_events.get("rebuild_by_hour") or []
    interventions_by_hour = history_events.get("interventions_by_hour") or []

    # 1) Drift slope over last 60 minutes
    n_drift = min(60, len(drift_60m))
    drift_slope = 0.0
    if n_drift >= 2:
        x = list(range(n_drift))
        y = [float(d) for d in drift_60m[-n_drift:]]
        drift_slope = _linear_regression_slope(x, y)

    # 2) Mismatch velocity (per hour delta)
    velocity = 0.0
    if len(mismatch_by_hour) >= 2:
        recent = mismatch_by_hour[-6:]  # last 6 hours
        if len(recent) >= 2:
            velocity = (recent[-1] - recent[0]) / max(1, len(recent) - 1)

    # 3) Rebuild acceleration (change in freq over last 6h)
    accel = 0.0
    if len(rebuild_by_hour) >= 6:
        first_half = sum(rebuild_by_hour[-6:-3]) if len(rebuild_by_hour) >= 6 else 0
        second_half = sum(rebuild_by_hour[-3:])
        accel = second_half - first_half

    # Normalize components to rough 0-1 scale
    # Drift slope: typical values ~1e-6 to 1e-2; use cap
    norm_drift = min(1.0, max(0, abs(drift_slope) * 1000))
    # Velocity: 0-5 per hour typical; cap at 1
    norm_velocity = min(1.0, max(0, velocity / 5.0))
    # Accel: -5 to +10 typical; shift and scale
    norm_accel = min(1.0, max(0, (accel + 5) / 15))

    instability = (
        DRIFT_SLOPE_WEIGHT * norm_drift
        + MISMATCH_VELOCITY_WEIGHT * norm_velocity
        + REBUILD_ACCELERATION_WEIGHT * norm_accel
    )
    risk_score = min(100, max(0, int(instability * 100)))

    if risk_score <= 30:
        forecast = "Stable"
        prediction_text = (
            "System stability trend is normal. No degradation predicted."
        )
    elif risk_score <= 60:
        forecast = "Elevated Risk"
        prediction_text = (
            "Increasing schedule rebuild frequency detected. Monitoring recommended."
        )
    else:
        forecast = "High Risk"
        prediction_text = (
            "Rapid correction activity detected. System health likely to degrade if trend continues."
        )

    return {
        "risk_score": risk_score,
        "forecast": forecast,
        "prediction_text": prediction_text,
        "components": {
            "drift_slope": round(drift_slope, 8),
            "mismatch_velocity": round(velocity, 2),
            "rebuild_acceleration": round(accel, 2),
        },
    }
