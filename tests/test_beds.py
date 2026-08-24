# -*- coding: utf-8 -*-
"""Music beds duck under speech by arithmetic, not guesswork.

P9 of the workflow plan (2026-08-24). The envelope is a pure function of
whisper's word times so two renders of one beat are identical — the
invariants pinned here:

- a beat with no gaps ducks FLAT (a bare number, no expression);
- a gap lifts the bed and the trapezoid ramps over 0.3s inside it;
- pauses shorter than a second never lift the bed (a breath is not a
  musical moment);
- head and tail silence count as gaps.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import sfx  # noqa: E402


def _eval(expr: str, t: float) -> float:
    return eval(expr.replace("min", "min").replace("max", "max"),
                {"min": min, "max": max, "t": t})


class SpeechGaps(unittest.TestCase):
    def test_a_breath_is_not_a_gap(self):
        words = [(0.0, 2.0), (2.5, 5.0)]
        self.assertEqual(sfx.speech_gaps(words, 5.0), [])

    def test_a_real_pause_is(self):
        words = [(0.0, 2.0), (3.5, 5.0)]
        self.assertEqual(sfx.speech_gaps(words, 5.0), [(2.0, 3.5)])

    def test_head_and_tail_silence_count(self):
        words = [(1.5, 3.0)]
        self.assertEqual(sfx.speech_gaps(words, 5.0),
                         [(0.0, 1.5), (3.0, 5.0)])

    def test_overlapping_words_never_produce_negative_gaps(self):
        words = [(0.0, 3.0), (2.0, 2.5)]
        self.assertEqual(sfx.speech_gaps(sorted(words), 3.4), [])


class DuckExpr(unittest.TestCase):
    def test_no_gaps_is_a_flat_number(self):
        expr = sfx.duck_expr([])
        self.assertAlmostEqual(float(expr), 10 ** (sfx.BED_DUCK_DB / 20), 5)

    def test_mid_gap_reaches_the_up_level(self):
        expr = sfx.duck_expr([(2.0, 4.0)])
        self.assertAlmostEqual(_eval(expr, 3.0),
                               10 ** (sfx.BED_UP_DB / 20), 4)

    def test_under_speech_sits_at_the_duck_level(self):
        expr = sfx.duck_expr([(2.0, 4.0)])
        self.assertAlmostEqual(_eval(expr, 0.5),
                               10 ** (sfx.BED_DUCK_DB / 20), 4)

    def test_the_ramp_is_between_the_levels(self):
        expr = sfx.duck_expr([(2.0, 4.0)])
        v = _eval(expr, 2.15)  # halfway up the 0.3s ramp
        duck = 10 ** (sfx.BED_DUCK_DB / 20)
        up = 10 ** (sfx.BED_UP_DB / 20)
        self.assertTrue(duck < v < up)


if __name__ == "__main__":
    unittest.main()
