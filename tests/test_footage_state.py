# -*- coding: utf-8 -*-
"""How much of what is on disk the analysis actually covers.

2026-08-25. `ingested` is only "catalog.json exists", and once it exists
it stays true forever. So the Footage desk said "Analyzed" over twelve
clips dropped in afterwards, and its only hedge was a standing amber
warning — permanently on screen, about a removal that may never have
happened, on every visit for the life of the project.

The catalog already lists its files by name and is already read here for
`ingested`, so the honest number is a set intersection. It is what lets
the desk state a fact instead of a hypothetical, and what lets the desk
footer offer "Analyze footage" again when files were added.

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


class FootageState(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work = self.tmp / "ep"
        (self.work / "footage").mkdir(parents=True)
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.work

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _drop(self, *names):
        """Files that LOOK like footage. ffprobe fails on them and the
        inventory keeps them at 0s/0x0 — which is the path this test
        wants: it is about coverage counting, not about probing."""
        for n in names:
            (self.work / "footage" / n).write_bytes(b"not really a video")

    def _catalog(self, names, skipped=()):
        d = self.work / "analysis"
        d.mkdir(exist_ok=True)
        (d / "catalog.json").write_text(json.dumps({
            "slug": "ep",
            "files": [{"name": n} for n in names],
            "skipped": list(skipped),
        }))

    def test_no_catalog_means_nothing_analyzed(self):
        self._drop("a.mp4", "b.mp4")
        st = editroom._footage_state("ep")
        self.assertFalse(st["ingested"])
        self.assertEqual(st["analyzed"], 0)
        self.assertEqual(len(st["files"]), 2)

    def test_a_catalog_covering_everything_reports_everything(self):
        self._drop("a.mp4", "b.mp4", "c.mp4")
        self._catalog(["a.mp4", "b.mp4", "c.mp4"])
        st = editroom._footage_state("ep")
        self.assertTrue(st["ingested"])
        self.assertEqual(st["analyzed"], 3)
        self.assertEqual(len(st["files"]), 3)

    def test_a_file_added_after_the_analysis_is_not_counted(self):
        """The whole point: `ingested` still says True here, and it is the
        gap between these two numbers that the desk reports."""
        self._drop("a.mp4", "b.mp4")
        self._catalog(["a.mp4", "b.mp4"])
        self._drop("late.mp4")
        st = editroom._footage_state("ep")
        self.assertTrue(st["ingested"])
        self.assertEqual(len(st["files"]), 3)
        self.assertEqual(st["analyzed"], 2)

    def test_a_file_removed_after_the_analysis_does_not_inflate_the_count(self):
        """The catalog still names it. Counting the CATALOG would report 3
        analyzed out of 2 on disk, which is worse than saying nothing."""
        self._drop("a.mp4", "b.mp4")
        self._catalog(["a.mp4", "b.mp4", "gone.mp4"])
        st = editroom._footage_state("ep")
        self.assertEqual(len(st["files"]), 2)
        self.assertEqual(st["analyzed"], 2)

    def test_skipped_is_carried_through(self):
        self._drop("a.mp4")
        self._catalog(["a.mp4"], skipped=[{"name": "x.mp4", "why": "no video stream"}])
        self.assertEqual(editroom._footage_state("ep")["skipped"], 1)

    def test_a_half_written_catalog_does_not_take_the_inventory_down(self):
        """A catalog being written while the desk polls is a real race on
        a machine doing both. The inventory is the important half."""
        self._drop("a.mp4", "b.mp4")
        d = self.work / "analysis"
        d.mkdir(exist_ok=True)
        (d / "catalog.json").write_text('{"slug": "ep", "files": [{"na')
        st = editroom._footage_state("ep")
        self.assertEqual(len(st["files"]), 2)
        self.assertTrue(st["ingested"])
        self.assertEqual(st["analyzed"], 0)


if __name__ == "__main__":
    unittest.main()
