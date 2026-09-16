# -*- coding: utf-8 -*-
"""A Blender title is a kit type beside the CSS cards, never instead of one.

Decision 8 (docs/decisions-illustrations.md). Two things had to be true
for `chapter_3d` to be pickable: every reader of RENDERERS (the validator,
the picker, the hover preview) finds a screen under the name, and the
cache key sees what the spec cannot name, the template. A flat card's key
must not move when a template does, or every episode re-bakes for a
Blender edit; a Blender card's must, or a template edit ships the old
card. Both are pinned here without launching Blender.

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

from pipeline import blender_kit, blender_title, editroom, graphics, overlay_kit, schemas  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


def _card(kit, cid="CARD01"):
    return {"id": cid, "type": "section", "kit_type": kit, "kicker": "Next",
            "text": "The room that proved the Earth turns", "beat_id": "b1",
            "at": 0.5, "duration": 3.0}


class Registration(unittest.TestCase):
    def test_both_kits_are_screens_the_kit_knows(self):
        for k in ("chapter_3d", "hook_3d"):
            self.assertIn(k, overlay_kit.RENDERERS)
            self.assertIn(k, editroom._KIT_TEMPLATES)
        self.assertIs(overlay_kit.RENDERERS["chapter_3d"], overlay_kit.RENDERERS["chapter"])
        self.assertIn("hook_3d", overlay_kit.SCRIM_CENTER)

    def test_the_validator_accepts_them_and_holds_the_chapter_floor(self):
        plan = {"slug": "ep", "cards": [_card("chapter_3d")]}
        self.assertEqual(schemas.validate_graphics_plan(plan), [])
        plan["cards"][0]["duration"] = 2.0
        self.assertTrue(any("2.5s" in e for e in schemas.validate_graphics_plan(plan)))

    def test_the_picker_has_a_group(self):
        groups = {g["title"]: g["kits"] for g in editroom._kit_groups()}
        self.assertEqual(groups["3D titles"], ["chapter_3d", "hook_3d"])


class CacheKey(unittest.TestCase):
    def test_a_template_change_moves_the_3d_key_and_not_the_flat_one(self):
        flat, three = _card("chapter"), _card("chapter_3d")
        k_flat, k_three = graphics.bake_key(flat, "landscape"), graphics.bake_key(three, "landscape")
        self.assertNotEqual(k_flat, k_three)
        with mock.patch.object(blender_kit, "template_sha", lambda: "0000deadbeef"):
            self.assertEqual(graphics.bake_key(flat, "landscape"), k_flat)
            self.assertNotEqual(graphics.bake_key(three, "landscape"), k_three)

    def test_the_sha_reads_the_bridge_scripts_and_the_text_scale(self):
        a = blender_kit.template_sha()
        with mock.patch.object(blender_title, "BLENDER_TEXT_SCALE", 1.401):
            b = blender_kit.template_sha()
        self.assertNotEqual(a, b)
        self.assertEqual(a, blender_kit.template_sha(), "a content hash, stable across calls")


class TheBranch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "graphics").mkdir()
        (self.tmp / "graphics_plan.json").write_text(json.dumps(
            {"slug": "ep", "cards": [_card("chapter_3d", "C3D"), _card("chapter", "CFLAT")]}))
        self._wp = graphics.work_path
        graphics.work_path = lambda slug: self.tmp

    def tearDown(self):
        graphics.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_cards_routes_a_3d_kit_to_blender_and_a_flat_one_to_chrome(self):
        calls = {"blender": [], "chrome": []}
        def fake_title(text, mov, kicker="", fps=24, seconds=3.0, blend=None, w=None, h=None):
            calls["blender"].append((text, kicker, seconds, w, h))
            Path(mov).write_bytes(b"mov"); return Path(mov)
        def fake_chrome(spec, mov, duration, w, h, tmp_dir, preset="reveal_up", log=print, **kw):
            calls["chrome"].append(spec.get("kit_type"))
            Path(mov).write_bytes(b"mov"); return Path(mov)
        with mock.patch.object(blender_title, "build_title", fake_title), \
                mock.patch("pipeline.animate.render_animation", fake_chrome):
            graphics.build_cards("ep", orientation="landscape", log=lambda *a: None)
        self.assertEqual(calls["blender"], [("The room that proved the Earth turns", "Next", 3.0, 3840, 2160)])
        self.assertEqual(calls["chrome"], ["chapter"])
        hashes = json.loads((self.tmp / "graphics" / ".bake_hashes.json").read_text())
        card = json.loads((self.tmp / "graphics_plan.json").read_text())["cards"][0]
        self.assertEqual(hashes["C3D"], editroom._current_key("ep", card, "landscape"))

    def test_the_canvas_reaches_the_spec_and_a_timeout_is_an_ingest_error(self):
        seen = {}
        def fake_spec(text, kicker="Next", fps=24, seconds=3.0, w=1920, h=1080):
            seen["wh"] = (w, h)
            return {"frames": 72, "w": w, "h": h}
        import subprocess
        def boom(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        with mock.patch.object(blender_title, "title_spec", fake_spec), \
                mock.patch.object(blender_title.os.path, "exists", lambda p: True), \
                mock.patch.object(blender_title.subprocess, "run", boom):
            with self.assertRaises(IngestError) as cm:
                blender_title.build_title("x", self.tmp / "graphics" / "x.mov", w=2160, h=3840)
        self.assertEqual(seen["wh"], (2160, 3840))
        self.assertIn("ran past", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
