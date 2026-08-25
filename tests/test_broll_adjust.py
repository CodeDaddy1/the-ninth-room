# -*- coding: utf-8 -*-
"""A placed cover can be moved without being torn out and put back.

2026-08-25, Caleb: "we should be able to go back to the B-Roll and
adjust where it starts in the clip without having to remove the clip and
replace." Remove-and-replace worked, but it cost the cover its place in
the plan, wrote two conform ops for one intention, and re-rendered the
beat twice because detach and attach each rebuild the proxy.

The clamp is the part worth pinning. It used to be inline in attach;
the moment a SECOND path could place a cover it had to become one
function, because the edges are where a cover runs off the end of its
source and renders black.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import editroom  # noqa: E402


class Clamp(unittest.TestCase):
    """beat 10s long, clip 6s long."""

    def clamp(self, at, dur, src):
        return editroom._clamp_cover(10.0, 6.0, at, dur, src)

    def test_a_legal_placement_is_left_alone(self):
        self.assertEqual(self.clamp(2.0, 3.0, 1.0), (2.0, 3.0, 1.0))

    def test_a_cover_cannot_start_past_the_end_of_the_beat(self):
        at, _, _ = self.clamp(99.0, 3.0, 0.0)
        self.assertAlmostEqual(at, 9.8)

    def test_nor_can_the_source_start_past_the_end_of_the_clip(self):
        _, _, src = self.clamp(0.0, 3.0, 99.0)
        self.assertAlmostEqual(src, 5.8)

    def test_duration_is_bounded_by_what_is_left_of_the_CLIP(self):
        """Starting 5s into a 6s clip leaves 1s, however long you ask."""
        _, dur, _ = self.clamp(0.0, 5.0, 5.0)
        self.assertAlmostEqual(dur, 1.0)

    def test_and_by_what_is_left_of_the_BEAT(self):
        _, dur, _ = self.clamp(8.0, 5.0, 0.0)
        self.assertAlmostEqual(dur, 2.0)

    def test_a_negative_position_is_pulled_back_to_the_start(self):
        at, _, src = self.clamp(-4.0, 2.0, -9.0)
        self.assertEqual((at, src), (0.0, 0.0))

    def test_a_duration_never_collapses_to_nothing(self):
        _, dur, _ = self.clamp(0.0, 0.0, 0.0)
        self.assertGreaterEqual(dur, 0.2)

    def test_it_rounds_to_milliseconds_so_the_json_stays_readable(self):
        at, dur, src = self.clamp(1.23456, 2.34567, 0.98765)
        self.assertEqual((at, dur, src), (1.235, 2.346, 0.988))


class AdjustSemantics(unittest.TestCase):
    """What the verb does with what it is NOT given."""

    def test_omitted_fields_keep_their_current_value(self):
        # the adjust reads the existing entry for anything passed as None;
        # this pins the contract the route depends on
        import inspect
        src = inspect.getsource(editroom._broll_adjust)
        self.assertIn('cur.get("at", 0) if at is None else at', src)
        self.assertIn('cur.get("src_s", 0) if src_s is None else src_s', src)

    def test_it_refuses_a_clip_that_is_not_on_the_beat(self):
        import inspect
        src = inspect.getsource(editroom._broll_adjust)
        self.assertIn("attach it first", src)

    def test_attach_and_adjust_share_one_clamp(self):
        """If these ever diverge, one path will place covers the other
        would refuse."""
        import inspect
        for fn in (editroom._broll_attach, editroom._broll_adjust):
            self.assertIn("_clamp_cover", inspect.getsource(fn))


class WhichCover(unittest.TestCase):
    """A beat may carry the SAME clip twice — once early, once late.

    `next(c for c in broll if c["clip_id"] == clip_id)` moves whichever
    copy comes first, so nudging the second one moved the first and the
    desk showed a cover jumping somewhere nobody clicked. Detach already
    took a position to tell them apart; adjust did not (2026-08-25).
    """

    def setUp(self):
        import json
        import shutil
        import tempfile
        from pathlib import Path
        self.json, self.shutil = json, shutil
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        (self.tmp / "analysis" / "timeline_map.json").write_text(json.dumps(
            {"beats": [{"id": "BT01", "record_s": 100.0, "record_e": 120.0,
                        "broll": [
                            {"clip_id": "B001", "file": "c.mp4",
                             "record_s": 102.0, "duration": 3.0, "src_s": 0.0},
                            {"clip_id": "B001", "file": "c.mp4",
                             "record_s": 112.0, "duration": 3.0, "src_s": 0.0}]}]}))
        (self.tmp / "edit_plan.json").write_text(json.dumps(
            {"slug": "ep", "beats": [{"id": "BT01", "broll": [
                {"clip_id": "B001", "at": 2.0, "duration": 3.0, "src_s": 0.0},
                {"clip_id": "B001", "at": 12.0, "duration": 3.0, "src_s": 0.0}]}]}))
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        self._cat = editroom._broll_catalog
        editroom._broll_catalog = lambda slug: [
            {"id": "B001", "file": "c.mp4", "duration": 30.0}]
        self._conf, self._mark = editroom._conform_append, editroom._mark_edited
        editroom._conform_append = lambda *a, **k: None
        editroom._mark_edited = lambda *a, **k: None
        from pipeline import proxy as proxy_mod
        self._proxy, self.proxy_mod = proxy_mod.build, proxy_mod
        proxy_mod.build = lambda *a, **k: None

    def tearDown(self):
        editroom.work_path = self._wp
        editroom._broll_catalog = self._cat
        editroom._conform_append, editroom._mark_edited = self._conf, self._mark
        self.proxy_mod.build = self._proxy
        self.shutil.rmtree(self.tmp, ignore_errors=True)

    def _plan(self):
        return self.json.loads((self.tmp / "edit_plan.json").read_text())["beats"][0]["broll"]

    def _map(self):
        tm = self.json.loads((self.tmp / "analysis" / "timeline_map.json").read_text())
        return tm["beats"][0]["broll"]

    def test_record_s_names_the_second_copy(self):
        editroom._broll_adjust("ep", "BT01", "B001", at=14.0,
                               record_s=112.0, log=lambda *a: None)
        self.assertEqual([c["at"] for c in self._plan()], [2.0, 14.0])
        self.assertEqual([c["record_s"] for c in self._map()], [102.0, 114.0])

    def test_and_the_first(self):
        editroom._broll_adjust("ep", "BT01", "B001", at=5.0,
                               record_s=102.0, log=lambda *a: None)
        self.assertEqual([c["at"] for c in self._plan()], [5.0, 12.0])
        self.assertEqual([c["record_s"] for c in self._map()], [105.0, 112.0])

    def test_without_a_position_the_first_still_moves(self):
        """The old behaviour, kept so an older caller is not broken."""
        editroom._broll_adjust("ep", "BT01", "B001", at=5.0, log=lambda *a: None)
        self.assertEqual([c["at"] for c in self._plan()], [5.0, 12.0])

    def test_the_two_files_never_disagree_about_which_moved(self):
        editroom._broll_adjust("ep", "BT01", "B001", at=14.0,
                               record_s=112.0, log=lambda *a: None)
        for plan_c, map_c in zip(self._plan(), self._map()):
            self.assertAlmostEqual(map_c["record_s"] - 100.0, plan_c["at"])


if __name__ == "__main__":
    unittest.main()
