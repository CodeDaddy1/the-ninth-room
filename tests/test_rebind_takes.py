# -*- coding: utf-8 -*-
"""A beat that names the wrong take, corrected by what it SAYS.

hmns carries nine of these: the label drifted during hand surgery while
the trim stayed right, so every one of those beats is named after a shot
it does not show. Nothing is wrong on screen — the assembler reads the
trim — but `validate_edit_plan` refuses the plan and `plan_beats`
refuses to assemble on a validation error, so the episode was frozen by
nine wrong strings.

The rule under test is that the WORDS decide. A take that says the
beat's caption is the take the beat shows; a numeric fit alone is not
enough, because the same seconds exist on every file.

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

from pipeline import (beat_identity as bi, ingest, migrate_ids as mi,  # noqa
                      plan_history as ph, rebind_takes as rb)

TAKES = {"takes": [
    {"id": "T1", "file": "a.mp4", "s": 0.0, "e": 10.0,
     "transcript": "The hook line about the butterfly."},
    {"id": "T2", "file": "b.mp4", "s": 0.0, "e": 10.0,
     "transcript": "One sentence that goes here."},
    {"id": "T3", "file": "b.mp4", "s": 30.0, "e": 50.0,
     "transcript": "Not on my watch, but I am blown away by today."},
]}


def _plan(take_id="T2", trim=(31.0, 49.0)):
    """BT02 carries T3's window while naming `take_id`."""
    return {"slug": "ep", "format": "youtube_long", "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "beats": [
                {"id": "BT01", "purpose": "hook", "take_id": "T1",
                 "trim": {"s": 0.0, "e": 10.0}, "transition_in": "cut"},
                {"id": "BT02", "purpose": "payoff", "take_id": take_id,
                 "trim": {"s": trim[0], "e": trim[1]},
                 "transition_in": "cut"}]}


