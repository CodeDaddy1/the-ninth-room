"""The craft bar's fields, taught to the schema — absent-tolerantly.

`pipeline/cutbar.py` grades `pace_cpm`, `opens_loop`, `pays_loop`,
`thread`, `framing`, `flag_note` and `peak`, but until now not one of them
existed in any validator. A field the schema has never heard of is a field
the writer can misspell, mistype or half-declare with nothing anywhere
reporting it: a `pays_loop` of 3 reads as absent to every grader, and the
session that wrote it never learns its declaration did nothing.

ABSENT-TOLERANCE IS THE WHOLE CONTRACT. Every plan on disk was written
before these fields existed, and three surgery paths — `_beat_swap`,
`_beat_trim`, `_trash_restore` — call `validate_edit_plan` and roll the
whole write back on ANY error. A check that fires on a plan simply for
being old would make Caleb's swap button refuse silently. So the rule is:
missing is silent, present-and-malformed is an error, and the real hmns
plan's error list may not grow by a single line.

What breaks if this is wrong: every existing cut stops opening, and the
surgery buttons fail without saying why.
"""
import json
import unittest
from pathlib import Path

from pipeline import schemas

WORK = Path(__file__).resolve().parent.parent / "work"


def _plan(**over):
    """A minimal valid landscape plan with one hook beat and one build."""
    takes = {"takes": [
        {"id": "T1", "file": "a.mp4", "s": 0.0, "e": 10.0, "duration": 10.0,
         "transcript": "One sentence."},
        {"id": "T2", "file": "b.mp4", "s": 0.0, "e": 10.0, "duration": 10.0,
         "transcript": "Another sentence."}]}
    plan = {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "beats": [
                {"id": "BT01", "purpose": "hook", "take_id": "T1",
                 "trim": {"s": 0.0, "e": 10.0}, "transition_in": "cut"},
                {"id": "BT02", "purpose": "payoff", "take_id": "T2",
                 "trim": {"s": 0.0, "e": 10.0}, "transition_in": "cut"}]}
    plan.update(over)
    return plan, takes


def _errs(plan, takes, broll=None):
    return schemas.validate_edit_plan(plan, takes, broll or {"clips": []})


class TheValidatorReportsInsteadOfRaising(unittest.TestCase):
    """A0. `_beat_sentence_errors` interpolated word positions from the
    trim without clamping the start index, so a trim lying outside its
    take's span indexed off the end of the transcript and the WHOLE
    validator raised IndexError — throwing away the errors it had already
    collected, including the bounds error naming the exact cause.

    This is live on the shipped hmns plan (BT19 names take T56, which runs
    0.00-2.07, and trims 4.14-7.30 — T57's window). A validator that dies
    on the input it exists to reject cannot be a gate, and the cut job is
    about to call it on untrusted agent output."""

    def test_a_trim_past_the_takes_end_reports_and_does_not_raise(self):
        plan, takes = _plan()
        plan["beats"][1]["trim"] = {"s": 40.0, "e": 47.0}   # take ends at 10
        errs = _errs(plan, takes)                            # must not raise
        self.assertTrue(any("outside take" in e for e in errs), errs)

    def test_the_bounds_error_survives_to_the_caller(self):
        """The point of the fix: the diagnosis is IN the returned list."""
        plan, takes = _plan()
        plan["beats"][1]["trim"] = {"s": 40.0, "e": 47.0}
        errs = _errs(plan, takes)
        self.assertTrue(any("T2" in e and "outside take" in e for e in errs),
                        errs)


