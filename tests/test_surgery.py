# -*- coding: utf-8 -*-
"""Review surgery: swap a take, trim a clip, restore a removal.

P3 of the workflow plan (2026-08-23). The invariants pinned here:

- a swap/trim writes ONLY through the validated plan path — a refused
  validation rolls the beat back and the file is untouched;
- surgery invalidates the verdict (the clip returns to the queue);
- both verbs enqueue a re-assemble, because proxies render from the
  ASSEMBLED timeline and a duration change invalidates it (the snap-cuts
  lesson, found live);
- the trash is a bounded undo whose restore re-validates before
  re-inserting — never a door to an invalid plan.

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


def _plan():
    return {
        "slug": "ep", "format": "youtube_long",
        "theme": {"problem": "p", "promise": "pr", "payoff": "pay"},
        "beats": [
            {"id": "BT01", "purpose": "hook", "chapter_id": "CH1",
             "take_id": "T1", "trim": {"s": 1.0, "e": 6.0},
             "fragment": True},
            {"id": "BT02", "purpose": "payoff", "chapter_id": "CH1",
             "take_id": "T2", "trim": {"s": 8.0, "e": 12.0},
             "fragment": True},
        ],
    }


def _takes():
    return {"takes": [
        {"id": "T1", "file": "a.mov", "s": 0.5, "e": 7.0, "duration": 6.5,
         "transcript": "the monkeys will open your bag"},
        {"id": "T2", "file": "a.mov", "s": 8.0, "e": 12.5, "duration": 4.5,
         "transcript": "welcome to the ship"},
        {"id": "T3", "file": "b.mov", "s": 0.0, "e": 6.0, "duration": 6.0,
         "transcript": "the monkeys really will open your bag today"},
    ], "groups": []}


class SurgeryBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        (self.tmp / "edit_plan.json").write_text(json.dumps(_plan()))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps(_takes()))
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        self._start = jobs.start
        self.queued = []
        jobs.start = lambda kind, slug: self.queued.append(kind)

    def tearDown(self):
        editroom.work_path = self._wp
        jobs.start = self._start
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self):
        return json.loads((self.tmp / "edit_plan.json").read_text())


class SwapTake(SurgeryBase):
    def test_swap_rewrites_take_and_trim_and_reassembles(self):
        out = editroom._beat_swap("ep", "BT01", "T3")
        b = self.plan()["beats"][0]
        self.assertEqual(b["take_id"], "T3")
        self.assertEqual(b["trim"], {"s": 0.0, "e": 6.0})
        self.assertTrue(out["assembling"])
        self.assertEqual(self.queued, ["assemble"])

    def test_swap_resets_the_verdict(self):
        (self.tmp / "review.json").write_text(json.dumps(
            {"BT01": {"status": "approved"}}))
        editroom._beat_swap("ep", "BT01", "T3")
        review = json.loads((self.tmp / "review.json").read_text())
        self.assertNotIn("BT01", review)

    def test_unknown_take_and_same_take_refuse(self):
        for tid, want in (("T9", "unknown take"), ("T1", "already uses")):
            with self.assertRaises(Exception) as cm:
                editroom._beat_swap("ep", "BT01", tid)
            self.assertIn(want, str(cm.exception))
        self.assertEqual(self.queued, [])

    def test_alternates_rank_by_similarity_and_exclude_current(self):
        alts = editroom._beat_alternates("ep", "BT01")
        ids = [a["id"] for a in alts]
        self.assertNotIn("T1", ids)
        # T3 shares the monkey line; T2 does not
        self.assertEqual(ids[0], "T3")
        self.assertGreater(alts[0]["similarity"], alts[-1]["similarity"])


class TrimBeat(SurgeryBase):
    def test_a_nudge_moves_both_edges_and_reassembles(self):
        out = editroom._beat_trim("ep", "BT01", 0.1, -0.2)
        self.assertEqual(self.plan()["beats"][0]["trim"],
                         {"s": 1.1, "e": 5.8})
        self.assertTrue(out["assembling"])

    def test_inversion_and_flash_frames_refuse(self):
        # +2.0 in and -2.0 out inside one nudge collapses BT02's 4s span
        with self.assertRaises(Exception) as cm:
            editroom._beat_trim("ep", "BT02", 2.0, -2.0)
        self.assertIn("flash frame", str(cm.exception))
        self.assertEqual(self.plan()["beats"][1]["trim"], {"s": 8.0, "e": 12.0})

    def test_oversize_steps_refuse(self):
        with self.assertRaises(Exception):
            editroom._beat_trim("ep", "BT01", 2.5, 0)


class TheTrash(SurgeryBase):
    def test_the_trash_is_capped(self):
        for i in range(10):
            editroom._trash_add("ep", "broll", {"beat_id": "BT01",
                                                "clip_id": "B%02d" % i,
                                                "at": 0, "duration": 1,
                                                "src_s": 0})
        entries = editroom._trash_list("ep")
        self.assertEqual(len(entries), editroom.TRASH_CAP)
        self.assertEqual(entries[-1]["clip_id"], "B09")

    def test_restoring_a_vanished_entry_refuses(self):
        with self.assertRaises(Exception) as cm:
            editroom._trash_restore("ep", 12345, "broll")
        self.assertIn("no longer", str(cm.exception))

    def test_a_plan_card_restore_revalidates(self):
        """An invalid card (unknown beat) must NOT come back."""
        (self.tmp / "graphics_plan.json").write_text(json.dumps(
            {"slug": "ep", "cards": []}))
        editroom._trash_add("ep", "card", {"card": {
            "id": "CARD01", "type": "section", "kit_type": "lower_third",
            "beat_id": "BT99", "at": 0.5, "duration": 3.0,
            "animation": "slide_up", "text": "x"}})
        ts = editroom._trash_list("ep")[-1]["ts"]
        with self.assertRaises(Exception):
            editroom._trash_restore("ep", ts, "card")
        gp = json.loads((self.tmp / "graphics_plan.json").read_text())
        self.assertEqual(gp["cards"], [])


if __name__ == "__main__":
    unittest.main()
