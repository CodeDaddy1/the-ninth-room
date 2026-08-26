# -*- coding: utf-8 -*-
"""Caleb's own tags, and the takes he admits as picture.

2026-08-26: "We should be able to add clips based on tags. We should also
be able to tag footage with keywords manually. If a footage is cut from
the story, we should be able to bring it back into the story as a clip to
use as b roll. Even if the clip was deemed a spoken take. Removing audio
makes it a broll."

Two facts made this cheap, and both are load-bearing here:

  * **A cover is already silent.** `timeline.py` writes b-roll on lane 2 as
    an FCPXML `<video>` element, never an `<asset-clip>` — built that way
    so museum crowd noise could not leak over the narration. So "removing
    the audio makes it b-roll" needs no audio work at all: a promoted
    spoken take contributes picture and nothing else, by construction.

  * **The catalog is DERIVED.** Ingest rebuilds catalog.json from probe on
    every run and `catalog_broll` rebuilds broll.json from that, so a flag
    written into either is erased by the next analyze. A promoted take
    erased that way would take its B-id with it while covers in the cut go
    on referencing that id by name — which is the same silent-repointing
    the id-stability rule already exists to prevent.

So the record is a SIDECAR, keyed by filename, exactly as
`footage_sources.json` is and for the same stated reason. These tests are
mostly about what survives a rebuild.

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

WORK = Path(__file__).resolve().parent.parent / "work"


class ManualSidecar(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work = self.tmp / "ep"
        (self.work / "analysis").mkdir(parents=True)
        self._iwp = ingest.work_path
        ingest.work_path = lambda slug: self.work
        broll.work_path = lambda slug: self.work
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        ingest.work_path = self._iwp
        broll.work_path = self._iwp
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    # --- the sidecar itself ------------------------------------------

    def test_absent_unreadable_and_wrong_shaped_all_mean_nothing_manual(self):
        self.assertEqual(broll.read_manual("ep"), {"tags": {}, "promoted": []})
        p = self.work / "broll_manual.json"
        for junk in ("not json at all", "[]", '{"tags": 3, "promoted": "no"}'):
            p.write_text(junk)
            self.assertEqual(broll.read_manual("ep"), {"tags": {}, "promoted": []},
                             "a damaged sidecar must read as empty, never raise")

    def test_tags_are_cleaned_deduped_and_lowercased(self):
        out = broll.set_tags("ep", "a.mov", ["  Dinosaur ", "dinosaur", "", "Hero"])
        self.assertEqual(out, ["dinosaur", "hero"])
        self.assertEqual(broll.read_manual("ep")["tags"]["a.mov"], ["dinosaur", "hero"])

    def test_clearing_tags_removes_the_key_rather_than_storing_an_empty_list(self):
        broll.set_tags("ep", "a.mov", ["x"])
        broll.set_tags("ep", "a.mov", [])
        self.assertNotIn("a.mov", broll.read_manual("ep")["tags"])

    def test_promote_is_idempotent_and_reversible(self):
        self.assertTrue(broll.promote("ep", "t.mov"))
        broll.promote("ep", "t.mov")
        self.assertEqual(broll.read_manual("ep")["promoted"], ["t.mov"],
                         "promoting twice must not list the file twice")
        broll.promote("ep", "t.mov", on=False)
        self.assertEqual(broll.read_manual("ep")["promoted"], [])

    def test_one_file_does_not_disturb_another(self):
        broll.set_tags("ep", "a.mov", ["x"])
        broll.promote("ep", "b.mov")
        broll.set_tags("ep", "c.mov", ["y"])
        m = broll.read_manual("ep")
        self.assertEqual(m["tags"], {"a.mov": ["x"], "c.mov": ["y"]})
        self.assertEqual(m["promoted"], ["b.mov"])

    # --- what the rebuild does with it -------------------------------

    def _catalog(self, *files):
        (self.work / "analysis" / "catalog.json").write_text(
            json.dumps({"slug": "ep", "files": list(files), "skipped": []}))

    def _file(self, name, cls="broll", **over):
        # a real path, so the sheet step has something to look at; the
        # sheet is pre-made below so ffmpeg never runs
        p = self.work / name
        p.write_bytes(b"\x00")
        e = {"name": name, "path": str(p), "kind": "video", "duration": 8.0,
             "class": cls, "width": 1920, "height": 1080, "fps": 24.0}
        e.update(over)
        return e

    def _presheet(self, *names):
        d = self.work / "analysis" / "sheets"
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            (d / (n + ".sheet.jpg")).write_bytes(b"\xff\xd8jpeg")

    def test_a_spoken_take_is_excluded_until_it_is_promoted(self):
        self._catalog(self._file("shot.mov", "broll"),
                      self._file("take.mov", "speech"))
        self._presheet("shot.mov", "take.mov")
        broll.catalog_broll("ep", log=lambda m: None)
        got = json.loads((self.work / "analysis" / "broll.json").read_text())
        self.assertEqual([c["file"] for c in got["clips"]], ["shot.mov"])

        broll.promote("ep", "take.mov")
        broll.catalog_broll("ep", log=lambda m: None)
        got = json.loads((self.work / "analysis" / "broll.json").read_text())
        files = [c["file"] for c in got["clips"]]
        self.assertIn("take.mov", files, "a promoted spoken take must be catalogued")
        entry = next(c for c in got["clips"] if c["file"] == "take.mov")
        self.assertTrue(entry["promoted"])
        self.assertEqual(entry["from_class"], "speech",
                         "it must still say what it was — the transcript is still real")

    def test_a_promoted_take_SURVIVES_the_next_analyze_and_keeps_its_id(self):
        """The whole reason this is a sidecar. A rebuild that dropped it
        would leave every cover referencing its id pointing at nothing."""
        self._catalog(self._file("shot.mov", "broll"),
                      self._file("take.mov", "speech"))
        self._presheet("shot.mov", "take.mov")
        broll.promote("ep", "take.mov")
        broll.catalog_broll("ep", log=lambda m: None)
        first = {c["file"]: c["id"] for c in
                 json.loads((self.work / "analysis" / "broll.json").read_text())["clips"]}
        # analyze again — catalog.json is rewritten from probe and knows
        # nothing about the promotion
        self._catalog(self._file("shot.mov", "broll"),
                      self._file("take.mov", "speech"))
        broll.catalog_broll("ep", log=lambda m: None)
        second = {c["file"]: c["id"] for c in
                  json.loads((self.work / "analysis" / "broll.json").read_text())["clips"]}
        self.assertIn("take.mov", second)
        self.assertEqual(first, second, "ids must not move across a rebuild")

    def test_the_agents_tags_and_Calebs_are_kept_apart_and_unioned(self):
        self._catalog(self._file("shot.mov", "broll"))
        self._presheet("shot.mov")
        broll.catalog_broll("ep", log=lambda m: None)
        # the agent's description pass writes its own
        p = self.work / "analysis" / "broll.json"
        d = json.loads(p.read_text())
        d["clips"][0]["tags"] = ["dinosaur"]
        p.write_text(json.dumps(d))

        broll.set_tags("ep", "shot.mov", ["sofia"])
        broll.catalog_broll("ep", log=lambda m: None)
        c = json.loads(p.read_text())["clips"][0]
        self.assertEqual(c["tags"], ["dinosaur", "sofia"], "both, agent first")
        self.assertEqual(c["manual_tags"], ["sofia"],
                         "and which are Caleb's stays knowable, so his can be removed")

    def test_a_screened_out_clip_is_not_promotable_into_the_cut_by_accident(self):
        # screening is mechanical uselessness — black, too short, duplicate.
        # Promotion is about CLASS, and must not reach past that judgement.
        self._catalog(self._file("dud.mov", "speech", screened_out=True,
                                 screen_reason="all black"))
        self._presheet("dud.mov")
        broll.promote("ep", "dud.mov")
        broll.catalog_broll("ep", log=lambda m: None)
        got = json.loads((self.work / "analysis" / "broll.json").read_text())
        self.assertEqual(got["clips"], [],
                         "promotion must not resurrect a clip that cannot be cut")
