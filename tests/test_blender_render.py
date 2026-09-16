# -*- coding: utf-8 -*-
"""Blender is a second frame maker, not a second encoder.

`pipeline/blender_render.py` exists so a 3D title, a model turntable, a
terrain flyover or a parallax push reaches Resolve through the one door
every graphic uses: PNG frames -> `animate.encode_frames` -> ProRes 4444
alpha. These tests pin the contract without launching Blender (that is a
multi-second app start per test): the argv is exact, a missing app or
.blend is refused before anything runs, and a render that wrote fewer
frames than asked — or left a gap — is refused before it is encoded,
because a short clip that plays fine and ends early is the failure nobody
notices until the episode is up.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import blender_render as br  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class _Proc(object):
    def __init__(self, code=0, err=""):
        self.returncode, self.stderr, self.stdout = code, err, ""


def _fake_blender(n_frames, code=0, skip=None):
    """A subprocess.run stand-in that writes n frames like the bridge does."""
    def run(cmd, capture_output=True, text=True, **kw):
        frames_dir = Path(cmd[cmd.index("--") + 1])
        for i in range(n_frames):
            if skip is not None and i == skip:
                continue
            (frames_dir / ("f%04d.png" % i)).write_bytes(b"png")
        return _Proc(code)
    return run


class Argv(unittest.TestCase):
    def test_the_command_is_exact_and_uses_the_bridge_script(self):
        cmd = br.blender_command(Path("/x/s.blend"), Path("/x/f"), 24, None, None)
        self.assertEqual(cmd[:4], [br.BLENDER, "--background", "--python-exit-code", "1"])
        self.assertEqual(cmd[4], "/x/s.blend")
        self.assertEqual(cmd[5:7], ["--python", str(br.BRIDGE)])
        self.assertEqual(cmd[7:], ["--", "/x/f", "24"])
        self.assertTrue(br.BRIDGE.is_file(), "bridge script missing")

    def test_a_range_needs_both_ends(self):
        with self.assertRaises(IngestError):
            br.blender_command(Path("s.blend"), Path("f"), 24, 1, None)
        cmd = br.blender_command(Path("s.blend"), Path("f"), 24, 1, 12)
        self.assertEqual(cmd[-2:], ["1", "12"])


class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.blend = self.tmp / "scene.blend"
        self.blend.write_bytes(b"BLENDER")
        self.out = self.tmp / "out" / "clip.mov"

    def test_a_missing_app_is_refused_before_anything_runs(self):
        with mock.patch.object(br, "BLENDER", "/nowhere/Blender"), \
                mock.patch.object(br.subprocess, "run") as run:
            with self.assertRaises(IngestError) as cm:
                br.render_blend(self.blend, self.out)
        self.assertIn("Blender not found", str(cm.exception))
        run.assert_not_called()

    def test_a_missing_blend_is_refused(self):
        with mock.patch.object(br.os.path, "exists", return_value=True):
            with self.assertRaises(IngestError):
                br.render_blend(self.tmp / "nope.blend", self.out)

    def test_a_failed_render_reports_blenders_stderr(self):
        with mock.patch.object(br.os.path, "exists", return_value=True), \
                mock.patch.object(br.subprocess, "run",
                                  return_value=_Proc(1, "boom")):
            with self.assertRaises(IngestError) as cm:
                br.render_blend(self.blend, self.out)
        self.assertIn("boom", str(cm.exception))

    def test_a_short_render_is_refused_before_encoding(self):
        with mock.patch.object(br.os.path, "exists", return_value=True), \
                mock.patch.object(br.subprocess, "run", _fake_blender(5)), \
                mock.patch.object(br, "encode_frames") as enc:
            with self.assertRaises(IngestError) as cm:
                br.render_blend(self.blend, self.out, start=1, end=12)
        self.assertIn("wrote 5 frames, expected 12", str(cm.exception))
        enc.assert_not_called()

    def test_a_gap_in_the_sequence_is_refused(self):
        with mock.patch.object(br.os.path, "exists", return_value=True), \
                mock.patch.object(br.subprocess, "run", _fake_blender(6, skip=3)), \
                mock.patch.object(br, "encode_frames") as enc:
            with self.assertRaises(IngestError) as cm:
                br.render_blend(self.blend, self.out)
        self.assertIn("gap at f0004.png", str(cm.exception))
        enc.assert_not_called()

    def test_a_full_render_is_handed_to_the_card_encoder(self):
        with mock.patch.object(br.os.path, "exists", return_value=True), \
                mock.patch.object(br.subprocess, "run", _fake_blender(12)), \
                mock.patch.object(br, "encode_frames",
                                  side_effect=lambda d, m, fps: m) as enc:
            out = br.render_blend(self.blend, self.out, fps=30, start=1, end=12)
        self.assertEqual(out, self.out)
        frames_dir, mov, fps = enc.call_args[0]
        self.assertEqual(frames_dir, self.out.parent / "clip_frames")
        self.assertEqual((mov, fps), (self.out, 30))


if __name__ == "__main__":
    unittest.main()
