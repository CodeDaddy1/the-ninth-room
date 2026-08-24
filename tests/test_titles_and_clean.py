# -*- coding: utf-8 -*-
"""Titles derive honestly; the clean verb can only delete the superseded.

P6 of the workflow plan (2026-08-24). Two invariants pinned:

- the episode title's precedence is override -> approved option -> slug,
  and a vanished approved option falls through instead of guessing
  (stories.json is overwritten per round);
- the stale-preview selection NEVER names a live beat's newest file —
  the current proxy is always the newest by construction, so "keep the
  newest per live beat" is safe without recomputing spec hashes.

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

from pipeline import editroom  # noqa: E402


class Titles(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_slug_is_the_last_resort(self):
        self.assertEqual(editroom._project_title("houston-museum"),
                         "Houston Museum")

    def test_the_approved_option_titles_the_episode(self):
        (self.tmp / "stories.json").write_text(json.dumps({"options": [
            {"id": "S1", "title": "Measured in People"}]}))
        (self.tmp / "story_feedback.json").write_text(json.dumps(
            {"rounds": [{"decision": "approve", "choice": "S1"}]}))
        self.assertEqual(editroom._project_title("crooise"),
                         "Measured in People")

    def test_a_vanished_option_falls_through(self):
        (self.tmp / "stories.json").write_text(json.dumps({"options": [
            {"id": "S4", "title": "wrong round"}]}))
        (self.tmp / "story_feedback.json").write_text(json.dumps(
            {"rounds": [{"decision": "approve", "choice": "S1"}]}))
        self.assertEqual(editroom._project_title("crooise"), "Crooise")

    def test_the_override_beats_everything(self):
        (self.tmp / "title.txt").write_text("The Ship That Scores Itself\n")
        (self.tmp / "stories.json").write_text(json.dumps({"options": [
            {"id": "S1", "title": "loser"}]}))
        (self.tmp / "story_feedback.json").write_text(json.dumps(
            {"rounds": [{"decision": "approve", "choice": "S1"}]}))
        self.assertEqual(editroom._project_title("crooise"),
                         "The Ship That Scores Itself")


class CleanSelection(unittest.TestCase):
    def test_live_beats_keep_their_newest(self):
        doomed = editroom._clean_stale_candidates(
            {"BT01": [("BT01.old.mp4", 100), ("BT01.new.mp4", 200)],
             "BT02": [("BT02.only.mp4", 150)]},
            live_ids={"BT01", "BT02"})
        self.assertEqual(doomed, ["BT01.old.mp4"])

    def test_dropped_beats_lose_everything(self):
        doomed = editroom._clean_stale_candidates(
            {"BT99": [("BT99.a.mp4", 100), ("BT99.b.mp4", 200)]},
            live_ids={"BT01"})
        self.assertEqual(sorted(doomed), ["BT99.a.mp4", "BT99.b.mp4"])

    def test_a_single_current_file_is_never_touched(self):
        self.assertEqual(editroom._clean_stale_candidates(
            {"BT01": [("BT01.cur.mp4", 100)]}, {"BT01"}), [])


if __name__ == "__main__":
    unittest.main()
