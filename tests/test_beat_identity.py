# -*- coding: utf-8 -*-
"""A beat is named after the shot it shows.

Beat ids were invented free-hand by the LLM (the only spec anywhere was
the literal example "BT01" in story-designer.md), and ten artifacts key
on one. A regeneration therefore did not orphan the old ids — it
re-pointed ~76 of hmns's 82 at different takes, invisibly, because BT06
still resolved. `pipeline/beat_identity.py` is the identity scheme that
makes that structurally impossible: an id carries its own anchor, and
the invariant checks the two never disagree.

What breaks if this is wrong: every future re-cut, swap or restore can
silently attach Caleb's verdicts, captions and cards to shots they were
never about.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import beat_identity as bi  # noqa: E402


def take_beat(bid, tid, s=0.0, e=10.0):
    return {"id": bid, "purpose": "explain", "take_id": tid,
            "trim": {"s": s, "e": e}, "transition_in": "cut"}


def spine_beat(bid, cid, s=0.0, e=4.0):
    """A picture beat, shaped like houston's 29 real ones: spine with
    src_s/src_e, no take_id and no trim."""
    return {"id": bid, "purpose": "stakes", "transition_in": "cut",
            "spine": {"clip_id": cid, "src_s": s, "src_e": e,
                      "audio": False}}


def plan(*beats):
    return {"slug": "ep", "format": "youtube_long",
            "orientation": "landscape",
            "theme": {"problem": "p", "promise": "q", "payoff": "r"},
            "beats": list(beats)}


class TheAnchorRule(unittest.TestCase):
    """One rule covers all four beat kinds."""

    def test_a_take_beat_anchors_on_its_take(self):
        self.assertEqual(bi.anchor(take_beat("BT01", "T362")), "T362")

    def test_a_picture_beat_anchors_on_its_spine_clip(self):
        self.assertEqual(bi.anchor(spine_beat("BT02", "B024")), "B024")

    def test_a_take_outranks_a_spine(self):
        """validate_edit_plan reads the spine only when take_id is
        absent, so a beat holding both anchors on its take."""
        b = take_beat("BT03", "T05")
        b["spine"] = {"clip_id": "B001", "src_s": 0.0, "src_e": 2.0}
        self.assertEqual(bi.anchor(b), "T05")

    def test_a_beat_with_neither_has_no_anchor(self):
        self.assertIsNone(bi.anchor({"id": "BT04", "purpose": "explain"}))
        self.assertIsNone(bi.anchor(None))


class ParseAndFormat(unittest.TestCase):

    def test_round_trip(self):
        self.assertEqual(bi.parse_id("B-T362"), ("T362", 1))
        self.assertEqual(bi.parse_id("B-T92-2"), ("T92", 2))
        self.assertEqual(bi.parse_id("B-B024"), ("B024", 1))
        self.assertEqual(bi.format_id("T362"), "B-T362")
        self.assertEqual(bi.format_id("T92", 5), "B-T92-5")

    def test_legacy_ids_do_not_parse(self):
        """BT\\d+ and B-\\w are disjoint, so a mixed state is
        detectable rather than plausible."""
        self.assertIsNone(bi.parse_id("BT06"))
        self.assertIsNone(bi.parse_id("BT103"))

    def test_one_identity_has_one_spelling(self):
        """A spelled-out -1 or a leading zero would be a second name
        for a beat that already has one."""
        self.assertIsNone(bi.parse_id("B-T92-1"))
        self.assertIsNone(bi.parse_id("B-T92-02"))
        self.assertIsNone(bi.parse_id("B-t92"))
        self.assertIsNone(bi.parse_id(None))

    def test_format_refuses_what_parse_would_refuse(self):
        with self.assertRaises(ValueError):
            bi.format_id("CARD01")
        with self.assertRaises(ValueError):
            bi.format_id("T92", 0)


class Derivation(unittest.TestCase):

    def test_ids_derive_in_beat_order(self):
        p = plan(take_beat("BT01", "T362"),
                 spine_beat("BT02", "B024"),
                 take_beat("BT70", "T04"))
        out = bi.derive_ids(p)
        self.assertEqual([b["id"] for b in out["beats"]],
                         ["B-T362", "B-B024", "B-T04"])
        self.assertEqual(out["id_scheme"], "anchor-v1")

    def test_occurrence_counts_repeats(self):
        """hmns repeats 11 take ids across beats — T92 five times — so
        occurrence is load-bearing, not decoration."""
        p = plan(take_beat("BT01", "T92", 0, 5),
                 take_beat("BT02", "T45"),
                 take_beat("BT03", "T92", 5, 9),
                 take_beat("BT04", "T92", 9, 12))
        out = bi.derive_ids(p)
        self.assertEqual([b["id"] for b in out["beats"]],
                         ["B-T92", "B-T45", "B-T92-2", "B-T92-3"])

    def test_derive_never_mutates_its_argument(self):
        p = plan(take_beat("BT01", "T362"), spine_beat("BT02", "B024"))
        before = copy.deepcopy(p)
        bi.derive_ids(p)
        self.assertEqual(p, before)

    def test_an_anchorless_beat_keeps_its_id_and_is_named_loudly(self):
        p = plan(take_beat("BT01", "T362"),
                 {"id": "BT02", "purpose": "explain"})
        out = bi.derive_ids(p)
        self.assertEqual(out["beats"][1]["id"], "BT02")
        errs = bi.id_errors(out)
        self.assertTrue(any("no take and no spine" in e for e in errs),
                        errs)


class Minting(unittest.TestCase):

    def test_a_removal_does_not_renumber_the_survivors(self):
        """B-T92-2 removed, then a new T92 beat minted: the mint fills
        the hole and B-T92-3 stays exactly where it is. Safe because
        the hole and its filler name the SAME shot."""
        existing = ["B-T92", "B-T92-3", "B-T45"]
        self.assertEqual(bi.mint_id("T92", existing), "B-T92-2")
        self.assertIn("B-T92-3", existing)

    def test_first_of_an_anchor_is_bare(self):
        self.assertEqual(bi.mint_id("T341", ["B-T92", "B-T92-2"]),
                         "B-T341")

    def test_legacy_ids_cannot_collide(self):
        self.assertEqual(bi.mint_id("T06", ["BT06", "BT70"]), "B-T06")


class TheInvariant(unittest.TestCase):

    def conforming(self):
        return bi.derive_ids(plan(take_beat("BT01", "T362"),
                                  spine_beat("BT02", "B024"),
                                  take_beat("BT03", "T362")))

    def test_a_conforming_plan_is_clean(self):
        self.assertEqual(bi.id_errors(self.conforming()), [])

    def test_an_unmarked_plan_is_left_alone(self):
        """hmns's live plan predates the scheme; a checker that bricked
        its surgery writes would punish the archive for predating the
        rule. Same reasoning that keeps coverage_notes advisory."""
        p = plan(take_beat("BT01", "T362"))
        self.assertEqual(bi.id_errors(p), [])

    def test_an_id_cannot_name_a_different_shot_than_its_beat(self):
        """The mis-binding case itself: the id says T362, the beat
        shows T04."""
        p = self.conforming()
        p["beats"][0]["take_id"] = "T04"
        errs = bi.id_errors(p)
        self.assertTrue(any("B-T362" in e and "T04" in e for e in errs),
                        errs)

    def test_a_legacy_survivor_in_a_marked_plan_is_caught(self):
        p = self.conforming()
        p["beats"][1]["id"] = "BT02"
        errs = bi.id_errors(p)
        self.assertTrue(any("does not parse" in e for e in errs), errs)

    def test_two_beats_cannot_share_a_name(self):
        p = self.conforming()
        p["beats"][2]["id"] = "B-T362"
        errs = bi.id_errors(p)
        self.assertTrue(any("duplicate id" in e for e in errs), errs)

    def test_occurrence_gaps_are_legal(self):
        """B-T362-3 without B-T362-2 is the trace of a removal —
        renumbering survivors is the disease, not the cure."""
        p = self.conforming()
        p["beats"][2]["id"] = "B-T362-3"
        self.assertEqual(bi.id_errors(p), [])


class MappingAcrossARegeneration(unittest.TestCase):

    def test_a_beat_that_kept_its_shot_keeps_its_history(self):
        old = plan(take_beat("BT01", "T362"),
                   take_beat("BT70", "T92"),
                   take_beat("BT08", "T92"))
        # regenerated: same shots, new order, one beat dropped, one new
        new = bi.derive_ids(plan(take_beat("x", "T92"),
                                 take_beat("x", "T362"),
                                 take_beat("x", "T45")))
        m = bi.id_map(old, new)
        self.assertEqual(m["map"],
                         {"BT01": "B-T362", "BT70": "B-T92"})
        self.assertEqual(m["unmatched_old"], ["BT08"])
        self.assertEqual(m["unmatched_new"], ["B-T45"])

    def test_occurrence_matches_positionally_on_both_sides(self):
        """The Nth beat showing a shot matches the Nth showing it —
        legacy ids encode nothing, so position is the only truth."""
        old = plan(take_beat("BT01", "T92"), take_beat("BT02", "T92"))
        new = bi.derive_ids(plan(take_beat("x", "T92"),
                                 take_beat("x", "T45"),
                                 take_beat("x", "T92")))
        m = bi.id_map(old, new)
        self.assertEqual(m["map"],
                         {"BT01": "B-T92", "BT02": "B-T92-2"})


class JunkTolerance(unittest.TestCase):
    """A malformed plan degrades to empty results, never a raise — the
    guard style anchor and derive_ids already use, extended to the
    mapping side after verification fuzzing found `plan or {}` passed a
    truthy non-dict straight to .get (2026-08-28)."""

    def test_a_non_dict_plan_maps_to_nothing(self):
        m = bi.id_map([1, 2], "junk")
        self.assertEqual(m["map"], {})
        self.assertEqual(m["unmatched_old"], [])
        self.assertEqual(m["unmatched_new"], [])

    def test_carry_over_junk_plans_still_carries_by_mapping(self):
        out = bi.carry_review({"a": {"status": "ok"}}, {"a": "b"},
                              [1], None)
        self.assertEqual(out["carried"]["b"], {"status": "ok"})

    def test_an_anchor_that_names_no_real_shot_refuses(self):
        """The one input derive_ids refuses instead of reporting: an
        anchor that is neither a take nor a clip means the session named
        a shot that does not exist, and minting an id for it would hide
        that. The caller's plan survives the raise."""
        plan = {"beats": [{"id": "BT01", "take_id": "X99"}]}
        with self.assertRaises(ValueError) as caught:
            bi.derive_ids(plan)
        self.assertIn("X99", str(caught.exception))
        self.assertEqual(plan["beats"][0]["id"], "BT01")
        self.assertNotIn("id_scheme", plan)


