# -*- coding: utf-8 -*-
"""J-cuts and L-cuts — audio that does not line up with its own picture.

The construct is a connected `<audio lane="-1">` child, verified against
Resolve 21.0.4.5 on 2026-08-23: a 1s child of clip A referencing clip B's
asset landed on A2 at frames 60-90 while B's video stayed at 90.

Two failure modes make these tests worth having, because BOTH fail silently:
a negative child offset kills the entire import (Resolve returns nil, no
error), and a source range outside the file pulls silence or a frozen tail.
Neither shows up as an exception — only as a wrong or missing timeline.

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

from pipeline import timeline  # noqa: E402

FPS = 30.0


def beat(bid, fname, rec_s, src_s, dur, **extra):
    d = {"id": bid, "file": fname, "record_s": rec_s, "record_e": rec_s + dur,
         "transition_in": "cut", "broll": [],
         "segments": [{"src_s": src_s, "src_e": src_s + dur, "record_s": rec_s}]}
    d.update(extra)
    return d


class SplitEditXML(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps({"files": [
            {"name": "a.mov", "path": str(self.tmp / "a.mov"),
             "duration": 60.0, "has_audio": True},
            {"name": "b.mov", "path": str(self.tmp / "b.mov"),
             "duration": 60.0, "has_audio": True},
            {"name": "silent.mov", "path": str(self.tmp / "silent.mov"),
             "duration": 60.0, "has_audio": False},
        ]}))
        self._wp, self._ad = timeline.work_path, timeline.analysis_dir
        timeline.work_path = lambda slug: self.tmp
        timeline.analysis_dir = lambda slug: self.tmp / "analysis"

    def tearDown(self):
        timeline.work_path, timeline.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def emit(self, beats, log=None):
        """log defaults to a sink so a suite run stays readable; pass a list's
        append to assert on what the writer said."""
        self.logged = []
        tl_map = {"fps": FPS, "orientation": "landscape",
                  "duration": max(b["record_e"] for b in beats), "beats": beats}
        return timeline.write_fcpxml(
            "t", tl_map, [], [], log=log or self.logged.append).read_text()

    def test_a_skipped_split_edit_says_why(self):
        """A dropped split edit used to vanish without a word -- the beat just
        was not in the cut and nobody could tell it had been asked for."""
        self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                   beat("BT2", "silent.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        self.assertTrue(any("skipped" in m and "BT2" in m for m in self.logged),
                        "the skip was silent: %r" % self.logged)

    def test_a_placed_split_edit_says_nothing(self):
        self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                   beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        self.assertEqual(self.logged, [])

    # --- the happy paths ------------------------------------------------

    def test_a_plain_pair_of_beats_emits_no_split_audio(self):
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0)])
        self.assertNotIn('<audio lane="-1"', xml)

    def test_j_cut_emits_connected_audio_on_the_previous_clip(self):
        """Hear BT2 one second before you see it."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        self.assertIn('<audio lane="-1"', xml)
        self.assertIn("BT2_jcut", xml)
        # 30fps grid: record 9s inside BT1 (src 0 @ record 0) -> child offset 9s
        self.assertIn('offset="%s"' % timeline.FrameGrid(FPS).rt(9.0), xml)
        # audio source is the second BEFORE BT2's own picture start (5.0)
        self.assertIn('start="%s"' % timeline.FrameGrid(FPS).rt(4.0), xml)

    def test_l_cut_emits_connected_audio_on_the_next_clip(self):
        """BT1's voice carries over BT2's picture."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 2.0, 10.0, audio_tail=1.5),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0)])
        self.assertIn('<audio lane="-1"', xml)
        self.assertIn("BT1_lcut", xml)
        # audio picks up exactly where BT1's picture stopped: src 2.0 + 10.0
        self.assertIn('start="%s"' % timeline.FrameGrid(FPS).rt(12.0), xml)

    def test_the_split_child_is_audio_not_video(self):
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        self.assertNotIn('<video lane="-1"', xml)

    # --- the silent failures these tests exist for ----------------------

    def test_a_j_cut_on_the_very_first_beat_is_skipped(self):
        """There is no previous clip to hang it on."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 5.0, 10.0, audio_lead=1.0),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0)])
        self.assertNotIn('<audio lane="-1"', xml)

    def test_an_l_cut_on_the_very_last_beat_is_skipped(self):
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0, audio_tail=1.0)])
        self.assertNotIn('<audio lane="-1"', xml)

    def test_a_j_cut_reaching_before_the_start_of_the_file_is_skipped(self):
        """src_s is 0.5 and the lead is 1.0 — there is no audio to pull."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 0.5, 10.0, audio_lead=1.0)])
        self.assertNotIn('<audio lane="-1"', xml)

    def test_an_l_cut_running_past_the_end_of_the_file_is_skipped(self):
        """The take ends at 60.0; there is no tail to carry."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 50.0, 10.0, audio_tail=2.0),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0)])
        self.assertNotIn('<audio lane="-1"', xml)

    def test_a_split_edit_from_a_silent_file_is_skipped(self):
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "silent.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        self.assertNotIn('<audio lane="-1"', xml)

    def test_no_child_offset_is_ever_negative(self):
        """A negative offset returns nil from ImportTimelineFromFile and takes
        the WHOLE timeline with it — the one truly unrecoverable failure."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=1.0),
                         beat("BT3", "a.mov", 20.0, 30.0, 10.0, audio_lead=2.0)])
        self.assertNotIn('offset="-', xml)

    # --- the outgoing half: stop the previous voice ---------------------

    def test_a_j_cut_trims_the_outgoing_clip_audio(self):
        """Without this both takes play at once and you hear two people."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        self.assertIn("audioDuration=", xml)
        # BT1 keeps 9s of its 10s of audio -- it stops where BT2's voice starts
        self.assertIn('audioDuration="%s"' % timeline.FrameGrid(FPS).rt(9.0), xml)
        self.assertIn('audioStart="%s"' % timeline.FrameGrid(FPS).rt(0.0), xml)

    def test_a_plain_cut_never_trims_audio(self):
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0)])
        self.assertNotIn("audioDuration=", xml)

    def test_an_l_cut_does_not_trim_the_outgoing_clip(self):
        """An L-cut EXTENDS audio; trimming the host would cut it short."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 2.0, 10.0, audio_tail=1.5),
                         beat("BT2", "b.mov", 10.0, 0.0, 10.0)])
        self.assertNotIn("audioDuration=", xml)

    def test_a_j_cut_is_dropped_rather_than_silence_a_whole_segment(self):
        """Lead == the host segment's whole length: trimming to zero would mute
        BT1 entirely, which is worse than the overlap. Drop the cut instead --
        and drop BOTH halves, never leave the child without its trim."""
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 5.0),
                         beat("BT2", "b.mov", 5.0, 5.0, 10.0, audio_lead=5.0)])
        self.assertNotIn("audioDuration=", xml)
        self.assertNotIn('<audio lane="-1"', xml)

    def test_the_trim_never_exceeds_the_clip(self):
        xml = self.emit([beat("BT1", "a.mov", 0.0, 0.0, 10.0),
                         beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=0.5)])
        self.assertIn('audioDuration="%s"' % timeline.FrameGrid(FPS).rt(9.5), xml)

    def test_the_timeline_still_parses_as_xml_with_splits_present(self):
        from xml.etree import ElementTree
        xml = self.emit([beat("BT1", "a.mov", 0.0, 2.0, 10.0, audio_tail=1.0),
                         beat("BT2", "b.mov", 10.0, 5.0, 10.0, audio_lead=1.0)])
        ElementTree.fromstring(xml)  # raises if malformed


if __name__ == "__main__":
    unittest.main()
