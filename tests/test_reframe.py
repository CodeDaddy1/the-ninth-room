# -*- coding: utf-8 -*-
"""Nothing gets stretched onto a canvas it does not fit.

Every scale in this pipeline was `scale=W:H` with no aspect handling. That
was invisible while a project was one shape end to end, and wrong the moment
it is not — a vertical episode sources stock, and stock is 16:9. proxy.py
already carries a comment about the stretch incident this caused on the
other axis.

Caleb's call, 2026-08-25: centre-crop, never stretch.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.reframe import crop_rect, fit_filter  # noqa: E402

LANDSCAPE = (3840, 2160)
PORTRAIT = (2160, 3840)


def aspect(w, h):
    return round(w / float(h), 4)


class Geometry(unittest.TestCase):
    def test_a_matching_shape_is_left_alone(self):
        """The common case — every clip in a single-orientation project —
        must add no crop pass and change no behaviour."""
        self.assertEqual(crop_rect(1920, 1080, *LANDSCAPE), (1920, 1080, 0, 0))
        self.assertEqual(fit_filter(1920, 1080, *LANDSCAPE), "scale=3840:2160")

    def test_sixteen_by_nine_onto_vertical_keeps_full_height(self):
        """The case that used to stretch: stock footage in a Short."""
        w, h, x, y = crop_rect(1920, 1080, *PORTRAIT)
        self.assertEqual(h, 1080)          # nothing added, nothing squashed
        self.assertLess(w, 1920)           # the sides go
        self.assertEqual(y, 0)
        self.assertEqual(x, (1920 - w) // 2)   # from the middle

    def test_vertical_onto_sixteen_by_nine_keeps_full_width(self):
        """The reverse is the same function and must also be right — a
        phone clip dropped into an episode."""
        w, h, x, y = crop_rect(1080, 1920, *LANDSCAPE)
        self.assertEqual(w, 1080)
        self.assertLess(h, 1920)
        self.assertEqual(x, 0)
        self.assertEqual(y, (1920 - h) // 2)

    def test_the_kept_region_has_the_canvas_shape(self):
        """The whole point: what survives must already be the right shape,
        so the scale that follows never distorts it."""
        for src in ((1920, 1080), (1080, 1920), (1440, 1080), (3840, 2160),
                    (1000, 1000), (2560, 1080)):
            for dst in (LANDSCAPE, PORTRAIT):
                w, h, _, _ = crop_rect(src[0], src[1], *dst)
                self.assertAlmostEqual(aspect(w, h), aspect(*dst), places=2,
                                       msg="%r -> %r gave %dx%d" % (src, dst, w, h))

    def test_the_crop_never_leaves_the_source(self):
        for src in ((1920, 1080), (1080, 1920), (640, 480), (4096, 2160)):
            for dst in (LANDSCAPE, PORTRAIT):
                w, h, x, y = crop_rect(src[0], src[1], *dst)
                self.assertLessEqual(w + x, src[0])
                self.assertLessEqual(h + y, src[1])
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)

    def test_dimensions_stay_even(self):
        """Odd dimensions break yuv420p encoders — the error would surface
        as an ffmpeg failure three stages later."""
        for src in ((1921, 1081), (999, 1777), (1233, 999)):
            w, h, _, _ = crop_rect(src[0], src[1], *PORTRAIT)
            self.assertEqual(w % 2, 0, "%r width %d" % (src, w))

    def test_the_same_shape_at_a_different_size_is_a_no_op(self):
        """1920x1080 and 3840x2160 are one shape; a rounding-based compare
        could return a one-pixel sliver crop instead of nothing."""
        self.assertEqual(crop_rect(1920, 1080, 3840, 2160), (1920, 1080, 0, 0))
        self.assertEqual(crop_rect(3840, 2160, 1920, 1080), (3840, 2160, 0, 0))

    def test_junk_is_refused_rather_than_producing_a_filter(self):
        for bad in ((0, 1080), (1920, -1), (1920.5, 1080), (True, 1080)):
            with self.assertRaises(ValueError):
                crop_rect(bad[0], bad[1], *PORTRAIT)


class FilterString(unittest.TestCase):
    def test_it_crops_before_it_scales(self):
        """Scaling first would have already distorted the picture."""
        f = fit_filter(1920, 1080, *PORTRAIT)
        self.assertLess(f.index("crop="), f.index("scale="))

    def test_it_names_the_canvas_it_is_filling(self):
        self.assertTrue(fit_filter(1080, 1920, *LANDSCAPE).endswith("scale=3840:2160"))


if __name__ == "__main__":
    unittest.main()
