# -*- coding: utf-8 -*-
"""The b-roll craft rules, mechanized.

2026-08-24: the crooise cut put five 1.1-second postcards over the hook
(one of them a different ship) while the line was about donuts — Caleb:
"supportive of the story, not a bombardment of noise". coverage_notes is
the arithmetic half of the fix: pure, advisory (existing plans must not
brick surgery writes), and the bar the coverage job must leave empty.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas  # noqa: E402


def beat(bid="BT01", dur=10.0, covers=None, **extra):
    b = {"id": bid, "take_id": "T1", "trim": {"s": 0.0, "e": dur}}
    if covers is not None:
        b["broll"] = covers
    b.update(extra)
    return b


def cover(clip="B001", at=1.0, dur=2.5, why="illustrate: the thing"):
    c = {"clip_id": clip, "at": at, "duration": dur}
    if why is not None:
        c["why"] = why
    return c


class CoverageNotes(unittest.TestCase):
    def notes(self, *beats):
        return schemas.coverage_notes({"beats": list(beats)})

    def test_a_clean_cover_passes_silently(self):
        self.assertEqual(self.notes(beat(covers=[cover()])), [])

    def test_an_uncovered_beat_says_nothing(self):
        self.assertEqual(self.notes(beat()), [])

    def test_sub_legible_covers_are_named(self):
        out = self.notes(beat(covers=[cover(dur=1.1)]))
        self.assertTrue(any("cannot be read" in x for x in out))

    def test_the_bombardment_rule(self):
        covers = [cover(clip="B%02d" % i, at=i * 2.0, dur=1.9)
                  for i in range(4)]
        out = self.notes(beat(dur=20.0, covers=covers))
        self.assertTrue(any("bombardment" in x for x in out))

    def test_the_landing_belongs_to_the_face(self):
        out = self.notes(beat(dur=10.0, covers=[cover(at=8.5, dur=1.9)]))
        self.assertTrue(any("landing" in x for x in out))

    def test_the_coverage_ratio(self):
        out = self.notes(beat(dur=10.0, covers=[
            cover(at=0.5, dur=3.5), cover(clip="B002", at=4.5, dur=3.5)]))
        self.assertTrue(any("stops being one" in x for x in out))

    def test_a_peak_is_never_covered(self):
        out = self.notes(beat(covers=[cover()], peak=True))
        self.assertTrue(any("peak" in x for x in out))

    def test_a_cover_without_a_why_is_named(self):
        out = self.notes(beat(covers=[cover(why=None)]))
        self.assertTrue(any("no why" in x for x in out))

    def test_vo_beats_are_exempt_from_ratio_and_landing(self):
        b = beat(dur=10.0, covers=[cover(at=0.0, dur=9.5)],
                 take_id="vo_CH1-S2_t1")
        b["take_id"] = "vo_CH1-S2_t1"
        self.assertEqual(self.notes(b), [])


if __name__ == "__main__":
    unittest.main()
