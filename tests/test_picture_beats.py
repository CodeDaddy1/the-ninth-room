# -*- coding: utf-8 -*-
"""A beat may have no take.

Caleb, 2026-08-28. Two real shapes need it, and neither could be expressed:

  * a stretch of pure picture with no line under it, and
  * b-roll carried by its OWN sound — which was the spine of an entire
    direction. Six of golf-testing's eleven sections were off-camera voices
    over b-roll ("Okay, there we go.", "Nice, babe.", "No way."), and a
    cover is emitted as a picture-only <video>, so those lines were
    inaudible in any cut the engine could build.

`validate_edit_plan` required `take_id` to be a str, so this was FORBIDDEN
by the schema rather than merely unimplemented — golf-testing's design
carried `take_id: null` on all eleven beats and could not be validated at
all.

Natural sound is opted INTO. A cover is silent on purpose because b-roll
audio leaking over narration is a known hazard (timeline.py: "museum crowd
noise!"), so a spine stays silent unless the plan says otherwise.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import shutil
import tempfile
from pathlib import Path

from pipeline import schemas, timeline  # noqa: E402

FPS = 30.0

CLIPS = {"clips": [{"id": "B001", "file": "a.mov", "duration": 9.12},
                   {"id": "B002", "file": "b.mov", "duration": 4.0}]}
TAKES = {"takes": [{"id": "T01", "file": "IMG_1.mov", "s": 0.0, "e": 10.0,
                    "kind": "oncamera", "transcript": "a line",
                    "duration": 10.0}]}


def plan(*beats):
    return {"slug": "ep", "format": "youtube_short", "orientation": "portrait",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "hook": {"take_id": "T01", "why": "w"},
            "beats": list(beats)}


def spine_beat(bid="BT01", purpose="hook", clip="B001", s=0.0, e=4.0,
               audio=None):
    b = {"id": bid, "purpose": purpose, "transition_in": "cut",
         "spine": {"clip_id": clip, "src_s": s, "src_e": e}}
    if audio is not None:
        b["spine"]["audio"] = audio
    return b


def take_beat(bid="BT02", purpose="payoff"):
    return {"id": bid, "purpose": purpose, "take_id": "T01",
            "trim": {"s": 0.0, "e": 10.0}, "transition_in": "cut"}


class ABeatMayHaveNoTake(unittest.TestCase):

    def errs(self, *beats):
        return schemas.validate_edit_plan(plan(*beats), TAKES, CLIPS)

    def test_a_spine_beat_validates_without_a_take(self):
        """THE REGRESSION. `_req(..., "take_id", str, ...)` rejected both a
        missing key and an explicit null, so golf-testing's eleven beats
        could not be validated at all."""
        out = self.errs(spine_beat(), take_beat())
        self.assertEqual([e for e in out if "take_id" in e], [], out)

    def test_a_beat_with_neither_take_nor_spine_is_still_an_error(self):
        """Relaxing the rule must not remove it."""
        out = self.errs({"id": "BT01", "purpose": "hook",
                         "transition_in": "cut"}, take_beat())
        self.assertTrue(any("take_id" in e for e in out), out)

    def test_a_spine_on_an_unknown_clip_is_named(self):
        out = self.errs(spine_beat(clip="B999"), take_beat())
        self.assertTrue(any("unknown clip 'B999'" in e for e in out), out)

    def test_a_spine_running_past_the_end_of_its_clip_is_named(self):
        out = self.errs(spine_beat(clip="B002", s=0.0, e=9.0), take_beat())
        self.assertTrue(any("but clip 'B002' is 4.00s" in e for e in out), out)

    def test_an_empty_spine_window_is_named(self):
        out = self.errs(spine_beat(s=3.0, e=3.0), take_beat())
        self.assertTrue(any("must be after" in e for e in out), out)

    def test_audio_must_be_a_bool(self):
        """'true' is not True, and a string would be truthy forever."""
        out = self.errs(spine_beat(audio="yes"), take_beat())
        self.assertTrue(any("'audio' should be bool" in e for e in out), out)

    def test_a_spine_beat_is_kind_picture(self):
        self.assertEqual(schemas.beat_kind(spine_beat(), {}), "picture")

    def test_a_take_still_wins_when_both_are_present(self):
        """A beat that has a take IS its take, whatever else it carries."""
        b = take_beat(bid="BT01", purpose="hook")
        b["spine"] = {"clip_id": "B999"}          # would be invalid alone
        out = self.errs(b, take_beat())
        self.assertEqual([e for e in out if "unknown clip" in e], [], out)


def map_beat(bid, fname, rec_s, dur, kind, natural_sound=False):
    """One record-time beat as plan_beats emits it."""
    return {"id": bid, "file": fname, "record_s": rec_s,
            "record_e": rec_s + dur, "transition_in": "cut", "broll": [],
            "kind": kind, "natural_sound": natural_sound,
            "segments": [{"src_s": 0.0, "src_e": dur, "record_s": rec_s}]}


class PictureBeatsInTheXML(unittest.TestCase):
    """The half that decides whether anyone can HEAR the beat."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps(
            {"files": [{"name": "clip.mov", "path": str(self.tmp / "clip.mov"),
                        "duration": 60.0, "has_audio": True},
                       {"name": "speech.mov",
                        "path": str(self.tmp / "speech.mov"),
                        "duration": 60.0, "has_audio": True}]}))
        self._wp, self._ad = timeline.work_path, timeline.analysis_dir
        timeline.work_path = lambda slug: self.tmp
        timeline.analysis_dir = lambda slug: self.tmp / "analysis"

    def tearDown(self):
        timeline.work_path, timeline.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.tmp, ignore_errors=True)

    def emit(self, *beats):
        tl_map = {"fps": FPS, "orientation": "landscape",
                  "duration": max(b["record_e"] for b in beats),
                  "beats": list(beats)}
        return timeline.write_fcpxml("t", tl_map, [], [],
                                     log=lambda *a: None).read_text()

    def test_natural_sound_is_an_asset_clip_so_the_audio_plays(self):
        """B-NATSOUND: the off-camera voices ARE the beat. An <asset-clip>
        carries the asset's audio; this is what makes those lines audible."""
        xml = self.emit(map_beat("BT01", "clip.mov", 0.0, 4.0, "picture",
                                 natural_sound=True))
        self.assertIn("<asset-clip", xml)
        self.assertNotIn("<video ref=", xml)

    def test_a_silent_picture_beat_is_a_video_element(self):
        """No opt-in, no audio — the same rule a cover follows, for the
        same reason: b-roll sound must not leak under the cut."""
        xml = self.emit(map_beat("BT01", "clip.mov", 0.0, 4.0, "picture"))
        self.assertIn("<video ref=", xml)
        self.assertNotIn("<asset-clip", xml)

    def test_a_speech_beat_is_untouched(self):
        xml = self.emit(map_beat("BT01", "speech.mov", 0.0, 10.0, "oncamera"))
        self.assertIn("<asset-clip", xml)
        self.assertNotIn("<video ref=", xml)

    def test_the_asset_still_declares_its_audio(self):
        """The <video> suppresses playback; it must not make the asset lie
        about what the file contains, or a later cover of the same clip
        would inherit the wrong declaration."""
        xml = self.emit(map_beat("BT01", "clip.mov", 0.0, 4.0, "picture"))
        self.assertIn('hasAudio="1"', xml)

    def test_mixed_beats_each_take_their_own_path(self):
        xml = self.emit(
            map_beat("BT01", "clip.mov", 0.0, 4.0, "picture"),
            map_beat("BT02", "speech.mov", 4.0, 10.0, "oncamera"),
            map_beat("BT03", "clip.mov", 14.0, 3.0, "picture",
                     natural_sound=True))
        self.assertEqual(xml.count("<video ref="), 1)
        self.assertEqual(xml.count("<asset-clip"), 2)


if __name__ == "__main__":
    unittest.main()
