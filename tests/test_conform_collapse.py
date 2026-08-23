# -*- coding: utf-8 -*-
"""The conform ledger's collapse rule — what actually reaches the timeline.

Why this file exists: the ledger is append-only, so it is NOT the list of work.
`_collapse_ops` is, and until 2026-08-23 the desk previewed the raw ledger
while the executor ran the collapsed one — three edits to one card advertised
three placements when exactly one would happen. Both the preview and the run
now read this function, so it is the single place that decides what Resolve
sees. Break it and either a stale card ships or a duplicate lands on V3.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import conform  # noqa: E402


def card(cid, f, ts):
    return {"op": "card_place", "beat_id": "",
            "payload": {"card_id": cid, "file": f}, "ts": ts}


def sfx(op, cue, f, beat, ts):
    return {"op": op, "beat_id": beat,
            "payload": {"id": cue, "file": f, "at_ms": 100}, "ts": ts}


def broll(op, f, rec, ts):
    return {"op": op, "beat_id": "BT20",
            "payload": {"file": f, "record_s": rec, "src_s": 0,
                        "duration": 2.0}, "ts": ts}


class CollapseCards(unittest.TestCase):
    def test_repeated_edits_to_one_card_keep_only_the_newest(self):
        """The live hmns case: OV05 edited three times, one placement runs."""
        ops = [card("OV05", "a.mov", 1),
               card("OV05", "b.mov", 2),
               card("OV05", "c.mov", 3)]
        kept = conform._collapse_ops(ops)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["payload"]["file"], "c.mov")

    def test_newest_is_by_ledger_order_not_filename(self):
        ops = [card("OV05", "z_last_alphabetically.mov", 1),
               card("OV05", "a_first_alphabetically.mov", 2)]
        kept = conform._collapse_ops(ops)
        self.assertEqual(kept[0]["payload"]["file"], "a_first_alphabetically.mov")

    def test_different_cards_both_survive(self):
        ops = [card("OV05", "a.mov", 1), card("OV07", "b.mov", 2)]
        kept = conform._collapse_ops(ops)
        self.assertEqual([o["payload"]["card_id"] for o in kept], ["OV05", "OV07"])

    def test_card_replace_supersedes_an_earlier_place(self):
        place = card("OV05", "a.mov", 1)
        replace = {"op": "card_replace", "beat_id": "",
                   "payload": {"card_id": "OV05", "file": "b.mov"}, "ts": 2}
        kept = conform._collapse_ops([place, replace])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["op"], "card_replace")


class CollapsePairs(unittest.TestCase):
    def test_sound_placed_then_removed_cancels_entirely(self):
        ops = [sfx("sfx_place", "cue1", "/x/thud.wav", "BT12", 1),
               sfx("sfx_remove", "cue1", "/x/thud.wav", "BT12", 2)]
        self.assertEqual(conform._collapse_ops(ops), [])

    def test_a_removal_without_its_place_still_runs(self):
        """A sound placed in an EARLIER conform must still be deleted."""
        ops = [sfx("sfx_remove", "cue9", "/x/old.wav", "BT12", 1)]
        kept = conform._collapse_ops(ops)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["op"], "sfx_remove")

    def test_broll_attached_then_removed_cancels(self):
        ops = [broll("broll_attach", "shot.mov", 12.5, 1),
               broll("broll_remove", "shot.mov", 12.5, 2)]
        self.assertEqual(conform._collapse_ops(ops), [])

    def test_same_file_at_a_different_position_is_a_different_op(self):
        """Position is part of the identity — two cutaways of one clip."""
        ops = [broll("broll_attach", "shot.mov", 12.5, 1),
               broll("broll_remove", "shot.mov", 40.0, 2)]
        self.assertEqual(len(conform._collapse_ops(ops)), 2)


class CollapseShape(unittest.TestCase):
    def test_empty_ledger_collapses_to_nothing(self):
        self.assertEqual(conform._collapse_ops([]), [])

    def test_surviving_ops_keep_ledger_order(self):
        ops = [card("A", "a.mov", 1), card("B", "b.mov", 2), card("C", "c.mov", 3)]
        kept = conform._collapse_ops(ops)
        self.assertEqual([o["payload"]["card_id"] for o in kept], ["A", "B", "C"])

    def test_collapse_returns_the_original_objects(self):
        """The pending endpoint tags superseded ops by identity (id()), so
        collapse must hand back the SAME dicts, not copies."""
        ops = [card("OV05", "a.mov", 1), card("OV05", "b.mov", 2)]
        kept = conform._collapse_ops(ops)
        self.assertIs(kept[0], ops[1])

    def test_collapse_does_not_mutate_the_ledger(self):
        ops = [card("OV05", "a.mov", 1), card("OV05", "b.mov", 2)]
        conform._collapse_ops(ops)
        self.assertEqual(len(ops), 2)


class OpDetail(unittest.TestCase):
    """One label, rendered by BOTH the preview and the progress panel."""

    def test_card_op_names_the_card_and_its_file(self):
        d = conform._op_detail(card("OV05", "custom_glass_overlay.mov", 1))
        self.assertIn("OV05", d)
        self.assertIn("custom_glass_overlay.mov", d)

    def test_file_is_shown_as_a_basename_not_a_full_path(self):
        d = conform._op_detail(sfx("sfx_place", "c1", "/long/path/to/thud.wav", "BT12", 1))
        self.assertEqual(d, "thud.wav")

    def test_falls_back_to_beat_id_when_there_is_nothing_else(self):
        self.assertEqual(
            conform._op_detail({"op": "x", "beat_id": "BT12", "payload": {}}), "BT12")

    def test_never_returns_none_even_with_no_payload(self):
        self.assertEqual(conform._op_detail({"op": "x", "beat_id": ""}), "")


if __name__ == "__main__":
    unittest.main()
