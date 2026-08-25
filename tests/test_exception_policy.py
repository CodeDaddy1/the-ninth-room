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
import json
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
        # JOBS_PATH is a module constant and _persist() reads it on every
        # write: without this the suite's fake jobs land in the REAL store
        # and the engine restores them into Caleb's activity tray on its
        # next restart ("t_boom FAILED: deliberate"). Found live 2026-08-24.
        self._jobs_path = jobs.JOBS_PATH
        jobs.JOBS_PATH = self.tmp / "_jobs.json"
        self._chain = dict(jobs.CHAIN)
        self._added = []
        os.environ["NINTH_NOTIFY"] = "0"

    def tearDown(self):
        # Drain FIRST. The worker runs on its own thread and persists on
        # every _update, so restoring JOBS_PATH while a test job is still
        # settling sends that write to the REAL store — 21 `t_*` rows
        # leaked into Caleb's tray that way, and this suite's own
        # StoreIsolation test is what caught it (2026-08-24).
        deadline = time.time() + 10
        while time.time() < deadline:
            live = [j for j in jobs._jobs.values()
                    if j["kind"] in self._added
                    and j["state"] in ("queued", "running")]
            if not live:
                break
            time.sleep(0.05)
        jobs.JOBS_PATH = self._jobs_path
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


class ReproxyGuard(unittest.TestCase):
    """A job whose precondition is missing refuses BEFORE it works.

    The workflow shakedown (2026-08-24) ran reproxy on a project with no
    cut: proxy.build raised a bare FileNotFoundError on
    analysis/timeline_map.json at 5%, which reads like a code defect when
    the honest answer is "there is no cut yet". Previews are per-BEAT, so
    the cut is the precondition.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "analysis").mkdir(parents=True)
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp

    def tearDown(self):
        jobs.work_path = self._wp
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_cut_refuses_with_a_sentence_not_a_traceback(self):
        with self.assertRaises(jobs.JobError) as e:
            jobs._run_reproxy("x", print, lambda p: None)
        self.assertIn("no cut", str(e.exception))
        self.assertIn("assemble", str(e.exception))

    def test_a_cut_lets_it_through_to_the_builder(self):
        (self.tmp / "analysis" / "timeline_map.json").write_text("{}")
        reached = []
        import pipeline.proxy as proxy_mod
        real = proxy_mod.build
        proxy_mod.build = lambda slug, log=None: reached.append(slug)
        try:
            jobs._run_reproxy("x", print, lambda p: None)
        finally:
            proxy_mod.build = real
        self.assertEqual(reached, ["x"])


class StoreIsolation(unittest.TestCase):
    """The suite must never write the store the engine restores from."""

    def test_the_real_job_store_is_never_the_test_store(self):
        from pipeline.ingest import PROJECT_ROOT
        real = PROJECT_ROOT / "work" / "_jobs.json"
        self.assertEqual(jobs.JOBS_PATH, real,
                         "a test leaked its JOBS_PATH stub past tearDown")
        if real.exists():
            import json as _json
            doc = _json.loads(real.read_text())
            rows = doc.get("jobs", []) if isinstance(doc, dict) else doc
            fakes = [r for r in rows
                     if str(r.get("kind", "")).startswith("t_")]
            self.assertEqual(fakes, [], "test jobs are in the real store")


class RestoreIsReadOnly(unittest.TestCase):
    """Importing this module must never rewrite the engine's job store.

    `_restore()` runs on import and marks anything left 'running' as
    failed — correct for THIS process's view, catastrophic when written
    back: a side process (a test, a CLI verb, an inspection script)
    would flip the live engine's in-flight jobs to
    "failed: engine restarted mid-job" in the file the engine restores
    from. Found live 2026-08-24 while inspecting a running queue.
    """

    def test_restore_marks_in_memory_but_writes_nothing(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            store = tmp / "_jobs.json"
            store.write_text(json.dumps({"jobs": [
                {"id": "J1", "kind": "ingest", "slug": "x", "label": "l",
                 "state": "running", "pct": 40, "note": ""},
                {"id": "J2", "kind": "assemble", "slug": "x", "label": "l",
                 "state": "queued", "pct": 0, "note": ""},
            ]}))
            before = store.read_text()
            saved_path, saved_jobs, saved_order = (
                jobs.JOBS_PATH, dict(jobs._jobs), list(jobs._order))
            jobs.JOBS_PATH = store
            jobs._jobs.clear()
            jobs._order.clear()
            try:
                jobs._restore()
                self.assertEqual(jobs._jobs["J1"]["state"], "failed",
                                 "this process must not believe it is running")
                self.assertEqual(store.read_text(), before,
                                 "restore wrote over the engine's store")
            finally:
                jobs.JOBS_PATH = saved_path
                jobs._jobs.clear(); jobs._jobs.update(saved_jobs)
                jobs._order.clear(); jobs._order.extend(saved_order)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