class TheRealPlanIsUnchanged(unittest.TestCase):
    """The brickage ratchet. Reads the artifact itself, not a fixture —
    the same reason the calibration report grades real cuts."""

    def test_hmns_validates_to_the_same_errors_it_always_did(self):
        w = WORK / "hmns"
        if not (w / "edit_plan.json").exists():
            self.skipTest("hmns is not on this machine")
        plan = json.loads((w / "edit_plan.json").read_text())
        takes = json.loads((w / "analysis" / "takes.json").read_text())
        broll = json.loads((w / "analysis" / "broll.json").read_text())
        errs = _errs(plan, takes, broll)
        # Every error is one of the two pre-existing families. A craft
        # field firing here would mean the new checks are not tolerant.
        for e in errs:
            self.assertTrue("outside take" in e or "mid-sentence" in e,
                            "a new check fired on the shipped plan: %s" % e)

    def test_hmns_broll_still_validates(self):
        w = WORK / "hmns"
        if not (w / "analysis" / "broll.json").exists():
            self.skipTest("hmns is not on this machine")
        broll = json.loads((w / "analysis" / "broll.json").read_text())
        self.assertEqual(schemas.validate_broll(broll), [])


class AbsentIsSilent(unittest.TestCase):

    def test_a_plan_declaring_none_of_them_passes(self):
        plan, takes = _plan()
        self.assertEqual(_errs(plan, takes), [])

    def test_chapters_without_pace_cpm_pass(self):
        plan, takes = _plan(chapters=[{"id": "CH1", "title": "One"}])
        self.assertEqual(_errs(plan, takes), [])


class PresentAndMalformedIsAnError(unittest.TestCase):

    def test_pace_cpm_must_be_a_positive_number(self):
        for bad in (0, -3, "fast", True):
            plan, takes = _plan(chapters=[{"id": "CH1", "title": "One",
                                           "pace_cpm": bad}])
            errs = _errs(plan, takes)
            self.assertTrue(any("pace_cpm" in e for e in errs),
                            "%r passed" % (bad,))

    def test_pace_cpm_accepts_a_real_ladder(self):
        plan, takes = _plan(chapters=[{"id": "CH1", "title": "One",
                                       "pace_cpm": 21.5}])
        self.assertEqual(_errs(plan, takes), [])

    def test_loop_and_thread_marks_must_be_non_empty_strings(self):
        for key in ("opens_loop", "pays_loop", "thread", "flag_note"):
            for bad in (3, "", "   ", True, ["L1"]):
                plan, takes = _plan()
                plan["beats"][0][key] = bad
                errs = _errs(plan, takes)
                self.assertTrue(any(key in e for e in errs),
                                "%s=%r passed" % (key, bad))

    def test_peak_must_be_a_boolean(self):
        for bad in ("yes", 1, "true"):
            plan, takes = _plan()
            plan["beats"][1]["peak"] = bad
            self.assertTrue(any("peak" in e for e in _errs(plan, takes)),
                            "%r passed" % (bad,))

    def test_declared_threads_and_loops_need_their_shape(self):
        plan, takes = _plan(threads=[{"id": "TH1"}])       # no why
        self.assertTrue(any("threads[0]" in e for e in _errs(plan, takes)))
        plan, takes = _plan(loops=[{"why": "x"}])          # no id
        self.assertTrue(any("loops[0]" in e for e in _errs(plan, takes)))

    def test_a_well_formed_declaration_passes(self):
        plan, takes = _plan(threads=[{"id": "TH1", "why": "the sloth thread"}],
                            loops=[{"id": "L1"}])
        plan["beats"][0]["opens_loop"] = "L1"
        plan["beats"][1]["pays_loop"] = "L1"
        plan["beats"][0]["thread"] = "TH1"
        self.assertEqual(_errs(plan, takes), [])


class AnUndeclaredThreadIsCraftNotCorruption(unittest.TestCase):
    """The split the repo already draws: validate_* is identity and
    corruption, *_notes is craft. cutbar reads an undeclared thread and
    asks for its why; the schema must not pre-empt that with an error,
    or the writer gets a refusal where it should get a note."""

    def test_a_beat_naming_an_undeclared_thread_still_validates(self):
        plan, takes = _plan()
        plan["beats"][0]["thread"] = "TH_NOT_DECLARED"
        self.assertEqual(_errs(plan, takes), [])


if __name__ == "__main__":
    unittest.main()