class ARebind(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        for mod in (rb, mi, ph):
            mod.work_path = ingest.work_path
        self.write("edit_plan.json", _plan())
        self.write("analysis/takes.json", TAKES)
        self.write("analysis/broll.json", {"clips": []})
        self.write("captions.json", {"slug": "ep", "beats": [
            {"beat_id": "BT02",
             "text": "Not on my watch, but I am blown away by today."}]})
        self.write("review.json", {
            "BT01": {"status": "approved", "note": "the hook lands"},
            "BT02": {"status": "approved", "note": "keep the ending"}})
        self.write("graphics_plan.json", {"cards": [
            {"id": "CARD01", "beat_id": "BT02", "at": 1.0, "duration": 3.0}]})

    def tearDown(self):
        ingest.work_path = self._wp
        for mod in (rb, mi, ph):
            mod.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, doc):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=2))

    def read(self, rel):
        return json.loads((self.tmp / rel).read_text())

    # ---- the survey ----------------------------------------------------

    def test_the_take_that_says_the_caption_is_proposed(self):
        s = rb.survey("ep")
        self.assertEqual([(p["beat_id"], p["was"], p["to"])
                          for p in s["proposals"]], [("BT02", "T2", "T3")])
        self.assertEqual(s["ambiguous"], [])

    def test_a_beat_that_names_its_own_take_is_left_alone(self):
        self.write("edit_plan.json", _plan(take_id="T3", trim=(31.0, 49.0)))
        self.assertEqual(rb.survey("ep")["proposals"], [])

    def test_a_held_tail_is_not_a_rebind(self):
        """Silence past the last word is legal now (schemas.take_window),
        so it must not be read as a mis-binding and re-pointed."""
        self.write("edit_plan.json", _plan(take_id="T1", trim=(0.0, 12.0)))
        self.assertEqual(rb.survey("ep")["proposals"], [])

    def test_a_beat_with_no_caption_is_reported_not_guessed(self):
        self.write("captions.json", {"slug": "ep", "beats": []})
        s = rb.survey("ep")
        self.assertEqual(s["proposals"], [])
        self.assertEqual(s["ambiguous"][0]["why"], "no caption to match against")

    def test_a_caption_that_no_candidate_says_is_reported(self):
        self.write("captions.json", {"slug": "ep", "beats": [
            {"beat_id": "BT02", "text": "words nobody anywhere ever spoke"}]})
        s = rb.survey("ep")
        self.assertEqual(s["proposals"], [])
        self.assertIn("only", s["ambiguous"][0]["why"])

    def test_two_takes_that_say_the_same_thing_are_too_close_to_call(self):
        t = json.loads(json.dumps(TAKES))
        t["takes"].append({"id": "T4", "file": "b.mp4", "s": 31.0, "e": 49.0,
                           "transcript": TAKES["takes"][2]["transcript"]})
        self.write("analysis/takes.json", t)
        s = rb.survey("ep")
        self.assertEqual(s["proposals"], [])
        self.assertIn("too close to call", s["ambiguous"][0]["why"])

    def test_the_survey_writes_nothing(self):
        before = {p.name: p.read_bytes() for p in self.tmp.rglob("*")
                  if p.is_file()}
        rb.survey("ep")
        rb.survey("ep")
        self.assertEqual({p.name: p.read_bytes() for p in self.tmp.rglob("*")
                          if p.is_file()}, before)

    # ---- the apply -----------------------------------------------------

    def test_the_label_is_corrected_and_the_cut_is_not(self):
        rb.apply("ep", log=lambda *a: None)
        b = self.read("edit_plan.json")["beats"][1]
        self.assertEqual(b["take_id"], "T3")
        self.assertEqual(b["trim"], {"s": 31.0, "e": 49.0})   # untouched

    def test_the_beat_is_renamed_after_the_shot_it_now_names(self):
        rb.apply("ep", log=lambda *a: None)
        ids = [b["id"] for b in self.read("edit_plan.json")["beats"]]
        self.assertEqual(ids, ["shot-T1", "shot-T3"])
        self.assertEqual(bi.id_errors(self.read("edit_plan.json")), [])

    def test_the_verdict_carries_with_its_status(self):
        """The trim does not move, so the cut Caleb approved is the same
        cut. A requeue here would throw away a real approval."""
        rb.apply("ep", log=lambda *a: None)
        self.assertEqual(self.read("review.json")["shot-T3"],
                         {"status": "approved", "note": "keep the ending"})

    def test_the_keyed_artifacts_follow_the_rename(self):
        rb.apply("ep", log=lambda *a: None)
        self.assertEqual(self.read("graphics_plan.json")["cards"][0]["beat_id"],
                         "shot-T3")

    def test_the_previous_cut_is_archived_and_backed_up(self):
        rb.apply("ep", log=lambda *a: None)
        self.assertEqual(ph.versions("ep")[0]["reason"], "manual")
        b = self.tmp / mi.BACKUP_DIRNAME / "edit_plan.json"
        self.assertEqual(json.loads(b.read_text())["beats"][1]["take_id"], "T2")

    def test_the_map_records_the_rename(self):
        rb.apply("ep", log=lambda *a: None)
        doc = self.read(mi.MAP_FILE)
        self.assertEqual(mi.resolve_id(doc, "BT02"), "shot-T3")

    def test_a_plan_with_nothing_to_fix_is_refused_by_name(self):
        self.write("edit_plan.json", _plan(take_id="T3"))
        with self.assertRaises(rb.RebindError):
            rb.apply("ep", log=lambda *a: None)

    def test_the_mapping_is_positional_not_by_anchor(self):
        """`beat_identity.id_map` pairs beats by (anchor, occurrence) —
        the one assumption a rebind breaks, since the anchor is the thing
        being corrected. Two beats swapping anchors must not swap
        histories."""
        plan = _plan()
        plan["beats"][1]["id"] = "shot-T2"
        new, renamed, every = rb._renamed_plan(plan, [{"index": 1, "to": "T3"}])
        self.assertEqual(renamed, {"BT01": "shot-T1", "shot-T2": "shot-T3"})
        self.assertEqual(every, renamed)

    def test_a_beat_that_does_not_move_is_still_in_the_carry_map(self):
        """`carry_review` archives any verdict whose id is absent from
        the mapping. Handing it only the renames archived 72 of hmns's
        82 verdicts in the sandbox run."""
        plan = _plan()
        plan["beats"][0]["id"] = "shot-T1"           # already correct
        new, renamed, every = rb._renamed_plan(plan, [{"index": 1, "to": "T3"}])
        self.assertNotIn("shot-T1", renamed)
        self.assertEqual(every["shot-T1"], "shot-T1")


if __name__ == "__main__":
    unittest.main()
