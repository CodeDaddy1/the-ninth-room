# -*- coding: utf-8 -*-
"""The contact sheets the Library never showed.

2026-08-25. `analysis/sheets/` holds one contact sheet per described
b-roll clip — 187 of them on the live episode, alongside 182 written
descriptions and 182 tag sets. None of it reached a screen: `sheet` is
written RELATIVE to `analysis/`, the Studio cannot resolve that, and
`/media/<slug>/analysis/sheets/...` 404s. So a desk whose entire job is
choosing a picture rendered one truncated line of prose per shot.

The fix is the one `_footage_state` already uses for thumbnails: resolve
to an absolute path and let `/file?p=` serve it. That route is guarded to
images under the repo root, so this file also pins that a `sheet` value
cannot be used to climb out of `analysis/`.

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


class BrollCatalog(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work = self.tmp / "ep"
        (self.work / "analysis" / "sheets").mkdir(parents=True)
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

    def _catalog(self, clips):
        (self.work / "analysis" / "broll.json").write_text(
            json.dumps({"slug": "ep", "clips": clips}))

    def _sheet(self, name):
        p = self.work / "analysis" / "sheets" / name
        p.write_bytes(b"\xff\xd8jpeg")
        return p

    def test_no_catalog_is_an_empty_list_not_an_error(self):
        self.assertEqual(editroom._broll_catalog("ep"), [])

    def test_a_sheet_on_disk_comes_back_ABSOLUTE(self):
        want = self._sheet("a.mp4.sheet.jpg")
        self._catalog([{"id": "B001", "file": "a.mp4", "duration": 3.0,
                        "sheet": "sheets/a.mp4.sheet.jpg"}])
        got = editroom._broll_catalog("ep")[0]["sheet"]
        self.assertTrue(os.path.isabs(got), "the client cannot resolve a relative path")
        # `.resolve()` on both sides: on macOS the tmpdir's /var is a
        # symlink to /private/var, so an unresolved expectation fails
        # against correct code
        self.assertEqual(Path(got), want.resolve())

    def test_a_sheet_that_is_not_on_disk_is_null_not_a_dead_path(self):
        # a path that 404s renders as a broken image, which reads as a bug
        # in the desk rather than a missing file
        self._catalog([{"id": "B001", "file": "a.mp4", "duration": 3.0,
                        "sheet": "sheets/never-made.jpg"}])
        self.assertIsNone(editroom._broll_catalog("ep")[0]["sheet"])

    def test_a_clip_with_no_sheet_field_is_null_too(self):
        self._catalog([{"id": "B001", "file": "a.mp4", "duration": 3.0}])
        self.assertIsNone(editroom._broll_catalog("ep")[0]["sheet"])

    def test_a_traversal_in_the_sheet_path_does_not_escape_analysis(self):
        """`sheet` comes off disk. `/file?p=` is guarded to images under
        the repo root, but the repo root holds plenty this desk has no
        business serving, so the escape is closed here as well."""
        outside = self.work / "secret.jpg"
        outside.write_bytes(b"\xff\xd8jpeg")
        self._catalog([{"id": "B001", "file": "a.mp4", "duration": 3.0,
                        "sheet": "../secret.jpg"}])
        self.assertIsNone(editroom._broll_catalog("ep")[0]["sheet"])

    def test_the_descriptions_and_TAGS_survive_the_serializer(self):
        """182 of 187 live clips carry tags like
        ['exterior', 'butterfly-center', 'establish', 'morning'] — the
        filters this desk has always promised and never had."""
        self._sheet("a.mp4.sheet.jpg")
        self._catalog([{
            "id": "B001", "file": "a.mp4", "duration": 3.0,
            "sheet": "sheets/a.mp4.sheet.jpg",
            "description": "Exterior, overcast morning: the glass cone",
            "tags": ["exterior", "establish", "morning"],
            "width": 1920, "height": 1080,
        }])
        c = editroom._broll_catalog("ep")[0]
        self.assertEqual(c["tags"], ["exterior", "establish", "morning"])
        self.assertIn("glass cone", c["description"])
        self.assertEqual((c["width"], c["height"]), (1920, 1080))


if __name__ == "__main__":
    unittest.main()
