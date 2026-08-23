# -*- coding: utf-8 -*-
"""The story brief actually reaches the agent, and bad briefs are refused.

The failure mode a pre-production questionnaire invites is being politely
ignored: the desk saves numbers, the prompt never mentions them, and the
designer pitches a 20-minute epic against a 8-minute brief. _brief_clause
is pure so these tests can pin the whole chain — file on disk to words in
the dispatched prompt — with no engine and no subprocess.

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

from pipeline import editroom, jobs  # noqa: E402


class BriefInThePrompt(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp_jobs = jobs.work_path
        jobs.work_path = lambda slug: self.tmp

    def tearDown(self):
        jobs.work_path = self._wp_jobs
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_brief(self, **over):
        b = {"target_minutes": 8, "chapters": 5, "notes": "", "ts": 0}
        b.update(over)
        (self.tmp / "story_brief.json").write_text(json.dumps(b))

    def test_no_brief_reads_clean(self):
        p = jobs._story_prompt("ep")
        self.assertNotIn("Caleb's brief", p)
        self.assertIn("stories.json", p)

    def test_the_numbers_reach_the_story_prompt(self):
        self.write_brief(target_minutes=8, chapters=5)
        p = jobs._story_prompt("ep")
        self.assertIn("~8-minute episode in 5 chapters", p)

    def test_the_numbers_reach_the_editplan_prompt_too(self):
        """Honoring the brief at pitch time and ignoring it at cut time
        would be the same failure one stage later."""
        self.write_brief(target_minutes=12, chapters=7)
        p = jobs._editplan_prompt("ep")
        self.assertIn("~12-minute episode in 7 chapters", p)

    def test_brief_notes_ride_along(self):
        self.write_brief(notes="lean into the aquarium")
        self.assertIn("lean into the aquarium", jobs._story_prompt("ep"))

    def test_a_corrupt_brief_never_breaks_a_pitch(self):
        (self.tmp / "story_brief.json").write_text("{not json")
        p = jobs._story_prompt("ep")
        self.assertNotIn("Caleb's brief", p)

    def test_the_prompt_teaches_clip_citations(self):
        p = jobs._story_prompt("ep")
        self.assertIn('"clips"', p)
        self.assertIn("favorites first", p)


class BriefValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_valid_brief_lands_on_disk(self):
        b = editroom._save_story_brief("ep", 10, 6, "notes here")
        on_disk = json.loads((self.tmp / "story_brief.json").read_text())
        self.assertEqual(on_disk["target_minutes"], 10)
        self.assertEqual(on_disk["chapters"], 6)
        self.assertEqual(b["notes"], "notes here")

    def test_bounds_hold(self):
        for mins, chaps in ((0, 6), (61, 6), (10, 0), (10, 13)):
            with self.assertRaises(Exception, msg=(mins, chaps)):
                editroom._save_story_brief("ep", mins, chaps)

    def test_non_numbers_are_refused_not_crashed(self):
        with self.assertRaises(Exception):
            editroom._save_story_brief("ep", "ten", "six")

    def test_location_is_kept_and_bounded(self):
        b = editroom._save_story_brief("ep", 10, 6, "", "Houston Museum of Natural Science")
        self.assertEqual(b["location"], "Houston Museum of Natural Science")
        with self.assertRaises(Exception):
            editroom._save_story_brief("ep", 10, 6, "", "x" * 201)

    def test_chapter_cap_is_the_kits_cap(self):
        # 12 passes, 13 refuses — the DoorMeter/kit ceiling
        editroom._save_story_brief("ep", 10, 12)
        with self.assertRaises(Exception):
            editroom._save_story_brief("ep", 10, 13)


if __name__ == "__main__":
    unittest.main()
