# -*- coding: utf-8 -*-
"""A peak is protected in three places, mechanically.

A `peak` beat is the moment the cut exists to deliver — the reaction, the
reveal, the thing a viewer would rewind to. Six of the seven film studies
on the shelf converged on protecting it independently: Johnny Harris as
engineered silence (19s and 13s of no VO at Srebrenica), Beau Miles as
darkness plus a ~6x slower cut rate, Mark Rober as the climax at 72% of
runtime, Kara & Nate as the film's ONLY true silence, 4.49s laid exactly on
the moment they admit the premise broke. That is more converging evidence
than any other rule in this program has behind it.

`schemas.coverage_notes` already refused covers on a peak. The three
mechanical sites did not exist, so the machine was free to talk over the
one moment the craft bar counts:

  1. `timeline.plan_beats` cut the silence out of it — and on a peak the
     pause IS the moment, so automatic dead-space removal deletes exactly
     what is being protected.
  2. `validate_edit_plan` allowed a zoom punch-in on it.
  3. `validate_graphics_plan` allowed a card over it.

What breaks if this is wrong: the bar counts peaks the renderer then
flattens, so a cut passes the craft gate and plays like it never did.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas, timeline  # noqa: E402

# One 30s take with a 3s hole in the middle — comfortably over
# MAX_KEEP_GAP_SEC (0.65), so the automatic cut fires on an ordinary beat.
GAP = [{"s": 12.0, "e": 15.0}]
TAKES = {"takes": [{"id": "T01", "file": "speech.mov", "s": 0.0, "e": 30.0,
                    "duration": 30.0, "kind": "oncamera",
                    "transcript": "One. Two."}]}
BROLL = {"clips": []}


def _plan(peak):
    """BT01 is the hook and stays under MAX_HOOK_SEC; BT02 is the beat
    under test and spans the 3s hole at 12-15s."""
    hook = {"id": "BT01", "purpose": "hook", "take_id": "T01",
            "trim": {"s": 0.0, "e": 8.0}, "transition_in": "cut",
            "fragment": True}
    b = {"id": "BT02", "purpose": "payoff", "take_id": "T01",
         "trim": {"s": 0.0, "e": 30.0}, "transition_in": "cut",
         "fragment": True}
    if peak:
        b["peak"] = True
    return {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "beats": [hook, b]}


class TheMachineStopsCuttingInsideAPeak(unittest.TestCase):
    """Site 1. plan_beats -> cut_dead_space."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        # NO `path` key: that is what keeps trough snapping (which needs
        # real audio) out of a unit test, exactly as the picture-beat
        # tests do it.
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps(
            {"files": [{"name": "speech.mov", "duration": 30.0, "fps": 30.0,
                        "class": "speech", "has_audio": True,
                        "words_file": "speech.words.json",
                        "silence": GAP}]}))
        # A splice is only legal where the preceding word CLOSES a
        # sentence (Caleb, 2026-08-19), so the gap at 12-15s needs a
        # sentence ending just before it or the automatic cut refuses and
        # the control below would pass for the wrong reason.
        (self.tmp / "analysis" / "speech.words.json").write_text(json.dumps(
            [{"w": "One.", "s": 10.0, "e": 11.5},
             {"w": "Two.", "s": 16.0, "e": 17.0}]))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps(TAKES))
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(BROLL))
        self._wp, self._ad = timeline.work_path, timeline.analysis_dir
        timeline.work_path = lambda slug: self.tmp
        timeline.analysis_dir = lambda slug: self.tmp / "analysis"

    def tearDown(self):
        timeline.work_path, timeline.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _segments(self, peak, cuts=None):
        plan = _plan(peak)
        if cuts is not None:
            plan["beats"][1]["cuts"] = cuts
        (self.tmp / "edit_plan.json").write_text(json.dumps(plan))
        tl = timeline.plan_beats("ep")
        return tl["beats"][1]["segments"]

    def test_an_ordinary_beat_still_loses_its_dead_space(self):
        """The control. Without it, a passing peak test proves nothing —
        it could be a fixture where the cut never fired at all."""
        self.assertGreater(len(self._segments(peak=False)), 1)

    def test_a_peak_beat_plays_whole(self):
        segs = self._segments(peak=True)
        self.assertEqual(len(segs), 1, segs)

    def test_the_editors_own_cuts_still_apply_on_a_peak(self):
        """The exemption is the GAPS, not the call. Dropping
        cut_dead_space outright would silently discard the deliberate
        removals the plan states — a different bug wearing this one's
        clothes."""
        segs = self._segments(peak=True, cuts=[{"s": 20.0, "e": 22.0}])
        self.assertEqual(len(segs), 2, segs)


class APunchIsNotAllowedOnAPeak(unittest.TestCase):
    """Site 2. A zoom punch-in is the edit commenting on the moment."""

    def _errs(self, plan):
        return schemas.validate_edit_plan(plan, TAKES, BROLL)

    def test_a_punch_on_a_peak_is_refused(self):
        plan = _plan(peak=True)
        plan["beats"][1]["punches"] = [{"at": 0.5, "zoom": 1.12}]
        errs = self._errs(plan)
        self.assertTrue(any("peak beat carries" in e for e in errs), errs)

    def test_a_punch_on_an_ordinary_beat_is_fine(self):
        plan = _plan(peak=False)
        plan["beats"][1]["punches"] = [{"at": 0.5, "zoom": 1.12}]
        self.assertEqual(self._errs(plan), [])

    def test_a_malformed_punch_is_named_wherever_it_sits(self):
        """`punches` had never been validated anywhere — the hype-director
        writes them and nothing checked the shape."""
        plan = _plan(peak=False)
        plan["beats"][1]["punches"] = [{"at": "half", "zoom": 1.12}]
        errs = self._errs(plan)
        self.assertTrue(any("punches[0]" in e for e in errs), errs)


class ACardIsNotAllowedOnAPeak(unittest.TestCase):
    """Site 3. Nothing shares the frame with the reaction."""

    def _gp(self, beat_id):
        return {"slug": "ep", "cards": [
            {"id": "CARD01", "type": "stat", "beat_id": beat_id,
             "at": 1.0, "duration": 3.0, "stat": "9", "kicker": "rooms"}]}

    def test_a_card_homed_to_a_peak_is_refused(self):
        errs = schemas.validate_graphics_plan(self._gp("BT02"),
                                              _plan(peak=True))
        self.assertTrue(any("peak beat BT02" in e for e in errs), errs)

    def test_the_same_card_on_an_ordinary_beat_is_fine(self):
        errs = schemas.validate_graphics_plan(self._gp("BT01"),
                                              _plan(peak=True))
        self.assertEqual([e for e in errs if "peak" in e], [], errs)

    def test_no_edit_plan_means_no_peak_refusal(self):
        """Absent-tolerant by construction: the desk validates cards with
        no cut in hand and must not start refusing them."""
        errs = schemas.validate_graphics_plan(self._gp("BT02"))
        self.assertEqual([e for e in errs if "peak" in e], [], errs)


if __name__ == "__main__":
    unittest.main()
