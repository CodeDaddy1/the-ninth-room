# -*- coding: utf-8 -*-
"""Deleting footage must not silently invalidate the cut.

2026-08-25. Caleb deleted four end-of-day garage clips from the Footage
desk. One of them was B184, the cover on BT93 — "illustrate: Sofia
running ahead to the car in the garage". `_delete_footage` checked only
that the file existed, so it succeeded, and the break surfaced hours
later as `beats[92].broll[2]: unknown b-roll clip 'B184'`. The files
were never at risk (deletes move to footage/.trash); the damage was the
silence.

Two ways a file is load-bearing, and only the first has ever bitten:
it may be a b-roll CLIP a beat covers with, or it may hold the SPEECH
TAKE a beat is built on. The second refuses even under force — losing a
beat's take is a re-cut decision, not a cleanup.

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
from pipeline import ingest  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class DeleteGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        (self.tmp / "analysis").mkdir(parents=True)
        for n in ("cover.mp4", "spoken.mp4", "spare.mp4"):
            (self.tmp / "footage" / n).write_bytes(b"x" * 32)
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(
            {"slug": "ep", "clips": [
                {"id": "B001", "file": "cover.mp4", "duration": 6.0},
                {"id": "B002", "file": "spare.mp4", "duration": 6.0}]}))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps(
            {"takes": [{"id": "T01", "file": "spoken.mp4"}]}))
        (self.tmp / "edit_plan.json").write_text(json.dumps(
            {"slug": "ep", "beats": [
                {"id": "BT01", "purpose": "hook", "take_id": "T01",
                 "broll": [{"clip_id": "B001", "at": 2.0, "duration": 3.0,
                            "src_s": 0.0, "why": "illustrate: the car"}]}]}))
        (self.tmp / "analysis" / "catalog.json").write_text('{"files":[]}')
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        self.detached = []
        self._detach = editroom._broll_detach
        editroom._broll_detach = lambda slug, b, c, at, **kw: self.detached.append((b, c, at))

    def tearDown(self):
        editroom.work_path = self._wp
        editroom._broll_detach = self._detach
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _exists(self, n):
        return (self.tmp / "footage" / n).is_file()

    # ---- what is in use ----

    def test_it_finds_the_cover_a_beat_uses(self):
        uses = editroom._footage_uses("ep", "cover.mp4")
        self.assertEqual(len(uses["covers"]), 1)
        self.assertEqual(uses["covers"][0]["beat_id"], "BT01")
        self.assertEqual(uses["covers"][0]["at"], 2.0)

    def test_it_finds_the_take_a_beat_is_built_on(self):
        uses = editroom._footage_uses("ep", "spoken.mp4")
        self.assertEqual([b["beat_id"] for b in uses["beats"]], ["BT01"])

    def test_an_unused_clip_is_used_by_nothing(self):
        uses = editroom._footage_uses("ep", "spare.mp4")
        self.assertEqual(uses, {"covers": [], "beats": []})

    # ---- the guard ----

    def test_an_unused_clip_still_deletes(self):
        out = editroom._delete_footage("ep", "spare.mp4", log=lambda *a: None)
        self.assertEqual(out["removed"], ["spare.mp4"])
        self.assertFalse(self._exists("spare.mp4"))

    def test_a_clip_in_the_cut_is_REFUSED_and_says_where(self):
        with self.assertRaises(IngestError) as e:
            editroom._delete_footage("ep", "cover.mp4", log=lambda *a: None)
        msg = str(e.exception)
        self.assertIn("B001", msg)
        self.assertIn("BT01", msg)
        self.assertTrue(self._exists("cover.mp4"), "refused but deleted anyway")

    def test_forcing_deletes_AND_removes_the_cover(self):
        out = editroom._delete_footage("ep", "cover.mp4", force=True,
                                       log=lambda *a: None)
        self.assertFalse(self._exists("cover.mp4"))
        self.assertEqual(self.detached, [("BT01", "B001", 2.0)])
        self.assertEqual(out["detached"][0]["beat_id"], "BT01")

    def test_the_cover_is_detached_at_its_REAL_position(self):
        """detach matches on position as well as clip id — passing 0.0
        would miss every cover that is not at the very start."""
        editroom._delete_footage("ep", "cover.mp4", force=True,
                                 log=lambda *a: None)
        self.assertEqual(self.detached[0][2], 2.0)

    def test_a_beats_take_refuses_even_under_force(self):
        with self.assertRaises(IngestError) as e:
            editroom._delete_footage("ep", "spoken.mp4", force=True,
                                     log=lambda *a: None)
        self.assertIn("re-cut", str(e.exception))
        self.assertTrue(self._exists("spoken.mp4"))

    def test_a_missing_file_is_still_a_plain_error(self):
        with self.assertRaises(IngestError):
            editroom._delete_footage("ep", "nope.mp4", log=lambda *a: None)


if __name__ == "__main__":
    unittest.main()


class ClearGuard(unittest.TestCase):
    """`Remove all` must obey the same law as removing one clip.

    2026-08-27. `_clear_footage` walked the footage directory and moved
    everything to .trash without ever calling `_footage_uses`. So the
    blunt verb could do precisely what the precise one refuses even under
    force — bin the take a beat is built on — and 368 files had less
    protection than one.

    Force is allowed to take the cut with it, because "remove all" means
    start over. It cannot do that a beat at a time (`_beat_remove`
    refuses the last beat), so the whole plan moves to .trash instead,
    BEFORE any media does.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        (self.tmp / "analysis").mkdir(parents=True)
        for n in ("cover.mp4", "spoken.mp4", "spare.mp4"):
            (self.tmp / "footage" / n).write_bytes(b"x" * 32)
        (self.tmp / "analysis" / "broll.json").write_text(json.dumps(
            {"slug": "ep", "clips": [
                {"id": "B001", "file": "cover.mp4", "duration": 6.0}]}))
        (self.tmp / "analysis" / "takes.json").write_text(json.dumps(
            {"takes": [{"id": "T01", "file": "spoken.mp4"}]}))
        (self.tmp / "analysis" / "catalog.json").write_text('{"files":[]}')
        self.plan = self.tmp / "edit_plan.json"
        self.plan.write_text(json.dumps(
            {"slug": "ep", "beats": [
                {"id": "BT01", "purpose": "hook", "take_id": "T01",
                 "broll": [{"clip_id": "B001", "at": 2.0, "duration": 3.0,
                            "src_s": 0.0, "why": "illustrate: the car"}]}]}))
        # BOTH modules: facts.work_path resolves through ingest, so
        # patching only editroom writes into the live work/ (the lesson
        # tests/test_footage_linking.py records in its setUp).
        self._wp, self._iwp = editroom.work_path, ingest.work_path
        editroom.work_path = lambda slug: self.tmp
        ingest.work_path = lambda slug: self.tmp
        self.detached = []
        self._detach = editroom._broll_detach
        editroom._broll_detach = \
            lambda slug, b, c, at, **kw: self.detached.append((b, c, at))

    def tearDown(self):
        editroom.work_path = self._wp
        ingest.work_path = self._iwp
        editroom._broll_detach = self._detach
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _shelf(self):
        return sorted(p.name for p in (self.tmp / "footage").iterdir()
                      if p.is_file())

    # ---- the single-clip refusals earn the same codes ----

    def test_deleting_a_clip_in_the_cut_carries_in_the_cut(self):
        with self.assertRaises(IngestError) as cm:
            editroom._delete_footage("ep", "cover.mp4")
        self.assertEqual(getattr(cm.exception, "code", None), "in_the_cut")

    def test_deleting_a_beats_take_carries_take_in_cut(self):
        with self.assertRaises(IngestError) as cm:
            editroom._delete_footage("ep", "spoken.mp4", force=True)
        self.assertEqual(getattr(cm.exception, "code", None), "take_in_cut")

    # ---- the refusal ----

    def test_it_refuses_when_the_cut_is_using_the_footage(self):
        with self.assertRaises(IngestError) as cm:
            editroom._clear_footage("ep")
        self.assertEqual(getattr(cm.exception, "code", None), "in_the_cut")

    def test_the_refusal_names_the_beat_and_counts_the_covers(self):
        with self.assertRaises(IngestError) as cm:
            editroom._clear_footage("ep")
        msg = str(cm.exception)
        self.assertIn("BT01", msg)
        self.assertIn("1 cover", msg)

    def test_a_refused_clear_moves_nothing(self):
        with self.assertRaises(IngestError):
            editroom._clear_footage("ep")
        self.assertEqual(self._shelf(),
                         ["cover.mp4", "spare.mp4", "spoken.mp4"])
        self.assertTrue(self.plan.exists())
        self.assertEqual(self.detached, [])

    # ---- with no cut, it is the plain verb it always was ----

    def test_it_clears_when_no_cut_uses_the_footage(self):
        self.plan.unlink()
        r = editroom._clear_footage("ep")
        self.assertEqual(r["removed"], 3)
        self.assertFalse(r["cut_cleared"])
        self.assertEqual(self._shelf(), [])

    # ---- force ----

    def test_force_detaches_every_cover_before_clearing(self):
        editroom._clear_footage("ep", force=True)
        self.assertEqual(self.detached, [("BT01", "B001", 2.0)])

    def test_force_moves_the_whole_plan_aside(self):
        r = editroom._clear_footage("ep", force=True)
        self.assertTrue(r["cut_cleared"])
        self.assertFalse(self.plan.exists())
        self.assertTrue(
            (self.tmp / "footage" / ".trash" / "edit_plan.json").is_file())

    def test_force_empties_the_shelf(self):
        r = editroom._clear_footage("ep", force=True)
        self.assertEqual(r["removed"], 3)
        self.assertEqual(self._shelf(), [])

    def test_the_plan_goes_before_the_media(self):
        """An interrupted clear must never leave a cut pointing at .trash.

        Simulated by failing the media move: the plan must already be gone.
        """
        real = os.replace
        state = {"plan_moved": False}

        def flaky(src, dst):
            if str(src).endswith("edit_plan.json"):
                state["plan_moved"] = True
                return real(src, dst)
            raise OSError("disk went away mid-clear")

        editroom.os.replace = flaky
        try:
            with self.assertRaises(OSError):
                editroom._clear_footage("ep", force=True)
        finally:
            editroom.os.replace = real
        self.assertTrue(state["plan_moved"])
        self.assertFalse(self.plan.exists())


class RefusalCodes(unittest.TestCase):
    """A refusal a desk can act on carries a STABLE code, not just prose.

    Both request handlers built `{"error": str(e)}` and dropped `e.code`
    on the floor, so a code only ever reached the Studio through the job
    record. Every synchronous refusal arrived as a message, which forced
    the Footage desk to match on `msg.includes('is in the cut')` — the
    one thing job-failure.ts forbids outright (2026-08-27).
    """

    def test_the_cover_refusal_carries_its_code(self):
        e = IngestError("x is in the cut: B001 covers BT01.", code="in_the_cut")
        self.assertEqual(editroom._err_body(e),
                         {"error": "x is in the cut: B001 covers BT01.",
                          "error_code": "in_the_cut"})

    def test_a_refusal_with_no_code_sends_prose_alone(self):
        body = editroom._err_body(IngestError("no clip named 'gone.mp4'"))
        self.assertEqual(body, {"error": "no clip named 'gone.mp4'"})
        self.assertNotIn("error_code", body)
