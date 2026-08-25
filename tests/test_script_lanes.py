# -*- coding: utf-8 -*-
"""Two lanes into the same script, and the interview that precedes both.

`origin: "footage"` is a visit — shot first, pitched, approved, then
scripted. `origin: "script"` is Caleb's other format: no filmed content at
all, written from a subject and research, performed later at his desk.

The script lane was impossible to START before 2026-08-24. Three separate
gates assumed footage came first, and one of them was an UNGUARDED read of
analysis/takes.json that simply crashed. Pinned here so it stays possible.

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

from pipeline import editroom, jobs  # noqa: E402


class Lanes(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp
        self._popen = jobs.subprocess.Popen if hasattr(jobs, "subprocess") else None

    def tearDown(self):
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self, **kw):
        d = {"target_minutes": 12, "chapters": 5, "vo_share": 0.35}
        d.update(kw)
        (self.tmp / "story_brief.json").write_text(json.dumps(d))

    # --- the lane is stated, not sniffed ---------------------------------

    def test_the_default_lane_is_footage(self):
        self.brief()
        self.assertEqual(jobs._script_origin("ep"), "footage")

    def test_an_empty_footage_folder_does_not_make_it_script_led(self):
        """Sniffing would make 'I have not uploaded yet' and 'there will
        never be footage' the same state, and they lead to opposite
        pipelines."""
        self.brief()
        self.assertEqual(jobs._script_origin("ep"), "footage")

    def test_a_stated_script_lane_is_honoured(self):
        self.brief(origin="script", subject="why the pendulum stopped")
        self.assertEqual(jobs._script_origin("ep"), "script")

    def test_a_missing_brief_is_not_a_crash(self):
        self.assertEqual(jobs._script_origin("ep"), "footage")

    # --- the interview's own guards --------------------------------------

    def test_the_interview_needs_a_brief(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_interview("ep", lambda *a: None, lambda p: None)
        self.assertIn("no brief yet", str(cm.exception))

    def test_the_script_lane_interview_needs_research(self):
        """With no footage, research is the ONLY material the director
        has — interviewing without it asks Caleb to supply what the
        pipeline is meant to fetch."""
        self.brief(origin="script", subject="the pendulum")
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_interview("ep", lambda *a: None, lambda p: None)
        self.assertIn("no research yet", str(cm.exception))

    def test_the_footage_lane_interview_needs_an_approved_direction(self):
        self.brief()
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_interview("ep", lambda *a: None, lambda p: None)
        self.assertIn("approving round", str(cm.exception))

    def test_an_approved_script_refuses_a_new_interview(self):
        self.brief(origin="script", subject="the pendulum")
        (self.tmp / "research.json").write_text('{"facts": []}')
        (self.tmp / "script.json").write_text(json.dumps({"locked": True}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_interview("ep", lambda *a: None, lambda p: None)
        self.assertIn("unlock", str(cm.exception))

    # --- the script lane needs no pitch, and must not crash on takes -----

    def test_the_script_lane_does_not_demand_an_approving_story_round(self):
        """There was no footage to pitch from, so there is no pitch."""
        self.brief(origin="script", subject="the pendulum")
        (self.tmp / "script_questions.json").write_text(json.dumps(
            {"slug": "ep", "stage": "interview", "questions": []}))
        calls = []
        # Patch the dispatcher the job ACTUALLY calls. The creative kinds
        # moved to _dispatch_json on 2026-08-25 to capture the session id;
        # this stub kept patching the old one, so the guard test spawned a
        # REAL Claude session — 250s suites and a starved local lane.
        real = jobs._dispatch_json
        jobs._dispatch_json = lambda *a, **k: calls.append(1)
        try:
            with self.assertRaises(RuntimeError) as cm:
                jobs._run_script("ep", lambda *a: None, lambda p: None)
        finally:
            jobs._dispatch_json = real
        # it got past every guard and only failed for want of an artifact
        self.assertEqual(len(calls), 1)
        self.assertIn("was not written", str(cm.exception))

    def test_the_missing_takes_file_is_not_a_crash(self):
        """The bug that made a footage-free episode impossible: an
        unguarded json.load of analysis/takes.json."""
        self.assertIsNone(jobs._read_json(self.tmp / "analysis" / "takes.json"))

    def test_the_footage_lane_still_demands_the_pitch(self):
        self.brief()
        (self.tmp / "script_questions.json").write_text(json.dumps(
            {"slug": "ep", "stage": "interview", "questions": []}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("approving round", str(cm.exception))

    # --- what reaches the writer -----------------------------------------

    def test_the_lane_reaches_the_prompt(self):
        self.brief(origin="script", subject="the pendulum")
        (self.tmp / "script_questions.json").write_text(json.dumps(
            {"slug": "ep", "stage": "interview", "questions": []}))
        p = jobs._script_prompt("ep")
        self.assertIn("SCRIPT-LED", p)
        self.assertIn("first person singular is allowed", p)
        self.assertIn("no ninth-room moment", p)

    def test_the_visit_lane_says_the_opposite(self):
        self.brief()
        p = jobs._script_prompt("ep")
        self.assertIn("VISIT", p)
        self.assertIn("ensemble", p)
        self.assertIn("ninth-room moment", p)

    def test_his_answers_reach_the_writer(self):
        """The failure mode an interview invites is being politely
        ignored — the same one the brief clause was written to prevent."""
        self.brief()
        (self.tmp / "script_feedback.json").write_text(json.dumps(
            {"rounds": [{"decision": "answers",
                         "answers": {"Q1": "the skin thread"},
                         "notes": "keep it wry"}]}))
        p = jobs._script_prompt("ep")
        self.assertIn("the skin thread", p)
        self.assertIn("keep it wry", p)

    def test_a_revision_carries_his_direction(self):
        self.brief()
        (self.tmp / "script.json").write_text(json.dumps({"round": 1}))
        (self.tmp / "script_feedback.json").write_text(json.dumps(
            {"rounds": [{"decision": "direction",
                         "notes": "chapter 4 is thin, merge it"}]}))
        p = jobs._script_prompt("ep")
        self.assertIn("REVISE", p)
        self.assertIn("chapter 4 is thin", p)
        self.assertIn("keep what he did not mention", p)


class BriefFields(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_topic_is_a_legitimate_subject(self):
        b = editroom._save_story_brief(
            "ep", 12, 5, "", "", 0.35,
            "why the Foucault pendulum stopped", "script")
        self.assertEqual(b["origin"], "script")
        self.assertEqual(b["subject"], "why the Foucault pendulum stopped")

    def test_a_script_lane_brief_needs_something_to_research(self):
        with self.assertRaises(editroom.IngestError) as cm:
            editroom._save_story_brief("ep", 12, 5, "", "", 0.35, "", "script")
        self.assertIn("needs a subject", str(cm.exception))

    def test_an_unknown_origin_is_refused(self):
        with self.assertRaises(editroom.IngestError):
            editroom._save_story_brief("ep", 12, 5, "", "x", 0.35, "", "hybrid")

    def test_a_visit_still_works_unchanged(self):
        b = editroom._save_story_brief("ep", 25, 9, "", "HMNS", 0.6)
        self.assertEqual(b["origin"], "footage")
        self.assertEqual(b["location"], "HMNS")


class ScriptLedPhase(unittest.TestCase):
    """The desk must let a footage-free project START. It used to pin it at
    'footage' forever, which made the format unreachable from the UI."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        (self.tmp / "footage").mkdir()
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.tmp
        editroom.analysis_dir = lambda slug: self.tmp / "analysis"

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self):
        (self.tmp / "story_brief.json").write_text(json.dumps(
            {"target_minutes": 12, "chapters": 5, "origin": "script",
             "subject": "the pendulum"}))

    def test_no_footage_no_longer_strands_it(self):
        self.brief()
        row = editroom._project_row("ep")
        self.assertEqual(row["phase"], "story")
        self.assertIn("Research it", row["next"])

    def test_with_research_it_asks_for_the_interview(self):
        self.brief()
        (self.tmp / "research.json").write_text('{"facts": []}')
        row = editroom._project_row("ep")
        self.assertEqual(row["phase"], "script")
        self.assertIn("Interview me", row["next"])

    def test_with_an_interview_it_asks_for_the_draft(self):
        self.brief()
        (self.tmp / "research.json").write_text('{"facts": []}')
        (self.tmp / "script_questions.json").write_text('{"questions": []}')
        row = editroom._project_row("ep")
        self.assertIn("Write the script", row["next"])

    def test_a_draft_asks_for_approval_not_recording(self):
        self.brief()
        (self.tmp / "research.json").write_text('{"facts": []}')
        (self.tmp / "script_questions.json").write_text('{"questions": []}')
        (self.tmp / "script.json").write_text(json.dumps(
            {"locked": False, "chapters": []}))
        row = editroom._project_row("ep")
        self.assertIn("approve it, or send direction", row["next"])

    def test_a_visit_phase_is_untouched(self):
        (self.tmp / "story_brief.json").write_text(json.dumps(
            {"target_minutes": 25, "chapters": 9, "origin": "footage"}))
        row = editroom._project_row("ep")
        self.assertEqual(row["phase"], "footage")


if __name__ == "__main__":
    unittest.main()
