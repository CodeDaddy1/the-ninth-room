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


class JustifiedWhys(unittest.TestCase):
    """R1, mechanized (2026-08-24, from the Beau Miles study).

    The rubric line "every cover names exactly one of the justifications"
    was the reviewer's judgment until now; a why that names none is a
    preference with a sentence in front of it. And the fifth
    justification exists because the first four are all defined against
    a spoken line — footage of the work advancing had no legal reason to
    exist, so R1 obliged an editor to delete exactly the coverage Beau
    Miles builds 20% of a film from.
    """

    def notes(self, why):
        return schemas.coverage_notes(
            {"beats": [beat(covers=[cover(why=why)])]})

    def test_every_justification_is_accepted(self):
        for kind in schemas.COVER_WHYS:
            self.assertEqual(self.notes("%s: the reason" % kind), [],
                             "%s should be legal" % kind)

    def test_process_is_one_of_them(self):
        self.assertIn("process", schemas.COVER_WHYS)
        self.assertEqual(self.notes("process: hands opening the case"), [])

    def test_a_dash_reads_the_same_as_a_colon(self):
        """Both formats appear in real editor output — a checker that
        graded punctuation would fail half of them for nothing."""
        self.assertEqual(self.notes("illustrate - the donut awning"), [])
        self.assertEqual(self.notes("illustrate: the donut awning"), [])

    def test_a_why_that_names_no_justification_is_flagged(self):
        notes = self.notes("it looked nice here")
        self.assertEqual(len(notes), 1)
        self.assertIn("must LEAD with one of", notes[0])
        self.assertIn("process", notes[0])  # the vocabulary is quoted

    def test_the_justification_must_LEAD(self):
        """A cover that buries the word mid-sentence has not claimed it."""
        self.assertEqual(len(self.notes("a nice wide that helps establish "
                                        "the hall")), 1)

    def test_a_missing_why_still_reads_as_missing_not_unknown(self):
        notes = schemas.coverage_notes(
            {"beats": [beat(covers=[cover(why=None)])]})
        self.assertEqual(len(notes), 1)
        self.assertIn("has no why", notes[0])

    def test_process_grants_itself_no_exemption(self):
        """The premise of the VO exemption is that there is no face to
        cut back to. A cover cannot create that condition by naming it."""
        covers = [cover(clip="B1", at=0.0, dur=3.0, why="process: the walk"),
                  cover(clip="B2", at=4.5, dur=4.5, why="process: the work")]
        notes = schemas.coverage_notes({"beats": [beat(dur=10.0,
                                                       covers=covers)]})
        self.assertTrue(any("covered" in n for n in notes),
                        "the 60%% ratio still applies: %r" % notes)
        self.assertTrue(any("landing" in n for n in notes),
                        "the landing still belongs to the face: %r" % notes)

    def test_why_kind_is_pure_and_says_none_for_nonsense(self):
        self.assertEqual(schemas.why_kind("Establish — the plaza"), "establish")
        self.assertEqual(schemas.why_kind("  bridge, hides the jump"), "bridge")
        self.assertIsNone(schemas.why_kind(""))
        self.assertIsNone(schemas.why_kind(None))
        self.assertIsNone(schemas.why_kind("vibes"))
