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


WORK = Path(__file__).resolve().parent.parent / "work"


class BulkBase(unittest.TestCase):
    """A work dir of our own, and a guard that we stayed in it.

    Patching `editroom.work_path` alone is not enough: `analysis_dir` is
    ingest's and it MKDIRS, so a test that reaches `_state` creates a real
    `work/<slug>/analysis` in the live tree — which then shows up as a
    phantom project on the Studio's board. That happened here (2026-08-26,
    a `work/ep` left behind), and the same guard has been in
    test_footage_state since the first time it did.
    """

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
        # every test in this file patches ingest's work_path too, so
        # `analysis_dir` cannot mkdir into the real shelf
        import pipeline.ingest as ingest_mod
        self._iwp = ingest_mod.work_path
        ingest_mod.work_path = lambda slug: self.tmp
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        import pipeline.ingest as ingest_mod
        editroom.work_path = self._wp
        ingest_mod.work_path = self._iwp
        jobs.start = self._start
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    def plan(self):
        return json.loads((self.tmp / "edit_plan.json").read_text())

    def ids(self):
        return [b["id"] for b in self.plan()["beats"]]

    def trash(self):
        p = self.tmp / "trash.json"
        return json.loads(p.read_text())["entries"] if p.exists() else []


class MoveChapter(BulkBase):
    def test_beat_ids_must_be_a_list_of_strings(self):
        """A bare string was ITERATED PER CHARACTER — "BT02" came back
        "not in the cut: B, T, 0" — and a number was a 500."""
        for bad in ("BT02", 7, {"id": "BT02"}, [1, 2]):
            with self.assertRaises(IngestError):
                editroom._beat_id_list(bad)
        self.assertEqual(editroom._beat_id_list(["BT02", " BT03 ", ""]),
                         ["BT02", "BT03"])
        self.assertEqual(editroom._beat_id_list(None), [])

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

    def test_a_move_keeps_the_verdict_but_DOES_reconcile_the_render(self):
        """This test used to assert `queued == []`, on the premise that
        `chapter_id` only decides where a clip READS.

        It does not — it is an AUDIO field. `sfx.py` groups the ducked
        music beds by chapter and walks a per-chapter clock, so a move
        changes which bed plays under the clip and shifts the music seek
        position for every later beat in both chapters. Without a
        re-assemble the rendered previews hold the old mix while the plan
        describes a new one (review, 2026-08-26).

        The verdict genuinely does stand: what the clip SHOWS is unchanged.
        """
        (self.tmp / "review.json").write_text(json.dumps(
            {"BT01": {"status": "approved"}}))
        out = editroom._beat_move("ep", ["BT01"], "CH2")
        review = json.loads((self.tmp / "review.json").read_text())
        self.assertEqual(review["BT01"]["status"], "approved")
        self.assertEqual(self.queued, ["assemble"])
        self.assertTrue(out["assembling"])

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
        self.assertEqual(entry["count"], 1)
        self.assertEqual(entry["beats"][0]["index"], 1)
        self.assertEqual(entry["beats"][0]["beat"]["take_id"], "T2")



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



