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

    def _far_outside(self):
        """A trim that lands in a NEIGHBOUR's words, which is what the
        bounds rule refuses since 2026-09-08. Silence past the last take
        on a file is legal now (`schemas.take_window`), so the fixture
        needs a neighbour for there to be anything to reach into."""
        plan, takes = _plan()
        takes["takes"].append({"id": "T3", "file": "b.mp4", "s": 30.0,
                               "e": 50.0, "duration": 50.0,
                               "transcript": "The neighbour's own line."})
        plan["beats"][1]["trim"] = {"s": 40.0, "e": 47.0}   # T2 ends at 10
        return plan, takes

    def test_a_trim_inside_another_take_reports_and_does_not_raise(self):
        plan, takes = self._far_outside()
        errs = _errs(plan, takes)                            # must not raise
        self.assertTrue(any("outside take" in e for e in errs), errs)

    def test_the_bounds_error_survives_to_the_caller(self):
        """The point of the fix: the diagnosis is IN the returned list."""
        plan, takes = self._far_outside()
        errs = _errs(plan, takes)
        self.assertTrue(any("T2" in e and "outside take" in e
                            for e in errs), errs)


class ABeatMayHoldTheSilenceAroundItsTake(unittest.TestCase):
    """A take's bounds are where the WORDS are. whisper ends them on the
    last syllable, and a beat routinely wants the silence on either side:
    hmns holds three of them on purpose, each with Caleb's note attached,
    and the assembler puts all three on screen. The old rule refused every
    one, which meant the shipped episode failed its own validator and
    could not be re-assembled at all (2026-09-08)."""

    def _two_takes_one_file(self):
        plan, takes = _plan()
        # T2 and T3 share b.mp4 with a 20s gap of silence between them
        takes["takes"].append({"id": "T3", "file": "b.mp4", "s": 30.0,
                               "e": 50.0, "duration": 50.0,
                               "transcript": "The neighbour's own line."})
        return plan, takes

    def test_a_held_tail_into_the_gap_is_legal(self):
        plan, takes = self._two_takes_one_file()
        plan["beats"][1]["trim"] = {"s": 0.0, "e": 12.0}     # 2s of silence
        self.assertEqual([e for e in _errs(plan, takes) if "trim" in e], [])

    def test_a_head_into_the_gap_is_legal(self):
        plan, takes = self._two_takes_one_file()
        plan["beats"][1]["take_id"] = "T3"
        plan["beats"][1]["trim"] = {"s": 28.0, "e": 50.0}    # 2s before it
        self.assertEqual([e for e in _errs(plan, takes) if "trim" in e], [])

    def test_the_gap_ends_where_the_next_takes_words_begin(self):
        plan, takes = self._two_takes_one_file()
        plan["beats"][1]["trim"] = {"s": 0.0, "e": 31.0}     # 1s into T3
        self.assertTrue(any("outside take" in e
                            for e in _errs(plan, takes)))

    def test_silence_after_the_last_take_on_a_file_is_capped_not_open(self):
        """With no neighbour there is nothing to reach into, so only
        MAX_HOLD_SEC bounds it. hmns's shot-T331 holds 1.6s of the kids
        still on camera and passes; an unbounded side would have let
        shot-T374 name a take on a 4.9s file and trim 236 to 240 of it."""
        plan, takes = _plan()                     # T2 on b.mp4 runs 0-10
        plan["beats"][1]["trim"] = {"s": 0.0, "e": 12.0}      # 2s hold
        self.assertEqual([e for e in _errs(plan, takes) if "trim" in e], [])
        plan["beats"][1]["trim"] = {"s": 0.0, "e": 14.0}      # 4s hold
        self.assertTrue(any("outside take" in e
                            for e in _errs(plan, takes)))

    def test_a_neighbour_on_a_DIFFERENT_file_does_not_bound_it(self):
        """T1 sits at 0-10 too, but on a.mp4. Only same-file takes are
        neighbours; otherwise every beat would be bounded by whatever
        happened to be recorded at the same clock time elsewhere."""
        plan, takes = _plan()
        plan["beats"][1]["trim"] = {"s": 0.0, "e": 12.0}
        self.assertEqual([e for e in _errs(plan, takes) if "trim" in e], [])

    def test_a_backwards_trim_is_still_refused(self):
        """Widening the window must not lose the check that a trim has
        to be a forward span at all."""
        plan, takes = _plan()
        plan["beats"][1]["trim"] = {"s": 8.0, "e": 3.0}
        self.assertTrue(any("empty or backwards" in e
                            for e in _errs(plan, takes)))

    def test_the_cap_wins_when_the_neighbours_are_far(self):
        t2 = {"id": "T2", "file": "b.mp4", "s": 20.0, "e": 30.0}
        rows = [{"id": "T1", "file": "b.mp4", "s": 0.0, "e": 10.0},
                t2,
                {"id": "T3", "file": "b.mp4", "s": 40.0, "e": 50.0},
                {"id": "T9", "file": "other.mp4", "s": 25.0, "e": 26.0}]
        self.assertEqual(schemas.take_window(t2, rows),
                         (20.0 - schemas.MAX_HOLD_SEC,
                          30.0 + schemas.MAX_HOLD_SEC))

    def test_a_close_neighbour_wins_over_the_cap(self):
        """The words of another take are the harder bound of the two."""
        t2 = {"id": "T2", "file": "b.mp4", "s": 20.0, "e": 30.0}
        rows = [{"id": "T1", "file": "b.mp4", "s": 12.0, "e": 19.0},
                t2,
                {"id": "T3", "file": "b.mp4", "s": 31.0, "e": 50.0}]
        self.assertEqual(schemas.take_window(t2, rows), (19.0, 31.0))


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
        # Every error is one of the three families that predate the craft
        # fields. A craft field firing here would mean the new checks are
        # not tolerant, which is what this ratchet is for.
        #
        # "kill list" joined the list on 2026-09-08, and it is a finding
        # rather than a regression: `rebind-takes` corrected beats[20]
        # from T49 to T50, which is the take it actually shows — and T50
        # carries a kill-list entry reading "Caleb: cut in review (was
        # BT17)". The mis-binding is why that rule never fired. Whether
        # the beat or the kill entry is the mistake is Caleb's call, and
        # it is open.
        for e in errs:
            self.assertTrue("outside take" in e or "mid-sentence" in e
                            or "kill list" in e,
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
