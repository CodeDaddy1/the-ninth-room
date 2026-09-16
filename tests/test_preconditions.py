# -*- coding: utf-8 -*-
"""A paid job's gates are declared, named, and answered before enqueue.

docs/decisions-job-preconditions.md (2026-08-28) said preconditions leave
jobs.py for a small module that declares them; nothing did until the
first paid kind needed a gate that answers BEFORE the click is billed.
`pipeline/preconditions.py` starts with the new kind only (decision 17):
existing kinds are untouched, and this file pins that too.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import illustration, paths, preconditions as pre  # noqa: E402


class Predicates(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = illustration.work_path
        illustration.work_path = lambda slug: self.tmp
        self._pwp = pre.work_path
        pre.work_path = lambda slug: self.tmp

    def tearDown(self):
        illustration.work_path = self._wp
        pre.work_path = self._pwp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def refused(self, preds):
        return [p.id for p in pre.refused(preds, "ep")]

    def test_every_propose_predicate_refuses_on_a_bare_project(self):
        with mock.patch.object(paths, "higgsfield_bin", lambda: "/nowhere/higgsfield"):
            ids = self.refused(pre.ILLUSTRATE_PROPOSE)
        for want in ("has_story", "has_targets", "higgsfield_cli_present"):
            self.assertIn(want, ids)
        self.assertNotIn("cap_headroom", ids, "nothing spent means headroom")

    def _script_project(self, locked=True):
        (self.tmp / "script.json").write_text(json.dumps({"locked": locked, "chapters": [
            {"id": "CH1", "sections": [{"id": "CH1.S2", "kind": "vo", "text": "x",
                                        "visual": {"want": "w", "why": "illustrate: w",
                                                   "from": "illustration"}}]}]}))

    def test_has_story_and_has_targets_on_the_script_lane(self):
        self._script_project(locked=False)
        self.assertIn("has_story", self.refused([pre.HAS_STORY]))
        self._script_project(locked=True)
        self.assertEqual(self.refused([pre.HAS_STORY, pre.HAS_TARGETS]), [])
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"section_id": "CH1.S2", "kind": "illustration", "status": "proposed"}]}))
        self.assertEqual(self.refused([pre.HAS_TARGETS]), ["has_targets"], "a live round covers it")

    def test_has_story_and_has_targets_on_the_footage_lane(self):
        (self.tmp / "analysis").mkdir()
        (self.tmp / "edit_plan.json").write_text(json.dumps({"beats": [
            {"id": "shot-T41", "purpose": "build", "take_id": "T41",
             "visual": {"want": "w", "why": "illustrate: w", "from": "illustration"}}]}))
        self.assertIn("has_story", self.refused([pre.HAS_STORY]), "no catalog yet")
        (self.tmp / "analysis" / "broll.json").write_text('{"slug":"ep","clips":[]}')
        self.assertEqual(self.refused([pre.HAS_STORY, pre.HAS_TARGETS]), [])

    def test_generate_needs_an_approved_round_that_fits_and_its_soul(self):
        self._script_project()
        (self.tmp / "assets").mkdir()
        self.assertIn("rounds_approved", self.refused([pre.ROUNDS_APPROVED]))
        r = {"id": "R1", "kind": "illustration", "section_id": "CH1.S2", "status": "approved",
             "honesty": "reconstruction", "target": "cover", "aspect": "16:9",
             "why": "illustrate: w", "sources": ["https://x"], "disclosure": "d",
             "steps": [{"stage": "plate", "model": "soul_cinema_studio", "soul": True,
                        "prompt": "p", "credits": 2.0, "tier": "std"}],
             "estimate_credits": 2.0, "marks": {}}
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [r]}))
        with mock.patch.object(paths, "soul_id", lambda: None):
            self.assertIn("soul_available", self.refused([pre.SOUL_AVAILABLE]))
        with mock.patch.object(paths, "soul_id", lambda: "c292"):
            self.assertEqual(self.refused([pre.ROUNDS_APPROVED, pre.SOUL_AVAILABLE,
                                           pre.CAP_FITS, pre.MARKS_CONSISTENT]), [])
        r["estimate_credits"] = 400.0
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [r]}))
        self.assertIn("cap_fits", self.refused([pre.CAP_FITS]))

    def test_retryable_is_declared_for_both_arms(self):
        self.assertTrue(pre.RETRYABLE[("illustrate", None)])
        self.assertFalse(pre.RETRYABLE[("illustrate", "generate")])

    def test_every_predicate_has_an_id_a_message_and_a_surface(self):
        for p in pre.ILLUSTRATE_PROPOSE + pre.ILLUSTRATE_GENERATE:
            self.assertTrue(p.id and p.message and p.surface, p)

    def test_existing_kinds_are_untouched(self):
        import ast
        src = (Path(__file__).resolve().parents[1] / "pipeline" / "preconditions.py").read_text()
        imported = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(a.name for a in node.names)
        self.assertFalse({"jobs", ".jobs", "pipeline.jobs"} & imported, imported)


if __name__ == "__main__":
    unittest.main()
