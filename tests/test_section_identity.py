# -*- coding: utf-8 -*-
"""Recordings match sections by FILENAME. That is the whole risk surface.

Two silent-corruption bugs live here, and neither shows up until the cut:

  1. A rewritten line keeps its section id, so its OLD recording keeps
     matching. The desk shows "recorded" and audio of words nobody said
     reaches the timeline. Fixed by putting the revision in the name.
  2. A `desk` take named `vo_*` would inherit the VO rules — and
     `validate_edit_plan` HARD-BLOCKS a vo_ beat's picture from shipping
     (>=90% b-roll). Caleb's face would be mathematically forbidden from
     appearing. Fixed by giving desk its own prefix.

Also pinned: sharpening this must not orphan hmns's real recordings, which
are on disk under the pre-2026-08-24 rev-less name.

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

from pipeline import editroom, schemas  # noqa: E402


class Naming(unittest.TestCase):
    def test_the_revision_rides_in_the_name(self):
        self.assertEqual(editroom._section_file_prefix("vo", "CH1.S2", 2),
                         "vo_CH1-S2_r2_t")

    def test_desk_gets_its_own_prefix(self):
        """Not a flag on a vo_ name — four independent rules key off the
        `vo_` prefix, and landing on the wrong side of them forbids the
        shot from ever being seen."""
        self.assertTrue(
            editroom._section_file_prefix("desk", "CH1.S2", 1)
            .startswith("desk_"))

    def test_dots_never_fight_the_extension(self):
        self.assertNotIn(".", editroom._section_file_prefix("vo", "CH1.S2", 1))

    def test_revision_one_still_answers_to_the_legacy_name(self):
        """hmns's recordings are on disk as vo_CH1-S2_t1.webm, with no
        revision segment. Orphaning them would be this module's own bug."""
        pres = editroom._section_file_prefixes("vo", "CH1.S2", 1)
        self.assertIn("vo_CH1-S2_t", pres)
        self.assertIn("vo_CH1-S2_r1_t", pres)

    def test_a_later_revision_does_not(self):
        self.assertEqual(editroom._section_file_prefixes("vo", "CH1.S2", 3),
                         ("vo_CH1-S2_r3_t",))

    def test_a_missing_rev_is_revision_one(self):
        self.assertEqual(editroom._sec_rev({}), 1)
        self.assertEqual(editroom._sec_rev({"rev": None}), 1)
        self.assertEqual(editroom._sec_rev({"rev": "junk"}), 1)
        self.assertEqual(editroom._sec_rev({"rev": 4}), 4)


