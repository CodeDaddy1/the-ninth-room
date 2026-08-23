# -*- coding: utf-8 -*-
"""Seeding the shoot plan from the approved story.

The plan stops being pre-shoot guesswork (Caleb, 2026-08-23): once a
direction is approved, its chapters become the capture list — title plus
the rough-cut text as the first shot to cover — and research angles land
as ninth-room candidates. The two honesty rules pinned here: no approval
means no seed, and a plan that already has chapters is someone's WORK,
never a seed target.

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

from pipeline import editroom  # noqa: E402


class SeedPlan(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        editroom.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def approve(self, choice='S2'):
        (self.tmp / 'story_feedback.json').write_text(json.dumps(
            {"rounds": [{"decision": "approve", "choice": choice}]}))

    def stories(self):
        (self.tmp / 'stories.json').write_text(json.dumps({"options": [
            {"id": "S1", "title": "loser"},
            {"id": "S2", "title": "winner", "beats_outline": [
                {"text": "CH1 · Move-in day — bags dropped, first look over the rail",
                 "target_s": 95},
                "COLD OPEN + preview montage — one shot per chapter",
                {"text": "CH2 · The park — Central Park at dusk"},
            ]},
        ]}))

    def test_no_approval_refuses(self):
        self.stories()
        with self.assertRaises(Exception) as cm:
            editroom._seed_plan("ep")
        self.assertIn("no approved story", str(cm.exception))

    def test_existing_chapters_are_work_not_a_seed_target(self):
        self.approve()
        self.stories()
        (self.tmp / 'plan.json').write_text(json.dumps(
            {"chapters": [{"title": "mine", "shots": [], "card_ideas": []}]}))
        with self.assertRaises(Exception) as cm:
            editroom._seed_plan("ep")
        self.assertIn("clobber", str(cm.exception))

    def test_chapters_seed_with_title_and_rough_cut_shot(self):
        self.approve()
        self.stories()
        plan = editroom._seed_plan("ep")
        chs = plan["chapters"]
        self.assertEqual(len(chs), 3)
        self.assertEqual(chs[0]["title"], "Move-in day")
        self.assertIn("bags dropped", chs[0]["shots"][0]["desc"])
        # plain-string outline items seed too (legacy pitch shape)
        self.assertEqual(chs[1]["title"], "COLD OPEN + preview montage")
        self.assertEqual(chs[2]["title"], "The park")

    def test_research_angles_become_ninth_room_candidates(self):
        self.approve()
        self.stories()
        (self.tmp / 'research.json').write_text(json.dumps(
            {"angles": ["The city that does 22 knots", "Who lives here"]}))
        plan = editroom._seed_plan("ep")
        self.assertIn("The city that does 22 knots", plan["ninth_room_candidates"])

    def test_the_briefs_location_fills_an_empty_place(self):
        self.approve()
        self.stories()
        (self.tmp / 'story_brief.json').write_text(json.dumps(
            {"target_minutes": 12, "chapters": 6,
             "location": "Allure of the Seas"}))
        self.assertEqual(editroom._seed_plan("ep")["place"], "Allure of the Seas")

    def test_a_script_outranks_the_pitch_as_seed_source(self):
        """stories.json is overwritten per round; the script survives and
        its VO lines name exactly the b-roll to capture (found live:
        approval said S2, stories.json held round 2's S4-S6)."""
        self.approve('S2')
        # stories.json from a LATER round -- S2 gone
        (self.tmp / 'stories.json').write_text(json.dumps({"options": [
            {"id": "S4"}, {"id": "S5"}]}))
        (self.tmp / 'script.json').write_text(json.dumps({
            "slug": "ep", "option_id": "S2", "chapters": [{
                "id": "CH1", "title": "Breakfast, Ruled On", "target_s": 100,
                "sections": [
                    {"id": "CH1.S1", "kind": "oncamera", "take_id": "T1",
                     "text": "chewy all day long", "est_s": 8},
                    {"id": "CH1.S2", "kind": "vo",
                     "text": "That is a real review of a real donut", "est_s": 10},
                ]}]}))
        plan = editroom._seed_plan("ep")
        ch = plan["chapters"][0]
        self.assertEqual(ch["title"], "Breakfast, Ruled On")
        self.assertEqual(ch["shots"][0]["desc"],
                         "Cover with b-roll: That is a real review of a real donut")

    def test_a_vanished_option_with_no_script_says_what_to_do(self):
        self.approve('S2')
        (self.tmp / 'stories.json').write_text(json.dumps({"options": [
            {"id": "S4"}]}))
        with self.assertRaises(Exception) as cm:
            editroom._seed_plan("ep")
        self.assertIn("Write the script first", str(cm.exception))

    def test_the_seeded_plan_passes_the_plan_validator(self):
        self.approve()
        self.stories()
        self.assertEqual(editroom._validate_plan(editroom._seed_plan("ep")), [])


if __name__ == "__main__":
    unittest.main()
