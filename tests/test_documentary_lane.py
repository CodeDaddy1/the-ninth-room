# -*- coding: utf-8 -*-
"""The script lane can reach the end of the pipeline.

2026-08-26, found driving a real short-form documentary (topic: oligarchy)
end to end. `_run_editplan` demanded a pitch and an approving story round —
and `_run_story` REFUSES to pitch a documentary at all, in the runner as
well as the queue's front door. So the cut was unreachable: the script
could be researched, interviewed over, written and approved, and "Build
the cut" answered "no story pitches yet — pitch stories first" forever.

Its approval is the approved SCRIPT, which is the artifact the cut is
actually built from on this lane — the edit-plan prompt already said so.

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

from pipeline import jobs  # noqa: E402

WORK = Path(__file__).resolve().parent.parent / "work"


class LaneBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    def _brief(self, origin):
        (self.tmp / "story_brief.json").write_text(json.dumps(
            {"origin": origin, "subject": "how ownership concentrates",
             "target_minutes": 0.75, "chapters": 1}))

    def _takes(self):
        (self.tmp / "analysis").mkdir(parents=True, exist_ok=True)
        (self.tmp / "analysis" / "takes.json").write_text(
            json.dumps({"takes": [], "groups": []}))

    def _script(self, locked):
        (self.tmp / "script.json").write_text(json.dumps(
            {"slug": "ep", "origin": "script", "locked": locked,
             "chapters": [{"id": "CH1", "title": "The name inside",
                           "target_s": 45, "sections": [
                               {"id": "CH1.S1", "kind": "vo", "text": "a line",
                                "est_s": 4.0}]}]}))


class EditPlanGate(LaneBase):
    def test_a_documentary_is_never_told_to_pitch(self):
        """The dead end. `_run_story` refuses this lane, so a precondition
        naming a pitch can never be satisfied."""
        self._brief("script")
        self._script(locked=True)
        self._takes()
        # it gets PAST the gate and fails later, on the dispatch — which is
        # a different thing entirely from being refused for a missing pitch
        with self.assertRaises(Exception) as cm:
            jobs._run_editplan("ep", lambda *a: None, lambda p: None)
        self.assertNotIn("pitch", str(cm.exception).lower())

    def test_unrecorded_lines_are_refused_BEFORE_a_session_is_dispatched(self):
        """The cut references recorded takes by id, so with no ingest the
        designer has nothing to reference.

        It cost a full billed session to learn that once: the agent ran,
        explained what it could not do, and the job failed with "session
        finished but edit_plan.json was not written". A gate a file check
        can answer must answer before the dispatch.
        """
        self._brief("script")
        self._script(locked=True)
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_editplan("ep", lambda *a: None, lambda p: None)
        msg = str(cm.exception)
        self.assertIn("not recorded yet", msg)
        # and it never reached the dispatch — that failure has its own words
        self.assertNotIn("session finished", msg)

    def test_a_documentary_without_a_script_is_told_to_write_one(self):
        self._brief("script")
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_editplan("ep", lambda *a: None, lambda p: None)
        self.assertIn("Script desk", str(cm.exception))

    def test_an_unapproved_script_is_refused_by_name(self):
        self._brief("script")
        self._script(locked=False)
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_editplan("ep", lambda *a: None, lambda p: None)
        self.assertIn("not approved", str(cm.exception))

    def test_the_FILMED_lane_still_wants_its_pitch(self):
        self._brief("footage")
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_editplan("ep", lambda *a: None, lambda p: None)
        self.assertIn("pitch stories first", str(cm.exception))

    def test_the_filmed_lane_still_wants_an_approving_round(self):
        self._brief("footage")
        (self.tmp / "stories.json").write_text(json.dumps({"options": []}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_editplan("ep", lambda *a: None, lambda p: None)
        self.assertIn("approving round", str(cm.exception))


class EditPlanPrompt(LaneBase):
    def test_a_documentary_is_never_pointed_at_files_it_cannot_have(self):
        """stories.json and story_feedback.json cannot exist on this lane;
        the prompt named both unconditionally."""
        self._brief("script")
        self._script(locked=True)
        self._takes()
        prompt = jobs._editplan_prompt("ep")
        self.assertNotIn("stories.json", prompt)
        self.assertNotIn("story_feedback.json", prompt)
        self.assertIn("script.json", prompt)
        self.assertIn("documentary", prompt)

    def test_the_filmed_lane_is_still_pointed_at_its_pitch(self):
        self._brief("footage")
        prompt = jobs._editplan_prompt("ep")
        self.assertIn("stories.json", prompt)
        self.assertIn("APPROVING round", prompt)


class AssembleGate(LaneBase):
    def test_no_cut_is_a_sentence_not_a_stack_trace(self):
        """`build_timeline` raised a bare FileNotFoundError at 2% and the
        desk showed "[Errno 2] No such file or directory: …/edit_plan.json".
        `_run_reproxy` has carried this guard, and its reason, for longer.
        """
        with self.assertRaises(jobs.JobError) as cm:
            jobs._run_assemble("ep", lambda *a: None, lambda p: None)
        msg = str(cm.exception)
        self.assertIn("no cut yet", msg)
        self.assertNotIn("Errno", msg)
        self.assertNotIn("edit_plan.json", msg)


if __name__ == "__main__":
    unittest.main()
