# -*- coding: utf-8 -*-
"""The cut has to get past something to become the cut.

`_run_editplan` was the only session-written artifact in the program with
no post-condition bar: `_run_script` is gated by `script_notes`,
`_run_coverage` by `validate_edit_plan` + `coverage_notes`, and the cut —
the artifact Caleb actually watches — was checked for one thing, that a
file appeared. What that produced is on record: 82 beats, 78% of them
undifferentiated `build`, one hook, one payoff, zero peaks, zero loops.

Staging-then-promote is not a tidier spelling of write-then-check. A
session that writes `edit_plan.json` directly has ALREADY replaced the
cut by the time anything looks at it, so a failed check leaves the
project holding a plan nobody approved. Writing to `staging/` means a
refusal changes nothing on disk — which is what makes a retry an edit of
the staged file rather than a second session re-deriving it from
nothing.

The craft bar is deliberately NOT armed here. `promote.BAR_ARMED` is the
whole switch, and it stays False until the thresholds have been through
the calibration review with Caleb — the same idiom as
`cutbar.GEAR_RATIO_MIN = None`. These tests pin both states, because a
switch nobody has flipped in a test is a switch nobody knows works.

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

from pipeline import (beat_identity as bi, cutbar, ingest, jobs,  # noqa: E402
                      plan_history as ph, promote, schemas)

TAKES = {"takes": [
    {"id": "T04", "file": "a.mp4", "s": 0.0, "e": 30.0, "duration": 30.0,
     "kind": "oncamera", "transcript": "One. Two. Three."},
    {"id": "T12", "file": "b.mp4", "s": 0.0, "e": 30.0, "duration": 30.0,
     "kind": "oncamera", "transcript": "Four. Five."}]}
BROLL = {"clips": []}


def _plan(hook_take="T04"):
    return {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "beats": [
                {"id": "whatever-1", "purpose": "hook", "take_id": hook_take,
                 "trim": {"s": 0.0, "e": 8.0}, "transition_in": "cut",
                 "fragment": True},
                {"id": "whatever-2", "purpose": "payoff", "take_id": "T12",
                 "trim": {"s": 0.0, "e": 9.0}, "transition_in": "cut",
                 "fragment": True}]}


class _SeamFixture(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp, self._ad = ingest.work_path, ingest.analysis_dir
        ingest.work_path = lambda slug: self.tmp
        ingest.analysis_dir = lambda slug: self.tmp / "analysis"
        for mod in (promote, ph):
            mod.work_path = ingest.work_path
        promote.analysis_dir = ingest.analysis_dir
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps(TAKES))
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(BROLL))
        self._armed = promote.BAR_ARMED

    def tearDown(self):
        promote.BAR_ARMED = self._armed
        ingest.work_path, ingest.analysis_dir = self._wp, self._ad
        for mod in (promote, ph):
            mod.work_path = self._wp
        promote.analysis_dir = self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def stage(self, plan):
        p = promote.staged_plan("ep")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(plan))
        return p

    def live(self):
        return json.loads((self.tmp / "edit_plan.json").read_text())

    def quiet(self, *a):
        pass


class Seam(_SeamFixture):

    # ---- the happy path ------------------------------------------------

    def test_a_clean_staged_cut_becomes_the_cut(self):
        self.stage(_plan())
        r = promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertEqual(r["beats"], 2)
        self.assertEqual(len(self.live()["beats"]), 2)

    def test_the_engine_mints_the_ids_whatever_the_agent_wrote(self):
        """The brief stops specifying ids: a beat is named after the shot
        it shows, so a rebuilt cut keeps its history by construction."""
        self.stage(_plan())
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertEqual([b["id"] for b in self.live()["beats"]],
                         ["B-T04", "B-T12"])
        self.assertEqual(self.live()["id_scheme"], bi.ID_SCHEME)

    def test_the_staged_file_is_kept_as_the_agents_raw_output(self):
        self.stage(_plan())
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertFalse(promote.staged_plan("ep").exists())
        # first promote has no predecessor to archive, so nothing is kept
        self.stage(_plan())
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        raw = ph.history_dir("ep") / "staged.v0001.json"
        self.assertTrue(raw.exists(), "the session's own output is the only "
                                      "record of what it actually wrote")

    # ---- the point of staging ------------------------------------------

    def test_a_missing_staged_file_names_the_path_it_wanted(self):
        with self.assertRaises(RuntimeError) as cm:
            promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertIn("staging", str(cm.exception))

    def test_an_invalid_cut_leaves_the_built_one_untouched(self):
        """THE WHOLE REASON FOR STAGING. Under write-then-check the
        project would already be holding the broken plan."""
        self.stage(_plan())
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        good = self.live()
        bad = _plan()
        bad["beats"][1]["take_id"] = "T99"          # a take that is not there
        self.stage(bad)
        with self.assertRaises(RuntimeError):
            promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertEqual(self.live(), good)

    def test_a_refused_promote_keeps_the_staged_file_for_the_retry(self):
        bad = _plan()
        bad["beats"][1]["take_id"] = "T99"
        self.stage(bad)
        with self.assertRaises(RuntimeError):
            promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertTrue(promote.staged_plan("ep").exists(),
                        "clearing it here would turn every retry back into "
                        "a full re-derivation")

    def test_the_refusal_quotes_the_findings_not_just_a_count(self):
        bad = _plan()
        bad["beats"][1]["take_id"] = "T99"
        self.stage(bad)
        with self.assertRaises(RuntimeError) as cm:
            promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertIn("T99", str(cm.exception))

    # ---- the bar, both ways --------------------------------------------

    def test_unarmed_the_bar_reports_and_does_not_block(self):
        promote.BAR_ARMED = False
        self.stage(_plan())
        r = promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertTrue(r["notes"], "this fixture has no peaks or loops")
        self.assertEqual(len(self.live()["beats"]), 2)

    def test_armed_the_same_cut_is_refused(self):
        """One constant is the entire arming step. If this passes only
        because the fixture is clean, the switch is untested."""
        promote.BAR_ARMED = True
        self.stage(_plan())
        with self.assertRaises(RuntimeError) as cm:
            promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.assertIn("misses the bar", str(cm.exception))
        self.assertFalse((self.tmp / "edit_plan.json").exists())

    def test_correctness_refuses_whether_or_not_the_bar_is_armed(self):
        """A plan that does not validate cannot be rendered at all, so it
        is not waiting on anybody's calibration."""
        promote.BAR_ARMED = False
        bad = _plan()
        bad["beats"][1]["take_id"] = "T99"
        self.stage(bad)
        with self.assertRaises(RuntimeError):
            promote.promote_cut("ep", reason="promote", log=self.quiet)

    # ---- history --------------------------------------------------------

    def test_the_replaced_cut_is_archived(self):
        self.stage(_plan())
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        self.stage(_plan(hook_take="T12"))
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        rows = ph.versions("ep")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reason"], "promote")

    # ---- check_cut, the shared implementation ---------------------------

    def test_check_cut_reads_the_staged_file_when_asked(self):
        self.stage(_plan())
        promote.promote_cut("ep", reason="promote", log=self.quiet)
        bad = _plan()
        bad["beats"][1]["take_id"] = "T99"
        self.stage(bad)
        self.assertEqual(promote.check_cut("ep")["errors"], [])
        self.assertTrue(promote.check_cut("ep", staged=True)["errors"])

    def test_check_cut_reports_rather_than_raising(self):
        bad = _plan()
        bad["beats"][1]["take_id"] = "T99"
        self.stage(bad)
        r = promote.check_cut("ep", staged=True)
        self.assertFalse(r["ok"])
        self.assertTrue(r["errors"])
        self.assertIn("beats", r["metrics"])