class Staleness(unittest.TestCase):
    """The desk's answer after a rewrite: not 'missing', which reads as an
    error — 'the line changed', which is what actually happened."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp())
        (self.work / "analysis").mkdir(parents=True)
        (self.work / "footage").mkdir()
        self._wp, self._ad = editroom.work_path, editroom.analysis_dir
        editroom.work_path = lambda slug: self.work
        editroom.analysis_dir = lambda slug: self.work / "analysis"

    def tearDown(self):
        editroom.work_path, editroom.analysis_dir = self._wp, self._ad
        shutil.rmtree(self.work, ignore_errors=True)

    def write(self, sections, catalog_names=()):
        (self.work / "script.json").write_text(json.dumps({
            "slug": "ep", "option_id": "S1", "target_minutes": 1,
            "chapters": [{"id": "CH1", "title": "c", "target_s": 60,
                          "sections": sections}]}))
        (self.work / "analysis" / "catalog.json").write_text(json.dumps({
            "files": [{"name": n, "class": "speech", "duration": 9.0}
                      for n in catalog_names]}))

    def section(self, sid="CH1.S1", **kw):
        d = {"id": sid, "kind": "vo", "text": "a line", "est_s": 10.0}
        d.update(kw)
        return d

    def test_a_recording_at_the_current_revision_counts(self):
        self.write([self.section(rev=1)], ["vo_CH1-S1_r1_t1.webm"])
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertTrue(sec["recorded"])

    def test_a_legacy_recording_still_counts(self):
        self.write([self.section(rev=1)], ["vo_CH1-S1_t1.webm"])
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertTrue(sec["recorded"])

    def test_a_rewritten_line_is_NOT_recorded(self):
        """The bug this whole phase exists to prevent: without the revision
        in the name, this take would keep matching and ship."""
        self.write([self.section(rev=2)], ["vo_CH1-S1_r1_t1.webm"])
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertFalse(sec["recorded"])

    def test_and_the_old_take_is_still_named_as_history(self):
        """It stays on disk. The desk can say which file it was rather than
        pretending nothing was ever recorded."""
        self.write([self.section(rev=2)], ["vo_CH1-S1_r1_t1.webm"])
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertTrue(sec["stale"])
        self.assertEqual(sec["stale_recordings"], ["vo_CH1-S1_r1_t1.webm"])

    def test_a_desk_section_is_reported_too(self):
        self.write([self.section(kind="desk", rev=1)],
                   ["desk_CH1-S1_r1_t1.mp4"])
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertTrue(sec["recorded"])
        self.assertTrue(sec["file_prefix"].startswith("desk_"))

    def test_a_vo_file_never_satisfies_a_desk_section(self):
        """Different performances entirely — one is a webcam read, the
        other is the shot."""
        self.write([self.section(kind="desk", rev=1)],
                   ["vo_CH1-S1_r1_t1.webm"])
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertFalse(sec["recorded"])

    def test_editing_a_line_bumps_its_revision(self):
        self.write([self.section(rev=1)], ["vo_CH1-S1_r1_t1.webm"])
        editroom._save_script_section("ep", "CH1.S1", "completely new words")
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertEqual(sec["rev"], 2)
        self.assertFalse(sec["recorded"])   # the old take is not these words

    def test_saving_identical_text_is_not_a_revision(self):
        """Opening an editor and clicking save must not orphan a take."""
        self.write([self.section(rev=1)], ["vo_CH1-S1_r1_t1.webm"])
        editroom._save_script_section("ep", "CH1.S1", "a line")
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertEqual(editroom._sec_rev(sec), 1)
        self.assertTrue(sec["recorded"])

    def test_a_desk_line_is_editable(self):
        """It is written, not quoted — unlike oncamera."""
        self.write([self.section(kind="desk", rev=1)])
        editroom._save_script_section("ep", "CH1.S1", "new desk words")
        sec = editroom._script_state("ep")["script"]["chapters"][0]["sections"][0]
        self.assertEqual(sec["text"], "new desk words")

    def test_an_oncamera_quote_is_not_editable(self):
        self.write([self.section(kind="oncamera", take_id="T1")])
        with self.assertRaises(editroom.IngestError):
            editroom._save_script_section("ep", "CH1.S1", "improved wording")


class DeskPictureShips(unittest.TestCase):
    """The rule that made the separate prefix necessary, pinned from the
    other side: a desk beat must NOT be treated as voice-over."""

    def plan(self, take_file):
        return ({"slug": "ep", "format": "youtube_long",
                 "orientation": "landscape",
                 "theme": {"problem": "p", "promise": "q", "payoff": "r"},
                 "hook": {"take_id": "T1", "why": "w"},
                 "beats": [{"id": "BT01", "purpose": "hook", "take_id": "T1",
                            "trim": {"s": 0.0, "e": 10.0},
                            "transition_in": "cut"}]},
                {"takes": [{"id": "T1", "file": take_file, "s": 0.0, "e": 10.0,
                            "transcript": "a line", "duration": 10.0}]})

    def test_a_voice_over_beat_still_may_not_show_its_picture(self):
        plan, takes = self.plan("vo_CH1-S1_r1_t1.webm")
        errs = schemas.validate_edit_plan(plan, takes, {"clips": []})
        self.assertTrue(any("teleprompter picture" in e for e in errs), errs)

    def test_a_desk_beat_may(self):
        """His face is the shot. No b-roll required, and none implied."""
        plan, takes = self.plan("desk_CH1-S1_r1_t1.mp4")
        errs = schemas.validate_edit_plan(plan, takes, {"clips": []})
        self.assertFalse(any("teleprompter picture" in e for e in errs), errs)

    def test_a_desk_beat_is_not_exempt_from_the_coverage_rules(self):
        """The VO exemption exists because there is no face to cut back
        to. A desk beat has one, so the landing still belongs to it."""
        plan, _ = self.plan("desk_CH1-S1_r1_t1.mp4")
        plan["beats"][0]["broll"] = [
            {"clip_id": "B1", "at": 8.5, "duration": 2.0,
             "why": "illustrate — the thing"}]
        notes = schemas.coverage_notes(plan)
        self.assertTrue(any("landing" in n for n in notes), notes)


if __name__ == "__main__":
    unittest.main()
