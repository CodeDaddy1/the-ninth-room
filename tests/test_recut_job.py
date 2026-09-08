# -*- coding: utf-8 -*-
"""Rebuilding a cut, and keeping the verdicts that still apply.

`_run_editplan` refuses when a plan exists — "the cut is built; re-cutting
is a session decision" — and that refusal is right: overwriting a cut the
desks and reviews hang off is a decision, not a button press. But it left
the Studio's own "Re-build the cut" banners dispatching `editplan`, which
means every one of them failed red, every time. A door that is drawn and
does not open.

`recut` is that door. It differs from `editplan` in exactly two ways: it
REQUIRES a plan rather than refusing one, and it hands the promote seam
the plan being replaced, so verdicts follow the SHOT through the id map
instead of being thrown away. Everything else is the same function.

Caleb's one line is required. That is pre-registration in miniature: a
re-cut with no stated intent cannot be judged afterwards against the one
it replaced, which is the entire point of the benchmark.

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

from pipeline import (beat_identity as bi, ingest, jobs,  # noqa: E402
                      plan_history as ph, promote)

TAKES = {"takes": [
    {"id": "T04", "file": "a.mp4", "s": 0.0, "e": 40.0, "duration": 40.0,
     "kind": "oncamera", "transcript": "One. Two."},
    {"id": "T12", "file": "b.mp4", "s": 0.0, "e": 40.0, "duration": 40.0,
     "kind": "oncamera", "transcript": "Three. Four."},
    {"id": "T30", "file": "c.mp4", "s": 0.0, "e": 40.0, "duration": 40.0,
     "kind": "oncamera", "transcript": "Five. Six."}]}


def _beat(bid, take, s, e, purpose="build"):
    return {"id": bid, "purpose": purpose, "take_id": take,
            "trim": {"s": s, "e": e}, "transition_in": "cut",
            "fragment": True}


def _plan(beats):
    return {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "beats": beats}


class TheRegistry(unittest.TestCase):

    def test_recut_is_a_kind_on_the_session_lane(self):
        self.assertIn("recut", jobs.KINDS)
        self.assertEqual(jobs.lane_of("recut"), "session")

    def test_it_chains_to_assemble(self):
        """A re-cut nobody can watch is not finished."""
        self.assertEqual(jobs.CHAIN.get("recut"), "assemble")

    def test_editplans_refusal_is_left_alone(self):
        """`recut` is the door past it, not a loosening of it."""
        src = (Path(__file__).resolve().parent.parent / "pipeline"
               / "jobs.py").read_text()
        self.assertIn("edit_plan.json already exists", src)


class Guards(unittest.TestCase):
    """Both answerable before the click, which is the job contract's whole
    point: a session that dispatches and then finds it had nothing to do
    costs billed minutes to learn what a file check knows for free."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        jobs.work_path = ingest.work_path

    def tearDown(self):
        ingest.work_path = self._wp
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_cut_to_recut_is_refused_by_name(self):
        with self.assertRaises(jobs.JobError) as cm:
            jobs.start("recut", "ep", arg="tighter")
        self.assertIn("no cut to re-cut", str(cm.exception))

    def test_a_missing_reason_is_refused(self):
        (self.tmp / "edit_plan.json").write_text("{}")
        with self.assertRaises(jobs.JobError) as cm:
            jobs.start("recut", "ep")
        self.assertIn("one line", str(cm.exception))

    def test_whitespace_is_not_a_reason(self):
        (self.tmp / "edit_plan.json").write_text("{}")
        with self.assertRaises(jobs.JobError):
            jobs.start("recut", "ep", arg="   ")

    def test_the_runner_repeats_the_guards(self):
        """A chain follower, a retry or a direct call goes straight to the
        runner — the lesson `_run_story` records at its own guard, learned
        from an ad-hoc script that spawned a real session."""
        with self.assertRaises(RuntimeError):
            jobs._run_recut("ep", lambda *a: None, lambda p: None, arg="x")
        (self.tmp / "edit_plan.json").write_text(json.dumps(_plan([])))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_recut("ep", lambda *a: None, lambda p: None)
        self.assertIn("one line", str(cm.exception))


