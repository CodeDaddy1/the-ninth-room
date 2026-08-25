# -*- coding: utf-8 -*-
"""The VO share is a per-episode dial, and it is measured in TIME.

2026-08-24, as the format moved VO-led. Caleb: "my vision is fluid, 90%
narrating voice for a few videos won't hurt the content" — so the target
lives in `story_brief.json` per episode, and the bar checks the script
against THAT number rather than a constant baked into the code.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import schemas  # noqa: E402


def script(*sections):
    return {"chapters": [{"id": "CH1", "title": "c", "sections":
                          [dict(s) for s in sections]}]}


def sec(sid, kind, est, text="a line", **kw):
    s = {"id": sid, "kind": kind, "est_s": est, "text": text}
    s.update(kw)
    return s


class Share(unittest.TestCase):
    def test_it_is_share_of_TIME_not_of_section_count(self):
        """Three short VO lines beside one long answer is not VO-led,
        and counting sections would claim it was."""
        sc = script(sec("S1", "vo", 5), sec("S2", "vo", 5), sec("S3", "vo", 5),
                    sec("S4", "oncamera", 85))
        self.assertEqual(len(sc["chapters"][0]["sections"]), 4)
        self.assertAlmostEqual(schemas.vo_share(sc), 0.15)

    def test_an_empty_script_is_zero_not_a_crash(self):
        self.assertEqual(schemas.vo_share({}), 0.0)
        self.assertEqual(schemas.vo_share(script()), 0.0)

    def test_junk_estimates_are_skipped_not_counted(self):
        sc = script(sec("S1", "vo", 60), sec("S2", "oncamera", "nonsense"))
        self.assertAlmostEqual(schemas.vo_share(sc), 1.0)


class Bar(unittest.TestCase):
    SC = script(sec("S1", "vo", 60), sec("S2", "oncamera", 40))

    def test_it_passes_at_the_episode_target(self):
        self.assertEqual(schemas.script_notes(self.SC, 0.6), [])

    def test_the_same_script_fails_a_higher_target(self):
        notes = schemas.script_notes(self.SC, 0.9)
        self.assertTrue(any("60% voice-over" in n for n in notes), notes)
        self.assertTrue(any("write more narration" in n for n in notes))

    def test_and_fails_a_lower_one_the_other_way(self):
        notes = schemas.script_notes(self.SC, 0.2)
        self.assertTrue(any("more of the screen" in n for n in notes), notes)

    def test_the_tolerance_is_real(self):
        sc = script(sec("S1", "vo", 65), sec("S2", "oncamera", 35))
        self.assertEqual(schemas.script_notes(sc, 0.6), [])   # 0.65, inside
        sc2 = script(sec("S1", "vo", 75), sec("S2", "oncamera", 25))
        self.assertTrue(schemas.script_notes(sc2, 0.6))       # 0.75, outside

    def test_a_narrated_number_needs_a_source(self):
        sc = script(sec("S1", "vo", 60, text="it weighs 400 tons"),
                    sec("S2", "oncamera", 40))
        self.assertTrue(any("no source" in n for n in schemas.script_notes(sc, 0.6)))

    def test_a_sourced_narrated_number_passes(self):
        sc = script(sec("S1", "vo", 60, text="it weighs 400 tons",
                        source="https://hmns.org/x"),
                    sec("S2", "oncamera", 40))
        self.assertEqual(schemas.script_notes(sc, 0.6), [])

    def test_an_on_camera_number_needs_nothing(self):
        """Caleb saying a number on camera is Caleb's claim, in his own
        voice — the traceability rule is about narration written later."""
        sc = script(sec("S1", "vo", 60), sec("S2", "oncamera", 40,
                                             text="about 400 tons"))
        self.assertEqual(schemas.script_notes(sc, 0.6), [])


if __name__ == "__main__":
    unittest.main()
