# -*- coding: utf-8 -*-
"""The exception policy, asserted through the REAL worker loop.

P0 of the team plan (2026-08-24). Caleb's review named the hole: the
stranded-guard bug wasn't the finding — the finding was that a raise
could hide behind a `done`. Policy, pinned here against the actual
worker thread (not helpers):

- a raise from the JOB FUNCTION lands `failed` with the full traceback
  on the record;
- a raise from the post-done CHAIN phase leaves the job `done` (its work
  is done) but the follower's chain state is `failed` — visible and
  re-runnable, never a log line;
- rechain() is idempotent: ok followers are skipped, an in-flight
  follower resolves to ok, never a double-queue;
- a chain stuck `pending` past the reap window (an engine death mid
  dispatch) is reaped to failed-with-note, still re-runnable.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402


def _wait(jid, states=("done", "failed"), timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = jobs._jobs.get(jid)
        if j and j["state"] in states:
            return j
        time.sleep(0.05)
    raise AssertionError("job %s never settled: %r"
                         % (jid, jobs._jobs.get(jid)))


class RealWorkerPolicy(unittest.TestCase):
    """Temp kinds registered in KINDS, real queue, real worker thread."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "x").mkdir()  # a slug dir so start()'s guard passes
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp / "x"
        self._chain = dict(jobs.CHAIN)
        self._added = []
        os.environ["NINTH_NOTIFY"] = "0"

    def tearDown(self):
        for k in self._added:
            jobs.KINDS.pop(k, None)
        jobs.CHAIN.clear()
        jobs.CHAIN.update(self._chain)
        jobs.work_path = self._wp
        del os.environ["NINTH_NOTIFY"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _kind(self, name, fn):
        jobs.KINDS[name] = (name, fn)
        self._added.append(name)

    def test_a_raising_job_lands_failed_with_traceback(self):
        def boom(slug, log, set_pct):
            raise RuntimeError("deliberate: the policy test")
        self._kind("t_boom", boom)
        j = jobs.start("t_boom", "x")
        j = _wait(j["id"])
        self.assertEqual(j["state"], "failed")
        self.assertIn("deliberate", j["error"])
        self.assertIn("RuntimeError", j.get("traceback", ""))
        self.assertIn("boom", j.get("traceback", ""))

    def test_a_chain_raise_leaves_done_with_chain_failed(self):
        def fine(slug, log, set_pct):
            set_pct(100)
        def follower_guard_explodes(slug, log, set_pct):
            set_pct(100)
        self._kind("t_fine", fine)
        self._kind("t_next", follower_guard_explodes)
        jobs.CHAIN["t_fine"] = "t_next"
        # make start() raise a NON-JobError for the follower only
        real_start = jobs.start
        def sabotage(kind, slug, arg=None):
            if kind == "t_next":
                raise OSError("disk full during persist")
            return real_start(kind, slug, arg)
        jobs.start = sabotage
        try:
            j = real_start("t_fine", "x")
            j = _wait(j["id"])
        finally:
            jobs.start = real_start
        self.assertEqual(j["state"], "done")
        self.assertEqual(j.get("chain", {}).get("t_next"), "failed")
        self.assertIn("disk full", j.get("chain_error", ""))

    def test_rechain_queues_the_failed_follower_idempotently(self):
        ran = []
        def fine(slug, log, set_pct):
            set_pct(100)
        def next_ok(slug, log, set_pct):
            ran.append("t_next")
            set_pct(100)
        self._kind("t_fine2", fine)
        self._kind("t_next2", next_ok)
        j = jobs.start("t_fine2", "x")
        j = _wait(j["id"])
        # simulate a failed chain on the record
        jobs._set_chain(j, "t_next2", "failed", "sabotaged")
        out = jobs.rechain(j["id"])
        self.assertEqual(out["chain"]["t_next2"], "ok")
        _wait_deadline = time.time() + 10
        while "t_next" not in ran and time.time() < _wait_deadline:
            time.sleep(0.05)
        self.assertIn("t_next", ran)
        # idempotent: rechain again — ok follower skipped, no second run
        n = len(ran)
        jobs.rechain(j["id"])
        time.sleep(0.3)
        self.assertEqual(len(ran), n)

    def test_stale_chain_pending_is_reaped(self):
        def fine(slug, log, set_pct):
            set_pct(100)
        self._kind("t_fine3", fine)
        j = jobs.start("t_fine3", "x")
        j = _wait(j["id"])
        with jobs._LOCK:
            jobs._jobs[j["id"]]["chain"] = {"assemble": "pending"}
            jobs._jobs[j["id"]]["ended_ts"] = int(time.time()) - 9999
        jobs.jobs()  # the listing reaps
        j2 = jobs._jobs[j["id"]]
        self.assertEqual(j2["chain"]["assemble"], "failed")
        self.assertIn("reaped", j2.get("chain_error", ""))


if __name__ == "__main__":
    unittest.main()
