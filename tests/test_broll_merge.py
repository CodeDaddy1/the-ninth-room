# -*- coding: utf-8 -*-
"""Re-analysis must not destroy the catalogue it is updating.

2026-08-25, found while answering "are we able to auto analyze the
uploaded assets?" — the honest answer turned out to be that
re-analysing at all was dangerous, for two reasons that both look like
housekeeping and are not:

  * DESCRIPTIONS. Python writes "" and the story-designer fills them as
    pre-work. A rebuild wiped all 186 of them on the live episode — the
    exact text the coverage editor reads to justify every cover.
  * IDS. They were positional (B%03d of len(clips)+1), so removing or
    screening out any earlier clip renumbered everything after it while
    60 covers in the cut referenced those ids BY NAME. Those covers would
    have silently pointed at different footage.

Both were proved against a copy of the real project before the fix.

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

from pipeline import broll, ingest  # noqa: E402


class MergeNotRebuild(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis" / "sheets").mkdir(parents=True)
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        self._ad = ingest.analysis_dir
        ingest.analysis_dir = lambda slug: self.tmp / "analysis"
        broll.analysis_dir = ingest.analysis_dir

    def tearDown(self):
        ingest.work_path = self._wp
        ingest.analysis_dir = self._ad
        broll.analysis_dir = self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _catalog(self, names):
        files = []
        for n in names:
            p = self.tmp / n
            p.write_bytes(b"x" * 2048)
            # a sheet already on disk means contact_sheet is never called
            (self.tmp / "analysis" / "sheets" / (n + ".sheet.jpg")).write_bytes(b"j")
            files.append({"name": n, "path": str(p), "kind": "video",
                          "class": "broll", "duration": 5.0,
                          "width": 1920, "height": 1080})
        (self.tmp / "analysis" / "catalog.json").write_text(
            json.dumps({"slug": "ep", "files": files}))

    def _broll(self):
        return json.loads((self.tmp / "analysis" / "broll.json").read_text())["clips"]

    def test_descriptions_survive_a_re_analysis(self):
        self._catalog(["a.mp4", "b.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        clips = self._broll()
        clips[0]["description"] = "the glass cone at dawn"
        clips[0]["tags"] = ["exterior"]
        (self.tmp / "analysis" / "broll.json").write_text(
            json.dumps({"slug": "ep", "clips": clips}))
        broll.catalog_broll("ep", log=lambda *a: None)
        after = self._broll()
        self.assertEqual(after[0]["description"], "the glass cone at dawn")
        self.assertEqual(after[0]["tags"], ["exterior"])

    def test_framing_survives_a_re_analysis(self):
        """The shot size is the story-designer's judgment, read off the
        9-frame contact sheet while it writes the description — same
        author, same lifecycle, so it needs the same carry-forward.

        Without it every tag dies at the next ingest SILENTLY, and the
        only symptom weeks later is the craft bar reporting clips as
        untagged that somebody already tagged. That is the exact failure
        this file exists to record, one field later."""
        self._catalog(["a.mp4", "b.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        clips = self._broll()
        clips[0]["framing"] = "detail"
        (self.tmp / "analysis" / "broll.json").write_text(
            json.dumps({"slug": "ep", "clips": clips}))
        broll.catalog_broll("ep", log=lambda *a: None)
        self.assertEqual(self._broll()[0]["framing"], "detail")

    def test_an_untagged_clip_carries_the_empty_string(self):
        """"" is the untagged state, and it must be a real key: the bar
        reads `clip.get("framing") not in SHOT_SIZES`, and a missing key
        and an empty one have to mean the same thing."""
        self._catalog(["a.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        self.assertEqual(self._broll()[0]["framing"], "")

    def test_a_catalog_with_framing_validates(self):
        """And a typo does not — it would otherwise surface as the bar
        reporting the clip untagged, which sends the writer to tag it
        again rather than to fix the spelling."""
        from pipeline import schemas
        self._catalog(["a.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        doc = json.loads(
            (self.tmp / "analysis" / "broll.json").read_text())
        self.assertEqual(schemas.validate_broll(doc), [])
        doc["clips"][0]["framing"] = "wide"
        self.assertEqual(schemas.validate_broll(doc), [])
        doc["clips"][0]["framing"] = "widee"
        self.assertTrue(any("framing" in e
                            for e in schemas.validate_broll(doc)))

    def test_an_added_file_gets_a_NEW_id_and_disturbs_nobody(self):
        self._catalog(["a.mp4", "b.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        first = {c["file"]: c["id"] for c in self._broll()}
        self._catalog(["a.mp4", "b.mp4", "c.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        after = {c["file"]: c["id"] for c in self._broll()}
        self.assertEqual(after["a.mp4"], first["a.mp4"])
        self.assertEqual(after["b.mp4"], first["b.mp4"])
        self.assertEqual(after["c.mp4"], "B003")

    def test_removing_an_EARLIER_clip_never_renumbers_the_rest(self):
        """The one that would have repointed 60 covers at other footage."""
        self._catalog(["a.mp4", "b.mp4", "c.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        before = {c["file"]: c["id"] for c in self._broll()}
        self.assertEqual(before["c.mp4"], "B003")
        self._catalog(["a.mp4", "c.mp4"])          # b is gone
        broll.catalog_broll("ep", log=lambda *a: None)
        after = {c["file"]: c["id"] for c in self._broll()}
        self.assertEqual(after["c.mp4"], "B003", "ids shifted under the cut")
        self.assertEqual(after["a.mp4"], "B001")

    def test_a_new_file_after_a_removal_does_not_reuse_a_dead_id(self):
        """B002 belonged to something once; a cover or a note may still
        name it, so the next file takes B004 rather than the gap."""
        self._catalog(["a.mp4", "b.mp4", "c.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        self._catalog(["a.mp4", "c.mp4", "d.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        after = {c["file"]: c["id"] for c in self._broll()}
        self.assertEqual(after["d.mp4"], "B004")

    def test_a_first_run_still_numbers_from_one(self):
        self._catalog(["a.mp4", "b.mp4"])
        broll.catalog_broll("ep", log=lambda *a: None)
        self.assertEqual([c["id"] for c in self._broll()], ["B001", "B002"])


if __name__ == "__main__":
    unittest.main()


class PromotingArmsAnalysis(unittest.TestCase):
    """Promoting an asset must analyse it without being asked.

    It used to leave the shelf and the catalogue out of step until
    someone remembered to re-analyze by hand — so the material sat there
    with no clip id and no way to reach a beat (2026-08-25).
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "assets").mkdir(parents=True)
        (self.tmp / "analysis").mkdir(parents=True)
        (self.tmp / "analysis" / "catalog.json").write_text('{"slug":"ep","files":[]}')
        (self.tmp / "assets" / "clip.mp4").write_bytes(b"x" * 64)
        (self.tmp / "assets" / "assets.json").write_text(json.dumps(
            {"assets": [{"id": "A1", "file": "clip.mp4"}]}))
        from pipeline import editroom, jobs
        self.editroom, self.jobs = editroom, jobs
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        self.armed = []
        self._note = jobs.note_upload
        jobs.note_upload = self.armed.append

    def tearDown(self):
        self.editroom.work_path = self._wp
        self.jobs.note_upload = self._note
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_using_an_asset_arms_the_analysis(self):
        out = self.editroom._use_asset("ep", "A1")
        self.assertTrue(out["analyzing"])
        self.assertEqual(self.armed, ["ep"])

    def test_a_project_with_no_catalog_yet_arms_nothing(self):
        """Nothing has been analysed, so there is nothing to keep in
        step — the first real ingest will pick this up anyway."""
        (self.tmp / "analysis" / "catalog.json").unlink()
        out = self.editroom._use_asset("ep", "A1")
        self.assertFalse(out["reingest"])
        self.assertEqual(self.armed, [])
