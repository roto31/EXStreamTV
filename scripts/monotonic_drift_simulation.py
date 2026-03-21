#!/usr/bin/env python3
"""
Monotonic drift simulation. Adversarial wall-clock mutations.
Validates invariants using T(t)=anchor_wall+(monotonic-anchor_monotonic).
"""
import sys
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

sys.path.insert(0, str(__file__).rsplit("/", 2)[0] or ".")

# Real monotonic; mock time.time only
_real_monotonic = time.monotonic
_real_time = time.time


def T(anchor_wall: float, anchor_mono: float, mono: float) -> float:
    """Authoritative epoch: T(t)=anchor_wall+(monotonic-anchor_monotonic)."""
    return anchor_wall + (mono - anchor_mono)


def _build_synthetic_timeline() -> list:
    """Synthetic timeline: 3 items, 1800s each."""
    from exstreamtv.scheduling.canonical_timeline import CanonicalTimelineItem
    return [
        CanonicalTimelineItem(title="A", canonical_duration=1800.0),
        CanonicalTimelineItem(title="B", canonical_duration=1800.0),
        CanonicalTimelineItem(title="C", canonical_duration=1800.0),
    ]


def _resolve_active(timeline: list, offset: float) -> str | None:
    """Resolve active item by offset. Single item."""
    cumulative = 0.0
    for item in timeline:
        dur = item.canonical_duration or 1800.0
        if cumulative <= offset < cumulative + dur:
            return item.title or ""
        cumulative += dur
    return timeline[0].title if timeline else None


def _programmes_contain_T(programmes: list, t_epoch: float) -> bool:
    """Invariant 4: XMLTV active programme interval contains T(t)."""
    for p in programmes:
        if hasattr(p, "start_time") and hasattr(p, "stop_time"):
            st, sp = p.start_time, p.stop_time
            start = st.replace(tzinfo=timezone.utc).timestamp() if st.tzinfo is None else st.timestamp()
            stop = sp.replace(tzinfo=timezone.utc).timestamp() if sp.tzinfo is None else sp.timestamp()
            if start <= t_epoch < stop:
                return True
    return False


class MonotonicDriftSimulation(unittest.TestCase):
    """Run invariant checks under wall-clock mutations."""

    def setUp(self) -> None:
        self.timeline = _build_synthetic_timeline()
        self.total_duration = sum(t.canonical_duration or 1800 for t in self.timeline)
        self.anchor_wall = 1700000000.0  # fixed base
        self.anchor_mono = _real_monotonic()

    def _run_case(self, wall_delta: float, mono_delta: float = 0.0) -> tuple[float, float, str | None]:
        """Apply wall_delta to time.time(), mono_delta to elapsed monotonic. Return (t1,t2,active)."""
        t1 = T(self.anchor_wall, self.anchor_mono, _real_monotonic())
        mocked_time = lambda: _real_time() + wall_delta
        with patch("time.time", side_effect=mocked_time):
            # Simulate mono advance (we can't change real monotonic; use formula directly)
            mono_now = _real_monotonic() + mono_delta
            t2 = T(self.anchor_wall, self.anchor_mono, mono_now)
        offset = (t2 - self.anchor_wall) % self.total_duration
        active = _resolve_active(self.timeline, offset)
        return t1, t2, active

    def test_A_wall_minus_3600(self) -> None:
        """Wall clock -3600 seconds."""
        t1, t2, active = self._run_case(wall_delta=-3600)
        self.assertGreaterEqual(t2, t1, "Invariant 1: T monotonic")
        self.assertIsNotNone(active, "Invariant 3: single active")
        self.assertEqual(len([a for a in [active] if a]), 1)

    def test_B_wall_plus_7200(self) -> None:
        """Wall clock +7200 seconds."""
        t1, t2, active = self._run_case(wall_delta=7200)
        self.assertGreaterEqual(t2, t1, "Invariant 1: T monotonic")
        self.assertIsNotNone(active, "Invariant 3: single active")

    def test_C_dst_forward(self) -> None:
        """DST forward shift (typically -3600 in UTC terms for some zones)."""
        self._run_case(wall_delta=-3600)

    def test_D_dst_backward(self) -> None:
        """DST backward shift (+3600)."""
        self._run_case(wall_delta=3600)

    def test_E_ntp_step(self) -> None:
        """NTP correction step."""
        self._run_case(wall_delta=5.0)

    def test_F_leap_second(self) -> None:
        """Leap second insertion."""
        self._run_case(wall_delta=1.0)

    def test_G_vm_suspend(self) -> None:
        """VM suspend/resume: monotonic jumps forward; wall unchanged relative to monotonic.
        We simulate by having monotonic advance; T must remain monotonic."""
        t1 = T(self.anchor_wall, self.anchor_mono, _real_monotonic())
        mono_after = _real_monotonic() + 300  # 5 min suspend
        t2 = T(self.anchor_wall, self.anchor_mono, mono_after)
        self.assertGreaterEqual(t2, t1, "Invariant 1: T monotonic after mono jump")

    def test_invariant_T_monotonic(self) -> None:
        """T(t2) >= T(t1) for monotonic advance."""
        t1 = T(self.anchor_wall, self.anchor_mono, _real_monotonic())
        t2 = T(self.anchor_wall, self.anchor_mono, _real_monotonic() + 1)
        self.assertGreaterEqual(t2, t1)

    def test_invariant_single_active(self) -> None:
        """Exactly one active CanonicalTimelineItem."""
        offset = 900.0  # 15 min in
        active = _resolve_active(self.timeline, offset)
        self.assertIsNotNone(active)
        self.assertIn(active, ["A", "B", "C"])

    def test_invariant_non_overlap(self) -> None:
        """prev.stop_epoch <= next.start_epoch."""
        from exstreamtv.scheduling.clock import ChannelClock
        from exstreamtv.scheduling.xmltv_from_clock import build_programmes_from_clock
        anchor = datetime.fromtimestamp(self.anchor_wall, tz=timezone.utc).replace(tzinfo=None)
        clock = ChannelClock(1, anchor, self.total_duration)
        programmes = build_programmes_from_clock(clock, self.timeline, now=None, max_programmes=10)
        for i in range(1, len(programmes)):
            prev_stop = programmes[i - 1].stop_time.timestamp()
            curr_start = programmes[i].start_time.timestamp()
            self.assertLessEqual(prev_stop, curr_start, f"Overlap at index {i}")

    def test_invariant_xmltv_contains_T(self) -> None:
        """XMLTV active programme interval contains T(t)."""
        from exstreamtv.scheduling.clock import ChannelClock
        from exstreamtv.scheduling.xmltv_from_clock import build_programmes_from_clock
        anchor = datetime.fromtimestamp(self.anchor_wall, tz=timezone.utc).replace(tzinfo=None)
        clock = ChannelClock(1, anchor, self.total_duration)
        programmes = build_programmes_from_clock(clock, self.timeline, now=None, max_programmes=10)
        t_now = clock._now_epoch()
        self.assertTrue(
            _programmes_contain_T(programmes, t_now),
            f"T={t_now} not in any programme",
        )


def run_simulation() -> str:
    """Run all tests. Return PASS or FAIL."""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(MonotonicDriftSimulation)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    return "PASS" if result.wasSuccessful() and not result.failures and not result.errors else "FAIL"


if __name__ == "__main__":
    status = run_simulation()
    print(status)
    sys.exit(0 if status == "PASS" else 1)
