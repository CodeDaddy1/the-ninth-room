# -*- coding: utf-8 -*-
"""The assembly craft bar — everything except the pace ladder, which has
its own file (test_cut_pace.py).

2026-08-28: the cut was the least-checked artifact in the program.
_run_script is hard-gated by script_notes and _run_coverage by
coverage_notes, but _run_editplan only checked that a file appeared — and
the shipped hmns cut is what that bought: 78% build beats, one hook, zero
peaks, a 2-cover hook, 12.6 cuts/min flat. These tests pin the bar that
would have named all four symptoms before the episode shipped.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import cutbar  # noqa: E402


def beat(bid, purpose="build", chapter="CH1", dur=10.0, at=0.0,
         covers=None, **extra):
    b = {"id": bid, "purpose": purpose, "chapter_id": chapter,
         "take_id": "T_" + bid, "trim": {"s": at, "e": at + dur}}
    if covers is not None:
        b["broll"] = covers
    b.update(extra)
    return b


def cover(clip="B01", at=1.0, dur=2.0, why="illustrate: the thing"):
    return {"clip_id": clip, "at": at, "duration": dur, "why": why}


def clip(cid, framing=None):
    c = {"id": cid, "file": cid + ".mp4", "duration": 30.0,
         "sheet": "sheets/%s.jpg" % cid}
    if framing is not None:
        c["framing"] = framing
    return c


def broll_of(*clips):
    return {"slug": "t", "clips": list(clips)}


def takes_for(plan, **overrides):
    """A clean take for every beat the plan references. `overrides` patches
    fields onto one take by its beat id (e.g. T_BT03={"restart": True})."""
    rows = []
    for b in plan["beats"]:
        tid = b.get("take_id")
        if not tid:
            continue
        t = {"id": tid, "file": "IMG_%s.mov" % tid, "s": 0.0, "e": 60.0,
             "transcript": "a clean full sentence about the room.",
             "n_words": 20, "duration": 10.0, "fillers": 0,
             "restart": False, "complete": True}
        t.update(overrides.get(tid, {}))
        rows.append(t)
    return {"slug": "t", "takes": rows,
            "groups": [{"id": "G%02d" % (i + 1), "take_ids": [t["id"]]}
                       for i, t in enumerate(rows)]}


def good_plan():
    """A cut that clears the whole bar: three chapters on a declining
    ladder, a chapter-preview hook, two protected peaks, two loops paid
    in order past the climax line, build share well under the cap."""
    beats = [
        # CH1 — hook run is BT01 alone (everything before the first
        # chapter_open); its three covers preview the three chapters
        beat("BT01", "hook", "CH1", dur=10.0, opens_loop="L1", covers=[
            cover("B01", 1.0, 2.0, "foretell: CH1 — the arch"),
            cover("B02", 4.0, 2.0, "foretell: CH2 — the vault door"),
            cover("B03", 7.0, 2.0, "foretell: CH3 — the ninth room")]),
        beat("BT02", "chapter_open", "CH1", dur=8.0, opens_loop="L2"),
        beat("BT03", "stakes", "CH1", dur=10.0),
        beat("BT04", "build", "CH1", dur=10.0),
        beat("BT05", "chapter_close", "CH1", dur=10.0),
        # CH2 — one protected peak
        beat("BT06", "chapter_open", "CH2", dur=10.0, covers=[
            cover("B04", 1.0, 2.0, "establish: the hall"),
            cover("B05", 5.0, 2.0, "illustrate: the case")]),
        beat("BT07", "build", "CH2", dur=12.0, peak=True),
        beat("BT08", "build", "CH2", dur=10.0),
        beat("BT09", "chapter_close", "CH2", dur=8.0),
        # CH3 — the payoff peak, both loops paid in opening order
        beat("BT10", "chapter_open", "CH3", dur=6.0),
        beat("BT11", "payoff", "CH3", dur=10.0, peak=True, pays_loop="L1"),
        beat("BT12", "build", "CH3", dur=6.0, pays_loop="L2"),
        beat("BT13", "button", "CH3", dur=5.0),
        beat("BT14", "chapter_close", "CH3", dur=6.3),
    ]
    return {
        "slug": "t", "format": "youtube_long",
        "chapters": [
            {"id": "CH1", "title": "One", "pace_cpm": 14.0},
            {"id": "CH2", "title": "Two", "pace_cpm": 12.0},
            {"id": "CH3", "title": "Three", "pace_cpm": 9.0}],
        "beats": beats,
    }


def good_broll():
    return broll_of(clip("B01", "wide"), clip("B02", "medium"),
                    clip("B03", "close"), clip("B04", "wide"),
                    clip("B05", "close"))


class TheBar(unittest.TestCase):
    def notes(self, plan, takes=None, broll=None):
        return cutbar.cut_notes(plan, takes, broll)

    def test_a_good_cut_clears_the_whole_bar(self):
        plan = good_plan()
        out = self.notes(plan, takes_for(plan), good_broll())
        self.assertEqual(out, [])

    def test_a_malformed_plan_notes_and_does_not_raise(self):
        """A plan mid-surgery is a real input — absent fields, wrong
        types, unknown ids. The bar must speak, never crash."""
        plan = {"chapters": [{"id": "CH1"}, "x", None, {"pace_cpm": "f"}],
                "beats": [None, 5,
                          {"id": "BT01", "purpose": "build",
                           "trim": {"s": "a"}, "peak": True, "thread": 3,
                           "opens_loop": 4,
                           "broll": [None, {"clip_id": 7,
                                            "duration": "x"}]},
                          {"pays_loop": "L9", "take_id": "T99"}],
                "loops": "nope", "threads": [{"id": "TH1"}, None, 7]}
        out = cutbar.cut_notes(plan, {"takes": "x"}, {"clips": None})
        self.assertTrue(out)
        self.assertIsInstance(cutbar.cut_metrics(plan, {"takes": "x"},
                                                 {"clips": None}), dict)

    def test_unhashable_ids_and_bad_groups_do_not_raise(self):
        """Found in verification (2026-08-28): a dict or list where an id
        goes reached a dict lookup and raised TypeError, and a None row
        in takes groups raised AttributeError — four paths, one root."""
        plan = {"chapters": [],
                "beats": [{"id": "B1", "take_id": {"a": 1},
                           "trim": {"s": 0.0, "e": 5.0},
                           "broll": [{"clip_id": [], "duration": 2.0,
                                      "why": "illustrate: x"}]}],
                "loops": [{"id": "L1", "opens": [], "pays": {}}]}
        takes = {"takes": [{"id": "T1"}], "groups": [None, "x",
                                                     {"take_ids": None}]}
        broll = broll_of(clip("C1", "wide"))
        self.assertIsInstance(cutbar.cut_notes(plan, takes, broll), list)
        m = cutbar.cut_metrics(plan, takes, broll)
        self.assertIsInstance(m, dict)
        self.assertIn("gear", m)

    def test_a_non_dict_plan_is_a_note_not_a_crash(self):
        self.assertTrue(cutbar.cut_notes(None, None, None))
        self.assertIsInstance(cutbar.cut_metrics(None, None, None), dict)


class PurposeDistribution(unittest.TestCase):
    def test_a_chapter_of_nothing_but_build_beats_is_named(self):
        """CALIBRATED 2026-08-28: the build-SHARE cap was dropped for
        being unreachable and for not tracking quality (hmns 78% with no
        arc, houston 75% with one). What replaced it asks each chapter
        for the thing itself — a moment that lands, between its doors."""
        plan = good_plan()
        for b in plan["beats"][2:]:
            if b.get("purpose") not in ("chapter_open", "chapter_close"):
                b["purpose"] = "build"
            b.pop("peak", None)
        out = cutbar.cut_notes(plan, None, None)
        hits = [n for n in out if "nothing between its doors" in n]
        self.assertTrue(hits)
        self.assertIn("CH", hits[0])

    def test_a_chapter_earns_its_texture_from_a_peak(self):
        """A peak counts as the chapter's landing moment even when every
        purpose in the run is build — the beat says what it is."""
        plan = good_plan()
        for b in plan["beats"][2:]:
            if b.get("purpose") not in ("chapter_open", "chapter_close"):
                b["purpose"] = "build"
            b.pop("peak", None)
        first = [n for n in cutbar.cut_notes(plan, None, None)
                 if "nothing between its doors" in n]
        cid = first[0].split(":")[0]
        for b in plan["beats"]:
            if b.get("chapter_id") == cid and b.get("purpose") == "build":
                b["peak"] = True
                b["trim"] = {"s": 0.0, "e": 20.0}
                break
        out = cutbar.cut_notes(plan, None, None)
        self.assertFalse(any(n.startswith(cid + ": nothing between")
                             for n in out))

    def test_the_build_share_cap_is_gone(self):
        """The cap could be passed by renaming beats, which changes no
        frames. Nothing may reintroduce it without a fresh measurement."""
        self.assertFalse(hasattr(cutbar, "BUILD_SHARE_MAX"))

    def test_a_chapter_missing_its_close_is_named(self):
        plan = good_plan()
        plan["beats"][4]["purpose"] = "build"     # CH1 loses its close
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("CH1: no chapter_close" in n for n in out))

    def test_an_unpaid_loop_never_closes(self):
        plan = good_plan()
        del plan["beats"][10]["pays_loop"]        # L1 opens, never pays
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("L1: opens and never pays" in n for n in out))

    def test_loops_pay_in_the_order_they_were_opened(self):
        plan = good_plan()
        plan["beats"][10]["pays_loop"] = "L2"     # L2 (opened second)...
        plan["beats"][11]["pays_loop"] = "L1"     # ...pays before L1
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("order they were opened" in n for n in out))

    def test_an_early_climax_is_named(self):
        plan = good_plan()
        plan["beats"][10].pop("pays_loop")
        plan["beats"][11].pop("pays_loop")
        plan["beats"][3]["pays_loop"] = "L1"      # both paid inside CH1,
        plan["beats"][4]["pays_loop"] = "L2"      # last at ~40% of runtime
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("climax sits at" in n for n in out))

    def test_a_long_form_cut_owes_two_loops(self):
        plan = good_plan()
        for b in plan["beats"]:
            b.pop("opens_loop", None)
            b.pop("pays_loop", None)
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("0 loops declared" in n for n in out))

    def test_a_plan_level_ledger_counts_as_declared(self):
        """houston's shipped plan declares {id, opens, pays} at PLAN level
        naming beat ids — the bar reads that shape too, because grading
        the field name is not grading the craft (2026-08-28)."""
        plan = good_plan()
        for b in plan["beats"]:
            b.pop("opens_loop", None)
            b.pop("pays_loop", None)
        plan["loops"] = [
            {"id": "L1", "opens": "BT01", "pays": "BT11"},
            {"id": "L2", "opens": "BT02", "pays": "BT12"}]
        out = cutbar.cut_notes(plan, None, None)
        self.assertFalse(any("loop" in n.lower() for n in out), out)


class Peaks(unittest.TestCase):
    def test_zero_peaks_is_named_with_the_count(self):
        plan = good_plan()
        for b in plan["beats"]:
            b.pop("peak", None)
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("0 peak beats" in n for n in out))

    def test_a_chapter_after_the_intro_with_no_peak_is_named(self):
        plan = good_plan()
        plan["beats"][6].pop("peak")              # CH2 loses its only peak
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("CH2: no peak beat" in n for n in out))

    def test_a_peak_shorter_than_the_band_is_named(self):
        plan = good_plan()
        plan["beats"][6]["trim"] = {"s": 0.0, "e": 3.0}   # a 3s "peak"
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("a peak runs 3.0s" in n for n in out))

    def test_a_long_reaction_inside_the_wide_band_does_not_false_fail(self):
        plan = good_plan()
        plan["beats"][6]["trim"] = {"s": 0.0, "e": 40.0}  # 40s laugh
        out = cutbar.cut_notes(plan, None, None)
        self.assertFalse(any("a peak runs" in n for n in out))


class HookMontage(unittest.TestCase):
    def test_a_thin_hook_is_taught_the_rule(self):
        plan = good_plan()
        plan["beats"][0]["broll"] = [
            cover("B01", 1.0, 2.0, "foretell: CH1 — the arch")]
        out = cutbar.cut_notes(plan, None, None)
        hits = [n for n in out if "chapter preview montage" in n]
        self.assertEqual(len(hits), 1)
        self.assertIn("the hook carries 1 cover", hits[0])

    def test_a_hook_cover_that_does_not_foretell_is_named(self):
        plan = good_plan()
        plan["beats"][0]["broll"][1]["why"] = "illustrate: the vault"
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("does not foretell" in n for n in out))

    def test_covers_naming_no_chapter_get_ONE_note_not_n(self):
        plan = good_plan()
        for c in plan["beats"][0]["broll"]:
            c["why"] = "foretell: something wonderful"
        out = cutbar.cut_notes(plan, None, None)
        hits = [n for n in out if "names a chapter" in n]
        self.assertEqual(len(hits), 1)

    def test_chapters_previewed_out_of_order_are_named(self):
        plan = good_plan()
        b = plan["beats"][0]["broll"]
        b[0]["why"], b[1]["why"] = b[1]["why"], b[0]["why"]
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("out of order" in n for n in out))

    def test_a_short_form_plan_owes_no_montage(self):
        plan = good_plan()
        plan["chapters"] = plan["chapters"][:2]
        plan["beats"][0]["broll"] = []
        out = cutbar.cut_notes(plan, None, None)
        self.assertFalse(any("montage" in n for n in out))


class GearChangeStaysDark(unittest.TestCase):
    def test_C5_is_metrics_only_while_unarmed(self):
        """Every edit plan in existence has zero vo beats, so the ratio
        has no calibration data — the constant is None and the bar says
        nothing, while the metric still reports."""
        self.assertIsNone(cutbar.GEAR_RATIO_MIN)
        plan = good_plan()
        takes = takes_for(plan)
        for t in takes["takes"]:
            t["file"] = "vo_" + t["file"]      # a fully VO-led flat cut
            t["kind"] = "vo"
        out = cutbar.cut_notes(plan, takes, good_broll())
        self.assertFalse(any("gear" in n.lower() for n in out))
        m = cutbar.cut_metrics(plan, takes, good_broll())
        self.assertIn("gear", m)
        self.assertEqual(m["gear"]["vo_beats"], 14)


class Threads(unittest.TestCase):
    def test_a_thread_needs_a_why_and_two_members(self):
        plan = good_plan()
        plan["threads"] = [{"id": "TH1"}]
        plan["beats"][3]["thread"] = "TH1"
        out = cutbar.cut_notes(plan, None, None)
        self.assertTrue(any("TH1: a thread with no why" in n for n in out))
        self.assertTrue(any("jump wearing a lanyard" in n for n in out))

    def test_a_declared_used_thread_is_silent(self):
        plan = good_plan()
        plan["threads"] = [{"id": "TH1",
                            "why": "the butterfly pays off at lunch"}]
        plan["beats"][3]["thread"] = "TH1"
        plan["beats"][7]["thread"] = "TH1"
        out = cutbar.cut_notes(plan, takes_for(plan), good_broll())
        self.assertEqual(out, [])


class ShotVariety(unittest.TestCase):
    def test_an_untagged_used_clip_is_sent_to_its_contact_sheet(self):
        plan = good_plan()
        broll = good_broll()
        del broll["clips"][0]["framing"]          # B01 is used, untagged
        out = cutbar.cut_notes(plan, takes_for(plan), broll)
        hits = [n for n in out if "contact sheet" in n]
        self.assertEqual(len(hits), 1)
        self.assertIn("B01", hits[0])

    def test_an_unused_untagged_clip_is_not_asked(self):
        plan = good_plan()
        broll = good_broll()
        broll["clips"].append(clip("B99"))        # untagged, never used
        out = cutbar.cut_notes(plan, takes_for(plan), broll)
        self.assertFalse(any("B99" in n for n in out))

    def test_consecutive_covers_holding_one_size_are_named(self):
        plan = good_plan()
        broll = good_broll()
        broll["clips"][4]["framing"] = "wide"     # BT06 runs wide, wide
        out = cutbar.cut_notes(plan, takes_for(plan), broll)
        self.assertTrue(any("consecutive covers hold wide" in n
                            for n in out))

    def test_a_match_cut_may_repeat_the_size(self):
        plan = good_plan()
        broll = good_broll()
        broll["clips"][4]["framing"] = "wide"
        plan["beats"][5]["broll"][1]["why"] = \
            "illustrate: match cut on the dome shape"
        out = cutbar.cut_notes(plan, takes_for(plan), broll)
        self.assertFalse(any("consecutive covers hold" in n for n in out))

    def test_any_change_satisfies_the_rule_even_a_loosening_one(self):
        """Only holding one size twice is the violation — a cut back out
        to a wide is a change, and taste stays the editor's."""
        plan = good_plan()
        broll = good_broll()
        broll["clips"][3]["framing"] = "close"    # BT06 runs close, then
        broll["clips"][4]["framing"] = "wide"     # loosens back to wide
        out = cutbar.cut_notes(plan, takes_for(plan), broll)
        self.assertFalse(any("consecutive covers hold" in n for n in out))

    def test_three_alike_across_a_vo_run_is_a_slideshow(self):
        plan = good_plan()
        broll = good_broll()
        takes = takes_for(plan)
        for t in takes["takes"]:
            if t["id"] in ("T_BT03", "T_BT04"):
                t["file"] = "vo_" + t["file"]
                t["kind"] = "vo"
        plan["beats"][2]["broll"] = [
            cover("B06", 0.0, 3.0, "illustrate: one"),
            cover("B07", 3.5, 3.0, "illustrate: two")]
        plan["beats"][3]["broll"] = [
            cover("B08", 0.0, 3.0, "illustrate: three")]
        broll["clips"] += [clip("B06", "medium"), clip("B07", "medium"),
                           clip("B08", "medium")]
        out = cutbar.cut_notes(plan, takes, broll)
        self.assertTrue(any("slideshow" in n for n in out))