class RemovalDefectsFoundInReview(BulkBase):
    """Each of these was a confirmed defect on 2026-08-26, with a
    reproduction. They are pinned so the fixes cannot quietly regress."""

    def _big_plan(self, n=12):
        """A cut long enough to exceed TRASH_CAP in one bulk action."""
        beats = [{"id": "BT01", "purpose": "hook", "chapter_id": "CH1",
                  "take_id": "T1", "trim": {"s": 1.0, "e": 6.0}, "fragment": True}]
        takes = [{"id": "T1", "file": "a.mov", "s": 0.5, "e": 7.0, "duration": 6.5,
                  "transcript": "the room had been sealed for forty years"}]
        for i in range(2, n):
            beats.append({"id": "BT%02d" % i, "purpose": "build",
                          "chapter_id": "CH1", "take_id": "T%d" % i,
                          "trim": {"s": 0.0, "e": 4.0}, "fragment": True})
            takes.append({"id": "T%d" % i, "file": "f%d.mov" % i, "s": 0.0,
                          "e": 4.5, "duration": 4.5,
                          "transcript": "a line about the inventory number %d" % i})
        beats.append({"id": "BT%02d" % n, "purpose": "payoff",
                      "chapter_id": "CH2", "take_id": "T%d" % n,
                      "trim": {"s": 0.0, "e": 5.0}, "fragment": True})
        takes.append({"id": "T%d" % n, "file": "z.mov", "s": 0.0, "e": 5.5,
                      "duration": 5.5, "transcript": "and then somebody opened it"})
        plan = _plan()
        plan["beats"] = beats
        (self.tmp / "edit_plan.json").write_text(json.dumps(plan))
        (self.tmp / "analysis" / "takes.json").write_text(
            json.dumps({"takes": takes, "groups": []}))

    def test_removing_more_clips_than_the_trash_cap_keeps_every_undo(self):
        """
        TRASH_CAP is 7 and `_beat_remove` used to add one entry per clip,
        so removing 8 pushed the earliest ones out of their own undo — and
        evicted every unrelated b-roll and card entry with them.
        """
        self._big_plan(12)
        ids = ["BT%02d" % i for i in range(2, 11)]     # nine clips
        editroom._beat_remove("ep", ids)
        beat_entries = [e for e in self.trash() if e["kind"] == "beat"]
        self.assertEqual(len(beat_entries), 1, "one batch, one entry")
        self.assertEqual(
            [r["beat"]["id"] for r in beat_entries[0]["beats"]], ids,
            "every removed clip is still undoable",
        )

    def test_a_bulk_removal_does_not_evict_unrelated_trash(self):
        self._big_plan(12)
        editroom._trash_add("ep", "broll", {"beat_id": "BT01", "clip_id": "B001",
                                            "at": 0, "duration": 2, "src_s": 0})
        editroom._beat_remove("ep", ["BT%02d" % i for i in range(2, 11)])
        kinds = [e["kind"] for e in self.trash()]
        self.assertIn("broll", kinds, "the cover's undo survived the batch")

    def test_restoring_a_batch_puts_every_clip_back_IN_ORDER(self):
        """
        Restoring one at a time is only correct ascending, and a trash list
        rendered newest-first hands them back descending: remove BT02 and
        BT03, restore BT03 then BT02, and the cut came back
        [BT01, BT02, BT04, BT03] — the payoff before a build beat.
        """
        editroom._beat_remove("ep", ["BT02", "BT03"])
        self.assertEqual(self.ids(), ["BT01", "BT04"])
        uid = [e for e in self.trash() if e["kind"] == "beat"][-1]["uid"]
        editroom._trash_restore("ep", uid)
        self.assertEqual(self.ids(), ["BT01", "BT02", "BT03", "BT04"])

    def test_the_undo_is_written_BEFORE_the_plan_is_committed(self):
        """
        Gate F11's rule, which `_broll_remove` already carries: a failure
        after the plan is written commits the removal while losing its
        undo. `_trash_add` reads trash.json unguarded, so a half-written
        one raised mid-removal and left the beats gone with no way back.
        """
        (self.tmp / "trash.json").write_text("{truncated")
        with self.assertRaises(Exception):
            editroom._beat_remove("ep", ["BT02"])
        self.assertEqual(self.ids(), ["BT01", "BT02", "BT03", "BT04"],
                         "the plan was NOT committed when the undo failed")

    def test_a_removed_clip_takes_its_verdict_with_it(self):
        """
        `_state` counts `approved` over every review entry but `total` over
        the timeline's beats, so an orphaned verdict made the header read
        "4 of 3 approved" — and `_normalize_review` re-processed the
        stranded entry forever.
        """
        (self.tmp / "review.json").write_text(json.dumps({
            "BT01": {"status": "approved"},
            "BT02": {"status": "approved"},
        }))
        editroom._beat_remove("ep", ["BT02"])
        review = json.loads((self.tmp / "review.json").read_text())
        self.assertNotIn("BT02", review)
        self.assertIn("BT01", review, "the surviving clip keeps its verdict")

    def test_a_negative_stored_index_cannot_insert_from_the_right(self):
        """`min(idx, len)` had no lower clamp, so a hand-edited or
        corrupt index counted from the END of the list.

        Clamped to 0 it lands at the head, which puts a build beat before
        the hook — and the validator refuses that, leaving the plan
        untouched. Both halves matter: the clamp stops the silent
        mis-insert, and the validator stops the bad cut.
        """
        editroom._beat_remove("ep", ["BT02"])
        before = self.ids()
        path = self.tmp / "trash.json"
        data = json.loads(path.read_text())
        data["entries"][-1]["beats"][0]["index"] = -5
        path.write_text(json.dumps(data))
        with self.assertRaises(IngestError):
            editroom._trash_restore("ep", data["entries"][-1]["uid"])
        self.assertEqual(self.ids(), before, "the plan is untouched")

    def test_a_legacy_single_beat_trash_entry_still_restores(self):
        """A trash file is exactly the artifact that outlives a format
        change. Nothing on disk carries the old one-beat-per-entry shape,
        but restoring must not depend on that being true."""
        editroom._beat_remove("ep", ["BT02"])
        path = self.tmp / "trash.json"
        data = json.loads(path.read_text())
        e = data["entries"][-1]
        legacy = {"kind": "beat", "ts": e["ts"], "uid": "legacy-1",
                  "beat_id": "BT02", "index": e["beats"][0]["index"],
                  "payload": e["beats"][0]["beat"]}
        data["entries"] = [legacy]
        path.write_text(json.dumps(data))
        editroom._trash_restore("ep", "legacy-1")
        self.assertEqual(self.ids(), ["BT01", "BT02", "BT03", "BT04"])


class GhostVerdicts(BulkBase):
    """review.json outlives the cut, and `_state` read the two halves from
    different populations.

    Live on hmns when this was found: 96 review entries against 82 timeline
    beats. All fourteen ghosts happened to be `reworked`, so the number
    agreed — and would have stopped agreeing the first time one of them was
    an approve.
    """

    def _timeline(self, ids):
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps({
            "fps": 24, "duration": 40.0,
            "beats": [{"id": i, "record_s": n * 10.0, "record_e": n * 10.0 + 9.0}
                      for n, i in enumerate(ids)],
        }))

    def test_approved_can_never_exceed_total(self):
        self._timeline(["BT01", "BT02", "BT03"])
        (self.tmp / "review.json").write_text(json.dumps({
            "BT01": {"status": "approved"},
            "BT02": {"status": "approved"},
            "BT03": {"status": "approved"},
            "BT99": {"status": "approved"},      # a ghost from an old cut
        }))
        counts = editroom._state("ep")["counts"]
        self.assertEqual(counts["total"], 3)
        self.assertEqual(counts["approved"], 3, "the ghost was counted")

    def test_a_ghost_cannot_hold_the_queue_open_either(self):
        self._timeline(["BT01"])
        (self.tmp / "review.json").write_text(json.dumps({
            "BT01": {"status": "approved"},
            "BT99": {"status": "flagged"},
        }))
        counts = editroom._state("ep")["counts"]
        self.assertEqual(counts["flagged"], 0)

if __name__ == "__main__":
    unittest.main()
