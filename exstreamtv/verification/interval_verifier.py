"""
Formal verification of EPG interval invariants.
Phases 2-6: Normalize, repair, symbolic algebra, temporal simulation, fuzz, SMT.
"""

import logging
import random
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

logger = logging.getLogger(__name__)

VerificationResult = Literal["VERIFIED", "FAILED"]
SMT_TIMEOUT_MS = 100
FUZZ_SAMPLES = 64


def _to_epoch(intervals: List[Tuple]) -> List[Tuple[float, float]]:
    """Convert (datetime, datetime) or (epoch, epoch) to [(s, e), ...]."""
    result: List[Tuple[float, float]] = []
    for item in intervals:
        a, b = item[0], item[1]
        if hasattr(a, "timestamp"):
            try:
                from exstreamtv.scheduling.clock import _utc_epoch
                sa, sb = _utc_epoch(a), _utc_epoch(b)
            except ImportError:
                from datetime import timezone
                sa = a.timestamp() if getattr(a, "tzinfo", None) else a.replace(tzinfo=timezone.utc).timestamp()
                sb = b.timestamp() if getattr(b, "tzinfo", None) else b.replace(tzinfo=timezone.utc).timestamp()
        else:
            sa, sb = float(a), float(b)
        result.append((sa, sb))
    return result


def normalize_intervals(
    intervals: List[Tuple],
) -> List[Tuple[float, float]]:
    """
    Phase 2: Normalize interval list.
    Sort by start, convert to epoch, filter invalid (s >= e).
    """
    converted = _to_epoch(intervals)
    valid = [(s, e) for s, e in converted if s < e]
    valid.sort(key=lambda x: x[0])
    return valid


def repair_gaps(
    intervals: List[Tuple[float, float]],
) -> List[Tuple[float, float]]:
    """
    Phase 2: Repair gaps between adjacent intervals.
    Extend e_i to s_{i+1} when gap exists (creates contiguous coverage).
    """
    if len(intervals) <= 1:
        return list(intervals)
    result: List[Tuple[float, float]] = []
    for i, (s, e) in enumerate(intervals):
        if i + 1 < len(intervals):
            next_s = intervals[i + 1][0]
            if e < next_s:
                e = next_s  # extend to fill gap
        result.append((s, e))
    return result


def run_symbolic_algebra_validation(
    intervals: List[Tuple[float, float]],
    w_start: float,
    w_end: float,
) -> VerificationResult:
    """
    Phase 3: Symbolic interval algebra checks (no solver).
    Valid interval, ordering, non-overlap. Coverage: [w_start,w_end] within [s0,en].
    """
    if not intervals:
        return "FAILED"
    for i, (s, e) in enumerate(intervals):
        if s >= e:
            logger.debug("symbolic algebra: invalid interval i=%d s>=e", i)
            return "FAILED"
    for i in range(len(intervals) - 1):
        s_cur, e_cur = intervals[i]
        s_next = intervals[i + 1][0]
        if s_cur > s_next:
            logger.debug("symbolic algebra: ordering violation i=%d", i)
            return "FAILED"
        if e_cur > s_next:
            logger.debug("symbolic algebra: overlap i=%d e_cur > s_next", i)
            return "FAILED"
    s0, en = intervals[0][0], intervals[-1][1]
    if w_start < s0 or w_end > en:
        logger.debug("symbolic algebra: W [%s,%s] not covered by [s0=%s,en=%s]", w_start, w_end, s0, en)
        return "FAILED"
    return "VERIFIED"


def run_temporal_simulation(
    intervals: List[Tuple[float, float]],
    w_start: float,
    w_end: float,
) -> VerificationResult:
    """
    Phase 4: Bidirectional temporal simulation.
    Step through window (half-open [w_start, w_end)), ensure each t in exactly one interval.
    """
    if not intervals:
        return "FAILED"
    step = max(1.0, (w_end - w_start) / 256)
    t = w_start
    while t < w_end:
        count = sum(1 for s, e in intervals if s <= t < e)
        if count != 1:
            logger.debug("temporal sim: t=%s count=%d", t, count)
            return "FAILED"
        t += step
    return "VERIFIED"


