# -*- coding: utf-8 -*-
"""Bulk verbs three and four: move a clip's chapter, take a clip out.

2026-08-26, artboard 25. The Review desk's bulk bar was drawn with FOUR
verbs and shipped with two, because the other two had no engine route:
`chapter_id` was a real, validated field on a beat that nothing could set,
and nothing anywhere could remove a beat from the cut.

What is pinned here:

- both verbs write only through the validated plan path, and a refused
  validation leaves the file exactly as it was;
- a move changes where a clip READS, not what it shows — so it does not
  reset the verdict and does not re-assemble;
- a removal DOES both, and lands in the same trash every dropped cover
  goes to, carrying its index so a restore cannot silently re-order the
  episode;
- the cut can never be emptied.

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
from pipeline.ingest import IngestError  # noqa: E402


def _plan():
    return {
        "slug": "ep", "format": "youtube_long",
        "theme": {"problem": "p", "promise": "pr", "payoff": "pay"},
        "chapters": [{"id": "CH1", "title": "The sealed room"},
                     {"id": "CH2", "title": "Who found it"}],
        "beats": [
            {"id": "BT01", "purpose": "hook", "chapter_id": "CH1",
             "take_id": "T1", "trim": {"s": 1.0, "e": 6.0}, "fragment": True},
            {"id": "BT02", "purpose": "build", "chapter_id": "CH1",
             "take_id": "T2", "trim": {"s": 8.0, "e": 12.0}, "fragment": True},
            {"id": "BT03", "purpose": "build", "chapter_id": "CH2",
             "take_id": "T3", "trim": {"s": 0.0, "e": 6.0}, "fragment": True},
            {"id": "BT04", "purpose": "payoff", "chapter_id": "CH2",
             "take_id": "T4", "trim": {"s": 0.0, "e": 5.0}, "fragment": True},
        ],
    }


def _takes():
    return {"takes": [
        {"id": "T1", "file": "a.mov", "s": 0.5, "e": 7.0, "duration": 6.5,
         "transcript": "the room had been sealed for forty years"},
        {"id": "T2", "file": "a.mov", "s": 8.0, "e": 12.5, "duration": 4.5,
         "transcript": "the caretaker had the key the whole time"},
        {"id": "T3", "file": "b.mov", "s": 0.0, "e": 6.0, "duration": 6.0,
         "transcript": "there is an inventory and it gets strange"},
        {"id": "T4", "file": "c.mov", "s": 0.0, "e": 5.5, "duration": 5.5,
         "transcript": "nobody had a reason to open it and then somebody did"},
    ], "groups": []}


class BulkBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir()
        (self.tmp / "edit_plan.json").write_text(json.dumps(_plan()))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps(_takes()))
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(
            {"clips": [{"id": "B001", "file": "b1.mov", "duration": 8.0}]}))
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        self._start = jobs.start
        self.queued = []
        jobs.start = lambda kind, slug: self.queued.append(kind)

    def tearDown(self):
        editroom.work_path = self._wp
        jobs.start = self._start
        shutil.rmtree(self.tmp, ignore_errors=True)

    def plan(self):
        return json.loads((self.tmp / "edit_plan.json").read_text())

    def ids(self):
        return [b["id"] for b in self.plan()["beats"]]

    def trash(self):
        p = self.tmp / "trash.json"
        return json.loads(p.read_text())["entries"] if p.exists() else []


class MoveChapter(BulkBase):
    def test_moves_many_clips_at_once(self):
        out = editroom._beat_move("ep", ["BT01", "BT02"], "CH2")
        self.assertEqual(out["moved"], ["BT01", "BT02"])
        chapters = {b["id"]: b.get("chapter_id") for b in self.plan()["beats"]}
        self.assertEqual(chapters, {"BT01": "CH2", "BT02": "CH2",
                                    "BT03": "CH2", "BT04": "CH2"})

    def test_a_move_does_not_re_order_the_cut(self):
        """A beat carries its chapter as a property, not a position — the
        bulk bar's job is to re-file clips, not to re-cut the episode."""
        editroom._beat_move("ep", ["BT01"], "CH2")
        self.assertEqual(self.ids(), ["BT01", "BT02", "BT03", "BT04"])

    def test_a_move_neither_resets_the_verdict_nor_reassembles(self):
        (self.tmp / "review.json").write_text(json.dumps(
            {"BT01": {"status": "approved"}}))
        editroom._beat_move("ep", ["BT01"], "CH2")
        review = json.loads((self.tmp / "review.json").read_text())
        self.assertEqual(review["BT01"]["status"], "approved")
        self.assertEqual(self.queued, [])

    def test_an_unknown_chapter_is_refused_and_nothing_moves(self):
        with self.assertRaises(IngestError):
            editroom._beat_move("ep", ["BT01"], "CH9")
        self.assertEqual(self.plan()["beats"][0]["chapter_id"], "CH1")

    def test_an_unknown_clip_is_refused_and_its_siblings_do_not_move(self):
        """One bad id in a bulk selection must not half-apply the batch."""
        with self.assertRaises(IngestError):
            editroom._beat_move("ep", ["BT01", "BT99"], "CH2")
        self.assertEqual(self.plan()["beats"][0]["chapter_id"], "CH1")

    def test_an_empty_selection_is_refused(self):
        with self.assertRaises(IngestError):
            editroom._beat_move("ep", [], "CH2")


