# -*- coding: utf-8 -*-
"""The script stage: budgets that must add up, recordings matched by name.

The feature exists because a 20-minute brief was unverifiable by eye
(Caleb, 2026-08-23). These tests pin the three honesty mechanisms:
validate_script refuses budget fiction (chapter sums vs targets), the
script job refuses to run without an approval or over an existing script
WITHOUT spawning a session, and recording status is decided by catalog
NAMES — deterministic, no transcript fuzz.

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

from pipeline import editroom, jobs, schemas  # noqa: E402


def script(**over):
    d = {
        "slug": "ep", "option_id": "S1", "target_minutes": 20,
        "chapters": [{
            "id": "CH1", "title": "Move-in day", "target_s": 180,
            "sections": [
                {"id": "CH1.S1", "kind": "oncamera", "take_id": "T1",
                 "text": "we're here", "est_s": 120},
                {"id": "CH1.S2", "kind": "vo",
                 "text": "a line to record later", "est_s": 55},
            ],
        }],
    }
    d.update(over)
    return d


TAKES = {"takes": [{"id": "T1"}]}


class ValidateScript(unittest.TestCase):
    def test_a_sound_script_validates(self):
        self.assertEqual(schemas.validate_script(script(), TAKES), [])

    def test_budget_fiction_is_refused(self):
        """Sections estimating 60s against a 180s target is the exact lie
        the pitch's target_s was supposed to prevent."""
        s = script()
        s["chapters"][0]["sections"][0]["est_s"] = 30
        s["chapters"][0]["sections"][1]["est_s"] = 30
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("off by more than 25%" in e for e in errs))

    def test_an_oncamera_section_must_quote_a_real_take(self):
        s = script()
        s["chapters"][0]["sections"][0]["take_id"] = "T999"
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("unknown take" in e for e in errs))

    def test_an_empty_section_is_a_hole(self):
        s = script()
        s["chapters"][0]["sections"][1]["text"] = "  "
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("empty text" in e for e in errs))

    def test_duplicate_section_ids_are_refused(self):
        s = script()
        s["chapters"][0]["sections"][1]["id"] = "CH1.S1"
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("duplicate section" in e for e in errs))

    def test_kind_is_closed(self):
        """Three kinds now — `desk` joined them 2026-08-24 for script-led
        episodes — but the set is still closed."""
        s = script()
        s["chapters"][0]["sections"][1]["kind"] = "narration"
        errs = schemas.validate_script(s, TAKES)
        self.assertTrue(any("kind must be" in e for e in errs), errs)

    def test_desk_is_one_of_them(self):
        s = script()
        s["chapters"][0]["sections"][1]["kind"] = "desk"
        self.assertEqual(schemas.validate_script(s, TAKES), [])


