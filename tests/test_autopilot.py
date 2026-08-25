# -*- coding: utf-8 -*-
"""The autopilot: chains fire on done, never on fail, and speak up.

P1 of the workflow plan (2026-08-23). The rules pinned here:

- a finished creative job enqueues its mechanical follower (editplan ->
  assemble, graphics -> reproxy, snapcuts -> assemble) and NOTHING else;
- a failed job never chains — the worker's fail branch simply does not
  call _after_done, so the test proves the done-path helper alone;
- a follower already queued is a logged skip, never a crash;
- notifications are darwin-gated and env-gated, and a broken osascript
  can never fail a finished job;
- the auto-ingest debounce is a pure decision so its races are testable
  without threads.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402


class TheChain(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self._start = jobs.start
        jobs.start = lambda kind, slug: self.calls.append((kind, slug))

    def tearDown(self):
        jobs.start = self._start

    def test_every_creative_kind_chains_to_its_mechanical_follower(self):
        for kind, follower in (("editplan", "assemble"),
                               ("graphics", "reproxy"),
                               ("snapcuts", "assemble"),
                               # the one auto-dispatched session (P10) —
                               # its own guards keep it first-pass-only
                               ("assemble", "retention"),
                               ):
            self.calls[:] = []
            jobs._after_done({"kind": kind, "slug": "ep"}, lambda *a: None)
            self.assertEqual(self.calls, [(follower, "ep")], kind)

    def test_unchained_kinds_enqueue_nothing(self):
        # `sourcing` is here on purpose: it proposes and STOPS, because
        # approving a download is a licence decision and Caleb's alone
        for kind in ("ingest", "reproxy", "story", "sourcing", "retention"):
            self.calls[:] = []
            jobs._after_done({"kind": kind, "slug": "ep"}, lambda *a: None)
            self.assertEqual(self.calls, [], kind)

    def test_an_already_queued_follower_is_chain_ok(self):
        """P0 policy: an in-flight follower satisfies the chain's INTENT."""
        def refuse(kind, slug):
            raise jobs.JobError("assemble is already queued for ep")
        jobs.start = refuse
        logged = []
        jobs._after_done({"kind": "editplan", "slug": "ep"},
                         lambda m: logged.append(m))
        self.assertTrue(any("already in flight" in m for m in logged))

    def test_a_guard_refusal_is_chain_failed_and_logged(self):
        """A conform-window refusal is a REAL failure now — visible and
        re-runnable, never a silent log line (the crooise lesson)."""
        def refuse(kind, slug):
            raise jobs.JobError("a conform is running — assemble after it")
        jobs.start = refuse
        logged = []
        jobs._after_done({"kind": "editplan", "slug": "ep"},
                         lambda m: logged.append(m))
        self.assertTrue(any("FAILED" in m for m in logged))

    def test_every_chain_entry_names_real_kinds(self):
        for kind, follower in jobs.CHAIN.items():
            self.assertIn(kind, jobs.KINDS)
            self.assertIn(follower, jobs.KINDS)


class TheNotifier(unittest.TestCase):
    def test_env_zero_never_spawns_osascript(self):
        import subprocess
        called = []
        real = subprocess.run
        subprocess.run = lambda *a, **k: called.append(a)
        try:
            os.environ["NINTH_NOTIFY"] = "0"
            jobs._notify("t", "b")
        finally:
            subprocess.run = real
            del os.environ["NINTH_NOTIFY"]
        self.assertEqual(called, [])

    def test_a_broken_osascript_never_raises(self):
        import subprocess
        real = subprocess.run
        def explode(*a, **k):
            raise OSError("no osascript here")
        subprocess.run = explode
        try:
            jobs._notify("t", "b")  # must not raise
        finally:
            subprocess.run = real


class AutoIngestDecision(unittest.TestCase):
    def test_a_newer_upload_supersedes_this_timer(self):
        self.assertEqual(
            jobs.autoingest_decision(100.0, 105.0, []), "skip")

    def test_the_settled_batch_starts_analysis(self):
        self.assertEqual(
            jobs.autoingest_decision(100.0, 100.0, []), "start")

    def test_a_running_ingest_means_check_again_later(self):
        running = [{"kind": "ingest", "state": "running"}]
        self.assertEqual(
            jobs.autoingest_decision(100.0, 100.0, running), "rearm")

    def test_an_ingest_that_started_after_the_batch_covers_it(self):
        done = [{"kind": "ingest", "state": "done", "started_ts": 101}]
        self.assertEqual(
            jobs.autoingest_decision(100.0, 100.0, done), "skip")

    def test_a_stale_earlier_ingest_does_not_cover_a_new_batch(self):
        done = [{"kind": "ingest", "state": "done", "started_ts": 90}]
        self.assertEqual(
            jobs.autoingest_decision(100.0, 100.0, done), "start")

    def test_a_same_second_covering_ingest_still_counts(self):
        """Review F4: started_ts is a float now — an ingest starting at
        100.95 covers an upload stamped 100.8, where int truncation to
        100 used to fire a spurious duplicate run."""
        done = [{"kind": "ingest", "state": "done", "started_ts": 100.95}]
        self.assertEqual(
            jobs.autoingest_decision(100.8, 100.8, done), "skip")

    def test_other_kinds_never_affect_the_verdict(self):
        others = [{"kind": "assemble", "state": "running"}]
        self.assertEqual(
            jobs.autoingest_decision(100.0, 100.0, others), "start")


class SnapcutsGuard(unittest.TestCase):
    """The guard refuses BEFORE touching the plan (same pattern as the
    session-job guards in test_script.py)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp

    def tearDown(self):
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_cut_refuses_cleanly(self):
        with self.assertRaises(RuntimeError) as cm:
            jobs._run_snapcuts("ep", lambda *a: None, lambda p: None)
        self.assertIn("no cut yet", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
