# -*- coding: utf-8 -*-
"""A clip can be trimmed to its usable range, and nothing is lost by it.

2026-08-28, Caleb: "edit the clip by manually cutting with a scrubber
during the footage ranking process." Triage had two verbs, stars and
reject, so a clip with a bad walk-up or a fumbled tail was thrown away
whole — the good forty seconds went with the bad four.

The range lives in a SIDECAR (`footage_trims.json`) in file-absolute
seconds, the same clock a take's s/e and a cover's src_s are in. An
absent entry means the whole clip is usable, and every reader goes
through `facts.trim_of` so the untrimmed path is the SAME code path.

The rule these tests exist for: a trim must never cause a take to be
dropped or renumbered. Take ids are positional and `edit_plan.json`
references them by name, so `trim_of` returning an empty window would
mark every take as unusable — which is why it degrades to the whole clip
instead of collapsing, and why it can never raise.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import inspect
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom, facts, ingest  # noqa: E402
from pipeline.ingest import IngestError  # noqa: E402


class Trims(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp

    def tearDown(self):
        ingest.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- reading ----

    def test_no_file_means_nothing_trimmed(self):
        self.assertEqual(facts.read_trims("ep"), {})

    def test_a_half_written_sidecar_means_nothing_trimmed(self):
        (self.tmp / "footage_trims.json").write_text('{"files": {"a.mp')
        self.assertEqual(facts.read_trims("ep"), {})

    def test_a_sidecar_of_the_wrong_shape_means_nothing_trimmed(self):
        (self.tmp / "footage_trims.json").write_text('["a.mp4"]')
        self.assertEqual(facts.read_trims("ep"), {})

    # ---- writing ----

    def test_a_trim_round_trips(self):
        out = facts.set_trim("ep", "A001.MP4", 4.0, 62.5)
        self.assertEqual(out, {"name": "A001.MP4",
                               "trim": {"in": 4.0, "out": 62.5}})
        self.assertEqual(facts.read_trims("ep"),
                         {"A001.MP4": {"in": 4.0, "out": 62.5}})

    def test_the_file_on_disk_carries_the_agreed_shape(self):
        """`{"files": {name: {"in", "out"}}}` — the Studio reads this."""
        facts.set_trim("ep", "A001.MP4", 1.0, 9.0)
        data = json.loads((self.tmp / "footage_trims.json").read_text())
        self.assertEqual(data, {"files": {"A001.MP4": {"in": 1.0,
                                                       "out": 9.0}}})

    def test_a_second_trim_replaces_the_first_and_leaves_others_alone(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.set_trim("ep", "b.mp4", 2.0, 8.0)
        facts.set_trim("ep", "a.mp4", 3.0, 4.0)
        self.assertEqual(facts.read_trims("ep"),
                         {"a.mp4": {"in": 3.0, "out": 4.0},
                          "b.mp4": {"in": 2.0, "out": 8.0}})

    def test_a_negative_in_is_pulled_back_to_the_start_of_the_file(self):
        out = facts.set_trim("ep", "a.mp4", -3.0, 9.0)
        self.assertEqual(out["trim"]["in"], 0.0)

    def test_seconds_are_rounded_to_milliseconds(self):
        out = facts.set_trim("ep", "a.mp4", 1.23456, 9.87654)
        self.assertEqual(out["trim"], {"in": 1.235, "out": 9.877})

    def test_strings_of_seconds_are_accepted_as_seconds(self):
        """The desk posts JSON; a number that arrived quoted is still a
        number, and refusing it would be a 400 nobody could act on."""
        self.assertEqual(facts.set_trim("ep", "a.mp4", "1.5", "4")["trim"],
                         {"in": 1.5, "out": 4.0})

    def test_a_path_is_reduced_to_a_basename(self):
        facts.set_trim("ep", "../../etc/passwd", 0.0, 9.0)
        self.assertIn("passwd", facts.read_trims("ep"))
        self.assertNotIn("..", json.dumps(facts.read_trims("ep")))

    # ---- the refusals, each with a code the desk can act on ----

    def _code(self, *args):
        with self.assertRaises(IngestError) as cm:
            facts.set_trim("ep", *args)
        return cm.exception.code

    def test_a_range_under_the_floor_is_a_mis_drag(self):
        self.assertEqual(self._code("a.mp4", 4.0, 4.3), "trim_too_short")
        self.assertEqual(facts.read_trims("ep"), {})

    def test_the_floor_itself_is_allowed(self):
        out = facts.set_trim("ep", "a.mp4", 4.0, 4.0 + facts.MIN_TRIM_S)
        self.assertEqual(out["trim"]["out"] - out["trim"]["in"],
                         facts.MIN_TRIM_S)

    def test_an_out_before_the_in_is_refused(self):
        self.assertEqual(self._code("a.mp4", 9.0, 1.0), "trim_too_short")

    def test_a_zero_length_range_is_refused(self):
        self.assertEqual(self._code("a.mp4", 5.0, 5.0), "trim_too_short")

    def test_something_that_is_not_a_number_is_refused(self):
        self.assertEqual(self._code("a.mp4", "start", 9.0), "bad_trim")

    def test_a_nan_bound_is_refused(self):
        """NaN survives float() and compares false against every bound, so
        it would pass the floor check and poison every clamp downstream."""
        self.assertEqual(self._code("a.mp4", float("nan"), 9.0), "bad_trim")
        self.assertEqual(self._code("a.mp4", 0.0, float("inf")), "bad_trim")

    def test_an_empty_name_is_refused(self):
        self.assertEqual(self._code("", 0.0, 9.0), "no_clip")

    def test_a_refusal_is_an_IngestError_so_the_desk_gets_a_400(self):
        """set_verdict raises a bare ValueError and becomes a 500 with
        'ValueError:' in the message. That wart is not the pattern."""
        with self.assertRaises(IngestError):
            facts.set_trim("ep", "a.mp4", 1.0, 1.1)

    # ---- clearing ----

    def test_clearing_pops_the_entry_rather_than_storing_a_blank(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        out = facts.set_trim("ep", "a.mp4", None, None)
        self.assertIsNone(out["trim"])
        self.assertEqual(facts.read_trims("ep"), {})

    def test_one_missing_bound_clears_rather_than_writing_half_a_window(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.set_trim("ep", "a.mp4", 2.0, None)
        self.assertEqual(facts.read_trims("ep"), {})

    def test_clearing_a_clip_that_was_never_trimmed_is_a_quiet_no_op(self):
        out = facts.set_trim("ep", "a.mp4", None, None)
        self.assertEqual(out, {"name": "a.mp4", "trim": None})
        self.assertFalse((self.tmp / "footage_trims.json").exists())

    def test_clearing_one_leaves_the_others(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.set_trim("ep", "b.mp4", 1.0, 9.0)
        facts.set_trim("ep", "a.mp4", None, None)
        self.assertEqual(list(facts.read_trims("ep")), ["b.mp4"])

    # ---- the race record_source was written for ----

    def test_concurrent_trims_all_survive(self):
        """12 concurrent record_source calls once kept 2 labels of 12. A
        scrubbing pass fires as fast as the desk can drag."""
        names = ["clip%02d.mp4" % i for i in range(12)]
        threads = [threading.Thread(target=facts.set_trim,
                                    args=("ep", n, 1.0, 9.0))
                   for n in names]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(facts.read_trims("ep")), sorted(names))

    # ---- lifecycle ----

    def test_forget_drops_only_the_named(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.set_trim("ep", "b.mp4", 1.0, 9.0)
        facts.forget_trims("ep", ["a.mp4"])
        self.assertEqual(list(facts.read_trims("ep")), ["b.mp4"])

    def test_forget_is_a_noop_when_nothing_matches(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.forget_trims("ep", ["gone.mp4"])
        self.assertEqual(list(facts.read_trims("ep")), ["a.mp4"])

    def test_forget_takes_a_bare_name_as_well_as_a_list(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.forget_trims("ep", "a.mp4")
        self.assertEqual(facts.read_trims("ep"), {})

    def test_clear_forgets_the_lot(self):
        facts.set_trim("ep", "a.mp4", 1.0, 9.0)
        facts.clear_trims("ep")
        self.assertEqual(facts.read_trims("ep"), {})

    def test_clear_on_a_project_with_no_trims_does_not_raise(self):
        facts.clear_trims("ep")


class TrimOf(unittest.TestCase):
    """The PURE resolver every downstream site calls.

    TOTAL by design: it runs on the assemble path and while takes are
    marked, where raising is not something a caller can recover from. And
    it must never answer with an EMPTY window — an empty window puts every
    take outside the trim, and marking all of them is the failure this
    feature must not cause.
    """

    def test_no_entry_is_the_whole_clip(self):
        self.assertEqual(facts.trim_of({}, "a.mp4", 60.0), (0.0, 60.0))

    def test_an_unknown_name_is_the_whole_clip(self):
        trims = {"b.mp4": {"in": 1.0, "out": 9.0}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (0.0, 60.0))

    def test_a_real_entry_is_returned(self):
        trims = {"a.mp4": {"in": 4.0, "out": 42.5}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (4.0, 42.5))

    def test_it_keys_on_the_basename_like_every_writer_does(self):
        trims = {"a.mp4": {"in": 4.0, "out": 42.5}}
        self.assertEqual(facts.trim_of(trims, "/cards/A/a.mp4", 60.0),
                         (4.0, 42.5))

    def test_an_out_past_the_real_end_is_clamped_to_the_file(self):
        """The file on disk is the truth; the sidecar is a note about it."""
        trims = {"a.mp4": {"in": 4.0, "out": 900.0}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (4.0, 60.0))

    def test_a_negative_in_is_pulled_back_to_zero(self):
        trims = {"a.mp4": {"in": -9.0, "out": 42.5}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (0.0, 42.5))

    def test_an_in_past_the_out_degrades_to_the_whole_clip(self):
        trims = {"a.mp4": {"in": 40.0, "out": 4.0}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (0.0, 60.0))

    def test_a_window_entirely_past_the_file_degrades_to_the_whole_clip(self):
        """A file replaced by a shorter one under the same name. Clamping
        alone would collapse this to (60, 60) and orphan every take."""
        trims = {"a.mp4": {"in": 90.0, "out": 95.0}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (0.0, 60.0))

    def test_a_window_the_ROUNDING_would_collapse_degrades_too(self):
        """The empty-window guard has to run AFTER the rounding, not before.

        `in` 59.9 / `out` 60.4 is a legal stored trim — it clears
        MIN_TRIM_S and is written by the route itself. Re-probe the file at
        59.9004s (replaced by a marginally shorter one) and clamping gives
        (59.9, 59.9004), which passes `end > start`; only the round to
        milliseconds afterwards collapses it to (59.9, 59.9). Found by
        adversarial verification 2026-08-28, reachable with no hand-editing
        at all.
        """
        trims = {"a.mp4": {"in": 59.9, "out": 60.4}}
        lo, hi = facts.trim_of(trims, "a.mp4", 59.9004)
        self.assertGreater(hi, lo)
        self.assertEqual((lo, hi), (0.0, 59.9004))

    def test_no_stored_window_can_ever_resolve_to_an_empty_one(self):
        """The whole feature rests on this: an empty window puts every take
        outside the trim, and marking all of them is the drop this must
        never cause."""
        empty = []
        for dur in (60.0, 4.921583, 1.0):
            for a in (0, 0.0001, 0.0004, dur - 0.0004, dur, dur + 1, -1):
                for b in (a, a + 0.0001, a + 0.5, dur, dur + 5, -1):
                    lo, hi = facts.trim_of({"a.mp4": {"in": a, "out": b}},
                                           "a.mp4", dur)
                    if hi <= lo:
                        empty.append((dur, a, b))
        self.assertEqual(empty, [])

    def test_a_junk_entry_degrades_to_the_whole_clip(self):
        for junk in ("4-42", ["4", "42"], {"in": "x", "out": 9.0},
                     {"in": None, "out": None}, {}, 7, None):
            self.assertEqual(facts.trim_of({"a.mp4": junk}, "a.mp4", 60.0),
                             (0.0, 60.0), junk)

    def test_a_non_finite_bound_degrades_to_the_whole_clip(self):
        trims = {"a.mp4": {"in": float("nan"), "out": 42.0}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 60.0), (0.0, 60.0))

    def test_a_trims_map_that_is_not_a_map_degrades_to_the_whole_clip(self):
        for junk in (None, [], "a.mp4", 3):
            self.assertEqual(facts.trim_of(junk, "a.mp4", 60.0), (0.0, 60.0))

    def test_an_unusable_duration_never_raises(self):
        for dur in (None, "sixty", float("nan"), -4.0):
            self.assertEqual(facts.trim_of({}, "a.mp4", dur), (0.0, 0.0))

    def test_an_unknown_duration_passes_a_stored_window_through(self):
        """_footage_state reports 0.0 for a clip nothing has probed yet.
        There is no length to clamp against, and clamping to it would
        answer (0, 0) — an empty window, the one answer that is never
        safe."""
        trims = {"a.mp4": {"in": 4.0, "out": 42.5}}
        self.assertEqual(facts.trim_of(trims, "a.mp4", 0.0), (4.0, 42.5))

    def test_a_string_duration_is_read_as_seconds(self):
        self.assertEqual(facts.trim_of({}, "a.mp4", "60"), (0.0, 60.0))


class CoverClamp(unittest.TestCase):
    """A cover may not be placed in the seconds the trim cut away.

    beat 10s long, clip 6s long, usable range 2.0–5.0s.
    """

    def clamp(self, at, dur, src, trim=(2.0, 5.0)):
        return editroom._clamp_cover(10.0, 6.0, at, dur, src, trim=trim)

    def test_without_a_trim_nothing_changes(self):
        """The untrimmed path is the same arithmetic, not a second branch."""
        self.assertEqual(editroom._clamp_cover(10.0, 6.0, 2.0, 3.0, 1.0),
                         (2.0, 3.0, 1.0))
        self.assertEqual(self.clamp(2.0, 3.0, 1.0, trim=(0.0, 6.0)),
                         (2.0, 3.0, 1.0))

    def test_a_source_before_the_trim_is_pushed_to_the_in_point(self):
        _, _, src = self.clamp(0.0, 2.0, 0.5)
        self.assertAlmostEqual(src, 2.0)

    def test_a_source_after_the_trim_is_pulled_back_inside_it(self):
        _, _, src = self.clamp(0.0, 2.0, 5.9)
        self.assertAlmostEqual(src, 4.8)

    def test_duration_is_bounded_by_the_OUT_point_not_the_file(self):
        """Starting at 4.0s in a 6s clip leaves 2s of file and 1s of trim."""
        _, dur, _ = self.clamp(0.0, 5.0, 4.0)
        self.assertAlmostEqual(dur, 1.0)

    def test_a_legal_placement_inside_the_window_is_left_alone(self):
        self.assertEqual(self.clamp(1.0, 2.0, 2.5), (1.0, 2.0, 2.5))

    def test_a_window_outside_the_file_falls_back_to_the_whole_clip(self):
        """A clip replaced by a shorter one must stay placeable."""
        self.assertEqual(self.clamp(0.0, 3.0, 0.0, trim=(90.0, 95.0)),
                         (0.0, 3.0, 0.0))

    def test_a_window_too_small_to_hold_a_cover_falls_back(self):
        self.assertEqual(self.clamp(0.0, 3.0, 0.0, trim=(2.0, 2.1)),
                         (0.0, 3.0, 0.0))

    def test_attach_and_adjust_both_resolve_the_trim(self):
        """If either stopped, one path would place covers in footage the
        other refuses — the drift `_clamp_cover` was extracted to stop."""
        for fn in (editroom._broll_attach, editroom._broll_adjust):
            self.assertIn("facts.trim_of", inspect.getsource(fn))


class DeskWiring(unittest.TestCase):
    """What the Footage desk reads, and what a delete takes with it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        (self.tmp / "analysis" / "sheets").mkdir(parents=True)
        for n in ("keep.mp4", "toss.mp4"):
            (self.tmp / "footage" / n).write_bytes(b"x" * 32)
        (self.tmp / "analysis" / "broll.json").write_text('{"clips": []}')
        (self.tmp / "analysis" / "takes.json").write_text('{"takes": []}')
        self._wp, self._ewp = ingest.work_path, editroom.work_path
        ingest.work_path = lambda slug: self.tmp
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        ingest.work_path = self._wp
        editroom.work_path = self._ewp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _sheet(self, name):
        return self.tmp / "analysis" / "sheets" / (name + ".sheet.jpg")

    def test_the_desk_state_carries_the_trims(self):
        facts.set_trim("ep", "keep.mp4", 4.0, 30.0)
        state = editroom._footage_state("ep")
        self.assertEqual(state["trims"],
                         {"keep.mp4": {"in": 4.0, "out": 30.0}})

    def test_an_untrimmed_project_reports_an_empty_map_not_a_missing_key(self):
        self.assertEqual(editroom._footage_state("ep")["trims"], {})

    def test_a_trim_drops_the_stale_contact_sheet(self):
        """Sheets are cached by existence alone and sampled across the
        clip's whole span, so a kept one offers frames from the seconds
        that were just cut away."""
        self._sheet("keep.mp4").write_bytes(b"jpg")
        editroom._set_footage_trim("ep", "keep.mp4", 4.0, 30.0,
                                   log=lambda *_: None)
        self.assertFalse(self._sheet("keep.mp4").exists())
        self.assertEqual(facts.read_trims("ep")["keep.mp4"]["in"], 4.0)

    def test_a_missing_sheet_is_not_an_error(self):
        out = editroom._set_footage_trim("ep", "keep.mp4", 4.0, 30.0,
                                         log=lambda *_: None)
        self.assertEqual(out["trim"], {"in": 4.0, "out": 30.0})

    def test_only_the_trimmed_clip_loses_its_sheet(self):
        self._sheet("keep.mp4").write_bytes(b"jpg")
        self._sheet("toss.mp4").write_bytes(b"jpg")
        editroom._set_footage_trim("ep", "keep.mp4", 4.0, 30.0,
                                   log=lambda *_: None)
        self.assertTrue(self._sheet("toss.mp4").exists())

    def test_clearing_a_trim_also_drops_the_sheet(self):
        """The sheet was sampled across the TRIMMED span; widening back to
        the whole clip leaves it just as wrong."""
        self._sheet("keep.mp4").write_bytes(b"jpg")
        editroom._set_footage_trim("ep", "keep.mp4", None, None,
                                   log=lambda *_: None)
        self.assertFalse(self._sheet("keep.mp4").exists())

    def test_a_refused_trim_writes_nothing_and_keeps_the_sheet(self):
        self._sheet("keep.mp4").write_bytes(b"jpg")
        with self.assertRaises(IngestError):
            editroom._set_footage_trim("ep", "keep.mp4", 4.0, 4.2,
                                       log=lambda *_: None)
        self.assertTrue(self._sheet("keep.mp4").exists())
        self.assertEqual(facts.read_trims("ep"), {})

    def test_deleting_a_clip_takes_its_trim_with_it(self):
        """A re-dropped card gives the same filename back, and it must not
        inherit a window dragged against footage it never was."""
        facts.set_trim("ep", "toss.mp4", 4.0, 30.0)
        facts.set_trim("ep", "keep.mp4", 1.0, 20.0)
        editroom._delete_footage("ep", "toss.mp4", log=lambda *_: None)
        self.assertEqual(list(facts.read_trims("ep")), ["keep.mp4"])

    def test_clearing_the_shelf_forgets_every_trim(self):
        facts.set_trim("ep", "keep.mp4", 4.0, 30.0)
        editroom._clear_footage("ep", log=lambda *_: None)
        self.assertEqual(facts.read_trims("ep"), {})

    def test_the_route_is_reachable_in_the_dispatch(self):
        """The desk's whole write path is this one string."""
        src = inspect.getsource(editroom.serve)
        self.assertIn('"/api/footage/trim"', src)
        self.assertIn("_set_footage_trim", src)


if __name__ == "__main__":
    unittest.main()
