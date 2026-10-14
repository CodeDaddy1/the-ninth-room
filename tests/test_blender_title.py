# -*- coding: utf-8 -*-
"""The 3D title card is the flat kit's numbers, handed to Blender.

Not one brand value may be typed into `pipeline/blender_title.py`: colours,
font, easing and shadow all come from `overlay_kit`, which reads the design
tokens. These tests pin that (a token change must reach the spec), pin the
one piece of arithmetic (sRGB hex to scene-linear, which is what keeps chalk
chalk under a Standard view transform), and pin the guards around the
Blender build without launching Blender.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import blender_title as bt  # noqa: E402
from pipeline import overlay_kit as kit  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class Colour(unittest.TestCase):
    def test_hex_to_linear_is_the_srgb_curve(self):
        self.assertEqual(bt.hex_to_linear("#000000"), [0.0, 0.0, 0.0])
        self.assertEqual(bt.hex_to_linear("#FFFFFF"), [1.0, 1.0, 1.0])
        r, g, b = bt.hex_to_linear("#808080")
        self.assertAlmostEqual(r, 0.2158, places=3)   # mid grey is ~22% linear
        self.assertEqual((r, g, b), (r, r, r))


class Parsers(unittest.TestCase):
    def test_the_kit_easing_tokens_parse(self):
        self.assertEqual(bt.parse_bezier("cubic-bezier(.16,1,.3,1)"), [0.16, 1.0, 0.3, 1.0])
        with self.assertRaises(IngestError):
            bt.parse_bezier("ease-in-out")

    def test_the_kit_shadow_parses_with_y_flipped_to_up(self):
        sh = bt.parse_shadows("0 0 5px rgba(4,16,32,.95),0 5px 24px rgba(4,16,32,.9)")
        self.assertEqual(len(sh), 2)
        self.assertEqual((sh[1]["dx"], sh[1]["dy"], sh[1]["blur"], sh[1]["alpha"]),
                         (0.0, -5.0, 24.0, 0.9))
        self.assertEqual(sh[0]["rgb"], bt.hex_to_linear("#041020"))
        with self.assertRaises(IngestError):
            bt.parse_shadows("none")


class Spec(unittest.TestCase):
    def test_every_brand_value_comes_from_the_kit(self):
        spec = bt.title_spec("The Ninth Room", kicker="Episode one")
        self.assertEqual(spec["colors"]["chalk"], bt.hex_to_linear(kit.CHALK))
        self.assertEqual(spec["colors"]["cyan"], bt.hex_to_linear(kit.CYAN))
        self.assertEqual(spec["colors"]["side"], bt.hex_to_linear(kit.NAVY_800))
        self.assertEqual(spec["motion"]["ease_reveal"], bt.parse_bezier(kit.EASE_REVEAL))
        self.assertEqual(spec["motion"]["ease_rule"], bt.parse_bezier(kit.EASE_RULE))
        self.assertEqual(spec["shadows"], bt.parse_shadows(kit.SHADOW_DISPLAY))
        self.assertEqual(spec["eyebrow"]["rule_thick_px"], kit.STROKE)
        self.assertTrue(Path(spec["font"]).is_file())

    def test_a_token_change_reaches_the_spec(self):
        with mock.patch.object(kit, "CHALK", "#FF0000"):
            spec = bt.title_spec("x")
        self.assertEqual(spec["colors"]["chalk"], [1.0, 0.0, 0.0])

    def test_the_kits_layout_numbers_and_the_caps_eyebrow(self):
        spec = bt.title_spec("x", kicker="Episode one", fps=24, seconds=3.0)
        self.assertEqual(spec["title"]["left_px"], 140)
        self.assertEqual(spec["title"]["inner_px"], 1560)
        self.assertEqual(spec["title"]["size_px"], 120)
        self.assertEqual(spec["eyebrow"]["text"], "EPISODE ONE")
        self.assertEqual(spec["frames"], 72)
        self.assertEqual(spec["text_scale"], bt.BLENDER_TEXT_SCALE)
        portrait = bt.title_spec("x", w=1080, h=1920)
        self.assertEqual((portrait["title"]["left_px"], portrait["title"]["inner_px"]), (64, 952))
        # a 4K portrait canvas is the same 1080-wide layout at dpr 2
        uhd = bt.title_spec("x", w=2160, h=3840)
        self.assertEqual((uhd["design_w"], uhd["design_h"], uhd["title"]["inner_px"]), (1080, 1920, 952))
        self.assertEqual((uhd["w"], uhd["h"]), (2160, 3840))

    def test_empty_text_is_refused(self):
        with self.assertRaises(IngestError):
            bt.title_spec("   ")


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.out = self.tmp / "clip" / "title.mov"

    def test_the_build_command_is_factory_startup_with_an_exit_code(self):
        cmd = bt.build_command(Path("/x/spec.json"))
        self.assertEqual(cmd[:5], [bt.BLENDER, "--background", "--factory-startup",
                                   "--python-exit-code", "1"])
        self.assertEqual(cmd[5:], ["--python", str(bt.BUILD_BRIDGE), "--", "/x/spec.json"])
        self.assertTrue(bt.BUILD_BRIDGE.is_file())

    def test_a_build_that_writes_no_blend_is_refused_before_rendering(self):
        with mock.patch.object(bt.os.path, "exists", return_value=True), \
                mock.patch.object(bt.subprocess, "run",
                                  return_value=mock.Mock(returncode=0, stderr="", stdout="")), \
                mock.patch.object(bt, "render_blend") as render:
            with self.assertRaises(IngestError) as cm:
                bt.build_title("x", self.out)
        self.assertIn("wrote no .blend", str(cm.exception))
        render.assert_not_called()

    def test_a_good_build_renders_the_scenes_whole_range(self):
        def fake_blender(cmd, capture_output=True, text=True, **kw):
            spec = json.loads(Path(cmd[-1]).read_text())
            Path(spec["blend"]).write_bytes(b"BLENDER")
            return mock.Mock(returncode=0, stderr="", stdout="")
        with mock.patch.object(bt.os.path, "exists", return_value=True), \
                mock.patch.object(bt.subprocess, "run", fake_blender), \
                mock.patch.object(bt, "render_blend", side_effect=lambda b, m, **kw: m) as render:
            out = bt.build_title("The Ninth Room", self.out, fps=24, seconds=2.0)
        self.assertEqual(out, self.out)
        blend, mov = render.call_args[0]
        self.assertEqual(blend, self.out.with_suffix(".blend"))
        kw = dict(render.call_args[1]); kw.pop("tmp_dir", None)
        self.assertEqual(kw, {"fps": 24, "start": 1, "end": 48})
        spec = json.loads(self.out.with_suffix(".title.json").read_text())
        self.assertEqual(spec["title"]["text"], "The Ninth Room")


if __name__ == "__main__":
    unittest.main()
