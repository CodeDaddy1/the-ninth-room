# -*- coding: utf-8 -*-
"""Vertical footage keeps its shape and gains a ground.

2026-08-24, Caleb: vertical clips should stay in their native format but
sit on "a full screen zoomed shot of original clip". The treatment is a
blurred, dimmed copy of the same frame scaled to cover the canvas, with
the native-aspect clip centred full-height on top, baked to a companion
file so no downstream stage learns about orientation.

The bug this suite exists to keep dead: `eq=brightness` in ffmpeg is an
ADDITIVE offset in [-1,1], not a multiplier. Using it for "75% as
bright" subtracted ~64 levels and measured out at 15% of the centre —
near black. Eyeballing a colour-bar frame showed nothing; measuring the
render caught it. So the render is measured here, not eyeballed.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import fill  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
HAVE_FFMPEG = os.path.exists(FFMPEG)


class Orientation(unittest.TestCase):
    def test_taller_than_wide_is_portrait(self):
        self.assertTrue(fill.is_portrait(1080, 1920))
        self.assertTrue(fill.is_portrait(720, 1280))

    def test_landscape_and_square_are_not(self):
        self.assertFalse(fill.is_portrait(3840, 2160))
        self.assertFalse(fill.is_portrait(1080, 1080))  # pillarboxes fine

    def test_garbage_dimensions_never_raise(self):
        for w, h in ((None, None), (0, 0), ("x", "y"), (0, 1920)):
            self.assertFalse(fill.is_portrait(w, h))


class Filter(unittest.TestCase):
    def test_the_background_covers_rather_than_squashes(self):
        f = fill.fill_filter(1920, 1080)
        self.assertIn("force_original_aspect_ratio=increase", f)
        self.assertIn("crop=1920:1080", f)

    def test_the_foreground_keeps_its_own_aspect(self):
        # scale=-2:H — height pinned, width derived, never both fixed
        self.assertIn("[fg]scale=-2:1080[fgv]", fill.fill_filter(1920, 1080))

    def test_the_dim_is_multiplicative_not_additive(self):
        """The regression. eq=brightness subtracts levels; lutyuv scales."""
        f = fill.fill_filter(1920, 1080, dim=0.75)
        self.assertIn("lutyuv=y=val*0.750", f)
        self.assertNotIn("eq=brightness", f)


class Redirect(unittest.TestCase):
    def test_it_keeps_the_original_on_the_record(self):
        e = {"name": "a.mp4", "path": "/f/a.mp4", "width": 1080, "height": 1920}
        out = fill.redirect(e, Path("/f/filled/a.mp4"), (3840, 2160))
        self.assertEqual(out["source_path"], "/f/a.mp4")
        self.assertEqual((out["native_width"], out["native_height"]), (1080, 1920))
        self.assertEqual(out["path"], "/f/filled/a.mp4")
        self.assertEqual((out["width"], out["height"]), (3840, 2160))
        self.assertTrue(out["filled"])

    def test_it_does_not_mutate_the_entry_it_was_given(self):
        e = {"name": "a.mp4", "path": "/f/a.mp4", "width": 1080, "height": 1920}
        fill.redirect(e, Path("/f/filled/a.mp4"), (3840, 2160))
        self.assertEqual(e["path"], "/f/a.mp4")

    def test_a_second_redirect_keeps_the_FIRST_source(self):
        """Re-baking must not record the filled file as the original."""
        e = {"name": "a.mp4", "path": "/f/a.mp4", "width": 1080, "height": 1920}
        once = fill.redirect(e, Path("/f/filled/a.mp4"), (3840, 2160))
        twice = fill.redirect(once, Path("/f/filled/a.mp4"), (3840, 2160))
        self.assertEqual(twice["source_path"], "/f/a.mp4")
        self.assertEqual(twice["native_height"], 1920)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not available")
class Render(unittest.TestCase):
    """The render itself, measured — the filter string can be perfect and
    the picture still wrong."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.src = self.tmp / "v.mp4"
        subprocess.run(
            [FFMPEG, "-nostdin", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=12:duration=1",
             "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
             str(self.src)], check=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _frame(self, path):
        from PIL import Image
        png = self.tmp / "f.png"
        subprocess.run([FFMPEG, "-nostdin", "-loglevel", "error", "-y",
                        "-ss", "0.5", "-i", str(path), "-frames:v", "1",
                        str(png)], check=True)
        return Image.open(png).convert("L")

    def test_the_canvas_is_landscape_and_the_centre_is_the_clip(self):
        dest = self.tmp / "filled.mp4"
        fill.bake(self.src, dest, (640, 360), log=lambda *a: None)
        im = self._frame(dest)
        self.assertEqual(im.size, (640, 360))

    def test_the_sides_are_dimmed_but_never_near_black(self):
        """The 15%-brightness bug, pinned. A dim of 0.75 must leave the
        ground clearly visible — dark enough to recede, light enough to
        read as the same place."""
        import numpy as np
        dest = self.tmp / "filled.mp4"
        fill.bake(self.src, dest, (640, 360), log=lambda *a: None)
        a = np.asarray(self._frame(dest), dtype=float)
        fg_w = 360 * 360 // 640
        x0 = (640 - fg_w) // 2
        sides = float(np.concatenate([a[:, 8:x0 - 8].ravel(),
                                      a[:, x0 + fg_w + 8:632].ravel()]).mean())
        centre = float(a[:, x0 + 8:x0 + fg_w - 8].mean())
        self.assertGreater(sides, 0.25 * centre,
                           "sides went near-black: additive dim is back")
        self.assertLess(sides, centre,
                        "sides must recede behind the subject")

    def test_the_sides_are_blurred_and_the_centre_is_not(self):
        import numpy as np
        dest = self.tmp / "filled.mp4"
        fill.bake(self.src, dest, (640, 360), log=lambda *a: None)
        a = np.asarray(self._frame(dest), dtype=float)
        fg_w = 360 * 360 // 640
        x0 = (640 - fg_w) // 2
        detail = lambda b: float(np.abs(np.diff(b, axis=1)).mean())  # noqa: E731
        self.assertGreater(detail(a[:, x0 + 8:x0 + fg_w - 8]),
                           3 * detail(a[:, 8:x0 - 8]),
                           "the subject is not meaningfully sharper")

    def test_a_failed_bake_leaves_no_half_written_file(self):
        dest = self.tmp / "filled.mp4"
        with self.assertRaises(RuntimeError):
            fill.bake(self.tmp / "does-not-exist.mp4", dest, (640, 360),
                      log=lambda *a: None)
        self.assertFalse(dest.exists())
        self.assertFalse(dest.with_suffix(".partial.mp4").exists())


if __name__ == "__main__":
    unittest.main()
