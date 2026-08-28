# -*- coding: utf-8 -*-
"""Triage survives the analysis it shapes.

2026-08-27. Rejecting a clip only pays for itself if pass 2 honours it —
whisper is the expensive stage, and spending it on footage Caleb has
already thrown away was the inversion the two-pass split exists to fix.

Verdicts live in a SIDECAR, never in the catalog: ingest rebuilds
catalog.json from scratch on every run, so anything hand-authored inside
it is destroyed by the next analysis. Sources, b-roll tags, promotions
and take verdicts all live beside it for exactly this reason.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import facts, ingest  # noqa: E402


class Verdicts(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp

    def tearDown(self):
        ingest.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- reading ----

    def test_no_file_means_nothing_triaged(self):
        self.assertEqual(facts.read_verdicts("ep"), {})
        self.assertEqual(facts.read_rejected("ep"), set())

    def test_a_half_written_sidecar_means_nothing_triaged(self):
        (self.tmp / "footage_verdicts.json").write_text('{"files": {"a.mp')
        self.assertEqual(facts.read_verdicts("ep"), {})

    # ---- writing ----

    def test_starring_a_clip(self):
        v = facts.set_verdict("ep", "A001.MP4", stars=4)
        self.assertEqual(v["stars"], 4)
        self.assertEqual(facts.read_verdicts("ep")["A001.MP4"]["stars"], 4)

    def test_rejecting_a_clip(self):
        facts.set_verdict("ep", "A001.MP4", rejected=True)
        self.assertEqual(facts.read_rejected("ep"), {"A001.MP4"})

    def test_stars_are_clamped_to_the_scale(self):
        self.assertEqual(facts.set_verdict("ep", "a.mp4", stars=99)["stars"], 5)
        self.assertEqual(facts.set_verdict("ep", "b.mp4", stars=-3)["stars"], 0)

    def test_rating_a_rejected_clip_un_rejects_it(self):
        """A 4-star reject is a state nothing downstream could act on."""
        facts.set_verdict("ep", "a.mp4", rejected=True)
        facts.set_verdict("ep", "a.mp4", stars=4)
        self.assertEqual(facts.read_rejected("ep"), set())

    def test_rejecting_a_starred_clip_clears_the_stars(self):
        facts.set_verdict("ep", "a.mp4", stars=5)
        v = facts.set_verdict("ep", "a.mp4", rejected=True)
        self.assertEqual(v["stars"], 0)
        self.assertTrue(v["rejected"])

    def test_clearing_both_forgets_the_clip_rather_than_storing_a_blank(self):
        facts.set_verdict("ep", "a.mp4", stars=3)
        facts.set_verdict("ep", "a.mp4", stars=0)
        self.assertEqual(facts.read_verdicts("ep"), {})

    def test_a_path_is_reduced_to_a_basename(self):
        facts.set_verdict("ep", "../../etc/passwd", stars=1)
        self.assertIn("passwd", facts.read_verdicts("ep"))
        self.assertNotIn("..", json.dumps(facts.read_verdicts("ep")))

    def test_an_empty_name_is_refused(self):
        with self.assertRaises(ValueError):
            facts.set_verdict("ep", "", stars=1)

    # ---- the race record_source was written for ----

    def test_concurrent_verdicts_all_survive(self):
        """12 concurrent record_source calls once kept 2 labels of 12. A
        keyboard triage pass fires faster than a folder drop."""
        names = ["clip%02d.mp4" % i for i in range(12)]
        threads = [threading.Thread(target=facts.set_verdict,
                                    args=("ep", n), kwargs={"stars": 3})
                   for n in names]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(facts.read_verdicts("ep")), sorted(names))

    # ---- lifecycle ----

    def test_forget_drops_only_the_named(self):
        facts.set_verdict("ep", "a.mp4", stars=2)
        facts.set_verdict("ep", "b.mp4", stars=2)
        facts.forget_verdicts("ep", ["a.mp4"])
        self.assertEqual(list(facts.read_verdicts("ep")), ["b.mp4"])

    def test_forget_is_a_noop_when_nothing_matches(self):
        facts.set_verdict("ep", "a.mp4", stars=2)
        facts.forget_verdicts("ep", ["gone.mp4"])
        self.assertEqual(list(facts.read_verdicts("ep")), ["a.mp4"])

    def test_clear_forgets_the_lot(self):
        facts.set_verdict("ep", "a.mp4", stars=2)
        facts.clear_verdicts("ep")
        self.assertEqual(facts.read_verdicts("ep"), {})

    def test_clear_on_a_project_with_no_verdicts_does_not_raise(self):
        facts.clear_verdicts("ep")


class IngestHonoursRejection(unittest.TestCase):
    """Pass 2 must not transcribe what triage threw away."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        for n in ("keep.mp4", "toss.mp4"):
            (self.tmp / "footage" / n).write_bytes(b"x" * 32)
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        self.probed = []
        self._probe = ingest.probe_file

        def counting(path):
            self.probed.append(path.name)
            raise ingest.IngestError("stub", code="bad_file")
        ingest.probe_file = counting

    def tearDown(self):
        ingest.work_path = self._wp
        ingest.probe_file = self._probe
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_with_no_verdicts_every_clip_is_analyzed(self):
        try:
            ingest.ingest("ep", log=lambda *_: None)
        except ingest.IngestError:
            pass
        self.assertEqual(sorted(self.probed), ["keep.mp4", "toss.mp4"])

    def test_a_rejected_clip_is_never_probed_or_transcribed(self):
        facts.set_verdict("ep", "toss.mp4", rejected=True)
        try:
            ingest.ingest("ep", log=lambda *_: None)
        except ingest.IngestError:
            pass
        self.assertEqual(self.probed, ["keep.mp4"])

    def test_rejecting_everything_refuses_rather_than_writing_an_empty_catalog(self):
        for n in ("keep.mp4", "toss.mp4"):
            facts.set_verdict("ep", n, rejected=True)
        with self.assertRaises(ingest.IngestError) as cm:
            ingest.ingest("ep", log=lambda *_: None)
        self.assertEqual(cm.exception.code, "all_rejected")
        self.assertEqual(self.probed, [])

    def test_a_STARRED_clip_is_still_analyzed(self):
        facts.set_verdict("ep", "toss.mp4", stars=5)
        try:
            ingest.ingest("ep", log=lambda *_: None)
        except ingest.IngestError:
            pass
        self.assertEqual(sorted(self.probed), ["keep.mp4", "toss.mp4"])


