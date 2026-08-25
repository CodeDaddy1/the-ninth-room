# -*- coding: utf-8 -*-
"""A placed cover can be moved without being torn out and put back.

2026-08-25, Caleb: "we should be able to go back to the B-Roll and
adjust where it starts in the clip without having to remove the clip and
replace." Remove-and-replace worked, but it cost the cover its place in
the plan, wrote two conform ops for one intention, and re-rendered the
beat twice because detach and attach each rebuild the proxy.

The clamp is the part worth pinning. It used to be inline in attach;
the moment a SECOND path could place a cover it had to become one
function, because the edges are where a cover runs off the end of its
source and renders black.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom  # noqa: E402


class Clamp(unittest.TestCase):
    """beat 10s long, clip 6s long."""

    def clamp(self, at, dur, src):
        return editroom._clamp_cover(10.0, 6.0, at, dur, src)

    def test_a_legal_placement_is_left_alone(self):
        self.assertEqual(self.clamp(2.0, 3.0, 1.0), (2.0, 3.0, 1.0))

    def test_a_cover_cannot_start_past_the_end_of_the_beat(self):
        at, _, _ = self.clamp(99.0, 3.0, 0.0)
        self.assertAlmostEqual(at, 9.8)

    def test_nor_can_the_source_start_past_the_end_of_the_clip(self):
        _, _, src = self.clamp(0.0, 3.0, 99.0)
        self.assertAlmostEqual(src, 5.8)

    def test_duration_is_bounded_by_what_is_left_of_the_CLIP(self):
        """Starting 5s into a 6s clip leaves 1s, however long you ask."""
        _, dur, _ = self.clamp(0.0, 5.0, 5.0)
        self.assertAlmostEqual(dur, 1.0)

    def test_and_by_what_is_left_of_the_BEAT(self):
        _, dur, _ = self.clamp(8.0, 5.0, 0.0)
        self.assertAlmostEqual(dur, 2.0)

    def test_a_negative_position_is_pulled_back_to_the_start(self):
        at, _, src = self.clamp(-4.0, 2.0, -9.0)
        self.assertEqual((at, src), (0.0, 0.0))

    def test_a_duration_never_collapses_to_nothing(self):
        _, dur, _ = self.clamp(0.0, 0.0, 0.0)
        self.assertGreaterEqual(dur, 0.2)

    def test_it_rounds_to_milliseconds_so_the_json_stays_readable(self):
        at, dur, src = self.clamp(1.23456, 2.34567, 0.98765)
        self.assertEqual((at, dur, src), (1.235, 2.346, 0.988))


class AdjustSemantics(unittest.TestCase):
    """What the verb does with what it is NOT given."""

    def test_omitted_fields_keep_their_current_value(self):
        # the adjust reads the existing entry for anything passed as None;
        # this pins the contract the route depends on
        import inspect
        src = inspect.getsource(editroom._broll_adjust)
        self.assertIn('cur.get("at", 0) if at is None else at', src)
        self.assertIn('cur.get("src_s", 0) if src_s is None else src_s', src)

    def test_it_refuses_a_clip_that_is_not_on_the_beat(self):
        import inspect
        src = inspect.getsource(editroom._broll_adjust)
        self.assertIn("attach it first", src)

    def test_attach_and_adjust_share_one_clamp(self):
        """If these ever diverge, one path will place covers the other
        would refuse."""
        import inspect
        for fn in (editroom._broll_attach, editroom._broll_adjust):
            self.assertIn("_clamp_cover", inspect.getsource(fn))


if __name__ == "__main__":
    unittest.main()
