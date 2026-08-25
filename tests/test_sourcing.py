# -*- coding: utf-8 -*-
"""Sourcing proposes; Caleb approves; only then does anything download.

2026-08-24, as the format moved VO-led. Every VO second is a second with
nobody on camera to cut to, so a VO-led cut needs covering footage of
roughly its narration time — and the library is finite. Measured on
HMNS: 186 clips, 28.0 minutes, which is 1.87x a 60% VO cut and only
1.25x a 90% one, before the coverage editor rejects anything.

The gate is the point. The agent that judges what the library lacks does
not also decide what gets downloaded: a licence is a commitment.

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

from pipeline import schemas, jobs, editroom  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


def script(vo_s=600.0, oncam_s=400.0):
    return {"chapters": [{"id": "CH1", "title": "c", "sections": [
        {"id": "CH1.S1", "kind": "vo", "text": "narrated", "est_s": vo_s},
        {"id": "CH1.S2", "kind": "oncamera", "text": "face", "est_s": oncam_s},
    ]}]}


def library(n=10, each=30.0):
    return {"clips": [{"id": "B%03d" % i, "duration": each} for i in range(n)]}


class Budget(unittest.TestCase):
    def test_it_counts_only_narration_against_the_library(self):
        b = schemas.coverage_budget(script(600, 400), library(10, 30))
        self.assertEqual(b["vo_seconds"], 600.0)
        self.assertEqual(b["library_seconds"], 300.0)
        self.assertEqual(b["shortfall_seconds"], 300.0)
        self.assertEqual(b["ratio"], 0.5)

    def test_a_comfortable_library_reports_no_shortfall(self):
        b = schemas.coverage_budget(script(300, 700), library(20, 30))
        self.assertEqual(b["shortfall_seconds"], 0.0)
        self.assertGreater(b["ratio"], 1.0)

    def test_clips_already_used_do_not_count_as_available(self):
        """One clip, one use — a library already spent is not in hand."""
        used = frozenset("B%03d" % i for i in range(8))
        b = schemas.coverage_budget(script(600, 400), library(10, 30), used)
        self.assertEqual(b["library_clips"], 2)
        self.assertEqual(b["library_seconds"], 60.0)

    def test_a_script_with_no_narration_has_no_budget(self):
        b = schemas.coverage_budget(script(0, 1000), library())
        self.assertEqual(b["vo_seconds"], 0.0)
        self.assertIsNone(b["ratio"])


class TheGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp_e, self._wp_j = editroom.work_path, jobs.work_path
        editroom.work_path = lambda slug: self.tmp
        jobs.work_path = lambda slug: self.tmp
        (self.tmp / "script.json").write_text(json.dumps(script()))
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(library()))
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"ts": 111, "section_id": "CH1.S1", "line": "l", "why": "w",
             "candidates": [], "status": "proposed"}]}))

    def tearDown(self):
        editroom.work_path, jobs.work_path = self._wp_e, self._wp_j
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _rounds(self):
        return json.loads((self.tmp / "asset_requests.json").read_text())["rounds"]

    def test_approving_marks_only_that_round(self):
        out = editroom._asset_round_verdict("x", 111, "approved",
                                            log=lambda *a: None)
        self.assertEqual(out["approved"], 1)
        self.assertEqual(self._rounds()[0]["status"], "approved")

    def test_skipping_is_recorded_not_deleted(self):
        editroom._asset_round_verdict("x", 111, "skipped", log=lambda *a: None)
        self.assertEqual(self._rounds()[0]["status"], "skipped")
        self.assertEqual(len(self._rounds()), 1)

    def test_a_fetched_round_may_be_re_opened_but_not_undone(self):
        """Changed 2026-08-25: re-sourcing a gap is normal when the
        rules change (video first). Sliding it back to skipped is not —
        that would orphan the asset already on disk."""
        doc = {"rounds": [{"ts": 111, "status": "done"}]}
        (self.tmp / "asset_requests.json").write_text(json.dumps(doc))
        out = editroom._asset_round_verdict("x", 111, "approved",
                                            log=lambda *a: None)
        self.assertEqual(out["status"], "approved")
        (self.tmp / "asset_requests.json").write_text(json.dumps(doc))
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 111, "skipped",
                                          log=lambda *a: None)

    def test_an_unknown_round_is_refused(self):
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 999, "approved",
                                          log=lambda *a: None)

    def test_fetch_refuses_while_nothing_is_approved(self):
        """The gate, from the job's side: proposing does not authorise
        downloading."""
        with self.assertRaises(jobs.JobError) as e:
            jobs._run_sourcing("x", lambda *a: None, lambda p: None,
                               arg="fetch")
        self.assertIn("nothing approved", str(e.exception))

    def test_sourcing_refuses_without_a_script(self):
        (self.tmp / "script.json").unlink()
        with self.assertRaises(jobs.JobError) as e:
            jobs._run_sourcing("x", lambda *a: None, lambda p: None)
        self.assertIn("no script", str(e.exception))

    def test_the_budget_clause_quotes_real_arithmetic(self):
        clause = jobs._sourcing_budget_clause("x")
        self.assertIn("minutes of narration", clause)
        self.assertIn("ratio", clause)


class Wiring(unittest.TestCase):
    def test_sourcing_runs_on_the_session_lane(self):
        self.assertEqual(jobs.lane_of("sourcing"), "session")

    def test_the_script_hands_off_to_it(self):
        self.assertEqual(jobs.CHAIN.get("script"), "sourcing")

    def test_and_sourcing_stops_at_the_gate(self):
        self.assertIsNone(jobs.CHAIN.get("sourcing"))


if __name__ == "__main__":
    unittest.main()


class ReopeningAFetchedRound(unittest.TestCase):
    """The rules changed (video first, 2026-08-25), so re-sourcing a gap
    that was already fetched is a normal thing to want — but a fetched
    round must not slide back to proposed or skipped, which would orphan
    the asset already on disk."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        (self.tmp / "asset_requests.json").write_text(json.dumps({"rounds": [
            {"ts": 1, "status": "done", "line": "a line"}]}))

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _status(self):
        return json.loads((self.tmp / "asset_requests.json").read_text())["rounds"][0]["status"]

    def test_approving_a_done_round_re_opens_it(self):
        out = editroom._asset_round_verdict("x", 1, "approved",
                                            log=lambda *a: None)
        self.assertEqual(out["status"], "approved")
        self.assertEqual(self._status(), "approved")

    def test_it_cannot_slide_back_to_skipped(self):
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 1, "skipped",
                                          log=lambda *a: None)
        self.assertEqual(self._status(), "done")

    def test_nor_back_to_proposed(self):
        with self.assertRaises(IngestError):
            editroom._asset_round_verdict("x", 1, "proposed",
                                          log=lambda *a: None)
        self.assertEqual(self._status(), "done")
