# -*- coding: utf-8 -*-
"""C1 — the declining pace ladder, measured against Kara & Nate.

Their six-chapter film ran 39.6 -> 14.0 cuts/min, ratio 0.35, with no
reversal in cut rate or median shot length (docs/film-studies/). hmns ran
12.6 throughout — the same speed for thirteen minutes — and nothing in the
program could say so. PACE_DECLINE_MAX is 0.7, loose next to their 0.35 on
purpose: the first setting only has to kill a flat series.

The realized-vs-declared band is wide (+/-35%) because the estimate is
SHAPE, not truth — silence cuts are added later by timeline.plan_beats.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import cutbar  # noqa: E402


def ladder(*cpms):
    """A chaptered plan whose only content is its declared ladder."""
    return {"slug": "t",
            "chapters": [{"id": "CH%d" % (i + 1), "title": "c",
                          "pace_cpm": v} for i, v in enumerate(cpms)],
            "beats": []}


def pace_notes(plan):
    return [n for n in cutbar.cut_notes(plan, None, None)
            if "pace_cpm" in n or "ladder" in n]


class TheLadder(unittest.TestCase):
    def test_a_flat_series_fails_the_decline(self):
        """hmns's shape: 12.6 throughout. Monotone, wobble-free — and
        still not a ladder, which is exactly what 0.7 exists to say."""
        out = pace_notes(ladder(12.6, 12.6, 12.6, 12.6, 12.6))
        self.assertTrue(any("ends at 12.6 against a 12.6 open" in n
                            for n in out))

    def test_one_reversal_is_a_second_wind_and_passes(self):
        """CALIBRATED 2026-08-28. Strict monotonicity was the spec and
        all five cuts on disk broke it — a museum day changes hall five
        times and a new room earns one climb. The overall decline still
        has to hold, so the series here ends under 0.7 of its open."""
        out = pace_notes(ladder(30.0, 14.0, 18.0, 12.0))
        self.assertFalse(any("second wind" in n for n in out))

    def test_a_second_reversal_names_itself_and_the_count(self):
        out = pace_notes(ladder(30.0, 14.0, 18.0, 12.0, 16.0, 9.0))
        hits = [n for n in out if "second wind" in n]
        self.assertEqual(len(hits), 1)
        self.assertIn("CH5", hits[0])
        self.assertIn("12.0 -> 16.0", hits[0])
        self.assertIn("not 2", hits[0])

    def test_a_ten_percent_wobble_is_not_a_reversal(self):
        """PACE_TOLERANCE: chapter energy breathes. 18.0 -> 19.0 is a
        wobble; the series still ends far enough under its open."""
        out = pace_notes(ladder(30.0, 18.0, 19.0, 12.0))
        self.assertFalse(any("only steps down" in n for n in out))

    def test_a_kara_and_nate_shaped_series_passes(self):
        """Their measured run: 39.6 to 14.0 over six chapters, no
        reversal — the shape the whole check is calibrated on."""
        out = pace_notes(ladder(39.6, 31.9, 26.9, 23.0, 18.1, 14.0))
        self.assertEqual(out, [])

    def test_missing_pace_cpm_names_the_chapter(self):
        plan = ladder(24.0, 16.0, 10.0)
        del plan["chapters"][1]["pace_cpm"]
        out = pace_notes(plan)
        self.assertTrue(any(n.startswith("CH2: no pace_cpm") for n in out))

    def test_a_plan_with_no_ladder_at_all_gets_ONE_note(self):
        """hmns today: five chapters, none declaring. One teaching note,
        not five copies of the same request."""
        plan = ladder(24.0, 16.0, 10.0)
        for ch in plan["chapters"]:
            del ch["pace_cpm"]
        out = pace_notes(plan)
        self.assertEqual(len(out), 1)
        self.assertIn("no chapter declares pace_cpm", out[0])
        self.assertIn("declining ladder", out[0])

    def test_a_single_chapter_plan_owes_no_ladder(self):
        self.assertEqual(pace_notes(ladder(20.0)), [])


class RealizedVersusDeclared(unittest.TestCase):
    def chapter_beats(self, n, dur, covers=0):
        """n beats of dur seconds each in CH1, `covers` covers total."""
        beats = []
        for i in range(n):
            b = {"id": "BT%02d" % (i + 1), "purpose": "build",
                 "chapter_id": "CH1",
                 "trim": {"s": 0.0, "e": float(dur)}}
            beats.append(b)
        for j in range(covers):
            beats[j % n].setdefault("broll", []).append(
                {"clip_id": "B%02d" % j, "at": 0.5, "duration": 2.0,
                 "why": "illustrate: the thing"})
        return beats

    def plan(self, declared, beats):
        return {"slug": "t",
                "chapters": [{"id": "CH1", "title": "c",
                              "pace_cpm": declared},
                             {"id": "CH2", "title": "c",
                              "pace_cpm": declared * 0.6}],
                "beats": beats}

    def test_realized_far_off_declared_is_named(self):
        # 2 beats, no covers, 60s -> 2 changes in 1 minute = 2 cuts/min
        plan = self.plan(30.0, self.chapter_beats(2, 30.0))
        out = cutbar.cut_notes(plan, None, None)
        hits = [n for n in out if "realizes" in n]
        self.assertEqual(len(hits), 1)
        self.assertIn("CH1", hits[0])
        self.assertIn("2.0 cuts/min against a declared 30.0", hits[0])

    def test_realized_inside_the_band_is_silent(self):
        # 8 beats + 2 covers in 60s -> 12 changes/min against declared 12
        plan = self.plan(12.0, self.chapter_beats(8, 7.5, covers=2))
        out = cutbar.cut_notes(plan, None, None)
        self.assertFalse([n for n in out if "realizes" in n])

    def test_a_chapter_with_no_beats_skips_the_band(self):
        """Mid-surgery a chapter can be empty; an estimate over zero
        minutes is not a finding."""
        plan = self.plan(30.0, [])
        out = cutbar.cut_notes(plan, None, None)
        self.assertFalse([n for n in out if "realizes" in n])


if __name__ == "__main__":
    unittest.main()