class ScriptJobGuards(unittest.TestCase):
    """A refused run must refuse BEFORE any session spawns."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp
        import subprocess
        self._popen = subprocess.Popen
        def explode(*a, **k):
            raise AssertionError("a guarded refusal must not spawn a session")
        subprocess.Popen = explode

    def tearDown(self):
        import subprocess
        subprocess.Popen = self._popen
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_approving_round_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("approving round", str(cm.exception))

    def test_an_existing_script_refuses_without_direction(self):
        """A script is REVISABLE as of 2026-08-24 — it used to refuse
        outright, which made the first draft the last word. What it still
        refuses is rewriting a script Caleb has not asked to change."""
        (self.tmp / "story_feedback.json").write_text(
            json.dumps({"rounds": [{"decision": "approve", "choice": "S1"}]}))
        (self.tmp / "script.json").write_text("{}")
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("nothing to revise from", str(cm.exception))

    def test_an_approved_script_refuses_even_with_direction(self):
        """Approval is what tells every later stage the words are final."""
        (self.tmp / "story_feedback.json").write_text(
            json.dumps({"rounds": [{"decision": "approve", "choice": "S1"}]}))
        (self.tmp / "script.json").write_text(json.dumps({"locked": True}))
        (self.tmp / "script_feedback.json").write_text(
            json.dumps({"rounds": [{"decision": "direction", "notes": "again"}]}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("unlock", str(cm.exception))

    def test_a_first_draft_refuses_while_a_required_question_is_open(self):
        """The gate Caleb asked for: no script is finalized without him."""
        (self.tmp / "story_feedback.json").write_text(
            json.dumps({"rounds": [{"decision": "approve", "choice": "S1"}]}))
        (self.tmp / "script_questions.json").write_text(json.dumps(
            {"slug": "ep", "stage": "interview",
             "questions": [{"id": "Q1", "ask": "which spine?",
                            "options": [], "required": True}]}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("waiting on you", str(cm.exception))
        self.assertIn("Q1", str(cm.exception))

    def test_a_first_draft_refuses_before_any_interview(self):
        (self.tmp / "story_feedback.json").write_text(
            json.dumps({"rounds": [{"decision": "approve", "choice": "S1"}]}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("no interview yet", str(cm.exception))

    def test_a_skippable_question_does_not_block(self):
        """Silence runs the default. Only a required, default-less question
        gates — otherwise the writer idles on an answer Caleb did not think
        was worth giving."""
        (self.tmp / "story_feedback.json").write_text(
            json.dumps({"rounds": [{"decision": "approve", "choice": "S1"}]}))
        (self.tmp / "script_questions.json").write_text(json.dumps(
            {"slug": "ep", "stage": "interview",
             "questions": [{"id": "Q1", "ask": "which spine?",
                            "options": [{"id": "a", "label": "skin"}],
                            "default": "a"}]}))
        # Reaching the session is the PASS here: this fixture's Popen stub
        # raises AssertionError to prove a refusal never spawns, so hitting
        # it proves the guards let this through.
        with self.assertRaises(AssertionError) as cm:
            jobs._run_script("ep", lambda *a: None, lambda p: None)
        self.assertIn("must not spawn", str(cm.exception))

    def test_graphics_without_a_cut_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_graphics("ep", lambda *a: None, lambda p: None)
        self.assertIn("no cut yet", str(cm.exception))

    def test_graphics_already_planned_refuses(self):
        (self.tmp / "edit_plan.json").write_text("{}")
        (self.tmp / "graphics_plan.json").write_text("{}")
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_graphics("ep", lambda *a: None, lambda p: None)
        self.assertIn("already planned", str(cm.exception))

    def test_publish_without_a_cut_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_publish("ep", lambda *a: None, lambda p: None)
        self.assertIn("nothing to publish", str(cm.exception))

    def test_retention_refuses_once_humans_reviewed(self):
        (self.tmp / "edit_plan.json").write_text("{}")
        (self.tmp / "proxies").mkdir()
        (self.tmp / "proxies" / "BT01.abc.mp4").write_bytes(b"x")
        (self.tmp / "review.json").write_text(json.dumps(
            {"BT01": {"status": "approved"}}))
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_retention("ep", lambda *a: None, lambda p: None)
        self.assertIn("humans are already reviewing", str(cm.exception))

    def test_retention_ignores_its_own_earlier_flags(self):
        """A re-assemble after a swap must not be blocked by the FIRST
        retention pass's own flags — only human entries gate."""
        (self.tmp / "edit_plan.json").write_text("{}")
        (self.tmp / "proxies").mkdir()
        (self.tmp / "proxies" / "BT01.abc.mp4").write_bytes(b"x")
        (self.tmp / "review.json").write_text(json.dumps(
            {"BT01": {"status": "flagged", "by": "retention-editor"}}))
        # passes the guard and would dispatch — prove it by the explode
        with self.assertRaises(AssertionError):
            jobs._run_retention("ep", lambda *a: None, lambda p: None)

    def test_qcgate_without_a_master_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_qcgate("ep", lambda *a: None, lambda p: None)
        self.assertIn("no master", str(cm.exception))

    def test_perf_without_stats_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_perf("_channel", lambda *a: None, lambda p: None)
        self.assertIn("no stats", str(cm.exception))

    def test_diagnose_wants_a_failed_job(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_diagnose("ep", lambda *a: None, lambda p: None,
                               arg="J000")
        self.assertIn("FAILED job id", str(cm.exception))

    def test_coverage_without_a_cut_refuses(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_coverage("ep", lambda *a: None, lambda p: None)
        self.assertIn("no cut yet", str(cm.exception))

    def test_the_prompt_carries_the_brief_and_the_contract(self):
        (self.tmp / "story_brief.json").write_text(
            json.dumps({"target_minutes": 20, "chapters": 7}))
        p = jobs._script_prompt("ep")
        self.assertIn("~20-minute episode in 7 chapters", p)
        self.assertIn('"vo"', p)
        self.assertIn("validate_script", p)


class ScriptStateAndEditing(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.tmp
        editroom.analysis_dir = lambda slug: self.tmp / "analysis"
        (self.tmp / "script.json").write_text(json.dumps(script()))

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def catalog(self, files):
        (self.tmp / "analysis" / "catalog.json").write_text(
            json.dumps({"files": files}))

    def test_recording_status_matches_by_name_and_class(self):
        self.catalog([
            {"name": "vo_CH1-S2_t1.webm", "class": "speech", "duration": 52.3},
            {"name": "vo_CH1-S2_t2.webm", "class": "broll", "duration": 4.0},
            {"name": "unrelated.mov", "class": "speech", "duration": 9.0},
        ])
        st = editroom._script_state("ep")
        sec = st["script"]["chapters"][0]["sections"][1]
        self.assertTrue(sec["recorded"])
        self.assertEqual(sec["recordings"], ["vo_CH1-S2_t1.webm", "vo_CH1-S2_t2.webm"])
        # the ingested REAL duration outranks the 150wpm estimate
        self.assertEqual(sec["recorded_s"], 52.3)

    def test_a_silent_upload_does_not_count_as_recorded(self):
        """A vo take that ingest classed broll (no speech heard) must not
        flip the section — a failed recording reading as done is the
        deaf-audit bug wearing a new hat."""
        self.catalog([{"name": "vo_CH1-S2_t1.webm", "class": "broll",
                       "duration": 30.0}])
        st = editroom._script_state("ep")
        self.assertFalse(st["script"]["chapters"][0]["sections"][1]["recorded"])

    def test_editing_a_vo_line_reestimates_its_seconds(self):
        sec = editroom._save_script_section(
            "ep", "CH1.S2", "five words spoken right here")
        self.assertEqual(sec["est_s"], round(5 / 150 * 60, 1))
        on_disk = json.loads((self.tmp / "script.json").read_text())
        self.assertEqual(
            on_disk["chapters"][0]["sections"][1]["text"],
            "five words spoken right here")

    def test_oncamera_text_is_a_quote_not_an_edit_surface(self):
        with self.assertRaises(Exception) as cm:
            editroom._save_script_section("ep", "CH1.S1", "reworded")
        self.assertIn("oncamera", str(cm.exception))

    def test_no_script_reads_as_null_not_a_crash(self):
        (self.tmp / "script.json").unlink()
        self.assertIsNone(editroom._script_state("ep")["script"])


class ResearchStage(unittest.TestCase):
    """The web's half of the story: gated on a named place, widened prompts."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp
        import subprocess
        self._popen = subprocess.Popen
        def explode(*a, **k):
            raise AssertionError("a guarded refusal must not spawn a session")
        subprocess.Popen = explode

    def tearDown(self):
        import subprocess
        subprocess.Popen = self._popen
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def brief(self, **over):
        b = {"target_minutes": 12, "chapters": 6, "notes": "", "location": ""}
        b.update(over)
        (self.tmp / "story_brief.json").write_text(json.dumps(b))

    def test_no_location_refuses_before_spawning(self):
        """A visit names a place, a desk episode names a topic — the brief
        needs one of them, and the refusal says so in those words."""
        self.brief(location="")
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_research("ep", lambda *a: None, lambda p: None)
        self.assertIn("no subject", str(cm.exception))

    def test_a_topic_is_researchable_without_a_place(self):
        """The script lane's whole premise: there is no location, only a
        subject."""
        self.brief(location="")
        p = self.tmp / "story_brief.json"
        p.write_text(json.dumps({"target_minutes": 12, "chapters": 5,
                                 "origin": "script",
                                 "subject": "why the Foucault pendulum stopped"}))
        prompt = jobs.RESEARCH_PROMPT % {
            "slug": "ep", "location": "why the Foucault pendulum stopped"}
        self.assertIn("Foucault", prompt)

    def test_the_place_reaches_every_prompt(self):
        self.brief(location="Royal Caribbean Allure of the Seas")
        for build in (jobs._story_prompt, jobs._editplan_prompt, jobs._script_prompt):
            self.assertIn("The place: Royal Caribbean Allure of the Seas",
                          build("ep"), build.__name__)

    def test_research_widens_the_story_prompt_only_when_it_exists(self):
        self.brief(location="somewhere")
        self.assertNotIn("RANGE WIDE", jobs._story_prompt("ep"))
        (self.tmp / "research.json").write_text(json.dumps({"facts": []}))
        p = jobs._story_prompt("ep")
        self.assertIn("RANGE WIDE", p)
        self.assertIn("research.json", p)

    def test_the_script_prompt_demands_sources_on_researched_lines(self):
        self.assertIn('source_url as "source"', jobs._script_prompt("ep"))


class VoCoverageRule(unittest.TestCase):
    """A teleprompter recording's picture must never ship."""

    TAKES = {"takes": [
        {"id": "V1", "file": "vo_CH1-S2_t1.webm", "s": 0.0, "e": 10.0,
         "complete": True, "fillers": 0},
    ]}
    BROLL = {"clips": [{"id": "B1", "file": "b.mov", "duration": 30.0}]}

    def plan(self, broll):
        return {"slug": "ep", "beats": [{
            "id": "BT01", "purpose": "vo", "take_id": "V1",
            "trim": {"s": 0.0, "e": 10.0}, "broll": broll,
        }]}

    def errs(self, broll):
        return schemas.validate_edit_plan(self.plan(broll), self.TAKES, self.BROLL)

    def test_a_vo_beat_with_no_broll_is_refused(self):
        self.assertTrue(any("teleprompter picture would ship" in e
                            for e in self.errs([])))

    def test_partial_cover_names_the_gap(self):
        errs = self.errs([{"clip_id": "B1", "at": 0.0, "duration": 4.0}])
        self.assertTrue(any("covers 4.0s of a 10.0s" in e for e in errs))

    def test_full_cover_passes_the_rule(self):
        errs = self.errs([{"clip_id": "B1", "at": 0.0, "duration": 10.0}])
        self.assertFalse(any("teleprompter" in e for e in errs))

    def test_the_editplan_prompt_teaches_the_script(self):
        import tempfile, shutil
        tmp = Path(tempfile.mkdtemp())
        wp = jobs.work_path
        jobs.work_path = lambda slug: tmp
        try:
            self.assertNotIn("approved SCRIPT", jobs._editplan_prompt("ep"))
            (tmp / "script.json").write_text("{}")
            p = jobs._editplan_prompt("ep")
            self.assertIn("approved SCRIPT", p)
            self.assertIn("covering their ENTIRE beat", p)
        finally:
            jobs.work_path = wp
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
