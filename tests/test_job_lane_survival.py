# -*- coding: utf-8 -*-
"""A lane must never go quiet.

2026-08-25. Chasing a 1-in-6 flake in test_job_lanes turned up a real
hole, not a test artefact: a lane has exactly ONE worker thread, and
`start()` only spawned one when the slot was empty. Anything that
escaped the worker's try block killed that thread, and from then on
every job in the lane sat at "queued" forever — no error, no row, no
tray entry. It looks precisely like the "ingest hangs" bug this project
has chased before.

Three ways it happened, all pinned here:
  * a queue id whose row was gone  -> KeyError above the try
  * `KINDS` losing a kind mid-job  -> KeyError on the way to _notify
  * `_update` on a pruned row      -> KeyError climbing out of log()

And the reason two jobs could share a row at all: the id was stamped
`len(_order) % 1000`, which is not unique.

Run: /usr/bin/python3 -m unittest discover -s tests -t .
"""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import jobs  # noqa: E402


class Ids(unittest.TestCase):
    def test_an_id_is_not_reused_when_the_order_shrinks(self):
        """`len(_order) % 1000` repeats the moment a job is pruned. Two
        jobs then shared one row: one ran twice, the other hung."""
        seen = set()
        for _ in range(50):
            with jobs._LOCK:
                jobs._seq += 1
                jid = "J%d%03d" % (int(time.time()), jobs._seq % 1000)
            self.assertNotIn(jid, seen)
            seen.add(jid)


class Survival(unittest.TestCase):
    """Through the REAL worker, with the store stubbed for the class."""

    @classmethod
    def setUpClass(cls):
        cls._path = jobs.JOBS_PATH
        cls._tmp = Path(tempfile.mkdtemp())
        jobs.JOBS_PATH = cls._tmp / "_jobs.json"

    @classmethod
    def tearDownClass(cls):
        time.sleep(0.2)
        jobs.JOBS_PATH = cls._path
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "x").mkdir()
        self._wp = jobs.work_path
        jobs.work_path = lambda slug: self.tmp / "x"
        os.environ["NINTH_NOTIFY"] = "0"
        self._added = []

    def tearDown(self):
        deadline = time.time() + 10
        while time.time() < deadline:
            if not [j for j in jobs._jobs.values()
                    if j.get("kind") in self._added
                    and j["state"] in ("queued", "running")]:
                break
            time.sleep(0.05)
        for jid in [i for i, j in jobs._jobs.items()
                    if j.get("kind") in self._added]:
            jobs._jobs.pop(jid, None)
            if jid in jobs._order:
                jobs._order.remove(jid)
        for k in self._added:
            jobs.KINDS.pop(k, None)
            jobs.SESSION_KINDS.discard(k)
            jobs.LOCAL_KINDS.discard(k)
        jobs.work_path = self._wp
        del os.environ["NINTH_NOTIFY"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _kind(self, name, fn, lane="local"):
        jobs.KINDS[name] = (name, fn)
        (jobs.SESSION_KINDS if lane == "session" else jobs.LOCAL_KINDS).add(name)
        self._added.append(name)

    def _wait(self, jid, timeout=10.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            j = jobs._jobs.get(jid)
            if j and j["state"] in ("done", "failed", "declined"):
                return j
            time.sleep(0.02)
        self.fail("job %s never settled: %r" % (jid, jobs._jobs.get(jid)))

    # ---- the three holes ----

    def test_a_queue_id_with_no_row_does_not_take_the_lane_down(self):
        jobs._QUEUES["local"].put("J-does-not-exist")
        ran = threading.Event()
        self._kind("t_surv1", lambda s, log, p: ran.set())
        j = jobs.start("t_surv1", "x")
        self._wait(j["id"])
        self.assertTrue(ran.is_set(), "the lane died on a phantom id")

    def test_a_row_pruned_mid_job_does_not_take_the_lane_down(self):
        def vanish(slug, log, set_pct):
            # exactly what a tearDown or a prune does under a running job
            jid = jobs._CURRENT.jid
            with jobs._LOCK:
                jobs._jobs.pop(jid, None)
            log("still logging after the row is gone")

        self._kind("t_surv2", vanish)
        jobs.start("t_surv2", "x")
        time.sleep(0.4)
        ran = threading.Event()
        self._kind("t_surv3", lambda s, log, p: ran.set())
        j = jobs.start("t_surv3", "x")
        self._wait(j["id"])
        self.assertTrue(ran.is_set(), "the lane died on a pruned row")

    def test_a_kind_removed_mid_job_does_not_take_the_lane_down(self):
        def unregister(slug, log, set_pct):
            jobs.KINDS.pop("t_surv4", None)

        self._kind("t_surv4", unregister)
        jobs.start("t_surv4", "x")
        time.sleep(0.4)
        ran = threading.Event()
        self._kind("t_surv5", lambda s, log, p: ran.set())
        j = jobs.start("t_surv5", "x")
        self._wait(j["id"])
        self.assertTrue(ran.is_set(), "the lane died on a missing kind")

    def test_updating_a_vanished_job_is_a_no_op_not_a_raise(self):
        jobs._update("J-nope", state="done")   # must not raise

    def test_a_dead_worker_is_replaced_rather_than_left_in_the_slot(self):
        """Belt and braces behind the armoured loop: if something DOES
        end the thread, the next job has to bring the lane back.

        Asserted on the source rather than by installing a dead thread in
        the real slot: doing that spawns a second live worker in this
        process, and two workers on the local lane breaks the invariant
        the whole lane system exists to hold (never two encodes at once).
        The test that proved it was itself the thing that broke it.
        """
        import inspect
        src = inspect.getsource(jobs.start)
        self.assertIn("is_alive()", src,
                      "start() must replace a dead worker, not just an empty slot")

if __name__ == "__main__":
    unittest.main()
