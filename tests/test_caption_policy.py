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


class CaptionsFollowTheVoice(unittest.TestCase):
    """2026-08-24, as the format moved VO-led: a narration line has
    nobody on screen to caption, so it gets none — but short form keeps
    every line, because Shorts are watched muted and are the discovery
    engine."""

    DOC = {"style": "punchline", "beats": [
        {"beat_id": "BT01", "text": "on camera, punchy", "selected": True},
        {"beat_id": "BT02", "text": "on camera, ordinary", "selected": False},
        {"beat_id": "BT03", "text": "narrated line", "selected": True},
    ]}
    VO = frozenset(["BT03"])

    def test_portrait_keeps_every_line_including_vo(self):
        out = captions.effective_captions(self.DOC, "portrait", self.VO)
        self.assertEqual(set(out), {"BT01", "BT02", "BT03"})

    def test_landscape_drops_the_vo_line(self):
        out = captions.effective_captions(self.DOC, "landscape", self.VO)
        self.assertNotIn("BT03", out)

    def test_landscape_keeps_the_selected_on_camera_line(self):
        out = captions.effective_captions(self.DOC, "landscape", self.VO)
        self.assertEqual(set(out), {"BT01"})

    def test_a_classic_doc_still_drops_vo_in_landscape(self):
        """No style field = every on-camera line bakes, but narration is
        narration whatever the caption style is."""
        doc = {"beats": [{"beat_id": "BT01", "text": "face"},
                         {"beat_id": "BT03", "text": "voice"}]}
        out = captions.effective_captions(doc, "landscape", self.VO)
        self.assertEqual(set(out), {"BT01"})

    def test_omitting_the_vo_set_changes_nothing(self):
        """The freeze: hmns has 0 VO beats, so the new argument is
        invisible to it."""
        a = captions.effective_captions(self.DOC, "landscape")
        b = captions.effective_captions(self.DOC, "landscape", frozenset())
        self.assertEqual(a, b)
        self.assertEqual(set(a), {"BT01", "BT03"})

    def test_vo_beats_of_reads_the_same_marker_the_coverage_bar_uses(self):
        tl = {"beats": [{"id": "BT01", "take_id": "T14"},
                        {"id": "BT02", "take_id": "vo_ch1_t1"},
                        {"id": "BT03"}]}
        self.assertEqual(captions.vo_beats_of(tl), frozenset(["BT02"]))