class TakeQuality(unittest.TestCase):
    def test_a_flagged_take_without_a_flag_note_is_named(self):
        plan = good_plan()
        takes = takes_for(plan, T_BT04={"restart": True})
        out = cutbar.cut_notes(plan, takes, good_broll())
        hits = [n for n in out if "flag_note" in n]
        self.assertEqual(len(hits), 1)
        self.assertIn("BT04", hits[0])
        self.assertIn("false start", hits[0])

    def test_a_flag_note_keeps_the_agents_judgment_legal(self):
        """The bar demands a reason, not a different take — a restart can
        be the best line in the episode when the restart IS the joke."""
        plan = good_plan()
        plan["beats"][3]["flag_note"] = "the restart IS the joke"
        takes = takes_for(plan, T_BT04={"restart": True})
        self.assertEqual(cutbar.cut_notes(plan, takes, good_broll()), [])

    def test_using_a_superseded_take_is_named(self):
        plan = good_plan()
        takes = takes_for(plan)
        takes["takes"].append(
            {"id": "T_LATER", "file": "IMG_L.mov", "s": 0.0, "e": 60.0,
             "transcript": "a clean full sentence about the room again.",
             "n_words": 24, "duration": 10.0, "fillers": 0,
             "restart": False, "complete": True})
        takes["groups"] = [{"id": "G01",
                            "take_ids": ["T_BT04", "T_LATER"]}]
        out = cutbar.cut_notes(plan, takes, good_broll())
        self.assertTrue(any("superseded by T_LATER" in n for n in out))


if __name__ == "__main__":
    unittest.main()