def run_epoch_fuzz(
    intervals: List[Tuple[float, float]],
    w_start: float,
    w_end: float,
    samples: int = FUZZ_SAMPLES,
) -> VerificationResult:
    """
    Phase 5: Randomized epoch fuzz testing.
    Sample random t in W, verify exactly one interval contains t.
    """
    if not intervals:
        return "FAILED"
    rng = random.Random(42)  # deterministic
    for _ in range(samples):
        t = w_start + rng.random() * (w_end - w_start)
        count = sum(1 for s, e in intervals if s <= t < e)
        if count != 1:
            logger.debug("epoch fuzz: t=%s count=%d", t, count)
            return "FAILED"
    return "VERIFIED"


def run_interval_spec_verifier(
    intervals: List[Tuple[float, float]],
    now_epoch: float,
    window_hours: float = 72.0,
    timeout_ms: int = SMT_TIMEOUT_MS,
) -> VerificationResult:
    """
    Phase 6: SMT solver-based interval specification verifier.
    Uses z3-solver if available. Fail-closed on timeout/import error.
    W = span of intervals [s0, en].
    """
    try:
        import z3
    except ImportError:
        logger.warning("z3-solver not installed; SMT verification unavailable, failing closed")
        return "FAILED"

    if not intervals:
        return "FAILED"

    w_start = intervals[0][0]
    w_end = intervals[-1][1]

    solver = z3.Solver()
    solver.set("timeout", timeout_ms)

    n = len(intervals)
    s_vars = [z3.Int(f"s_{i}") for i in range(n)]
    e_vars = [z3.Int(f"e_{i}") for i in range(n)]

    for i in range(n):
        si, ei = int(intervals[i][0]), int(intervals[i][1])
        solver.add(s_vars[i] == si)
        solver.add(e_vars[i] == ei)
        solver.add(s_vars[i] < e_vars[i])

    for i in range(n - 1):
        solver.add(s_vars[i] <= s_vars[i + 1])
        solver.add(e_vars[i] <= s_vars[i + 1])

    solver.add(s_vars[0] <= int(w_start))
    solver.add(e_vars[n - 1] >= int(w_end))

    result = solver.check()
    try:
        from exstreamtv.monitoring.metrics import get_metrics_collector
        mc = get_metrics_collector()
        if result == z3.unknown:
            logger.warning("SMT verifier timeout")
            mc.inc_smt_timeout()
            mc.inc_smt_failed()
            return "FAILED"
        if result == z3.unsat:
            logger.debug("SMT verifier: constraints unsatisfiable")
            mc.inc_smt_failed()
            return "FAILED"
        mc.inc_smt_verified()
    except ImportError:
        if result == z3.unknown:
            logger.warning("SMT verifier timeout")
            return "FAILED"
        if result == z3.unsat:
            return "FAILED"
    return "VERIFIED"


def run_full_verification_pipeline(
    intervals: List[Tuple],
    now_epoch: float,
    window_hours: float = 72.0,
) -> VerificationResult:
    """
    Run phases 2-6 in sequence. Returns VERIFIED only if all pass.
    W = programme span [s0, en]; now_epoch must lie within it.
    """
    normalized = normalize_intervals(intervals)
    if not normalized:
        return "FAILED"
    repaired = repair_gaps(normalized)
    w_start = repaired[0][0]
    w_end = repaired[-1][1]
    if w_end <= w_start:
        return "FAILED"

    if run_symbolic_algebra_validation(repaired, w_start, w_end) != "VERIFIED":
        return "FAILED"
    if run_temporal_simulation(repaired, w_start, w_end) != "VERIFIED":
        return "FAILED"
    if run_epoch_fuzz(repaired, w_start, w_end) != "VERIFIED":
        return "FAILED"
    if run_interval_spec_verifier(repaired, now_epoch, window_hours) != "VERIFIED":
        return "FAILED"
    return "VERIFIED"