class CarryingTheReview(unittest.TestCase):

    def setUp(self):
        self.old = plan(take_beat("BT01", "T362", 1.02, 10.63),
                        take_beat("BT70", "T92", 0.0, 8.0),
                        take_beat("BT99", "T45"))
        self.new = bi.derive_ids(
            plan(take_beat("x", "T362", 1.02, 10.63),   # same cut
                 take_beat("x", "T92", 0.0, 6.5)))      # re-trimmed
        self.mapping = bi.id_map(self.old, self.new)
        self.review = {
            "BT01": {"status": "approved", "note": "", "ts": 1},
            "BT70": {"status": "approved",
                     "note": "hold the door shot longer", "ts": 2},
            "BT99": {"status": "flagged",
                     "note": "the payoff is buried", "ts": 3},
        }

    def carry(self):
        return bi.carry_review(self.review, self.mapping,
                               self.old, self.new)

    def test_same_shot_same_cut_carries_unchanged(self):
        out = self.carry()
        self.assertEqual(out["carried"]["B-T362"],
                         self.review["BT01"])
        self.assertNotIn("B-T362", out["requeued"])

    def test_same_shot_moved_cut_keeps_the_note_and_requeues(self):
        """Mirrors _reset_review on a swap: the verdict is about a cut
        nobody has watched, but deleting the reviewer's words destroyed
        irrecoverable text (gate F11)."""
        out = self.carry()
        entry = out["carried"]["B-T92"]
        self.assertNotIn("status", entry)
        self.assertEqual(entry["note"], "hold the door shot longer")
        self.assertEqual(out["requeued"], ["B-T92"])

    def test_a_gone_beat_strands_by_name_with_its_text(self):
        """hmns already carries 14 ghost entries against 82 live beats;
        the rule is that a strand is always named, never dropped."""
        out = self.carry()
        self.assertEqual(len(out["stranded"]), 1)
        s = out["stranded"][0]
        self.assertEqual(s["id"], "BT99")
        self.assertEqual(s["entry"]["note"], "the payoff is buried")

    def test_a_trim_inside_the_eps_is_the_same_cut(self):
        self.new["beats"][0]["trim"]["e"] = 10.63 + 0.04  # under 0.05
        out = self.carry()
        self.assertEqual(out["carried"]["B-T362"]["status"], "approved")

    def test_carry_is_pure(self):
        before = copy.deepcopy(self.review)
        out = self.carry()
        out["carried"]["B-T92"]["note"] = "scribbled on"
        self.assertEqual(self.review, before)


if __name__ == "__main__":
    unittest.main()
