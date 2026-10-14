# -*- coding: utf-8 -*-
"""A reconstruction cannot reach a master unmarked or uncredited.

Decision 6: the kit eyebrow RECONSTRUCTION sits over a photoreal
illustration for its whole length. Decision 15: the publish package
carries a Credits section naming the model and the YouTube disclosure
when a reconstruction is in the cut; Export never blocks on a licence.

The marker is a kit card the ENGINE owns (`MARK<n>`, kit_type
`provenance`): `illustration.sync_markers` derives one per reconstruction
span from the timeline map after every graphics, reproxy, assemble,
attach and detach, so a graphics session that rewrites the whole plan
cannot drop them, and `marker_notes` refuses an unmarked span or any card
overlapping one (graphics-director's law: never two cards at once).

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

from pipeline import deliver, editroom, illustration as il, ingest, jobs, overlay_kit, schemas  # noqa: E402


class _Cut(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        (self.tmp / "graphics").mkdir()
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        for mod in (il, jobs, editroom, deliver):
            mod.work_path = ingest.work_path
        self._bake = il._bake_cards
        il._bake_cards = lambda slug, ids, log=None: None
        self.tl = {"slug": "ep", "orientation": "landscape", "beats": [
            {"id": "b1", "record_s": 0.0, "record_e": 8.0, "purpose": "build", "broll": [
                {"clip_id": "B009", "file": "plaza.mp4", "record_s": 2.0, "duration": 3.0,
                 "src_s": 0.0, "provenance": "reconstruction"},
                {"clip_id": "B001", "file": "hall.mp4", "record_s": 5.5, "duration": 2.0, "src_s": 0.0}]},
            {"id": "b2", "record_s": 8.0, "record_e": 28.0, "purpose": "build", "file": "sea.mp4",
             "provenance": "reconstruction", "broll": []},
            {"id": "b3", "record_s": 28.0, "record_e": 33.0, "purpose": "build", "broll": [
                {"clip_id": "B010", "file": "egg.mp4", "record_s": 29.0, "duration": 2.0,
                 "src_s": 0.0, "provenance": "illustration"}]}]}
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps(self.tl))
        (self.tmp / "edit_plan.json").write_text(json.dumps({"slug": "ep", "beats": [
            {"id": "b1", "purpose": "build"}, {"id": "b2", "purpose": "build"}, {"id": "b3", "purpose": "build"}]}))

    def tearDown(self):
        ingest.work_path = self._wp
        for mod in (il, jobs, editroom, deliver):
            mod.work_path = self._wp
        il._bake_cards = self._bake
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self):
        return json.loads((self.tmp / "graphics_plan.json").read_text())

    def marks(self):
        return sorted((c["beat_id"], c["at"], c["duration"]) for c in self.plan()["cards"]
                      if c["id"].startswith("MARK"))


class Markers(_Cut):
    def test_one_card_per_reconstruction_span_split_under_fifteen_seconds(self):
        out = il.sync_markers("ep")
        self.assertEqual(self.marks(), [("b1", 2.0, 3.0), ("b2", 0.0, 15.0), ("b2", 15.0, 5.0)])
        self.assertEqual(len(out["added"]), 3)
        for c in self.plan()["cards"]:
            self.assertEqual((c["type"], c["kit_type"], c["text"]), ("section", "provenance", "RECONSTRUCTION"))
        self.assertFalse(any(c["beat_id"] == "b3" for c in self.plan()["cards"]), "an illustration is not marked")

    def test_every_marker_passes_the_plan_validator(self):
        il.sync_markers("ep")
        ep = json.loads((self.tmp / "edit_plan.json").read_text())
        self.assertEqual(schemas.validate_graphics_plan(self.plan(), ep), [])

    def test_idempotent_and_survives_a_rewritten_plan(self):
        il.sync_markers("ep")
        first = self.plan()["cards"]
        out = il.sync_markers("ep")
        self.assertEqual(out["added"], [])
        self.assertEqual(self.plan()["cards"], first)
        # the graphics session rewrites the whole file without the markers
        (self.tmp / "graphics_plan.json").write_text(json.dumps({"slug": "ep", "cards": [
            {"id": "CARD01", "type": "section", "kit_type": "lower_third", "text": "Hi",
             "beat_id": "b3", "at": 0.5, "duration": 3.0}]}))
        il.sync_markers("ep")
        ids = [c["id"] for c in self.plan()["cards"]]
        self.assertIn("CARD01", ids)
        self.assertEqual(len([i for i in ids if i.startswith("MARK")]), 3)

    def test_an_orphan_goes_when_its_span_goes(self):
        il.sync_markers("ep")
        self.tl["beats"][0]["broll"] = [c for c in self.tl["beats"][0]["broll"] if c["clip_id"] != "B009"]
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps(self.tl))
        out = il.sync_markers("ep")
        self.assertEqual(len(out["removed"]), 1)
        self.assertEqual(self.marks(), [("b2", 0.0, 15.0), ("b2", 15.0, 5.0)])

    def test_notes_name_an_unmarked_span_and_an_overlapping_card(self):
        self.assertTrue(any("unmarked" in n for n in il.marker_notes("ep")))
        il.sync_markers("ep")
        self.assertEqual(il.marker_notes("ep"), [])
        plan = self.plan()
        plan["cards"].append({"id": "CARD09", "type": "section", "kit_type": "chapter", "text": "Ch",
                              "beat_id": "b1", "at": 3.0, "duration": 2.5})
        (self.tmp / "graphics_plan.json").write_text(json.dumps(plan))
        notes = il.marker_notes("ep")
        self.assertEqual(len(notes), 1)
        self.assertIn("CARD09", notes[0]); self.assertIn("MARK", notes[0])

    def test_nothing_to_mark_writes_nothing(self):
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps({"beats": [
            {"id": "b3", "record_s": 0.0, "record_e": 5.0, "broll": []}]}))
        il.sync_markers("ep")
        self.assertFalse((self.tmp / "graphics_plan.json").exists())
        self.assertEqual(il.marker_notes("ep"), [])

    def test_the_kit_knows_the_screen(self):
        self.assertIn("provenance", overlay_kit.RENDERERS)
        html = overlay_kit.RENDERERS["provenance"]({"text": "RECONSTRUCTION", "kicker": "RECONSTRUCTION"},
                                                    overlay_kit._frame(1920, 1080))
        self.assertIn("RECONSTRUCTION", html)
        self.assertIn("provenance", editroom._KIT_TEMPLATES)


class Credits(_Cut):
    def setUp(self):
        super().setUp()
        (self.tmp / "assets").mkdir()
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps({"slug": "ep", "clips": [
            {"id": "B009", "file": "plaza.mp4", "duration": 8.0, "sheet": "s", "provenance": "reconstruction"},
            {"id": "B010", "file": "egg.mp4", "duration": 5.0, "sheet": "s", "provenance": "illustration"},
            {"id": "B011", "file": "spare.mp4", "duration": 5.0, "sheet": "s", "provenance": "illustration"}]}))
        (self.tmp / "edit_plan.json").write_text(json.dumps({"slug": "ep", "beats": [
            {"id": "b1", "purpose": "build", "broll": [{"clip_id": "B009", "at": 2.0, "duration": 3.0}]},
            {"id": "b2", "purpose": "build", "spine": {"clip_id": "B010", "src_s": 0, "src_e": 4}, "broll": []}]}))
        (self.tmp / "assets" / "assets.json").write_text(json.dumps({"assets": [
            {"id": "r-plaza", "file": "plaza.mp4", "promoted_as": "plaza.mp4", "kind": "illustration",
             "honesty": "reconstruction", "model": "kling3_0", "cost_credits": 7.5, "status": "done", "job_id": "j"},
            {"id": "r-egg", "file": "egg.mp4", "promoted_as": "egg.mp4", "kind": "illustration",
             "honesty": "illustration", "model": "nano_banana_pro", "cost_credits": 2.0, "status": "done", "job_id": "j"},
            {"id": "r-spare", "file": "spare.mp4", "promoted_as": "spare.mp4", "kind": "illustration",
             "honesty": "illustration", "model": "seedance_2_5", "cost_credits": 45.0, "status": "done", "job_id": "j"}]}))

    def test_in_cut_lists_only_what_the_plan_uses(self):
        rows = il.in_cut("ep")
        self.assertEqual(sorted(r["id"] for r in rows), ["r-egg", "r-plaza"])

    def test_the_credits_clause_names_the_models_and_the_disclosure(self):
        clause = jobs._credits_clause("ep")
        self.assertIn("kling3_0", clause); self.assertIn("nano_banana_pro", clause)
        self.assertNotIn("seedance_2_5", clause)
        self.assertIn("# Credits", clause)
        self.assertIn("altered or synthetic", clause.lower())

    def test_the_publish_post_check_demands_credits_and_the_disclosure(self):
        md = "# Title options\n- a\n# Description\nhello\n# Tags\nx\n"
        with self.assertRaises(RuntimeError) as cm:
            jobs._check_publish_md("ep", md)
        self.assertIn("Credits", str(cm.exception))
        md += "# Credits\nIllustrations generated with kling3_0, nano_banana_pro via Higgsfield.\n"
        with self.assertRaises(RuntimeError) as cm:
            jobs._check_publish_md("ep", md)
        self.assertIn("disclos", str(cm.exception).lower())
        md = md.replace("hello", "hello\nThis video contains altered or synthetic content: one reconstruction.")
        jobs._check_publish_md("ep", md)
        # no illustration in the cut: no credits demanded
        (self.tmp / "edit_plan.json").write_text(json.dumps({"slug": "ep", "beats": []}))
        jobs._check_publish_md("ep", "# Title options\n- a\n# Description\nhello\n# Tags\nx\n")

    def test_the_checklist_row_never_blocks(self):
        # what proxy._load reads unconditionally further down the checklist
        (self.tmp / "footage").mkdir()
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps({"slug": "ep", "files": [], "skipped": []}))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps({"slug": "ep", "takes": [], "groups": []}))
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps({"slug": "ep", "beats": []}))
        with mock.patch.object(editroom, "_state", lambda slug: (_ for _ in ()).throw(RuntimeError("no engine"))), \
                mock.patch.object(deliver.subprocess, "run", lambda *a, **k: mock.Mock(stdout="", returncode=0)):
            out = deliver.checklist("ep")
        row = next(r for r in out["rows"] if r["id"] == "credits")
        self.assertFalse(row["ok"]); self.assertFalse(row["blocking"])
        others = [r["ok"] for r in out["rows"] if r.get("blocking", True)]
        self.assertEqual(out["ready"], all(others))


if __name__ == "__main__":
    unittest.main()


class ThumbnailTargets(unittest.TestCase):
    """Decision 5: thumbnails and Shorts covers ride the illustration round
    kind; a generated frame never becomes the thumbnail by accident
    (_bake_thumbnail refuses it), and one chosen on purpose is copied into
    deliverables with the same versioning as a baked one."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "assets").mkdir()
        (self.tmp / "deliverables").mkdir()
        (self.tmp / "assets" / "R9-plate.png").write_bytes(b"png")
        (self.tmp / "assets" / "R9-motion.mp4").write_bytes(b"mp4")
        (self.tmp / "assets" / "assets.json").write_text(json.dumps({"assets": [
            {"id": "R9-plate", "file": "R9-plate.png", "kind": "illustration", "honesty": "illustration",
             "target": "thumbnail", "model": "text2image_soul_v2", "cost_credits": 2.0, "status": "done", "job_id": "j"},
            {"id": "R9-motion", "file": "R9-motion.mp4", "kind": "illustration", "honesty": "illustration",
             "target": "short_cover", "model": "kling3_0", "cost_credits": 7.5, "status": "done", "job_id": "j"},
            {"id": "egg", "file": "egg.mp4", "kind": "illustration", "honesty": "illustration",
             "target": "cover", "model": "kling3_0", "cost_credits": 7.5, "status": "done", "job_id": "j"}]}))
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_thumbnail_row_is_versioned_into_deliverables_never_overwriting(self):
        (self.tmp / "deliverables" / "thumbnail_v1.png").write_bytes(b"old")
        out = editroom._use_illustration_thumbnail("ep", "R9-plate")
        self.assertEqual(out["file"], "thumbnail_v2.png")
        self.assertEqual((self.tmp / "deliverables" / "thumbnail_v1.png").read_bytes(), b"old")
        self.assertEqual((self.tmp / "deliverables" / "thumbnail_v2.png").read_bytes(), b"png")
        out = editroom._use_illustration_thumbnail("ep", "R9-motion")
        self.assertEqual(out["file"], "short_cover_v1.mp4")

    def test_a_cover_row_is_not_a_thumbnail(self):
        from pipeline.ingest import IngestError
        with self.assertRaises(IngestError):
            editroom._use_illustration_thumbnail("ep", "egg")

    def test_a_short_cover_round_validates_with_a_soul_plate_and_motion(self):
        r = {"id": "R9", "kind": "illustration", "section_id": "CH1.S1", "status": "proposed",
             "honesty": "illustration", "target": "short_cover", "aspect": "9:16",
             "steps": [{"stage": "plate", "model": "text2image_soul_v2", "soul": True,
                        "prompt": "the host at the rail", "credits": 2.0, "tier": "std"},
                       {"stage": "motion", "model": "kling3_0", "start_image": "plate",
                        "prompt": "a slow push", "credits": 7.5, "tier": "std"}],
             "estimate_credits": 9.5, "marks": {}}
        script = {"chapters": [{"id": "CH1", "sections": [{"id": "CH1.S1", "kind": "vo", "text": "x"}]}]}
        self.assertEqual(il.validate_round(r, "short", script=script), [])