class VerdictsFollowTheShot(unittest.TestCase):
    """The three fates, and the rule behind them: a verdict belongs to the
    SHOT Caleb watched, not to the slot it occupied."""

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
        (self.tmp / "analysis" / "broll.json").write_text(
            json.dumps({"clips": []}))
        # the cut Caleb reviewed
        first = _plan([_beat("x1", "T04", 0.0, 8.0, "hook"),
                       _beat("x2", "T12", 0.0, 9.0),
                       _beat("x3", "T30", 0.0, 9.0, "payoff")])
        p = promote.staged_plan("ep")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(first))
        promote.promote_cut("ep", reason="promote", log=lambda *a: None)
        self.before = json.loads((self.tmp / "edit_plan.json").read_text())
        (self.tmp / "review.json").write_text(json.dumps({
            "B-T04": {"status": "approved", "note": "the hook lands"},
            "B-T12": {"status": "approved", "note": "keep"},
            "B-T30": {"status": "flagged", "note": "fix the tail"}}))

    def tearDown(self):
        ingest.work_path, ingest.analysis_dir = self._wp, self._ad
        for mod in (promote, ph):
            mod.work_path = self._wp
        promote.analysis_dir = self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def recut(self, beats):
        promote.staged_plan("ep").write_text(json.dumps(_plan(beats)))
        return promote.promote_cut("ep", reason="recut", note="tighter",
                                   carry_from=self.before,
                                   log=lambda *a: None)

    def review(self):
        return json.loads((self.tmp / "review.json").read_text())

    def test_an_unchanged_beat_keeps_its_verdict(self):
        r = self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                        _beat("b", "T12", 0.0, 9.0),
                        _beat("c", "T30", 0.0, 9.0, "payoff")])
        self.assertIn("B-T12", r["carried"])
        self.assertEqual(self.review()["B-T12"],
                         {"status": "approved", "note": "keep"})

    def test_a_recut_beat_comes_back_to_the_queue_keeping_its_note(self):
        """The note is Caleb's reasoning and still applies to the shot;
        the approval was of a cut that no longer exists."""
        r = self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                        _beat("b", "T12", 0.0, 6.5),      # trim moved
                        _beat("c", "T30", 0.0, 9.0, "payoff")])
        self.assertIn("B-T12", r["requeued"])
        self.assertEqual(self.review()["B-T12"], {"note": "keep"})

    def test_a_dropped_beat_is_archived_by_name_never_silently(self):
        r = self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                        _beat("c", "T30", 0.0, 9.0, "payoff")])
        self.assertEqual(r["stranded"], ["B-T12"])
        arch = json.loads((self.tmp / promote.REVIEW_ARCHIVE).read_text())
        self.assertEqual(arch["entries"][0]["entry"]["note"], "keep")
        self.assertNotIn("B-T12", self.review())

    def test_a_new_beat_has_no_history_to_inherit(self):
        r = self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                        _beat("b", "T12", 0.0, 9.0),
                        _beat("c", "T30", 0.0, 9.0, "payoff"),
                        _beat("d", "T04", 20.0, 28.0)])
        self.assertEqual(r["added"], ["B-T04-2"])

    def test_a_reordered_beat_still_carries_because_the_shot_is_the_same(self):
        """The reason the scheme anchors on the shot: moving a beat is not
        a reason to re-watch it."""
        r = self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                        _beat("c", "T30", 0.0, 9.0),
                        _beat("b", "T12", 0.0, 9.0, "payoff")])
        self.assertIn("B-T12", r["carried"])
        self.assertEqual(self.review()["B-T12"]["status"], "approved")

    def test_the_report_records_what_moved(self):
        r = self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                        _beat("b", "T12", 0.0, 6.5),
                        _beat("c", "T30", 0.0, 9.0, "payoff")])
        rep = json.loads((self.tmp / promote.RECUT_REPORT).read_text())
        self.assertEqual(rep["note"], "tighter")
        self.assertIn("metrics_before", rep)
        self.assertIn("metrics", rep)

    def test_the_replaced_cut_is_archived_as_a_recut(self):
        self.recut([_beat("a", "T04", 0.0, 8.0, "hook"),
                    _beat("c", "T30", 0.0, 9.0, "payoff")])
        self.assertEqual(ph.latest("ep")["reason"], "recut")


if __name__ == "__main__":
    unittest.main()
