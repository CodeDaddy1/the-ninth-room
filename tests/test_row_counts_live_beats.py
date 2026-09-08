# -*- coding: utf-8 -*-
"""The project row counts clips that exist.

`review.json` outlives the beats it describes. hmns holds 96 entries
against 82 live beats, and all fourteen of its queue-state rows are
ghosts of beats some earlier hand surgery removed.

`_project_row` counted the FILE. The Review desk counts the live beats.
So the board said "14 clip(s) still in the queue. Clear them, then
Conform" while the desk it sent you to said 82 of 82 approved and offered
nothing to clear — two surfaces disagreeing about one episode, and the
row was the wrong one. Caleb found it by reading the desk (2026-09-08).

The ghosts are not deleted by this. They hold his notes, and the beat-id
migration archives them by name into `review_archive.json`. They just
stop being counted as outstanding work.

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

from pipeline import editroom, ingest  # noqa: E402


class RowCountsLiveBeats(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.tmp
        editroom.analysis_dir = lambda slug: self.tmp / "analysis"

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self, ids):
        (self.tmp / "edit_plan.json").write_text(json.dumps(
            {"slug": "ep", "beats": [{"id": i} for i in ids]}))

    def review(self, **rows):
        (self.tmp / "review.json").write_text(json.dumps(
            {k: {"status": v} for k, v in rows.items()}))

    def row(self):
        return editroom._project_row("ep")

    def test_a_ghost_in_a_queue_state_is_not_outstanding_work(self):
        """THE REGRESSION. Nothing on any desk can clear it, because the
        clip it names is gone."""
        self.plan(["BT01", "BT02"])
        self.review(BT01="approved", BT02="approved", BT99="flagged")
        r = self.row()
        self.assertEqual(r["review"]["queue"], 0)
        self.assertEqual(r["review"]["approved"], 2)

    def test_a_live_beat_in_a_queue_state_still_counts(self):
        """The fix must not silence real work — that would be the same
        bug pointing the other way."""
        self.plan(["BT01", "BT02"])
        self.review(BT01="approved", BT02="flagged", BT99="flagged")
        r = self.row()
        self.assertEqual(r["review"]["queue"], 1)
        self.assertEqual(r["review"]["flagged"], 1)

    def test_reworked_and_edited_are_queue_states_too(self):
        self.plan(["BT01", "BT02"])
        self.review(BT01="reworked", BT02="edited")
        self.assertEqual(self.row()["review"]["queue"], 2)

    def test_a_ghost_approval_does_not_inflate_the_approved_count(self):
        self.plan(["BT01"])
        self.review(BT01="approved", BT98="approved", BT99="approved")
        self.assertEqual(self.row()["review"]["approved"], 1)

    def reviewable(self):
        """Enough on disk for the row to reach its review branch: a plan,
        a timeline map and proxies. Without these the phase never gets
        past `assembly` and a next-line assertion passes for the wrong
        reason — which is how the first version of these two tests was
        green while proving nothing."""
        # the phase chain gates on footage and ingest long before it
        # reaches the review branches
        (self.tmp / "footage").mkdir(exist_ok=True)
        (self.tmp / "footage" / "a.mp4").write_bytes(b"x")
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps(
            {"files": [{"name": "a.mp4", "class": "speech",
                        "duration": 10.0, "words_file": None}]}))
        (self.tmp / "analysis" / "takes.json").write_text(
            json.dumps({"takes": []}))
        (self.tmp / "analysis" / "timeline_map.json").write_text(
            json.dumps({"beats": [{"id": "BT01"}, {"id": "BT02"}]}))
        (self.tmp / "proxies").mkdir(exist_ok=True)
        for b in ("BT01", "BT02"):
            (self.tmp / "proxies" / (b + ".abc123.mp4")).write_bytes(b"m")

    def test_the_next_line_stops_naming_a_queue_that_cannot_be_cleared(self):
        self.plan(["BT01", "BT02"])
        self.reviewable()
        self.review(BT01="approved", BT02="approved", BT99="flagged")
        r = self.row()
        self.assertNotIn("still in the queue", r["next"])
        self.assertEqual(r["phase"], "master",
                         "with every live clip approved the episode is "
                         "ready to render, not stuck in a queue")

    def test_it_still_names_a_queue_that_can(self):
        self.plan(["BT01", "BT02"])
        self.reviewable()
        self.review(BT01="approved", BT02="flagged")
        r = self.row()
        self.assertIn("1 clip(s) still in the queue", r["next"])
        self.assertEqual(r["phase"], "review")

    def test_no_plan_falls_back_rather_than_reporting_zero(self):
        """A project mid-rebuild has review rows and no plan. Reporting
        zero there would be a new lie in place of the old one."""
        self.review(BT01="flagged", BT02="flagged")
        self.assertEqual(self.row()["review"]["queue"], 2)

    def test_an_unreadable_plan_falls_back_too(self):
        (self.tmp / "edit_plan.json").write_text("{truncated")
        self.review(BT01="flagged")
        self.assertEqual(self.row()["review"]["queue"], 1)

    def test_the_row_and_the_desk_agree_on_the_real_hmns(self):
        """Both surfaces, one episode, one answer."""
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        w = Path(__file__).resolve().parent.parent / "work" / "hmns"
        if not (w / "review.json").exists():
            self.skipTest("hmns is not on this machine")
        row = editroom._project_row("hmns")["review"]
        state = editroom._state("hmns")["counts"]
        self.assertEqual(row["approved"], state["approved"])
        self.assertEqual(row["flagged"], state["flagged"])


if __name__ == "__main__":
    unittest.main()
