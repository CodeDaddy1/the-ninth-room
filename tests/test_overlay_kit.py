# -*- coding: utf-8 -*-
"""The Cyanotype kit renders, and refuses sizes that render to nothing.

`RENDERERS` is the authoritative list (CLAUDE.md: read the dict, don't trust a
count in prose), so this walks it rather than naming screens. Every one is
exercised in both orientations, because the kit branches on `F["portrait"]`
and a Short is not just a narrower frame.

The two clamps close deferred kit defects: `_fit(text, 0)` emitted
`font-size:0px` — copy that is present in the DOM and invisible on screen,
which reads as a bake failure — and `_arch` below 8px rounded every feature of
its 8u grid to zero, producing an empty box where the brand's own mark should
be. Both were unreachable while every call site passed a positive literal;
both become reachable the moment a size is caller-driven.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import overlay_kit as kit  # noqa: E402

# One spec carrying every field any screen might read. Screens ignore what
# they do not use, so this exercises all of them without 49 fixtures.
SPEC = {
    "text": "The one thing that wasn't on the map",
    "kicker": "Room nine", "subtext": "New rooms every week",
    "cta": "Subscribe", "value": 55, "duration": 3,
    "emojis": [{"char": "\U0001f99c"}], "attribution": "",
    "rows": [{"label": "Then", "value": "1901"}, {"label": "Now", "value": "2026"}],
    "items": ["one", "two", "three"], "q": "How tall?",
    "options": ["A", "B"], "answer": "A", "number": 9,
    "title": "Chapter two", "caption": "a caption", "quote": "a quote",
    "name": "Sofia", "emphasis": ["one thing"],
}
FRAMES = ((1920, 1080), (1080, 1920))


class EveryScreenRenders(unittest.TestCase):
    def test_every_renderer_produces_html_in_both_orientations(self):
        for name in sorted(kit.RENDERERS):
            for w, h in FRAMES:
                spec = dict(SPEC, kit_type=name)
                with self.subTest(screen=name, frame="%dx%d" % (w, h)):
                    html = kit.overlay_html(spec, w, h)
                    self.assertTrue(html, "%s rendered empty" % name)

    def test_no_screen_emits_invisible_type(self):
        """font-size:0px is copy that is in the DOM and absent on screen."""
        for name in sorted(kit.RENDERERS):
            for w, h in FRAMES:
                with self.subTest(screen=name):
                    html = kit.overlay_html(dict(SPEC, kit_type=name), w, h)
                    self.assertNotIn("font-size:0px", html)

    def test_an_unknown_kit_type_is_refused(self):
        with self.assertRaises(ValueError):
            kit.overlay_html({"kit_type": "not_a_real_kit"}, 1920, 1080)


class SizeClamps(unittest.TestCase):
    def test_fit_refuses_a_zero_base(self):
        with self.assertRaises(ValueError):
            kit._fit("hello", 0)

    def test_fit_refuses_a_negative_base(self):
        with self.assertRaises(ValueError):
            kit._fit("hello", -20)

    def test_fit_still_returns_a_size_for_ordinary_copy(self):
        self.assertGreater(kit._fit("hello world", 64), 0)

    def test_fit_shrinks_long_copy_rather_than_overflowing(self):
        short = kit._fit("Room nine", 120)
        long = kit._fit("Room nine and the very long title that keeps going "
                        "well past any sensible width", 120)
        self.assertLess(long, short)

    def test_arch_refuses_a_width_that_rounds_its_grid_to_zero(self):
        with self.assertRaises(ValueError):
            kit._arch(4)

    def test_arch_still_draws_at_its_real_call_sizes(self):
        for width in (64, 200):
            self.assertTrue(kit._arch(width))


if __name__ == "__main__":
    unittest.main()