class TheCraftClauseCarriesRealNumbers(unittest.TestCase):
    """A gate that asks for declarations nobody was told to make is not a
    gate, it is a trap: the session spends its minutes and the promote
    refuses over fields the agent never heard of."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        jobs.work_path = ingest.work_path

    def tearDown(self):
        ingest.work_path = self._wp
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self, **kw):
        (self.tmp / "story_brief.json").write_text(json.dumps(kw))

    def test_the_numbers_are_READ_from_cutbar_not_retyped(self):
        """The calibration doc's promise is that recalibrating means
        changing one constant. Prove the clause follows the constant."""
        self.brief(chapters=5, delivery="long")
        was = cutbar.PACE_DECLINE_MAX
        try:
            first = jobs._craft_clause("ep")
            cutbar.PACE_DECLINE_MAX = 0.42
            second = jobs._craft_clause("ep")
        finally:
            cutbar.PACE_DECLINE_MAX = was
        self.assertIn("70%", first)
        self.assertIn("42%", second)

    def test_the_peak_count_follows_the_chapter_count(self):
        self.brief(chapters=5, delivery="long")
        self.assertIn("Protect 4 PEAK", jobs._craft_clause("ep"))
        self.brief(chapters=9, delivery="long")
        self.assertIn("Protect 8 PEAK", jobs._craft_clause("ep"))

    def test_a_short_is_not_told_to_build_a_chapter_ladder(self):
        self.brief(chapters=1, delivery="short")
        c = jobs._craft_clause("ep")
        self.assertIn("SHORT", c)
        self.assertNotIn("pace_cpm", c)
        self.assertNotIn("chapter-preview montage", c)

    def test_the_chapter_half_of_the_peak_rule_is_dropped_below_two(self):
        """Saying it anyway teaches a short-form writer to look for a
        structure its format does not have."""
        self.brief(chapters=1, delivery="short")
        self.assertNotIn("every chapter after the intro",
                         jobs._craft_clause("ep"))
        self.brief(chapters=5, delivery="long")
        self.assertIn("every chapter after the intro",
                      jobs._craft_clause("ep"))

    def test_it_names_the_command_that_proves_the_bar_empty(self):
        self.brief(chapters=5)
        self.assertIn("cut-check ep --staged", jobs._craft_clause("ep"))

    def test_it_asks_for_every_field_the_bar_grades(self):
        self.brief(chapters=5, delivery="long")
        c = jobs._craft_clause("ep")
        for field in ("peak", "pace_cpm", "opens_loop", "pays_loop",
                      "framing", "flag_note", "threads"):
            self.assertIn(field, c, "the bar grades %s and the writer is "
                                    "never told about it" % field)


class TheBriefAndTheBarAgree(unittest.TestCase):
    """The standing rule from the film studies: a finding is not adopted
    until something READS it. Four findings sat agreed-and-unwired for
    months. The craft bar is measured by `cutbar`, stated per-episode by
    `_craft_clause`, and explained once in the agent's own brief — and if
    the brief stops naming a field, the writer stops emitting it and the
    bar starts failing cuts for a reason nobody wrote down."""

    BRIEF = (Path(__file__).resolve().parent.parent / ".claude" / "agents"
             / "story-designer.md")

    def brief(self):
        return self.BRIEF.read_text()

    def test_the_brief_names_every_field_the_bar_grades(self):
        for field in ("peak", "pace_cpm", "opens_loop", "pays_loop",
                      "framing", "flag_note", "threads"):
            self.assertIn(field, self.brief(),
                          "the bar grades %s and the brief never says so"
                          % field)

    def test_the_brief_sends_the_writer_to_staging_not_the_live_cut(self):
        b = self.brief()
        self.assertIn("staging/edit_plan.json", b)
        self.assertIn("minted by the engine", b)

    def test_the_brief_names_the_command_the_runner_actually_runs(self):
        self.assertIn("cut-check", self.brief())

    def test_the_brief_does_not_still_teach_the_old_verify_recipe(self):
        """It used to paste a python one-liner that validated the LIVE
        plan — the file the agent must no longer write."""
        b = self.brief()
        self.assertNotIn("plan  = json.load(open('work/<slug>/edit_plan.json'))",
                         b)


class TheEnvelopeFlagDoesNotEatTheVerdict(_SeamFixture):
    """`_recheck_*` return `ok` meaning "this artifact passes". The routes
    wrapped them in `dict(..., ok=True)` for the call-succeeded flag,
    which overwrote it — and the Studio badges "clean ✓" on `ok`
    (session-doors.tsx:116), so a script that missed its bar was reported
    clean on the one surface built to say it had not. The HTTP 200 is
    already the call-succeeded signal.
    """

    def test_recheck_says_false_when_the_cut_actually_fails(self):
        from pipeline import editroom
        was = editroom.work_path
        editroom.work_path = ingest.work_path
        try:
            self.stage(_plan())
            promote.promote_cut("ep", reason="promote", log=self.quiet)
            r = editroom._recheck_cut("ep")
            self.assertTrue(r["notes"], "the fixture has no peaks or loops")
            self.assertFalse(r["ok"], "a failing cut reported as ok is the "
                                      "false pass this class exists for")
        finally:
            editroom.work_path = was

    def test_recheck_says_true_only_when_it_really_passes(self):
        """A flag that is always False is as useless as one always True."""
        from pipeline import editroom
        was = editroom.work_path
        editroom.work_path = ingest.work_path
        try:
            self.stage(_plan())
            promote.promote_cut("ep", reason="promote", log=self.quiet)
            r = editroom._recheck_cut("ep")
            self.assertEqual(r["ok"], not r["errors"] and not r["notes"])
        finally:
            editroom.work_path = was


if __name__ == "__main__":
    unittest.main()