class RemoveClips(BulkBase):
    def test_removes_and_reassembles(self):
        out = editroom._beat_remove("ep", ["BT02"])
        self.assertEqual(out["removed"], ["BT02"])
        self.assertEqual(self.ids(), ["BT01", "BT03", "BT04"])
        self.assertEqual(out["remaining"], 3)
        self.assertEqual(self.queued, ["assemble"])

    def test_the_removal_lands_in_the_trash_with_its_index(self):
        editroom._beat_remove("ep", ["BT02"])
        entry = self.trash()[-1]
        self.assertEqual(entry["kind"], "beat")
        self.assertEqual(entry["beat_id"], "BT02")
        self.assertEqual(entry["index"], 1)
        self.assertEqual(entry["payload"]["take_id"], "T2")

    def test_a_restore_puts_the_clip_back_where_it_was(self):
        """Appending would re-order the episode silently, which is a
        different edit from the one being undone."""
        editroom._beat_remove("ep", ["BT02"])
        self.assertEqual(self.ids(), ["BT01", "BT03", "BT04"])
        uid = self.trash()[-1]["uid"]
        editroom._trash_restore("ep", uid)
        self.assertEqual(self.ids(), ["BT01", "BT02", "BT03", "BT04"])

    def test_restoring_a_clip_that_came_back_is_refused(self):
        editroom._beat_remove("ep", ["BT02"])
        uid = self.trash()[-1]["uid"]
        editroom._trash_restore("ep", uid)
        with self.assertRaises(IngestError):
            editroom._trash_restore("ep", uid)

    def test_removing_the_only_payoff_is_refused_in_words(self):
        with self.assertRaises(IngestError) as cm:
            editroom._beat_remove("ep", ["BT04"])
        self.assertIn("payoff", str(cm.exception))
        self.assertNotIn("plan:", str(cm.exception))
        self.assertEqual(len(self.ids()), 4)

    def test_removing_the_hook_is_refused_in_words_not_schema(self):
        """The validator already refuses it ("plan: first beat must be the
        hook") — but that string reaches someone who ticked four rows and
        pressed Remove. Say the actual thing."""
        with self.assertRaises(IngestError) as cm:
            editroom._beat_remove("ep", ["BT01"])
        self.assertIn("hook", str(cm.exception))
        self.assertNotIn("plan:", str(cm.exception))
        self.assertEqual(len(self.ids()), 4)

    def test_the_cut_can_never_be_emptied(self):
        with self.assertRaises(IngestError) as cm:
            editroom._beat_remove("ep", ["BT01", "BT02", "BT03", "BT04"])
        self.assertIn("at least one", str(cm.exception))
        self.assertEqual(len(self.ids()), 4)

    def test_an_unknown_clip_refuses_the_whole_batch(self):
        with self.assertRaises(IngestError):
            editroom._beat_remove("ep", ["BT02", "BT99"])
        self.assertEqual(len(self.ids()), 4)

    def test_a_repeated_id_removes_one_clip_not_two(self):
        """⇧-click ranges overlap; the bar must not double-count."""
        out = editroom._beat_remove("ep", ["BT02", "BT02"])
        self.assertEqual(out["remaining"], 3)
        self.assertEqual(self.ids(), ["BT01", "BT03", "BT04"])

    def test_an_empty_selection_is_refused(self):
        with self.assertRaises(IngestError):
            editroom._beat_remove("ep", [])

    def test_removing_several_restores_each_to_its_own_index(self):
        editroom._beat_remove("ep", ["BT02", "BT03"])
        self.assertEqual(self.ids(), ["BT01", "BT04"])
        for e in [e for e in self.trash() if e["kind"] == "beat"]:
            editroom._trash_restore("ep", e["uid"])
        self.assertEqual(self.ids(), ["BT01", "BT02", "BT03", "BT04"])


if __name__ == "__main__":
    unittest.main()
