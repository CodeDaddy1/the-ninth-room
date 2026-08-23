# -*- coding: utf-8 -*-
"""The edge-rescue contract: segments only grow, and only when it helps.

History that shaped these tests (2026-08-23): the first version snapped
edges to the quietest single INSTANT and made the audit count WORSE
(49 -> 51) — an instant minimum can sit between two voice bursts while the
audit measures a sustained 250ms stretch. The rewrite scores candidates
with the audit's own arithmetic and moves an edge only from FAIL to PASS.
These tests pin all three legs:

    1. direction — an edge only moves INTO the removed gap (grow-only),
    2. the move rule — passing edges never move, doomed edges never move,
       failing edges move to the NEAREST passing spot,
    3. jurisdiction — hard cuts are never touched.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import timeline, troughs  # noqa: E402


class FakeAudio:
    """Stands in for _EdgeAudio: `hot` maps time-ranges to voice presence.
    edge_hot(t, direction) reports hot when any hot range intersects the
    250ms probe outside the cut — shape-compatible with the real thing."""

    def __init__(self, hot_ranges):
        self.hot = hot_ranges

    def edge_hot(self, t, direction):
        lo, hi = (t, t + troughs.EDGE_WITHIN_SEC) if direction > 0 \
            else (t - troughs.EDGE_WITHIN_SEC, t)
        for (a, b) in self.hot:
            if a < hi and b > lo:
                return -20.0
        return None


def snap(rs, re_, hot_ranges, cache=None):
    fake = FakeAudio(hot_ranges)
    return troughs.snap_removal(
        "/fake.mov", rs, re_, cache if cache is not None else {},
        audio_factory=lambda path, start, dur: fake)


class DirectionRules(unittest.TestCase):
    def test_out_edge_searches_later_only(self):
        lo, hi = troughs.out_edge_window(10.0, 12.0)
        self.assertEqual(lo, 10.0)
        self.assertAlmostEqual(hi, 10.45)

    def test_out_edge_stops_short_of_the_removal_end(self):
        lo, hi = troughs.out_edge_window(10.0, 10.2)
        self.assertAlmostEqual(hi, 10.2 - troughs.GUARD_SEC)

    def test_a_removal_too_small_to_search_is_refused(self):
        self.assertIsNone(troughs.out_edge_window(10.0, 10.05))

    def test_in_edge_searches_earlier_only(self):
        lo, hi = troughs.in_edge_window(12.0, 10.0)
        self.assertAlmostEqual(lo, 11.55)
        self.assertEqual(hi, 12.0)

    def test_in_edge_respects_the_moved_out_edge(self):
        lo, hi = troughs.in_edge_window(12.0, 11.8)
        self.assertAlmostEqual(lo, 11.8 + troughs.GUARD_SEC)


class MoveRule(unittest.TestCase):
    def test_a_passing_edge_never_moves(self):
        """The common case must be free: silence outside -> stay put."""
        self.assertEqual(snap(10.0, 12.0, hot_ranges=[]), (10.0, 12.0))

    def test_a_failing_out_edge_moves_to_the_nearest_passing_spot(self):
        # voice tail runs past the cut until 10.30; probes fail until the
        # 250ms window clears it
        rs, re_ = snap(10.0, 12.0, hot_ranges=[(9.5, 10.30)])
        self.assertGreater(rs, 10.0)          # moved — it was failing
        self.assertAlmostEqual(rs, 10.30, places=2)  # nearest passing spot
        self.assertEqual(re_, 12.0)           # the other edge passed; stayed

    def test_a_failing_in_edge_moves_earlier_only(self):
        # voice starts at 11.7, before silencedetect closed the gap at 12.0
        rs, re_ = snap(10.0, 12.0, hot_ranges=[(11.7, 12.4)])
        self.assertEqual(rs, 10.0)
        self.assertLess(re_, 12.0)
        self.assertAlmostEqual(re_, 11.7, places=2)

    def test_a_doomed_edge_stays_put(self):
        """Voice everywhere: no candidate passes — churn buys nothing."""
        self.assertEqual(snap(10.0, 12.0, hot_ranges=[(0.0, 99.0)]), (10.0, 12.0))

    def test_segments_only_grow(self):
        """The content-safety half, whatever the audio says."""
        for hot in ([], [(9.0, 10.4)], [(11.5, 13.0)], [(0.0, 99.0)]):
            rs, re_ = snap(10.0, 12.0, hot_ranges=hot)
            self.assertGreaterEqual(rs, 10.0, hot)
            self.assertLessEqual(re_, 12.0, hot)

    def test_the_removal_never_inverts(self):
        rs, re_ = snap(10.0, 10.4, hot_ranges=[(9.0, 13.0)])
        self.assertGreaterEqual(re_ - rs, troughs.GUARD_SEC)

    def test_decisions_are_cached_by_edge_and_window(self):
        calls = []
        def factory(path, start, dur):
            calls.append(start)
            return FakeAudio([(9.5, 10.30)])
        cache = {}
        for _ in range(2):
            troughs.snap_removal("/fake.mov", 10.0, 12.0, cache, audio_factory=factory)
        # second run answers fully from cache — footage is immutable
        self.assertEqual(len(calls), 2)


class CutDeadSpaceIntegration(unittest.TestCase):
    """The wiring: silence removals get the rescue, hard cuts never do."""

    GAPS = [{"s": 10.0, "e": 12.0}]
    WORDS = [{"s": 9.0, "e": 9.9, "w": "stops."}, {"s": 12.1, "e": 12.5, "w": "Next"}]

    def test_no_audio_path_means_the_old_behaviour_exactly(self):
        segs = timeline.cut_dead_space(0.0, 20.0, self.GAPS, words=self.WORDS)
        self.assertEqual(segs, [(0.0, 10.2), (11.8, 20.0)])

    def test_failing_silence_edges_are_rescued(self):
        real = troughs._EdgeAudio
        troughs._EdgeAudio = lambda path, start, dur: FakeAudio([(9.5, 10.45)])
        try:
            segs = timeline.cut_dead_space(
                0.0, 20.0, self.GAPS, words=self.WORDS,
                audio_path="/fake.mov", trough_cache={})
        finally:
            troughs._EdgeAudio = real
        (s1s, s1e), (s2s, s2e) = segs
        self.assertGreater(s1e, 10.2)   # out edge moved past the voice tail
        self.assertLess(s1e, s2s)

    def test_hard_cuts_stay_exactly_where_the_editor_put_them(self):
        def explode(path, start, dur):
            raise AssertionError("a hard cut must never be measured")
        real = troughs._EdgeAudio
        troughs._EdgeAudio = explode
        try:
            segs = timeline.cut_dead_space(
                0.0, 20.0, gaps=[], hard_cuts=[{"s": 5.0, "e": 6.0}],
                audio_path="/fake.mov", trough_cache={})
        finally:
            troughs._EdgeAudio = real
        self.assertEqual(segs, [(0.0, 5.0), (6.0, 20.0)])


if __name__ == "__main__":
    unittest.main()