class RowHonoursRejection(unittest.TestCase):
    """The footer must not offer to analyze what Analyze will skip.

    2026-08-27, found in a browser: two rejected clips read as "2 files
    added since the analysis", so the footer offered "Analyze again"
    permanently and running it changed nothing — the analysis was already
    complete. A desk and its footer disagreeing about whether there is
    work left is the failure `_footage_state` was aligned to `_project_row`
    to prevent in the first place.
    """

    def setUp(self):
        from pipeline import editroom
        self.editroom = editroom
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "footage").mkdir(parents=True)
        (self.tmp / "analysis").mkdir(parents=True)
        for n in ("keep.mp4", "toss.mp4"):
            (self.tmp / "footage" / n).write_bytes(b"x" * 32)
        # analysed: the catalog covers ONLY the clip that was not rejected
        (self.tmp / "analysis" / "catalog.json").write_text(json.dumps(
            {"slug": "ep", "files": [{"name": "keep.mp4"}], "skipped": []}))
        (self.tmp / "analysis" / "takes.json").write_text('{"takes": []}')
        self._wp, self._ewp = ingest.work_path, editroom.work_path
        ingest.work_path = lambda slug: self.tmp
        editroom.work_path = lambda slug: self.tmp

    def tearDown(self):
        ingest.work_path = self._wp
        self.editroom.work_path = self._ewp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_rejected_clip_is_not_outstanding_work(self):
        facts.set_verdict("ep", "toss.mp4", rejected=True)
        row = self.editroom._project_row("ep")
        self.assertEqual(row["footage"], 1)
        self.assertEqual(row["analyzed"], 1)

    def test_without_rejection_the_uncatalogued_clip_IS_outstanding(self):
        row = self.editroom._project_row("ep")
        self.assertEqual(row["footage"], 2)
        self.assertEqual(row["analyzed"], 1)


class SessionLabels(unittest.TestCase):
    """Naming a stretch of the visit, and merging two by naming them alike.

    Stored per clip rather than per cluster: a cluster is a run of capture
    times, so dropping one more clip into the middle of a shoot can move
    every boundary, and a name keyed to "session 3" would drift onto
    footage it was never about.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp

    def tearDown(self):
        ingest.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nothing_named_yet(self):
        self.assertEqual(facts.read_session_labels("ep"), {})

    def test_naming_a_session_names_every_clip_in_it(self):
        facts.name_session("ep", ["a.mp4", "b.mp4"], "The dinosaur hall")
        self.assertEqual(facts.read_session_labels("ep"),
                         {"a.mp4": "The dinosaur hall",
                          "b.mp4": "The dinosaur hall"})

    def test_two_stretches_named_alike_carry_one_label(self):
        facts.name_session("ep", ["a.mp4"], "The visit")
        facts.name_session("ep", ["z.mp4"], "The visit")
        labels = facts.read_session_labels("ep")
        self.assertEqual(labels["a.mp4"], labels["z.mp4"])

    def test_an_empty_label_CLEARS_rather_than_storing_a_blank(self):
        facts.name_session("ep", ["a.mp4"], "Hall one")
        facts.name_session("ep", ["a.mp4"], "")
        self.assertEqual(facts.read_session_labels("ep"), {})

    def test_whitespace_is_not_a_name(self):
        facts.name_session("ep", ["a.mp4"], "   ")
        self.assertEqual(facts.read_session_labels("ep"), {})

    def test_a_label_is_capped_rather_than_unbounded(self):
        facts.name_session("ep", ["a.mp4"], "x" * 400)
        self.assertEqual(len(facts.read_session_labels("ep")["a.mp4"]), 120)

    def test_a_path_is_reduced_to_a_basename(self):
        facts.name_session("ep", ["../../etc/passwd"], "nope")
        self.assertIn("passwd", facts.read_session_labels("ep"))
        self.assertNotIn("..", json.dumps(facts.read_session_labels("ep")))

    def test_no_clips_is_refused(self):
        with self.assertRaises(ValueError):
            facts.name_session("ep", [], "Hall one")

    def test_a_half_written_sidecar_means_nothing_named(self):
        (self.tmp / "footage_sessions.json").write_text('{"files": {"a.mp')
        self.assertEqual(facts.read_session_labels("ep"), {})

    def test_forget_drops_only_the_named(self):
        facts.name_session("ep", ["a.mp4", "b.mp4"], "Hall")
        facts.forget_session_labels("ep", ["a.mp4"])
        self.assertEqual(list(facts.read_session_labels("ep")), ["b.mp4"])

    def test_clear_forgets_the_lot(self):
        facts.name_session("ep", ["a.mp4"], "Hall")
        facts.clear_session_labels("ep")
        self.assertEqual(facts.read_session_labels("ep"), {})
