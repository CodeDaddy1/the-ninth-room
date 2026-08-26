# -*- coding: utf-8 -*-
"""The ship checklist has to answer the question being asked.

2026-08-25. Four of eight rows on the live episode answered a different
one:

  * "Cards exported and current — all current" over an episode with ZERO
    cards. Nothing stale was found in an empty set.
  * "Captions baked — all baked" with no captions.json at all, so the
    loop that finds unbaked beats never ran.
  * "Review queue empty — 2 beats open" while 88 of 93 clips had never
    been opened. It counted only clips SENT BACK; `n_reviewed` was
    computed two lines above and unused. The Review desk one click away
    said "90 clips need you".
  * "22 edits queued" while Review's own button said 12 — the engine
    collapses the conform ledger before executing, and this row counted
    the raw list.

A ship checklist is read by counting green ticks. Two of those ticks
meant "we did not look", and one number was reassuring and wrong.

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

from pipeline import conform as conform_mod, deliver, editroom, ingest  # noqa: E402

WORK = Path(__file__).resolve().parent.parent / "work"


class Checklist(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work = self.tmp / "ep"
        (self.work / "footage").mkdir(parents=True)
        (self.work / "analysis").mkdir()
        self._patched = []
        for mod in (deliver, editroom, ingest):
            self._patched.append((mod, mod.work_path))
            mod.work_path = lambda slug, w=self.work: w
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        for mod, fn in self._patched:
            mod.work_path = fn
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")

    def _plan(self, beat_ids):
        (self.work / "edit_plan.json").write_text(json.dumps(
            {"slug": "ep", "beats": [{"id": b} for b in beat_ids]}))
        # the checklist short-circuits to a single "not assembled yet" row
        # without this — every row below it needs a timeline to check
        (self.work / "analysis" / "timeline_map.json").write_text(json.dumps(
            {"slug": "ep", "beats": []}))
        # proxy._load reads these unconditionally further down the checklist
        (self.work / "analysis" / "catalog.json").write_text(
            json.dumps({"slug": "ep", "files": [], "skipped": []}))
        (self.work / "analysis" / "takes.json").write_text(
            json.dumps({"slug": "ep", "takes": [], "groups": []}))

    def _review(self, statuses):
        (self.work / "review.json").write_text(json.dumps(
            {k: {"status": v} for k, v in statuses.items()}))

    def _row(self, rid):
        rows = deliver.checklist("ep")["rows"]
        for r in rows:
            if r["id"] == rid:
                return r
        self.fail("no %s row in %s" % (rid, [r["id"] for r in rows]))

    # ---- nothing to check is not the same as checked and fine ----

    def test_no_cards_is_NOT_a_tick(self):
        self._plan(["BT01"])
        self.assertEqual(self._row("cards")["state"], "none")
        self.assertIn("no cards", self._row("cards")["detail"])

    def test_a_card_that_EXISTS_is_never_reported_as_nothing_to_check(self):
        """The distinction this row could not make. A card with no export
        is `todo`, not `none` — and either way it is not the same answer
        as an episode that has no cards at all."""
        self._plan(["BT01"])
        (self.work / "graphics_plan.json").write_text(json.dumps(
            {"cards": [{"id": "CARD01", "beat_id": "BT01"}]}))
        row = self._row("cards")
        self.assertNotEqual(row["state"], "none")
        self.assertNotIn("no cards", row["detail"])

    def test_no_captions_file_is_NOT_a_tick(self):
        self._plan(["BT01"])
        row = self._row("captions")
        self.assertEqual(row["state"], "none")
        self.assertEqual(row["detail"], "none written")

    def test_captions_written_and_baked_ARE_a_tick(self):
        self._plan(["BT01"])
        (self.work / "captions.json").write_text(json.dumps(
            {"beats": [{"beat_id": "BT01", "text": "hello"}]}))
        (self.work / "captions").mkdir()
        (self.work / "captions" / "BT01.mov").write_bytes(b"x")
        row = self._row("captions")
        self.assertEqual(row["state"], "ok")
        self.assertEqual(row["detail"], "all baked")

    def test_a_none_row_does_not_block_shipping(self):
        # an episode with no captions on purpose must still be able to ship
        self._plan(["BT01"])
        self.assertTrue(self._row("captions")["ok"])
        self.assertTrue(self._row("cards")["ok"])

    # ---- the clips nobody has opened ----

    def test_clips_never_opened_are_counted(self):
        """The live shape: 93 clips, 3 approved, 1 flagged, 1 edited, 88
        untouched — reported as "2 beats open"."""
        self._plan(["BT%02d" % i for i in range(1, 94)])
        self._review({"BT01": "approved", "BT02": "approved", "BT03": "approved",
                      "BT04": "flagged", "BT05": "edited"})
        row = self._row("review")
        self.assertFalse(row["ok"])
        self.assertIn("88 clips never opened", row["detail"])
        self.assertIn("2 sent back", row["detail"])

    def test_one_untouched_clip_is_singular(self):
        self._plan(["BT01", "BT02"])
        self._review({"BT01": "approved"})
        self.assertIn("1 clip never opened", self._row("review")["detail"])

    def test_every_clip_approved_is_a_tick(self):
        self._plan(["BT01", "BT02"])
        self._review({"BT01": "approved", "BT02": "approved"})
        row = self._row("review")
        self.assertTrue(row["ok"])
        self.assertEqual(row["detail"], "every clip approved")

    def test_a_verdict_on_a_beat_the_cut_dropped_does_not_count(self):
        """review.json keeps entries for ids a re-assembly removed; 14 such
        ghosts once held this row amber while the desk was rightly green."""
        self._plan(["BT01"])
        self._review({"BT01": "approved", "GHOST": "flagged"})
        self.assertTrue(self._row("review")["ok"])

    # ---- the ledger the engine will actually execute ----

    def test_the_conform_row_counts_EFFECTIVE_ops(self):
        """22 raw ops collapse to 12; Review's button already said 12."""
        self._plan(["BT01"])
        mk = lambda op, clip: {"op": op, "payload": {"beat_id": "BT01", "clip_id": clip}}
        raw = [mk("broll_attach", "B01"), mk("broll_remove", "B01"),
               mk("broll_attach", "B02")]
        collapsed = conform_mod._collapse_ops(raw)
        self.assertLess(len(collapsed), len(raw),
                        "this fixture must actually collapse, or it proves nothing")
        real = editroom._conform_pending
        editroom._conform_pending = lambda slug: raw
        try:
            detail = self._row("conform")["detail"]
        finally:
            editroom._conform_pending = real
        self.assertEqual(detail, "%d edits queued" % len(collapsed))


if __name__ == "__main__":
    unittest.main()
