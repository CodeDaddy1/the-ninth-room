# -*- coding: utf-8 -*-
"""Punchline captions: ~30% that punch, Shorts keep 100%, hmns frozen.

P5 of the workflow plan (2026-08-23). One function owns the policy
(captions.effective_captions) and every consumer — the proxy spec, the
batch bake, the single-beat rebake — reads through it, so the rules can
only drift in one place:

- classic (no style field) captions EVERY line: the original mute-first
  contract, and what keeps every pre-pivot episode's proxy cache keys
  byte-identical (the frozen promise);
- punchline captions only the selected lines in landscape;
- vertical keeps every line regardless — Shorts are watched muted.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import captions  # noqa: E402

CLASSIC = {"slug": "ep", "beats": [
    {"beat_id": "BT01", "text": "hello"},
    {"beat_id": "BT02", "text": "world"},
]}

PUNCH = {"slug": "ep", "style": "punchline", "beats": [
    {"beat_id": "BT01", "text": "the joke", "selected": True, "why": "joke"},
    {"beat_id": "BT02", "text": "connective tissue", "selected": False},
    {"beat_id": "BT03", "text": "no flag at all"},
]}


class EffectiveCaptions(unittest.TestCase):
    def test_classic_captions_every_line(self):
        out = captions.effective_captions(CLASSIC, "landscape")
        self.assertEqual(out, {"BT01": "hello", "BT02": "world"})

    def test_punchline_landscape_keeps_only_the_picks(self):
        out = captions.effective_captions(PUNCH, "landscape")
        self.assertEqual(out, {"BT01": "the joke"})

    def test_a_missing_selected_flag_is_not_a_pick(self):
        """Hand-edited files must fail SAFE: an unflagged line under the
        punchline style stays uncaptioned rather than sneaking in."""
        out = captions.effective_captions(PUNCH, "landscape")
        self.assertNotIn("BT03", out)

    def test_vertical_keeps_every_line(self):
        out = captions.effective_captions(PUNCH, "portrait")
        self.assertEqual(len(out), 3)

    def test_the_frozen_promise_classic_is_bitwise_stable(self):
        """The pre-pivot shape (exactly what hmns has on disk) must map to
        the same dict it always did — this is what keeps its proxy spec
        keys unchanged."""
        legacy = {"slug": "hmns", "beats": [
            {"beat_id": "BT01", "text": "So, jam-packed day"}]}
        self.assertEqual(captions.effective_captions(legacy, "landscape"),
                         {"BT01": "So, jam-packed day"})

    def test_empty_and_missing_docs_are_harmless(self):
        self.assertEqual(captions.effective_captions({}, "landscape"), {})
        self.assertEqual(captions.effective_captions(None, "landscape"), {})


if __name__ == "__main__":
    unittest.main()
