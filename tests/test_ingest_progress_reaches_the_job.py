# -*- coding: utf-8 -*-
"""The Activity dock should show what the engine already knows.

2026-08-26. `ingest.write_progress` has recorded byte-weighted progress
with an ETA since the ingest work, and it reached the project row and the
Footage desk — never the JOB. So the dock, the one surface whose entire
purpose is showing what is running, sat at a hardcoded 2% and said
"[job] ingest: probe + transcribe" for the whole transcription, which is
by far the longest phase.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import ingest, jobs  # noqa: E402

WORK = Path(__file__).resolve().parent.parent / "work"


class ObserverBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._iwp = ingest.work_path
        ingest.work_path = lambda slug: self.tmp
        self._before = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()

    def tearDown(self):
        ingest.work_path = self._iwp
        shutil.rmtree(self.tmp, ignore_errors=True)
        after = set(p.name for p in WORK.iterdir()) if WORK.is_dir() else set()
        self.assertEqual(after - self._before, set(),
                         "the test wrote into the REAL work dir")


class TheObserver(ObserverBase):
    def test_every_progress_write_reaches_the_observer(self):
        seen = []
        with ingest.observing("ep", seen.append):
            ingest.write_progress("ep", stage="transcribe", done=3, total=10,
                                  pct=0.31, eta_s=174, current="A008.mov")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["stage"], "transcribe")
        self.assertEqual(seen[0]["eta_s"], 174)

    def test_it_is_removed_when_the_block_closes(self):
        seen = []
        with ingest.observing("ep", seen.append):
            pass
        ingest.write_progress("ep", stage="transcribe", done=1, total=2)
        self.assertEqual(seen, [])

    def test_it_is_removed_even_when_the_body_raises(self):
        seen = []
        with self.assertRaises(ValueError):
            with ingest.observing("ep", seen.append):
                raise ValueError("boom")
        ingest.write_progress("ep", stage="transcribe", done=1, total=2)
        self.assertEqual(seen, [])

    def test_one_slug_never_sees_another_slug(self):
        seen = []
        with ingest.observing("ep", seen.append):
            ingest.write_progress("other", stage="transcribe", done=1, total=2)
        self.assertEqual(seen, [])

    def test_an_observer_that_throws_cannot_sink_the_ingest(self):
        """A progress line must never be able to kill real pipeline work."""
        def boom(_f):
            raise RuntimeError("observer exploded")
        with ingest.observing("ep", boom):
            ingest.write_progress("ep", stage="transcribe", done=1, total=2)
        # and the file was still written
        self.assertTrue((self.tmp / "ingest_progress.json").exists())

    def test_no_shared_tmp_is_left_behind(self):
        ingest.write_progress("ep", stage="transcribe", done=1, total=2)
        leftovers = [p.name for p in self.tmp.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_concurrent_writers_do_not_race_on_one_tmp_path(self):
        """A fixed `.tmp` sibling is worse than no atomicity once two
        writers exist — auto-ingest fires per upload, so two runs seconds
        apart is ordinary."""
        import threading
        errors = []
        start = threading.Barrier(12)

        def one(i):
            try:
                start.wait(timeout=5)
                for _ in range(20):
                    ingest.write_progress("ep", stage="transcribe",
                                          done=i, total=12)
            except Exception as e:      # noqa: BLE001
                errors.append(e)

        ts = [threading.Thread(target=one, args=(i,)) for i in range(12)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=10)
        self.assertEqual(errors, [])
        self.assertTrue((self.tmp / "ingest_progress.json").exists())


class TheJobRow(ObserverBase):
    """What the dock would actually render."""

    def _capture(self):
        pcts, notes = [], []

        def log(*parts):
            pass
        log.note = notes.append
        return pcts, notes, log

    def test_the_transcribe_phase_moves_the_bar_and_names_the_file(self):
        pcts, notes, log = self._capture()
        seen = {}

        def fake_ingest(slug):
            ingest.write_progress(slug, stage="transcribe", done=0, total=4,
                                  pct=0.0, eta_s=None, current="A.mov")
            ingest.write_progress(slug, stage="transcribe", done=2, total=4,
                                  pct=0.5, eta_s=174, current="C.mov")

        self._run_with(fake_ingest, pcts, log)
        # 2% + 56% of the byte fraction — not a hardcoded 2 for the whole run
        self.assertEqual(pcts[:3], [2, 2, 30])
        self.assertIn("reading 3 of 4", notes[-1])
        self.assertIn("C.mov", notes[-1])
        self.assertIn("2:54 left", notes[-1])

    def test_the_broll_phase_moves_too(self):
        pcts, notes, log = self._capture()

        def fake_ingest(slug):
            ingest.write_progress(slug, stage="broll", done=5, total=10)

        self._run_with(fake_ingest, pcts, log)
        self.assertIn(89, pcts)
        self.assertIn("contact sheets · 5 of 10", notes[-1])

    def test_a_progress_row_with_no_total_is_ignored_not_a_crash(self):
        pcts, notes, log = self._capture()

        def fake_ingest(slug):
            ingest.write_progress(slug, stage="transcribe", done=0, total=0)
            ingest.write_progress(slug, stage="takes", done=0, total=1,
                                  pct=None, eta_s=None)

        self._run_with(fake_ingest, pcts, log)
        self.assertEqual(notes, [])

    def _run_with(self, fake_ingest, pcts, log):
        """Drive `_run_ingest` with every real stage stubbed out."""
        import pipeline.takes as takes_mod
        import pipeline.broll as broll_mod
        import pipeline.editroom as editroom_mod
        saved = (ingest.ingest, takes_mod.analyze, broll_mod.catalog_broll,
                 editroom_mod._stamp_takes)
        ingest.ingest = fake_ingest
        takes_mod.analyze = lambda slug: None
        broll_mod.catalog_broll = lambda slug: None
        editroom_mod._stamp_takes = lambda slug: 0
        try:
            jobs._run_ingest("ep", log, pcts.append)
        finally:
            (ingest.ingest, takes_mod.analyze, broll_mod.catalog_broll,
             editroom_mod._stamp_takes) = saved


if __name__ == "__main__":
    unittest.main()
