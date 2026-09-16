# -*- coding: utf-8 -*-
"""Provenance survives the doors a picture passes through.

2026-09-15: the first illustrations were promoted from the Library shelf
into footage/. At the symlink every fact about them died: broll.json
carried no provenance, the timeline map none, and build_api graded the
cyanotype plate through the DJI D-Log LUT as if it had been shot in log.
The rule the plan makes is stored once (broll.json, derived from the
manifest at catalog time) and read everywhere; nothing sniffs a filename.

What breaks if this is wrong: a plate reaches the master a different
colour from the one Caleb approved; a re-analyze silently forgets which
clips are illustrations and every rule keyed on provenance goes blind.

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

from pipeline import illustration, schemas  # noqa: E402


def _manifest(adir, rows):
    adir.mkdir(parents=True, exist_ok=True)
    (adir / "assets.json").write_text(json.dumps({"assets": rows}))


class ProvenanceOf(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.adir = self.tmp / "assets"
        _manifest(self.adir, [
            {"id": "a", "file": "egg.mp4", "kind": "illustration",
             "honesty": "illustration", "promoted_as": "egg_2.mp4"},
            {"id": "b", "file": "plaza.png", "kind": "illustration",
             "honesty": "reconstruction"},
            {"id": "c", "file": "stock.mp4", "kind": "video", "license": "CC0"},
        ])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_promoted_name_wins_then_the_file_then_the_still_clip(self):
        self.assertEqual(illustration.provenance_of(self.adir, "egg_2.mp4"), "illustration")
        self.assertEqual(illustration.provenance_of(self.adir, "egg.mp4"), "illustration")
        self.assertEqual(illustration.provenance_of(self.adir, "plaza_still.mp4"), "reconstruction")

    def test_a_camera_or_stock_file_has_none(self):
        self.assertIsNone(illustration.provenance_of(self.adir, "stock.mp4"))
        self.assertIsNone(illustration.provenance_of(self.adir, "DJI_0001.MP4"))

    def test_no_manifest_means_camera(self):
        self.assertIsNone(illustration.provenance_of(self.tmp / "nowhere", "egg.mp4"))


class Catalog(unittest.TestCase):
    """broll.catalog_broll derives `provenance` and a re-analyze keeps it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir()
        (self.tmp / "analysis").mkdir()
        _manifest(self.tmp / "assets", [
            {"id": "a", "file": "egg.mp4", "kind": "illustration",
             "honesty": "illustration", "promoted_as": "egg.mp4"}])
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps({"files": [
            {"name": "egg.mp4", "path": str(self.tmp / "footage" / "egg.mp4"),
             "kind": "video", "class": "broll", "duration": 5.0,
             "width": 3840, "height": 2160, "fps": 24.0},
            {"name": "hall.mp4", "path": str(self.tmp / "footage" / "hall.mp4"),
             "kind": "video", "class": "broll", "duration": 9.0,
             "width": 3840, "height": 2160, "fps": 24.0}]}))
        from pipeline import broll
        self.broll = broll
        self._ad, self._wp = broll.analysis_dir, broll.work_path
        broll.analysis_dir = lambda slug: self.tmp / "analysis"
        broll.work_path = lambda slug: self.tmp
        self._sheet = broll.contact_sheet
        broll.contact_sheet = lambda *a, **k: None
        self._prog = None

    def tearDown(self):
        self.broll.analysis_dir, self.broll.work_path = self._ad, self._wp
        self.broll.contact_sheet = self._sheet
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _clips(self):
        with mock.patch("pipeline.ingest.write_progress", lambda *a, **k: None), \
                mock.patch("pipeline.takes.file_trims", lambda slug: {}):
            self.broll.catalog_broll("ep", log=lambda *a: None)
        return {c["file"]: c for c in
                json.loads((self.tmp / "analysis" / "broll.json").read_text())["clips"]}

    def test_the_catalog_derives_provenance_and_leaves_camera_clips_bare(self):
        clips = self._clips()
        self.assertEqual(clips["egg.mp4"]["provenance"], "illustration")
        self.assertNotIn("provenance", clips["hall.mp4"])

    def test_a_second_analyze_keeps_it(self):
        first = self._clips()
        second = self._clips()
        self.assertEqual(second["egg.mp4"]["id"], first["egg.mp4"]["id"])
        self.assertEqual(second["egg.mp4"]["provenance"], "illustration")

    def test_validate_broll_accepts_provenance_only_from_the_two_values(self):
        ok = {"slug": "ep", "clips": [{"id": "B001", "file": "egg.mp4", "duration": 5.0,
                                       "sheet": "s.jpg", "provenance": "reconstruction"}]}
        self.assertEqual(schemas.validate_broll(ok), [])
        bad = json.loads(json.dumps(ok)); bad["clips"][0]["provenance"] = "ai"
        self.assertTrue(any("provenance" in e for e in schemas.validate_broll(bad)))


class TimelineAndColour(unittest.TestCase):
    def test_camera_file_names_skips_every_provenance_item(self):
        from pipeline import build_api
        tl_map = {"beats": [
            {"id": "b1", "file": "take.mp4", "broll": [
                {"clip_id": "B001", "file": "egg.mp4", "provenance": "illustration"},
                {"clip_id": "B002", "file": "hall.mp4"}]},
            {"id": "b2", "file": "plate.mp4", "provenance": "reconstruction", "broll": []},
        ]}
        by_name = {n: {"name": n} for n in ("take.mp4", "egg.mp4", "hall.mp4", "plate.mp4")}
        names, exempt = build_api.camera_file_names(tl_map, by_name)
        self.assertEqual(sorted(names), ["hall.mp4", "take.mp4"])
        self.assertEqual(exempt, 2)

    def test_the_untouched_count_must_cover_the_exempt_items(self):
        from pipeline import build_api
        self.assertIsNone(build_api.check_untouched("graded=3 lut=3 untouched=2", 2))
        with self.assertRaises(Exception):
            build_api.check_untouched("graded=3 lut=3 untouched=1", 2)

    def test_exempt_files_reads_the_catalog(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "analysis").mkdir()
            (tmp / "analysis" / "broll.json").write_text(json.dumps({"clips": [
                {"id": "B001", "file": "egg.mp4", "provenance": "illustration"},
                {"id": "B002", "file": "hall.mp4"}]}))
            with mock.patch.object(illustration, "work_path", lambda slug: tmp):
                self.assertEqual(illustration.exempt_files("ep"), {"egg.mp4"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
