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

from pipeline import editroom, ingest  # noqa: E402

WORK = Path(__file__).resolve().parent.parent / "work"


class Sandboxed(unittest.TestCase):
    """A work dir of our own, and a guard that we stayed in it.

    Patching only `editroom.work_path` was not enough: `analysis_dir` is
    `ingest`'s, it mkdirs, and `editroom` imported it by value — so the
    first run of this file created a real `work/ep/analysis` in the live
    tree, which then showed up as a phantom project on the Studio's board
    (2026-08-25). A test that can write into the shelf is a hazard whether
    or not it asserts anything.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work = self.tmp / "ep"
        (self.work / "footage").mkdir(parents=True)
        self._wp, self._iwp = editroom.work_path, ingest.work_path
        editroom.work_path = lambda slug: self.work
        ingest.work_path = lambda slug: self.work
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        editroom.work_path = self._wp
        ingest.work_path = self._iwp
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")


class FootageState(Sandboxed):
    def setUp(self):
        super().setUp()
        editroom._CATALOG_CACHE.clear()

    def _drop(self, *names):
        """Files that LOOK like footage. ffprobe fails on them and the
        inventory keeps them at 0s/0x0 — which is the path this test
        wants: it is about coverage counting, not about probing."""
        for n in names:
            (self.work / "footage" / n).write_bytes(b"not really a video")

    def _catalog(self, names, skipped=(), takes=True):
        d = self.work / "analysis"
        d.mkdir(exist_ok=True)
        if takes:
            (d / "takes.json").write_text("{}")
        (d / "catalog.json").write_text(json.dumps({
            "slug": "ep",
            "files": [{"name": n} for n in names],
            "skipped": list(skipped),
        }))
        editroom._CATALOG_CACHE.clear()

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

    def test_skipped_names_the_files_it_set_aside(self):
        """Names, not a count. Ingest skips an unreadable or zero-duration
        clip rather than sinking the batch, and the only useful thing the
        desk can say is WHICH one to replace. hmns has been carrying an
        unshown skip since August."""
        self._drop("a.mp4", "broken.mp4")
        self._catalog(["a.mp4"], skipped=["broken.mp4"])
        st = editroom._footage_state("ep")
        self.assertEqual(st["skipped"], ["broken.mp4"])
        self.assertEqual(st["analyzed"], 1)

    def test_a_skip_for_a_file_no_longer_on_disk_is_not_reported(self):
        # you removed the corrupt clip; the catalog still names it
        self._drop("a.mp4")
        self._catalog(["a.mp4"], skipped=["gone.mp4"])
        self.assertEqual(editroom._footage_state("ep")["skipped"], [])

    def test_a_dict_shaped_skip_entry_is_tolerated(self):
        self._drop("a.mp4", "broken.mp4")
        self._catalog(["a.mp4"], skipped=[{"name": "broken.mp4", "why": "stub"}])
        self.assertEqual(editroom._footage_state("ep")["skipped"], ["broken.mp4"])

    def test_a_catalog_with_no_TAKES_is_not_analyzed(self):
        """An ingest that dies at the takes stage writes the catalog and no
        takes. Reading only catalog.json made this desk say "all analyzed"
        directly above a footer saying "1 file waiting to be analyzed" and
        a band explaining why the analysis failed — the project row has
        always used the stricter definition, and now so does this."""
        self._drop("a.mp4")
        self._catalog(["a.mp4"], takes=False)
        st = editroom._footage_state("ep")
        self.assertFalse(st["ingested"])
        self.assertEqual(st["analyzed"], 0)

    def test_a_half_written_catalog_does_not_take_the_inventory_down(self):
        """A catalog being written while the desk polls is a real race on
        a machine doing both. The inventory is the important half."""
        self._drop("a.mp4", "b.mp4")
        d = self.work / "analysis"
        d.mkdir(exist_ok=True)
        (d / "takes.json").write_text("{}")
        (d / "catalog.json").write_text('{"slug": "ep", "files": [{"na')
        st = editroom._footage_state("ep")
        self.assertEqual(len(st["files"]), 2)
        self.assertTrue(st["ingested"])
        self.assertEqual(st["analyzed"], 0)
        self.assertEqual(st["skipped"], [])


class TheProjectRow(Sandboxed):
    """The same coverage number, on the row every board reads.

    This began as an mtime comparison — catalog vs newest footage — to
    avoid parsing the catalog per poll. On live data it was WRONG: both
    real projects reported "footage changed" with no file newer than
    their catalog, because `footage/` also holds `.thumbs`, `stills` and
    `.trash`, so caching one preview or binning one clip moves the
    directory's own mtime. The names are the only honest answer; the
    parse is memoised on (mtime, size) instead.
    """

    def setUp(self):
        super().setUp()
        (self.work / "analysis").mkdir()
        editroom._CATALOG_CACHE.clear()

    def _analyzed(self, names, skipped=()):
        (self.work / "analysis" / "takes.json").write_text("{}")
        (self.work / "analysis" / "catalog.json").write_text(json.dumps(
            {"files": [{"name": n} for n in names], "skipped": list(skipped)}))
        editroom._CATALOG_CACHE.clear()

    def _clip(self, name):
        (self.work / "footage" / name).write_bytes(b"x")

    def test_a_fully_analyzed_project_reports_every_file(self):
        self._clip("a.mp4")
        self._clip("b.mp4")
        self._analyzed(["a.mp4", "b.mp4"])
        row = editroom._project_row("ep")
        self.assertEqual(row["footage"], 2)
        self.assertEqual(row["analyzed"], 2)

    def test_a_clip_added_after_the_analysis_is_not_counted(self):
        self._clip("a.mp4")
        self._analyzed(["a.mp4"])
        self._clip("late.mp4")
        row = editroom._project_row("ep")
        self.assertTrue(row["ingested"], "ingested is a latch — it stays true")
        self.assertEqual(row["footage"], 2)
        self.assertEqual(row["analyzed"], 1)

    def test_caching_previews_or_binning_a_clip_is_NOT_a_change_to_analyze(self):
        """The false positive that killed the mtime version. `.thumbs` and
        `.trash` live inside `footage/`, so writing either moves the
        directory's mtime while the analysis is still perfectly current."""
        self._clip("a.mp4")
        self._analyzed(["a.mp4"])
        (self.work / "footage" / ".thumbs").mkdir()
        (self.work / "footage" / ".thumbs" / "a.mp4.jpg").write_bytes(b"x")
        (self.work / "footage" / ".trash").mkdir()
        row = editroom._project_row("ep")
        self.assertEqual(row["analyzed"], 1)
        self.assertEqual(row["footage"], 1)

    def test_an_unanalyzed_project_reports_zero_not_a_gap(self):
        # `!ingested` is a different sentence with a different door; it
        # must not also read as "1 file not analyzed yet"
        self._clip("a.mp4")
        row = editroom._project_row("ep")
        self.assertFalse(row["ingested"])
        self.assertEqual(row["analyzed"], 0)

    def test_a_DELIBERATE_skip_is_accounted_for_not_outstanding(self):
        """hmns, live: 368 files, 367 analyzed, 1 skipped. Counting that
        skip as work left to do offers Analyze again forever — re-running
        reproduces the same skip, and the number never moves."""
        self._clip("a.mp4")
        self._clip("broken.mp4")
        self._analyzed(["a.mp4"], skipped=["broken.mp4"])
        row = editroom._project_row("ep")
        self.assertEqual(row["footage"], 2)
        self.assertEqual(row["analyzed"], 1)
        self.assertEqual(row["skipped"], 1)
        self.assertEqual(row["analyzed"] + row["skipped"], row["footage"],
                         "nothing is outstanding")

    def test_the_parse_is_memoised_but_notices_a_rewrite(self):
        self._clip("a.mp4")
        self._analyzed(["a.mp4"])
        self.assertEqual(editroom._project_row("ep")["analyzed"], 1)
        self._clip("b.mp4")
        # a re-analysis rewrites the catalog; size changes, so does the answer
        self._analyzed(["a.mp4", "b.mp4"])
        self.assertEqual(editroom._project_row("ep")["analyzed"], 2)


if __name__ == "__main__":
    unittest.main()
