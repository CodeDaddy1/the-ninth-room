# -*- coding: utf-8 -*-
"""Footage is linked, not copied — and a copied project can be repaired.

2026-08-24, measured: a contact sheet built from a DJI `.LRF` proxy
takes 0.5s; from the 4K MP4 it takes 8.8s — 17x. `broll._prefer_proxy`
already prefers the LRF, but it looks for a sibling of the RESOLVED
path, so a project filled by copying only the MP4s silently loses the
fast path. 186 sheets cost ~26 minutes of a 112-minute ingest that way.

Linking restores it, saves the footage's weight on disk, and removes
the copy wait before ingest starts. What is pinned here is the part
that can destroy work: the repair must verify before it swaps, and must
refuse anything it cannot prove identical.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


WORK = Path(__file__).resolve().parent.parent / "work"


class Linking(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.lib = self.root / "lib"
        (self.lib / "shoot").mkdir(parents=True)
        self.work = self.root / "work" / "ep"
        (self.work / "footage").mkdir(parents=True)
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.root / "work" / slug
        # `_link_footage` records the card the folder came from, and
        # `facts` resolves its work dir through INGEST — patching
        # editroom's alone left it writing a real `work/ep/` into the live
        # shelf, where it showed up as a phantom project on the Studio's
        # board (2026-08-26). The guard below is the same one
        # test_footage_state has carried since the first time this
        # happened to it.
        import pipeline.ingest as ingest_mod
        self._iwp = ingest_mod.work_path
        ingest_mod.work_path = lambda slug: self.root / "work" / slug
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        import pipeline.ingest as ingest_mod
        editroom.work_path = self._wp
        ingest_mod.work_path = self._iwp
        shutil.rmtree(self.root, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    def clip(self, name, body=b"CLIP", where=None):
        p = (where or (self.lib / "shoot")) / name
        p.write_bytes(body + b"\0" * 4096)
        return p

    # ---- link ----

    def test_it_links_video_and_leaves_the_original_alone(self):
        src = self.clip("A001.MP4")
        out = editroom._link_footage("ep", str(self.lib / "shoot"),
                                     log=lambda *a: None)
        dest = self.work / "footage" / "A001.MP4"
        self.assertEqual(out["linked"], 1)
        self.assertTrue(dest.is_symlink())
        self.assertEqual(os.path.realpath(dest), str(src.resolve()))
        self.assertTrue(src.exists())

    def test_it_ignores_non_video_siblings(self):
        self.clip("A001.MP4")
        (self.lib / "shoot" / "notes.txt").write_text("hi")
        out = editroom._link_footage("ep", str(self.lib / "shoot"),
                                     log=lambda *a: None)
        self.assertEqual(out["linked"], 1)

    def test_it_never_overwrites_footage_already_there(self):
        keep = self.work / "footage" / "A001.MP4"
        keep.write_bytes(b"ORIGINAL")
        self.clip("A001.MP4", b"DIFFERENT")
        out = editroom._link_footage("ep", str(self.lib / "shoot"),
                                     log=lambda *a: None)
        self.assertEqual(out["linked"], 0)
        self.assertEqual(out["skipped"], 1)
        self.assertEqual(keep.read_bytes(), b"ORIGINAL")

    def test_a_missing_folder_is_refused(self):
        with self.assertRaises(IngestError):
            editroom._link_footage("ep", str(self.root / "nope"),
                                   log=lambda *a: None)

    # ---- relink (the repair) ----

    def test_it_swaps_a_verified_copy_for_a_link_and_reports_bytes(self):
        body = b"REAL" + b"x" * 8192
        src = self.clip("A001.MP4", body)
        copy = self.work / "footage" / "A001.MP4"
        shutil.copy2(src, copy)
        out = editroom._relink_footage("ep", str(self.lib),
                                       log=lambda *a: None)
        self.assertEqual(out["relinked"], 1)
        self.assertEqual(out["bytes"], copy.stat().st_size)
        self.assertTrue(copy.is_symlink())
        self.assertEqual(copy.read_bytes(), src.read_bytes())

    def test_it_refuses_a_same_name_file_with_different_content(self):
        """The case that would destroy footage: two cards reusing a
        counter. Same name, different recording — never swap."""
        self.clip("A001.MP4", b"LIBRARY-VERSION")
        copy = self.work / "footage" / "A001.MP4"
        copy.write_bytes(b"DIFFERENT-RECORDING" + b"\0" * 4096)
        before = copy.read_bytes()
        out = editroom._relink_footage("ep", str(self.lib),
                                       log=lambda *a: None)
        self.assertEqual(out["relinked"], 0)
        self.assertEqual(out["unmatched"], 1)
        self.assertFalse(copy.is_symlink())
        self.assertEqual(copy.read_bytes(), before)

    def test_it_leaves_an_unmatched_name_untouched(self):
        self.clip("A001.MP4")
        orphan = self.work / "footage" / "ORPHAN.MP4"
        orphan.write_bytes(b"only here" + b"\0" * 4096)
        out = editroom._relink_footage("ep", str(self.lib),
                                       log=lambda *a: None)
        self.assertEqual(out["unmatched"], 1)
        self.assertIn("ORPHAN.MP4", out["unmatched_names"])
        self.assertTrue(orphan.is_file() and not orphan.is_symlink())

    def test_it_skips_what_is_already_linked(self):
        src = self.clip("A001.MP4")
        os.symlink(src, self.work / "footage" / "A001.MP4")
        out = editroom._relink_footage("ep", str(self.lib),
                                       log=lambda *a: None)
        self.assertEqual(out["relinked"], 0)
        self.assertEqual(out["unmatched"], 0)

    def test_it_finds_the_match_anywhere_under_the_library(self):
        deep = self.lib / "2026" / "05-17" / "cardB"
        deep.mkdir(parents=True)
        src = self.clip("A009.MP4", b"DEEP", where=deep)
        copy = self.work / "footage" / "A009.MP4"
        shutil.copy2(src, copy)
        out = editroom._relink_footage("ep", str(self.lib),
                                       log=lambda *a: None)
        self.assertEqual(out["relinked"], 1)
        self.assertEqual(os.path.realpath(copy), str(src.resolve()))

    def test_an_empty_library_refuses_rather_than_reporting_success(self):
        (self.work / "footage" / "A001.MP4").write_bytes(b"x" * 4096)
        with self.assertRaises(IngestError):
            editroom._relink_footage("ep", str(self.root / "empty"),
                                     log=lambda *a: None)


if __name__ == "__main__":
    unittest.main()
