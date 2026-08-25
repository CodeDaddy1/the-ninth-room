# -*- coding: utf-8 -*-
"""Flagging bad takes — with thresholds the footage chose, not I.

2026-08-24. `takes.py` has computed restart/fillers/complete/wpm/volume
since the stage was written, and nothing ever filtered on any of it: the
story-designer saw all 355 takes of an episode and was trusted to avoid
the fumbles by reading them.

Two thresholds were wrong on the first attempt and the real footage said
so, which is why both are pinned here:

  * an ABSOLUTE quiet floor of -40 dB flagged 26% of HMNS, because the
    median take sits at -36 dB — the camera mic runs quiet in a big room.
    That is the rig, not a defect. The floor is relative now.
  * wpm on a fragment is arithmetic noise: "Yeah." at 1 word in 0.02s
    reads as 3000 wpm.

These are FLAGS, never verdicts. Only a human kill is enforced.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import takes  # noqa: E402


def take(tid="T1", **kw):
    t = {"id": tid, "transcript": "a clean full sentence here about a thing.",
         "n_words": 9, "duration": 4.0, "fillers": 0, "restart": False,
         "complete": True, "mean_volume_db": -30.0}
    t.update(kw)
    return t


class Flags(unittest.TestCase):
    def test_a_clean_take_is_not_flagged(self):
        self.assertEqual(takes.take_flags(take(), floor=-44.0), [])

    def test_a_false_start_and_an_unfinished_line_are_flagged(self):
        self.assertIn("false start", takes.take_flags(take(restart=True)))
        self.assertIn("unfinished sentence",
                      takes.take_flags(take(complete=False)))

    def test_fillers_are_judged_as_a_RATE_not_a_count(self):
        """Two 'um's in nine words is a fumble; two in ninety is speech."""
        self.assertTrue(takes.take_flags(take(fillers=2, n_words=9)))
        # 90 words at a normal 150 wpm is 36s — the earlier fixture said
        # 4s, which really is 1350 wpm, and the rushed flag was right
        self.assertEqual(takes.take_flags(take(fillers=2, n_words=90,
                                               duration=36.0),
                                          floor=-44.0), [])

    def test_wpm_is_ignored_on_a_fragment(self):
        """The 3000 wpm bug: a one-word take is not 'rushed'."""
        self.assertEqual(takes.take_flags(take(n_words=1, duration=0.02),
                                          floor=-44.0), [])
        self.assertEqual(takes.take_flags(take(n_words=5, duration=0.2),
                                          floor=-44.0), [])

    def test_wpm_fires_on_a_real_line_delivered_too_fast(self):
        f = takes.take_flags(take(n_words=40, duration=6.0), floor=-44.0)
        self.assertTrue(any("wpm" in x for x in f), f)

    def test_quiet_is_relative_and_silent_without_a_floor(self):
        t = take(mean_volume_db=-46.0)
        self.assertTrue(any("quiet" in x for x in takes.take_flags(t, -44.0)))
        self.assertEqual(takes.take_flags(t, None), [])   # no floor, no claim


class QuietFloor(unittest.TestCase):
    def test_the_floor_follows_the_episode(self):
        quiet = [take("T%d" % i, mean_volume_db=-36.0) for i in range(20)]
        self.assertAlmostEqual(takes.quiet_floor(quiet), -44.0)
        loud = [take("T%d" % i, mean_volume_db=-18.0) for i in range(20)]
        self.assertAlmostEqual(takes.quiet_floor(loud), -26.0)

    def test_too_few_takes_to_know_what_normal_sounds_like(self):
        self.assertIsNone(takes.quiet_floor([take()]))

    def test_takes_with_no_volume_reading_do_not_skew_it(self):
        rows = [take("T%d" % i, mean_volume_db=-30.0) for i in range(10)]
        rows += [take("X%d" % i, mean_volume_db=None) for i in range(10)]
        self.assertAlmostEqual(takes.quiet_floor(rows), -38.0)


class Superseded(unittest.TestCase):
    def test_the_last_complete_attempt_wins_its_cluster(self):
        rows = [take("T1", n_words=4, complete=False),
                take("T2", n_words=9, complete=True)]
        groups = [{"id": "G1", "take_ids": ["T1", "T2"]}]
        sup = takes.superseded_takes(rows, groups)
        self.assertEqual(sup, {"T1": "T2"})

    def test_a_cluster_of_one_supersedes_nothing(self):
        rows = [take("T1")]
        self.assertEqual(
            takes.superseded_takes(rows, [{"id": "G1", "take_ids": ["T1"]}]), {})

    def test_an_incomplete_keeper_is_used_only_when_nothing_is_complete(self):
        rows = [take("T1", n_words=3, complete=False),
                take("T2", n_words=7, complete=False)]
        groups = [{"id": "G1", "take_ids": ["T1", "T2"]}]
        self.assertEqual(takes.superseded_takes(rows, groups), {"T1": "T2"})

    def test_flag_takes_folds_it_all_together(self):
        rows = [take("T1", n_words=4, complete=False),
                take("T2", n_words=9, complete=True)]
        groups = [{"id": "G1", "take_ids": ["T1", "T2"]}]
        out = takes.flag_takes(rows, groups)
        self.assertIn("T1", out)
        self.assertIn("superseded by T2", out["T1"])
        self.assertNotIn("T2", out)   # the keeper is clean


if __name__ == "__main__":
    unittest.main()


class ScreenedTakesAreRefused(unittest.TestCase):
    """A kill on the Takes desk must be ENFORCED, not merely advertised.

    Before this, "killed" was a label the story-designer wrote inside the
    finished edit plan — a fumbled line could only be rejected after it
    had already been quoted. A brief can be ignored; a validator cannot.
    """

    def _takes(self, screened=()):
        rows = []
        for tid in ("T1", "T2"):
            t = take(tid)
            t["s"], t["e"], t["file"] = 0.0, 4.0, "A.MP4"
            if tid in screened:
                t["screened_out"] = True
                t["screen_reason"] = "false start"
            rows.append(t)
        return {"takes": rows, "groups": []}

    def _script(self, tid):
        return {"slug": "x", "option_id": "S1", "target_minutes": 1.0,
                "chapters": [{"id": "CH1", "title": "c", "target_s": 40.0,
                              "sections": [{"id": "CH1.S1", "kind": "oncamera",
                                            "text": "a line", "take_id": tid,
                                            "est_s": 40.0}]}]}

    def test_a_script_quoting_a_screened_take_is_refused(self):
        from pipeline import schemas
        errs = schemas.validate_script(self._script("T1"),
                                       self._takes(screened=("T1",)))
        self.assertTrue(any("screened out" in e for e in errs), errs)
        self.assertTrue(any("false start" in e for e in errs), errs)

    def test_the_same_script_passes_when_the_take_is_kept(self):
        from pipeline import schemas
        errs = schemas.validate_script(self._script("T1"), self._takes())
        self.assertEqual([e for e in errs if "screened" in e], [])

    def test_a_cut_built_on_a_screened_take_is_refused(self):
        from pipeline import schemas
        plan = {"slug": "x", "chapters": [{"id": "CH1", "title": "c"}],
                "beats": [{"id": "BT01", "purpose": "hook",
                           "chapter_id": "CH1", "take_id": "T1",
                           "trim": {"s": 0.0, "e": 3.0}, "broll": []}]}
        errs = schemas.validate_edit_plan(plan, self._takes(screened=("T1",)),
                                          {"clips": []})
        self.assertTrue(any("screened out" in e for e in errs), errs)


class VerdictStore(unittest.TestCase):
    """The kill has to survive a re-ingest, because a re-ingest rebuilds
    takes.json from scratch and would otherwise silently un-kill
    everything Caleb rejected."""

    def setUp(self):
        import tempfile, shutil, json as _json
        from pathlib import Path
        from pipeline import editroom
        self.editroom = editroom
        self.shutil = shutil
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp = editroom.work_path
        editroom.work_path = lambda slug: self.tmp
        (self.tmp / "analysis" / "takes.json").write_text(_json.dumps(
            {"takes": [{"id": "T1", "transcript": "one"},
                       {"id": "T2", "transcript": "two"}], "groups": []}))

    def tearDown(self):
        self.editroom.work_path = self._wp
        self.shutil.rmtree(self.tmp, ignore_errors=True)

    def _takes_doc(self):
        import json as _json
        return _json.loads((self.tmp / "analysis" / "takes.json").read_text())

    def test_a_kill_stamps_the_artifact_agents_read(self):
        self.editroom._set_take_verdict("x", "T1", "kill", "false start",
                                        log=lambda *a: None)
        t1 = self._takes_doc()["takes"][0]
        self.assertTrue(t1["screened_out"])
        self.assertEqual(t1["screen_reason"], "false start")

    def test_undo_clears_the_stamp(self):
        self.editroom._set_take_verdict("x", "T1", "kill", log=lambda *a: None)
        self.editroom._set_take_verdict("x", "T1", "undo", log=lambda *a: None)
        self.assertNotIn("screened_out", self._takes_doc()["takes"][0])

    def test_a_verdict_survives_a_rebuild_of_takes_json(self):
        import json as _json
        self.editroom._set_take_verdict("x", "T1", "kill", "fumble",
                                        log=lambda *a: None)
        # a re-ingest writes takes.json fresh, with no screening on it
        (self.tmp / "analysis" / "takes.json").write_text(_json.dumps(
            {"takes": [{"id": "T1", "transcript": "one"},
                       {"id": "T2", "transcript": "two"}], "groups": []}))
        self.assertEqual(self.editroom._stamp_takes("x"), 1)
        self.assertTrue(self._takes_doc()["takes"][0]["screened_out"])

    def test_an_unknown_take_is_refused(self):
        from pipeline.ingest import IngestError
        with self.assertRaises(IngestError):
            self.editroom._set_take_verdict("x", "T999", "kill",
                                            log=lambda *a: None)

    def test_a_bogus_verdict_is_refused(self):
        from pipeline.ingest import IngestError
        with self.assertRaises(IngestError):
            self.editroom._set_take_verdict("x", "T1", "maybe",
                                            log=lambda *a: None)
